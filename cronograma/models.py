from django.db import models
from obra.models import Construction
from catalogo.models import Concept
from django.core.exceptions import ValidationError
from django.utils import timezone


class Schedule(models.Model):
    """Modelo principal para cronogramas/programas de obra"""
    id = models.AutoField(primary_key=True)
    construction = models.ForeignKey(
        'obra.Construction', 
        on_delete=models.CASCADE, 
        related_name='schedules'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.construction.name}"
    
    def deactivate(self):
        """Método para desactivar este cronograma"""
        self.is_active = False
        self.save()
    
    def total_amount(self):
        """Retorna el importe total de todas las actividades"""
        return sum(activity.total_amount for activity in self.activities.all())
    
    def validate_construction_budget(self):
        """Valida que el importe total no exceda el presupuesto de la obra"""
        if self.total_amount() > self.construction.budget:
            raise ValidationError("El importe total del cronograma excede el presupuesto de la obra")
    
    def validate_dates(self):
        """Valida que la fecha de fin del cronograma no exceda la fecha de fin de la obra"""
        if not self.activities.exists():
            return
        
        latest_end_date = max(activity.end_date for activity in self.activities.all())
        if latest_end_date > self.construction.end_date:
            raise ValidationError("La fecha de fin del cronograma excede la fecha de fin de la obra")


class Activity(models.Model):
    """Modelo para agrupar conceptos en actividades"""
    id = models.AutoField(primary_key=True)
    schedule = models.ForeignKey(
        Schedule, 
        on_delete=models.CASCADE, 
        related_name='activities'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField()
    progress_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.0
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['start_date', 'end_date']
    
    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"
    
    @property
    def total_amount(self):
        """Calcula el importe total de todos los conceptos asociados"""
        return sum(item.concept.unit_price * item.concept.quantity for item in self.activity_concepts.all())
    
    @property
    def duration_days(self):
        """Calcula la duración en días de la actividad"""
        return (self.end_date - self.start_date).days + 1
    
    def clean(self):
        """Validaciones adicionales para la actividad"""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin")
        
        if self.progress_percentage < 0 or self.progress_percentage > 100:
            raise ValidationError("El porcentaje de avance debe estar entre 0 y 100")


class ActivityConcept(models.Model):
    """Modelo para relacionar conceptos con actividades"""
    id = models.AutoField(primary_key=True)
    activity = models.ForeignKey(
        Activity, 
        on_delete=models.CASCADE, 
        related_name='activity_concepts'
    )
    concept = models.ForeignKey(
        'catalogo.Concept', 
        on_delete=models.CASCADE, 
        related_name='activity_associations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('activity', 'concept')
    
    def __str__(self):
        return f"{self.activity.name} - {self.concept.description}"


class CriticalPath(models.Model):
    """Modelo para gestionar la ruta crítica (funcionalidad opcional)"""
    id = models.AutoField(primary_key=True)
    schedule = models.OneToOneField(
        Schedule, 
        on_delete=models.CASCADE, 
        related_name='critical_path'
    )
    calculated_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Ruta crítica para {self.schedule.name}"


class CriticalPathActivity(models.Model):
    """Actividades que forman parte de la ruta crítica"""
    id = models.AutoField(primary_key=True)
    critical_path = models.ForeignKey(
        CriticalPath, 
        on_delete=models.CASCADE, 
        related_name='critical_activities'
    )
    activity = models.ForeignKey(
        Activity, 
        on_delete=models.CASCADE, 
        related_name='critical_path_inclusions'
    )
    sequence_order = models.PositiveIntegerField()
    
    class Meta:
        ordering = ['sequence_order']
        unique_together = ('critical_path', 'activity')
    
    def __str__(self):
        return f"Actividad crítica: {self.activity.name} (orden: {self.sequence_order})"