"""
Serializers para el módulo de fotografías
"""

from rest_framework import serializers
from django.core.files.uploadedfile import InMemoryUploadedFile
from ..models import Photo
from ..services.image_service import image_service
from ..services.blob_service import blob_service
import uuid
from datetime import datetime


class PhotoUploadRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitar SAS token para subida de foto
    """
    filename = serializers.CharField(max_length=255)
    file_size = serializers.IntegerField(min_value=1)
    content_type = serializers.CharField(max_length=50)
    physical_advance_id = serializers.IntegerField()
    construction_id = serializers.IntegerField()
    
    # Metadatos opcionales del cliente
    device_model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    gps_accuracy = serializers.FloatField(required=False, allow_null=True)
    taken_at = serializers.DateTimeField(required=False, allow_null=True)
    
    def validate_filename(self, value):
        """Valida que el nombre del archivo tenga una extensión válida"""
        if not value:
            raise serializers.ValidationError("El nombre del archivo es requerido")
        
        # Extraer extensión
        parts = value.lower().split('.')
        if len(parts) < 2:
            raise serializers.ValidationError("El archivo debe tener una extensión")
        
        extension = parts[-1]
        from django.conf import settings
        
        if extension not in settings.PHOTO_ALLOWED_FORMATS:
            raise serializers.ValidationError(
                f"Formato no válido. Formatos permitidos: {', '.join(settings.PHOTO_ALLOWED_FORMATS)}"
            )
        
        return value
    
    def validate_file_size(self, value):
        """Valida el tamaño del archivo"""
        from django.conf import settings
        
        if value > settings.PHOTO_MAX_SIZE:
            max_mb = settings.PHOTO_MAX_SIZE / (1024 * 1024)
            raise serializers.ValidationError(
                f"Archivo muy grande. Tamaño máximo: {max_mb}MB"
            )
        
        return value
    
    def validate_physical_advance_id(self, value):
        """Valida que el avance físico exista"""
        from ..models import Physical
        
        try:
            Physical.objects.get(id=value)
        except Physical.DoesNotExist:
            raise serializers.ValidationError("El avance físico especificado no existe")
        
        return value
    
    def validate_construction_id(self, value):
        """Valida que la obra exista"""
        from obra.models import Construction
        
        try:
            Construction.objects.get(id=value)
        except Construction.DoesNotExist:
            raise serializers.ValidationError("La obra especificada no existe")
        
        return value


class PhotoConfirmUploadSerializer(serializers.Serializer):
    """
    Serializer para confirmar que la subida se completó exitosamente
    """
    photo_id = serializers.UUIDField()
    upload_successful = serializers.BooleanField()
    error_message = serializers.CharField(required=False, allow_blank=True)
    
    # Metadatos adicionales que pueden venir del cliente
    actual_file_size = serializers.IntegerField(required=False)
    client_upload_duration = serializers.FloatField(required=False)  # segundos
    
    def validate_photo_id(self, value):
        """Valida que la foto exista y esté en estado correcto"""
        try:
            photo = Photo.objects.get(id=value)
            if photo.upload_status not in ['PENDING', 'UPLOADING']:
                raise serializers.ValidationError(
                    "La foto no está en un estado válido para confirmación"
                )
            return value
        except Photo.DoesNotExist:
            raise serializers.ValidationError("La foto especificada no existe")


class PhotoMetadataSerializer(serializers.Serializer):
    """
    Serializer para actualizar metadatos de una foto después de procesamiento
    """
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    gps_accuracy = serializers.FloatField(required=False, allow_null=True)
    device_model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    camera_make = serializers.CharField(max_length=50, required=False, allow_blank=True)
    camera_model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    taken_at = serializers.DateTimeField(required=False, allow_null=True)
    exif_data = serializers.JSONField(required=False)


class PhotoSerializer(serializers.ModelSerializer):
    """
    Serializer principal para el modelo Photo
    """
    file_size_mb = serializers.ReadOnlyField()
    image_resolution = serializers.ReadOnlyField()
    has_gps = serializers.ReadOnlyField()
    display_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    # Información del usuario y avance
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    physical_advance_description = serializers.CharField(
        source='physical_advance.concept.description', 
        read_only=True
    )
    construction_name = serializers.CharField(source='construction.name', read_only=True)
    
    class Meta:
        model = Photo
        fields = [
            'id', 'original_filename', 'blob_path', 'file_size_bytes', 'file_size_mb',
            'content_type', 'image_width', 'image_height', 'image_resolution',
            'upload_status', 'uploaded_at', 'taken_at', 'latitude', 'longitude',
            'gps_accuracy', 'has_gps', 'device_model', 'camera_make', 'camera_model',
            'exif_data', 'is_processed', 'processing_notes', 'display_url', 
            'thumbnail_url', 'uploaded_by', 'uploaded_by_username', 'physical_advance',
            'physical_advance_description', 'construction', 'construction_name'
        ]
        read_only_fields = [
            'id', 'uploaded_at', 'blob_path', 'blob_url', 'thumbnail_blob_path',
            'thumbnail_blob_url', 'is_processed', 'processing_notes'
        ]
    
    def get_display_url(self, obj):
        """Retorna URL de visualización con SAS token"""
        try:
            return obj.get_display_url(with_sas=True, expiry_hours=24)
        except Exception:
            return None
    
    def get_thumbnail_url(self, obj):
        """Retorna URL del thumbnail con SAS token"""
        try:
            return obj.get_thumbnail_url(with_sas=True, expiry_hours=24)
        except Exception:
            return None


class PhotoListSerializer(serializers.ModelSerializer):
    """
    Serializer simplificado para listados de fotos
    """
    file_size_mb = serializers.ReadOnlyField()
    has_gps = serializers.ReadOnlyField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)
    
    class Meta:
        model = Photo
        fields = [
            'id', 'original_filename', 'file_size_mb', 'content_type',
            'image_width', 'image_height', 'upload_status', 'uploaded_at',
            'taken_at', 'has_gps', 'device_model', 'thumbnail_url',
            'uploaded_by_username', 'physical_advance', 'construction'
        ]
    
    def get_thumbnail_url(self, obj):
        """Retorna URL del thumbnail"""
        try:
            return obj.get_thumbnail_url(with_sas=True, expiry_hours=24)
        except Exception:
            return None


class PhotoBulkUploadRequestSerializer(serializers.Serializer):
    """
    Serializer para solicitudes de subida múltiple
    """
    photos = PhotoUploadRequestSerializer(many=True)
    
    def validate_photos(self, value):
        """Valida que no se excedan los límites de subida múltiple"""
        if len(value) > 20:  # Límite de 20 fotos por batch
            raise serializers.ValidationError("Máximo 20 fotos por lote")
        
        if len(value) == 0:
            raise serializers.ValidationError("Debe incluir al menos una foto")
        
        return value


class PhotoAnalyticsSerializer(serializers.Serializer):
    """
    Serializer para estadísticas de fotos
    """
    construction_id = serializers.IntegerField(required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    
    def validate(self, data):
        """Valida que las fechas sean coherentes"""
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                "La fecha de inicio debe ser anterior a la fecha de fin"
            )
        
        return data