# permissions_dev.py
from rest_framework import permissions

class AllowAnyInDev(permissions.BasePermission):
    """
    Permite todos los accesos en desarrollo, pero se puede reemplazar en producción
    """
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        return True