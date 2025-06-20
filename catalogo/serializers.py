from rest_framework import serializers
from .models import Catalog, WorkItem, Concept

class CatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = Catalog
        fields = ['id', 'construction','name', 'creation_date', 'is_active', 'reason_of_change']

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("El nombre del catálogo no puede estar vacío.")
        return value

class WorkItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkItem
        fields = ['id', 'catalog', 'name']
    
    def validate(self, data):
        if WorkItem.objects.filter(
            name=data['name'],
            catalog=data['catalog']
        ).exists():
            raise serializers.ValidationError("Ya existe una partida con este nombre en el catálogo.")
        return data

class ConceptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Concept
        fields = ['id', 'catalog','work_item', 'description', 'unit', 'quantity', 'unit_price', 'clasification']
            
    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("La cantidad debe ser mayor que cero.")
        return value
    
    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio unitario debe ser mayor que cero.")
        return value
    
    def validate_clasification(self, value):
        valid_choices = [choice[0] for choice in Concept.CLASIFICATION_OPTIONS]
        if value not in valid_choices:
            raise serializers.ValidationError("Clasificación no válida.")
        return value
    
    def validate(self, data):
        if Concept.objects.filter(
            description=data['description'],
            work_item=data['work_item'],
        ).exists():
            raise serializers.ValidationError("Ya existe un concepto igual en la misma partida.")
        return data
    
    def get_catalog_name(self, obj):
        return obj.catalog.name if obj.catalog else None
        
    def get_work_item_name(self, obj):
        return obj.work_item.name if obj.work_item else None