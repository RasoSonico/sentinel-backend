from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    outter_id = models.CharField(max_length=100, unique=True, null=True)
    azure_tenant = models.CharField(max_length=100, null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        ordering = ['username']

    def __str__(self):
        return self.username
    
    def has_role(self, role_name):
     return self.roles.filter(role=role_name).exists()
    
class Role (models.Model):
    """
    Modelo para representar los roles de los usuarios en la base de datos.
    """
    ROLES = [
        ('ADMIN', 'Administrador'),
        ('INSPECTOR', 'Inspector'),
        ('INVERSIONISTA', 'Inversionista'),
        ('DESARROLLADOR', 'Desarrollador'),
        ('CONTRATISTA', 'Contratista'),
    ]

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, choices=ROLES, default='INSPECTOR')
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'
        ordering = ['name']

    def __str__(self):
        return self.name


class UserRole(models.Model):
    """
    Modelo para representar los roles de los usuarios en la base de datos.
    """


    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        verbose_name = 'Rol de Usuario'
        verbose_name_plural = 'Roles de Usuario'
        ordering = ['user']

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"
    