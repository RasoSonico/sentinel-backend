from rest_framework import serializers
from .models import Construction, UserConstruction, ConstructionChangeControl
from usuarios.serializers import UserSerializer, UserRoleSerializer
from usuarios.models import Role

class ConstructionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Construction
        fields = ['id', 'name', 'location', 'country', 'state', 'client', 'description', 
                 'creation_date', 'start_date', 'end_date', 'budget', 'status']
        read_only_fields = ['id', 'creation_date']
    
    def validate(self, data):
        if 'start_date' in data and 'end_date' in data:
            if data['start_date'] > data['end_date']:
                raise serializers.ValidationError("La fecha de inicio no puede ser posterior a la fecha de fin")
        if 'creation_date' in data and data['creation_date'] > data['end_date']:
            raise serializers.ValidationError("La fecha de creación no puede ser mayor a la fecha de término")
        return data
    
    def validate_budget(self, value):
        if value < 0:
            raise serializers.ValidationError("El presupuesto no puede ser negativo")
        return value

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description']

class UserConstructionSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    role_details = RoleSerializer(source='role', read_only=True)
    construction_details = ConstructionSerializer(source='construction', read_only=True)
    
    class Meta:
        model = UserConstruction
        fields = ['id', 'user', 'construction', 'role', 'is_active', 'asignation_date', 
                 'user_details', 'role_details', 'construction_details']
        read_only_fields = ['id', 'asignation_date']

class ConstructionChangeControlSerializer(serializers.ModelSerializer):
    modified_by_details = UserSerializer(source='modified_by', read_only=True)
    construction_details = ConstructionSerializer(source='construction', read_only=True)
    
    class Meta:
        model = ConstructionChangeControl
        fields = ['id', 'construction', 'modification', 'reason', 'modification_date', 
                 'modified_by', 'modified_by_details', 'construction_details']
        read_only_fields = ['id']

    def validate_modification(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("La modificación debe ser un objeto JSON válido")
    
        if 'cambios' not in value:
            raise serializers.ValidationError("El objeto debe contener el campo 'cambios'")
    
        cambios = value.get('cambios', {})
        if not cambios:
            raise serializers.ValidationError("El campo 'cambios' no puede estar vacío")
    
    # Verifica que solo tenga los campos permitidos
        campos_permitidos = ['fecha_fin', 'presupuesto', 'alcance']
        campos_no_permitidos = [campo for campo in cambios.keys() if campo not in campos_permitidos]
    
        if campos_no_permitidos:
            raise serializers.ValidationError(f"Campos no permitidos: {', '.join(campos_no_permitidos)}. Solo se permiten: {', '.join(campos_permitidos)}")
    
    # Verifica estructura de cada cambio
        for campo, valores in cambios.items():
            if not isinstance(valores, dict):
                raise serializers.ValidationError(f"Los valores para '{campo}' deben ser un objeto")
            
            if 'anterior' not in valores or 'nuevo' not in valores:
                raise serializers.ValidationError(f"Los cambios para '{campo}' deben incluir 'anterior' y 'nuevo'")
        
        return value