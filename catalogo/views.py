# views.py
from rest_framework import generics, permissions
from core import settings
from .models import Catalog, WorkItem, Concept
from .serializers import CatalogSerializer, WorkItemSerializer, ConceptSerializer

class CatalogList(generics.ListCreateAPIView):
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Catalog.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(construction__in=user_constructions)
        
        return queryset

class CatalogDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer
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

class WorkItemList(generics.ListCreateAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = WorkItem.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(catalog__construction__in=user_constructions)
        
        # Mantener filtro por catálogo
        catalog = self.request.query_params.get('catalog', None)
        if catalog is not None:
            queryset = queryset.filter(catalog=catalog)
            
        return queryset

class WorkItemDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer
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
            queryset = queryset.filter(catalog__construction__in=user_constructions)
        
        return queryset

class ConceptList(generics.ListCreateAPIView):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Concept.objects.all()
        
        # Filtrar por obras asignadas al usuario
        if user.is_authenticated and not user.is_staff:
            from obra.models import UserConstruction
            user_constructions = UserConstruction.objects.filter(
                user=user,
                is_active=True
            ).values_list('construction', flat=True)
            queryset = queryset.filter(catalog__construction__in=user_constructions)
        
        # Mantener filtros existentes
        work_item = self.request.query_params.get('work_item', None)
        catalog = self.request.query_params.get('catalog', None)
        
        if work_item is not None:
            queryset = queryset.filter(work_item=work_item)
        if catalog is not None:
            queryset = queryset.filter(catalog=catalog)
            
        return queryset

class ConceptDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
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
            queryset = queryset.filter(catalog__construction__in=user_constructions)
        
        return queryset