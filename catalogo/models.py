from django.db import models
from obra.models import Construction


# Catalog está relacionado con Construction y a su vez Construction está relacionado con el usuario. 

class Catalog(models.Model):
    """
    Modelo para representar un catálogo en la base de datos.
    """
    id = models.AutoField(primary_key=True)
    construction = models.ForeignKey('obra.Construction', on_delete=models.CASCADE, related_name='catalogs', null=True)
    name = models.TextField(blank=True, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    reason_of_change = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Catalogo'
        verbose_name_plural = 'Catalogos'
        ordering = ['id']


class WorkItem(models.Model):
    """
    Modelo para representar una partida en la base de datos.
    """
    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(Catalog, on_delete=models.PROTECT, related_name='work_items')
    name = models.TextField()
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'Partida'
        verbose_name_plural = 'Partidas'
        ordering = ['id']


class Concept(models.Model):
    """
    Modelo para representar un concepto en la base de datos.
    """
    CLASIFICATION_OPTIONS = [
        ('ORD', 'ORDINARIO'),
        ('ADI', 'ADICIONAL'),
        ('EXT', 'EXTRAORDINARIO'),
    ]

    #Revisar campo por campo si es necesario el null=True o blank=True
    
    id = models.AutoField(primary_key=True)
    catalog = models.ForeignKey(Catalog, on_delete=models.PROTECT, related_name='concepts')
    work_item = models.ForeignKey(WorkItem, on_delete=models.PROTECT, related_name='concepts')
    description = models.TextField()
    unit = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    clasification = models.CharField(max_length=3, choices=CLASIFICATION_OPTIONS, default='ORD')
    is_active = models.BooleanField(default=True)


    def __str__(self):
        return self.description
    
    class Meta:
        verbose_name = 'Concepto'
        verbose_name_plural = 'Conceptos'
        ordering = ['id']

