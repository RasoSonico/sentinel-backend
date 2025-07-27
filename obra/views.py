from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Construction, UserConstruction, ConstructionChangeControl
from .serializers import (ConstructionSerializer, UserConstructionSerializer, 
                         ConstructionChangeControlSerializer)

# Importación condicional de permisos
if settings.DEBUG:
    from core.permissions_dev import AllowAnyInDev
    PermissionClass = AllowAnyInDev
else:
    from usuarios.permissions import IsSameUserOrAdmin, HasRole
    PermissionClass = IsSameUserOrAdmin

class ConstructionViewSet(viewsets.ModelViewSet):
    queryset = Construction.objects.all()
    serializer_class = ConstructionSerializer
    permission_classes = [permissions.IsAuthenticated]  
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'country', 'state']
    search_fields = ['name', 'client', 'description']
    ordering_fields = ['name', 'creation_date', 'start_date', 'end_date', 'budget']
    
    def get_queryset(self):
        """Filtrar obras según permisos del usuario"""
        user = self.request.user
        queryset = Construction.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(id__in=user_constructions)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_constructions(self, request):
        user = request.user
        if user.is_anonymous:
            return Response({"error": "Usuario no autenticado"}, status=401)
        
        role = request.query_params.get('role', None)
        
        queryset = Construction.objects.filter(
            user_obras__user=user,
            user_obras__is_active=True
        )
        
        if role:
            queryset = queryset.filter(user_obras__role__name=role)
        
        serializer = self.get_serializer(queryset.distinct(), many=True)
        return Response(serializer.data)

class UserConstructionViewSet(viewsets.ModelViewSet):
    queryset = UserConstruction.objects.all()
    serializer_class = UserConstructionSerializer
    permission_classes = [permissions.IsAuthenticated]  # Usar la clase condicional
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'construction', 'role', 'is_active']
    
    def get_queryset(self):
        user = self.request.user
        queryset = UserConstruction.objects.all()
        
        # Filtrar por usuario autenticado
        if user.is_authenticated and not user.is_staff:
            queryset = queryset.filter(user=user)
        
        return queryset

class ConstructionChangeControlViewSet(viewsets.ModelViewSet):
    queryset = ConstructionChangeControl.objects.all()
    serializer_class = ConstructionChangeControlSerializer
    permission_classes = [permissions.IsAuthenticated]  # Usar la clase condicional
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['construction', 'modified_by']
    ordering_fields = ['modification_date']
    
    def get_queryset(self):
        user = self.request.user
        queryset = ConstructionChangeControl.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            user_constructions = UserConstruction.objects.filter(
                user=user, 
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset
    
    def perform_create(self, serializer):
        # Verificar si el usuario es anónimo
        user = self.request.user
        if user.is_anonymous:
            serializer.save()  # Sin asignar usuario
        else:
            # Asignar automáticamente el usuario actual
            serializer.save(modified_by=user)