from rest_framework import serializers
from .models import Incident, IncidentType, IncidentClassification


class IncidentTypeSerializer(serializers.ModelSerializer):
    """
    Serializer para el catálogo de tipos de incidencia (dropdown)
    """
    class Meta:
        model = IncidentType
        fields = ['id', 'name', 'description']
        
    def validate_name(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Name cannot be empty")
        return value


class IncidentClassificationSerializer(serializers.ModelSerializer):
    """
    Serializer para el catálogo de clasificaciones de incidencia (dropdown)
    """
    class Meta:
        model = IncidentClassification
        fields = ['id', 'name', 'description']
        
    def validate_name(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Name cannot be empty")
        return value


class IncidentSerializer(serializers.ModelSerializer):
    """
    Serializer para registros de incidencias
    """
    type_detail = IncidentTypeSerializer(source='type', read_only=True)
    clasification_detail = IncidentClassificationSerializer(source='clasification', read_only=True)
    
    class Meta:
        model = Incident
        fields = [
            'id', 'type', 'type_detail', 'clasification', 'clasification_detail',
            'construction', 'user', 'date', 'description'
        ]
        read_only_fields = ['date', 'user', 'construction']
        
    def validate_type(self, value):
        if not value:
            raise serializers.ValidationError("Incident type is required")
        return value
        
    def validate_clasification(self, value):
        if not value:
            raise serializers.ValidationError("Incident classification is required")
        return value
        
    def validate_description(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Description is required")
        return value