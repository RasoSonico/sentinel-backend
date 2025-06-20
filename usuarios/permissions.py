from rest_framework import permissions

class IsSameUserOrAdmin(permissions.BasePermission):
    """
    Permite acceso solo al propio usuario o administradores
    """
    def has_object_permission(self, request, view, obj):
        # Permitir si es admin
        if request.user.is_staff:
            return True
            
        # Permitir si es el mismo usuario
        return obj.id == request.user.id

class HasRole(permissions.BasePermission):
    """
    Verifica que el usuario tenga el rol requerido
    """
    def __init__(self, required_role):
        self.required_role = required_role
        
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        # Verificar rol
        return request.user.roles.filter(role=self.required_role).exists()