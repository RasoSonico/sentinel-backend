from rest_framework import serializers
from .models import Machinery, MachineryCatalog, WorkForce, WorkForceCatalog


class MachineryCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer para el catálogo de maquinaria (dropdown)
    """
    class Meta:
        model = MachineryCatalog
        fields = ['id', 'name', 'brand']
        
    def validate_name(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Name cannot be empty")
        return value


class WorkForceCatalogSerializer(serializers.ModelSerializer):
    """
    Serializer para el catálogo de fuerza laboral (dropdown)
    """
    class Meta:
        model = WorkForceCatalog
        fields = ['id', 'name', 'category']


class MachinerySerializer(serializers.ModelSerializer):
    """
    Serializer para registros de maquinaria
    """
    machinery_detail = MachineryCatalogSerializer(source='machinery', read_only=True)
    
    class Meta:
        model = Machinery
        fields = [
            'id', 'machinery', 'machinery_detail', 'construction', 
            'user', 'serial_number', 'number', 'is_active', 'date', 
            'active_time', 'activity', 'comments'
        ]
        read_only_fields = ['date', 'user', 'construction']
        
    def validate_machinery(self, value):
        if not value:
            raise serializers.ValidationError("Machinery type is required")
        return value
        
    def validate_number(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Number must be greater than 0")
        return value
        
    def validate_activity(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Activity is required")
        return value


class WorkForceSerializer(serializers.ModelSerializer):
    """
    Serializer para registros de fuerza laboral
    """
    name_detail = WorkForceCatalogSerializer(source='name', read_only=True)
    
    class Meta:
        model = WorkForce
        fields = [
            'id', 'name', 'name_detail', 'user', 'construction', 
            'number', 'activity', 'date', 'comments'
        ]
        read_only_fields = ['date', 'user', 'construction']
        
    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Workforce type is required")
        return value
        
    def validate_number(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Number must be greater than 0")
        return value
        
    def validate_activity(self, value):
        if not value or value.strip() == '':
            raise serializers.ValidationError("Activity is required")
        return value