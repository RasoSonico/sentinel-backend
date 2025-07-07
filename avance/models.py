import uuid
from django.db import models
from catalogo.models import Concept
from django.db.models import Sum, F


class Physical(models.Model):
    """Modelo para registrar avances físicos"""
    id = models.AutoField(primary_key=True)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE, related_name='physical_progress')
    volume = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Por revisar'),
        ('APPROVED', 'Aprobado'),
        ('REJECTED', 'Rechazado')
    ], default='PENDING')
    comments = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Avance Físico'
        verbose_name_plural = 'Avances Físicos'
        ordering = ['-date']

    def __str__(self):
        return f"Avance de {self.concept.description} - {self.date}"
    
class PhysicalStatusHistory(models.Model):
    """Modelo para registrar el historial de cambios de estado de los avances físicos"""
    id = models.AutoField(primary_key=True)
    physical = models.ForeignKey(Physical, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey('usuarios.User', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['changed_at']
        verbose_name = 'Historial de Estatus de Avance'
        verbose_name_plural = 'Historial de Estatus de Avances'

class Estimation(models.Model):
    """
    Modelo para estimaciones financieras
    Este modelo es un resumen de estimación que muestra el nombre de la estimación
    el periodo que abarca, el monto total y su estado (borrador, enviada, aprobada o pagada)
    y comentarios en caso de tener
    """
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    period_start = models.DateField()
    period_end = models.DateField()
    total_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[
        ('DRAFT', 'Borrador'),
        ('SUBMITTED', 'Enviada'),
        ('APPROVED', 'Aprobada'),
        ('PAID', 'Pagada')
    ], default='DRAFT')
    construction = models.ForeignKey('obra.Construction', on_delete=models.CASCADE, null=True)
    is_planned = models.BooleanField(default=False, help_text="Indica si esta estimación es una planificación")
    based_on_schedule = models.BooleanField(default=False, help_text="Indica si se generó desde un cronograma")
    schedule = models.ForeignKey('cronograma.Schedule', null=True, blank=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey('usuarios.User', on_delete=models.SET_NULL, null=True, related_name='created_estimations')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def calculate_total(self):
        return self.details.aggregate(total=Sum(F('amount')))['total'] or 0
    
    def update_total(self):
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount'])
    
    class Meta:
        verbose_name = 'Estimación'
        verbose_name_plural = 'Estimaciones'
        ordering = ['-period_start']

    def __str__(self):
        return f"Estimación {self.name} ({self.period_start} a {self.period_end})"

class EstimationDetail(models.Model):
    """
    Detalle de conceptos incluidos en una estimación
    Este modelo asocia varios conceptos a una estimación específica, permitiendo
    registrar el volumen y el monto de cada concepto por separado
    
    """
    estimation = models.ForeignKey(Estimation, on_delete=models.CASCADE, related_name='details')
    concept = models.ForeignKey(Concept, on_delete=models.PROTECT, related_name='estimation_details')
    volume = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    execution_date = models.DateField(null=True, blank=True, help_text="Fecha específica de ejecución planificada")
    commitment_status = models.CharField(max_length=50, choices=[
        ('PENDING', 'Pendiente'),
        ('COMMITTED', 'Comprometido'),
        ('EXECUTED', 'Ejecutado'),
        ('DELAYED', 'Retrasado')
    ], default='PENDING', null=True, blank=True)
    activity = models.ForeignKey('cronograma.Activity', null=True, blank=True, on_delete=models.SET_NULL)
    imported_from_schedule = models.BooleanField(default=False)
    
    # Resto de campos y métodos existentes...
    
    class Meta:
        unique_together = ['estimation', 'concept']
        verbose_name = 'Detalle de Estimación'
        verbose_name_plural = 'Detalles de Estimación'
        ordering = ['estimation', 'concept']

    def __str__(self):
        return f"{self.concept.description} - {self.volume} {self.concept.unit}"
    
class CommitmentTracking(models.Model):
    """Modelo para seguimiento de compromisos planificados vs ejecutados"""
    estimation_detail = models.ForeignKey(EstimationDetail, on_delete=models.CASCADE, related_name='commitments')
    planned_date = models.DateField()
    actual_date = models.DateField(null=True, blank=True)
    planned_volume = models.DecimalField(max_digits=10, decimal_places=2)
    actual_volume = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variance_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('ON_TRACK', 'En tiempo'),
        ('DELAYED', 'Retrasado'),
        ('ADVANCED', 'Adelantado'),
        ('COMPLETED', 'Completado')
    ], default='ON_TRACK')
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['planned_date']
        verbose_name = 'Seguimiento de Compromiso'
        verbose_name_plural = 'Seguimientos de Compromisos'

    def __str__(self):
        return f"Compromiso para {self.estimation_detail.concept.description} - {self.planned_date}"
    
class Photo(models.Model):
    """
    Modelo mejorado para fotografías con metadatos completos
    """
    UPLOAD_STATUS_CHOICES = [
        ('PENDING', 'Pendiente de subida'),
        ('UPLOADING', 'Subiendo'),
        ('COMPLETED', 'Completada'),
        ('FAILED', 'Falló'),
    ]
    
    # Identificación
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Información del archivo
    original_filename = models.CharField(max_length=255)
    blob_path = models.CharField(max_length=500, unique=True)  # ruta en blob
    blob_url = models.URLField(max_length=1000, blank=True, null=True)
    thumbnail_blob_path = models.CharField(max_length=500, blank=True, null=True)
    thumbnail_blob_url = models.URLField(max_length=1000, blank=True, null=True)
    
    # Información de tamaño y formato
    file_size_bytes = models.BigIntegerField()
    content_type = models.CharField(max_length=50)
    image_width = models.PositiveIntegerField()
    image_height = models.PositiveIntegerField()
    
    # Estado de subida
    upload_status = models.CharField(
        max_length=20, 
        choices=UPLOAD_STATUS_CHOICES, 
        default='PENDING'
    )
    
    # Metadatos de usuario y tiempo
    uploaded_by = models.ForeignKey('usuarios.User', on_delete=models.CASCADE, related_name='uploaded_photos')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    taken_at = models.DateTimeField(null=True, blank=True)  # fecha de captura según EXIF
    
    # Ubicación GPS
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    gps_accuracy = models.FloatField(null=True, blank=True)  # precisión en metros
    
    # Información del dispositivo
    device_model = models.CharField(max_length=100, blank=True, null=True)
    camera_make = models.CharField(max_length=50, blank=True, null=True)
    camera_model = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadatos EXIF completos (JSON)
    exif_data = models.JSONField(default=dict, blank=True)
    
    # Relaciones
    physical_advance = models.ForeignKey(
        'Physical', 
        on_delete=models.CASCADE, 
        related_name='photos'
    )
    construction = models.ForeignKey(
        'obra.Construction',
        on_delete=models.CASCADE,
        related_name='photos'
    )
    
    # Campos de procesamiento
    is_processed = models.BooleanField(default=False)
    processing_notes = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Fotografía'
        verbose_name_plural = 'Fotografías'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['upload_status']),
            models.Index(fields=['construction', 'uploaded_at']),
            models.Index(fields=['physical_advance']),
            models.Index(fields=['uploaded_by', 'uploaded_at']),
        ]

    def __str__(self):
        return f"Foto {self.original_filename} - {self.physical_advance}"
    
    @property
    def file_size_mb(self):
        """Retorna el tamaño del archivo en MB"""
        return round(self.file_size_bytes / (1024 * 1024), 2)
    
    @property
    def image_resolution(self):
        """Retorna la resolución como string"""
        return f"{self.image_width}x{self.image_height}"
    
    @property
    def has_gps(self):
        """Verifica si la foto tiene coordenadas GPS"""
        return self.latitude is not None and self.longitude is not None
    
    def get_display_url(self, with_sas=True, expiry_hours=24):
        """
        Retorna URL de visualización, generando SAS token si es necesario
        """
        if not with_sas and self.blob_url:
            return self.blob_url
            
        # Si necesitamos SAS token, lo generaremos en el servicio
        from .services.blob_service import blob_service
        try:
            return blob_service.generate_read_sas_token(self.blob_path, expiry_hours)
        except Exception:
            return self.blob_url  # Fallback
    
    def get_thumbnail_url(self, with_sas=True, expiry_hours=24):
        """
        Retorna URL del thumbnail
        """
        if not self.thumbnail_blob_path:
            return None
            
        if not with_sas and self.thumbnail_blob_url:
            return self.thumbnail_blob_url
            
        from .services.blob_service import blob_service
        try:
            return blob_service.generate_read_sas_token(self.thumbnail_blob_path, expiry_hours)
        except Exception:
            return self.thumbnail_blob_url

