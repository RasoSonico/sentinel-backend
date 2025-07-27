from rest_framework import generics, permissions
from .models import Incident, IncidentType, IncidentClassification
from .serializers import (
    IncidentSerializer, 
    IncidentTypeSerializer, 
    IncidentClassificationSerializer
)


# Vistas para Catálogos (dropdowns)
class IncidentTypeListCreate(generics.ListCreateAPIView):
    """
    Vista para listar y crear tipos de incidencia
    GET: Lista todos los tipos para dropdown
    POST: Crear nuevo tipo de incidencia
    """
    queryset = IncidentType.objects.all()
    serializer_class = IncidentTypeSerializer
    permission_classes = [permissions.IsAuthenticated]


class IncidentTypeDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar tipo de incidencia específico
    GET: Obtener detalle del tipo
    PUT/PATCH: Actualizar tipo
    DELETE: Eliminar tipo
    """
    queryset = IncidentType.objects.all()
    serializer_class = IncidentTypeSerializer
    permission_classes = [permissions.IsAuthenticated]


class IncidentClassificationListCreate(generics.ListCreateAPIView):
    """
    Vista para listar y crear clasificaciones de incidencia
    GET: Lista todas las clasificaciones para dropdown
    POST: Crear nueva clasificación
    """
    queryset = IncidentClassification.objects.all()
    serializer_class = IncidentClassificationSerializer
    permission_classes = [permissions.IsAuthenticated]


class IncidentClassificationDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar clasificación específica
    GET: Obtener detalle de la clasificación
    PUT/PATCH: Actualizar clasificación
    DELETE: Eliminar clasificación
    """
    queryset = IncidentClassification.objects.all()
    serializer_class = IncidentClassificationSerializer
    permission_classes = [permissions.IsAuthenticated]


# Vistas para Incidencias
class IncidentListCreate(generics.ListCreateAPIView):
    """
    Vista para listar y crear incidencias
    GET: Lista incidencias filtradas por obras del usuario
    POST: Crear nueva incidencia
    """
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Incident.objects.all()
        
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


class IncidentDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar incidencia específica
    GET: Obtener detalle de incidencia
    PUT/PATCH: Actualizar incidencia
    DELETE: Eliminar incidencia
    """
    queryset = Incident.objects.all()
    serializer_class = IncidentSerializer
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
    
    def perform_update(self, serializer):
        # Mantener el usuario original, pero permitir actualizar otros campos
        # No sobrescribir user y construction en updates
        serializer.save()