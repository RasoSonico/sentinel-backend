# serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserRole


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    confirm_password = serializers.CharField(write_only=True, required=False)
    roles = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'password', 'confirm_password', 'outter_id', 'roles', 'is_active']
        read_only_fields = ['id', 'outter_id']
        
    def get_roles(self, obj):
        # Devuelve solo los nombres de los roles, no los objetos completos
        return [user_role.role.name for user_role in obj.roles.all()]
        
    def validate(self, data):
        # Validar contraseñas solo en creación
        if 'password' in data:
            if not 'confirm_password' in data:
                raise serializers.ValidationError({"confirm_password": "Se requiere confirmar la contraseña"})
            
            if data['password'] != data['confirm_password']:
                raise serializers.ValidationError({"password": "Las contraseñas no coinciden"})
            
            try:
                validate_password(data['password'])
            except ValidationError as e:
                raise serializers.ValidationError({"password": e.messages})
                
            # Eliminar confirm_password del dict final
            data.pop('confirm_password')
            
        return data
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create(**validated_data)
        
        if password:
            user.set_password(password)
            user.save()
            
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        # Actualizar campos normales
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        # Actualizar contraseña si se proporcionó
        if password:
            instance.set_password(password)
            
        instance.save()
        return instance

class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role']
        
        
    def validate(self, data):
        # Verificar que no exista ya esta combinación usuario-rol
        if UserRole.objects.filter(user=data['user'], role=data['role']).exists():
            raise serializers.ValidationError("Este usuario ya tiene asignado este rol")
        return data

