# views.py
from rest_framework import generics

from core import settings
from .models import Catalog, WorkItem, Concept
from .serializers import CatalogSerializer, WorkItemSerializer, ConceptSerializer

class CatalogList(generics.ListCreateAPIView):
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer
    
    def get_queryset(self):
        user = self.request.user
        #Para pruebas
        if user.is_anonymous or settings.DEBUG:
            return Catalog.objects.all()
        user_constructions = user.user_obras.filter(is_active=True).values_list('construction', flat=True)
        return Catalog.objects.filter(construction__in=user_constructions)

class CatalogDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = Catalog.objects.all()
    serializer_class = CatalogSerializer

class WorkItemList(generics.ListCreateAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer

    def get_queryset(self):
        queryset = WorkItem.objects.all()
        
        # Filtrar por obras del usuario
        user = self.request.user
        #Para pruebas
        if user.is_anonymous or settings.DEBUG:
            return WorkItem.objects.all()        
        if not user.is_staff:  # Si no es admin, filtrar por obras asignadas
            user_constructions = user.user_obras.filter(is_active=True).values_list('construction', flat=True)
            queryset = queryset.filter(catalog__construction__in=user_constructions)
        
        # Mantener filtro por catálogo
        catalog = self.request.query_params.get('catalog', None)
        if catalog is not None:
            queryset = queryset.filter(catalog=catalog)
            
        return queryset

class WorkItemDetail(generics.RetrieveUpdateDestroyAPIView):
    queryset = WorkItem.objects.all()
    serializer_class = WorkItemSerializer

class ConceptList(generics.ListCreateAPIView):
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer
    
    def get_queryset(self):
        queryset = Concept.objects.all()
        
        # Filtrar por obras del usuario
        user = self.request.user
        #Para pruebas
        if user.is_anonymous or settings.DEBUG:
            return Concept.objects.all()

        if not user.is_staff:  # Si no es admin, filtrar por obras asignadas
            user_constructions = user.user_obras.filter(is_active=True).values_list('construction', flat=True)
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