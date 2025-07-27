from django.db import models

class Incident(models.Model):
    """
    Modelo para representar un incidente en la base de datos.
    """
    id = models.AutoField(primary_key=True)
    type = models.ForeignKey('IncidentType', on_delete=models.PROTECT, related_name='incidents', null=True)
    clasification = models.ForeignKey('IncidentClassification', on_delete=models.PROTECT, related_name='incidents', null=True)
    construction = models.ForeignKey('obra.Construction', on_delete=models.CASCADE, related_name='incidents', null=True)
    user = models.ForeignKey('usuarios.User', on_delete=models.PROTECT, related_name='incidents', null=True)
    date = models.DateField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)


    def __str__(self):
        return f"Incident {self.id} - {self.description[:50]}"

    class Meta:
        verbose_name = 'Incidencia'
        verbose_name_plural = 'Incidencias'
        ordering = ['-date']

class IncidentType(models.Model):
    """
    Modelo para representar un tipo de incidencia.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Tipo de Incidencia'
        verbose_name_plural = 'Tipos de Incidencias'
        ordering = ['id']

class IncidentClassification(models.Model):
    """
    Modelo para representar una clasificación de incidencia.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Clasificación de Incidencia'
        verbose_name_plural = 'Clasificaciones de Incidencias'
        ordering = ['id']