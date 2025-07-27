from django.db import models

class Machinery(models.Model):
    """
    Modelo para representar el registro maquinaria en la base de datos.
    """
    id = models.AutoField(primary_key=True)
    machinery = models.ForeignKey('MachineryCatalog', on_delete=models.PROTECT, related_name='machinery')
    construction = models.ForeignKey('obra.Construction', on_delete=models.CASCADE, related_name='machinery', null=True)
    user = models.ForeignKey('usuarios.User', on_delete=models.PROTECT, related_name='machinery', null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    number = models.IntegerField(default=0, blank=True, null=True) #Cantidad de maquinaria
    is_active = models.BooleanField(default=True)
    date = models.DateField(auto_now_add=True)
    active_time = models.DecimalField(max_digits=10, decimal_places=2, default=0.0, blank=True, null=True)
    activity = models.CharField(max_length=100, blank=True, null=True)
    comments = models.TextField(blank=True, null=True)


    def __str__(self):
        return str(self.machinery)

    class Meta:
        verbose_name = 'Maquinaria'
        verbose_name_plural = 'Maquinarias'
        ordering = ['id']

class MachineryCatalog(models.Model):
    """
    Modelo para representar un catálogo de maquinaria.
    """
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    brand = models.CharField(max_length=100, blank=True, null=True)    

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Catálogo de Maquinaria'
        verbose_name_plural = 'Catálogos de Maquinaria'
        ordering = ['id']

class WorkForce(models.Model):
    """
    Modelo para representar el registro de fuerza de trabajo.
    """
    id = models.AutoField(primary_key=True)
    name = models.ForeignKey('WorkForceCatalog', on_delete=models.PROTECT, related_name='workforce', null=True)
    user = models.ForeignKey('usuarios.User', on_delete=models.PROTECT, related_name='workforce', null=True)
    construction = models.ForeignKey('obra.Construction', on_delete=models.CASCADE, related_name='workforce', null=True)
    number = models.IntegerField(default=0, blank=True, null=True) #Cantidad de trabajadores
    activity = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    comments = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.construction.name}"

    class Meta:
        verbose_name = 'Fuerza Laboral'
        verbose_name_plural = 'Fuerzas Laborales'
        ordering = ['id']

class WorkForceCatalog(models.Model):
    """
    Modelo para representar un catálogo de fuerza laboral.
    """
    id = models.AutoField(primary_key=True)
    name = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Catálogo de Fuerza Laboral'
        verbose_name_plural = 'Catálogos de Fuerza Laboral'
        ordering = ['id']