from django.db import models
from usuarios.models import User, Role
from django.core.exceptions import ValidationError

# Create your models here.
class Construction(models.Model):
    """
    Modelo para representar una obra en la base de datos.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    location = models.URLField(max_length=200, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    client = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    creation_date = models.DateField(auto_now_add=True)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[
        ('PLANNED', 'Planeada'),
        ('IN_PROGRESS', 'En progreso'),
        ('COMPLETED', 'Completada'),
        ('CANCELLED', 'Cancelada')
    ], default='PLANNED')

    class Meta:
        verbose_name = 'Obra'
        verbose_name_plural = 'Obras'
        ordering = ['-creation_date']

    def __str__(self):
        return self.name
    
    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin")

class UserConstruction(models.Model):
    """
    Modelo para representar la relación entre usuarios y obras.
    """
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_obras')
    construction = models.ForeignKey(Construction, on_delete=models.PROTECT, related_name='user_obras')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='user_obras')
    is_active = models.BooleanField(default=True)
    asignation_date = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = 'Usuario-Obra'
        verbose_name_plural = 'Usuarios-Obras'
        ordering = ['asignation_date']

    def __str__(self):
        return f"{self.user.username} - {self.construction}"
    
class ConstructionChangeControl(models.Model):
    """
    Control de cambios de una obra.
    """
    id = models.AutoField(primary_key=True)
    construction = models.ForeignKey(Construction, on_delete=models.PROTECT, related_name='change_control')
    modification= models.JSONField(encoder=None, blank=True, null=True)
    reason = models.CharField(max_length=500,blank=True, null=True)
    modification_date = models.DateField()
    modified_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='construction_changes')

    class Meta:
        verbose_name = 'Control de Cambios'
        verbose_name_plural = 'Controles de Cambios'
        ordering = ['-modification_date']

    def __str__(self):
        return f"Control de Cambio {self.id} - {self.construction.name}"