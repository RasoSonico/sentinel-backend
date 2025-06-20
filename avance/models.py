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
