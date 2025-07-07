import requests
import json
from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.contrib.auth import authenticate
from .models import User, UserRole, Role
from .serializers import UserSerializer, UserRoleSerializer, RoleSerializer
from .permissions import HasRole, IsSameUserOrAdmin
from core import settings
from rest_framework_simplejwt.tokens import RefreshToken


if settings.DEBUG:
    from core.permissions_dev import AllowAnyInDev
    PermissionClass = AllowAnyInDev
    AdminPermissionClass = AllowAnyInDev
else:
    from .permissions import IsSameUserOrAdmin
    PermissionClass = IsSameUserOrAdmin
    AdminPermissionClass = IsAdminUser

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated] 
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        user = request.user
        user_roles = [user_role.role.name for user_role in user.roles.all()]

        return Response({
                "id": str(user.id),
                "name": f"{user.first_name} {user.last_name}".strip(),
                "email": user.email,
                "roles": user_roles,
            })
    
    @action(detail=True, methods=['post'], permission_classes=[AdminPermissionClass])
    def assign_role(self, request, pk=None):
        """
        Asignar un rol a un usuario específico
        POST /api/usuarios/users/{user_id}/assign_role/
        Body: {"role_id": 1}
        """
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {"error": "Se requiere role_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            role = Role.objects.get(id=role_id)
        except Role.DoesNotExist:
            return Response(
                {"error": "Rol no encontrado"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Verificar si ya tiene el rol
        if UserRole.objects.filter(user=user, role=role).exists():
            return Response(
                {"error": "El usuario ya tiene este rol asignado"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Crear la asignación
        user_role = UserRole.objects.create(user=user, role=role)
        serializer = UserRoleSerializer(user_role)
        
        return Response({
            "message": f"Rol '{role.name}' asignado exitosamente a {user.username}",
            "user_role": serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['delete'], permission_classes=[AdminPermissionClass])
    def remove_role(self, request, pk=None):
        """
        Remover un rol de un usuario específico
        DELETE /api/usuarios/users/{user_id}/remove_role/
        Body: {"role_id": 1}
        """
        user = self.get_object()
        role_id = request.data.get('role_id')
        
        if not role_id:
            return Response(
                {"error": "Se requiere role_id"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user_role = UserRole.objects.get(user=user, role_id=role_id)
            role_name = user_role.role.name
            user_role.delete()
            
            return Response({
                "message": f"Rol '{role_name}' removido exitosamente de {user.username}"
            }, status=status.HTTP_200_OK)
            
        except UserRole.DoesNotExist:
            return Response(
                {"error": "El usuario no tiene este rol asignado"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar roles
    Endpoints:
    - GET /api/usuarios/roles/ - Listar todos los roles
    - POST /api/usuarios/roles/ - Crear nuevo rol
    - GET /api/usuarios/roles/{id}/ - Obtener rol específico
    - PUT /api/usuarios/roles/{id}/ - Actualizar rol
    - DELETE /api/usuarios/roles/{id}/ - Eliminar rol
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [AdminPermissionClass]
    
    def create(self, request, *args, **kwargs):
        """
        Crear un nuevo rol
        POST /api/usuarios/roles/
        Body: {"name": "INSPECTOR", "description": "Inspector de obra"}
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            role = serializer.save()
            return Response({
                "message": f"Rol '{role.name}' creado exitosamente",
                "role": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'], permission_classes=[AdminPermissionClass])
    def users(self, request, pk=None):
        """
        Obtener todos los usuarios con este rol
        GET /api/usuarios/roles/{role_id}/users/
        """
        role = self.get_object()
        user_roles = UserRole.objects.filter(role=role).select_related('user')
        users_data = []
        
        for user_role in user_roles:
            users_data.append({
                "id": user_role.user.id,
                "username": user_role.user.username,
                "email": user_role.user.email,
                "first_name": user_role.user.first_name,
                "last_name": user_role.user.last_name,
            })
        
        return Response({
            "role": role.name,
            "users": users_data,
            "total_users": len(users_data)
        })

class UserRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar asignaciones de roles directamente
    """
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [AdminPermissionClass]
    
    def create(self, request, *args, **kwargs):
        """
        Crear una nueva asignación de rol
        POST /api/usuarios/user-roles/
        Body: {"user": 1, "role": 2}
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user_role = serializer.save()
            return Response({
                "message": f"Rol '{user_role.role.name}' asignado a '{user_role.user.username}'",
                "user_role": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

