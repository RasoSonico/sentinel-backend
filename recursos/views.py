from rest_framework import generics, permissions
from .models import Machinery, MachineryCatalog, WorkForce, WorkForceCatalog
from .serializers import (
    MachinerySerializer, 
    MachineryCatalogSerializer, 
    WorkForceSerializer, 
    WorkForceCatalogSerializer
)


# Vistas para Catálogos (dropdowns)
class MachineryCatalogList(generics.ListCreateAPIView):
    """
    Vista para listar catálogo de maquinaria y crear nuevos tipos
    GET: Lista todos los tipos de maquinaria para dropdown
    POST: Crear nuevo tipo de maquinaria
    """
    queryset = MachineryCatalog.objects.all()
    serializer_class = MachineryCatalogSerializer
    permission_classes = [permissions.IsAuthenticated]


class WorkForceCatalogList(generics.ListCreateAPIView):
    """
    Vista para listar catálogo de fuerza laboral y crear nuevos tipos
    GET: Lista todos los tipos de fuerza laboral para dropdown
    POST: Crear nuevo tipo de fuerza laboral
    """
    queryset = WorkForceCatalog.objects.all()
    serializer_class = WorkForceCatalogSerializer
    permission_classes = [permissions.IsAuthenticated]


# Vistas para Registros de Recursos
class MachineryList(generics.ListCreateAPIView):
    """
    Vista para listar y crear registros de maquinaria
    GET: Lista maquinaria filtrada por obras del usuario
    POST: Crear nuevo registro de maquinaria
    """
    queryset = Machinery.objects.all()
    serializer_class = MachinerySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Machinery.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset
    
    def perform_create(self, serializer):
        # Asignar automáticamente el usuario y construcción
        user = self.request.user
        
        # Obtener la construcción del usuario (primera activa)
        from obra.models import UserConstruction
        user_construction = UserConstruction.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if user_construction:
            serializer.save(
                user=user,
                construction=user_construction.construction
            )
        else:
            serializer.save(user=user)


class MachineryDetail(generics.RetrieveUpdateAPIView):
    """
    Vista para obtener y actualizar registro específico de maquinaria
    GET: Obtener detalle de maquinaria
    PUT/PATCH: Actualizar registro de maquinaria
    """
    queryset = Machinery.objects.all()
    serializer_class = MachinerySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset


class WorkForceList(generics.ListCreateAPIView):
    """
    Vista para listar y crear registros de fuerza laboral
    GET: Lista fuerza laboral filtrada por obras del usuario
    POST: Crear nuevo registro de fuerza laboral
    """
    queryset = WorkForce.objects.all()
    serializer_class = WorkForceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = WorkForce.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset
    
    def perform_create(self, serializer):
        # Asignar automáticamente el usuario y construcción
        user = self.request.user
        
        # Obtener la construcción del usuario (primera activa)
        from obra.models import UserConstruction
        user_construction = UserConstruction.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if user_construction:
            serializer.save(
                user=user,
                construction=user_construction.construction
            )
        else:
            serializer.save(user=user)


class WorkForceDetail(generics.RetrieveUpdateAPIView):
    """
    Vista para obtener y actualizar registro específico de fuerza laboral
    GET: Obtener detalle de fuerza laboral
    PUT/PATCH: Actualizar registro de fuerza laboral
    """
    queryset = WorkForce.objects.all()
    serializer_class = WorkForceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset