"""
Servicio para procesamiento de imágenes
Incluye redimensionamiento, generación de thumbnails, conversión de formatos
y extracción de metadatos EXIF
"""

import io
import os
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS
import json
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Intentar importar pillow-heif para soporte HEIC
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_SUPPORTED = True
except ImportError:
    HEIF_SUPPORTED = False
    logger.warning("pillow-heif no está instalado. Soporte HEIC limitado.")

# Intentar importar exifread para metadatos avanzados
try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False
    logger.warning("exifread no está disponible. Metadatos limitados.")


class ImageService:
    """
    Servicio para procesamiento de imágenes
    """
    
    @staticmethod
    def validate_image(file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Valida que el archivo sea una imagen válida
        """
        try:
            # Verificar extensión
            file_ext = filename.lower().split('.')[-1]
            if file_ext not in settings.PHOTO_ALLOWED_FORMATS:
                return {
                    'valid': False,
                    'error': f'Formato no permitido. Formatos válidos: {", ".join(settings.PHOTO_ALLOWED_FORMATS)}'
                }
            
            # Verificar tamaño
            if len(file_data) > settings.PHOTO_MAX_SIZE:
                size_mb = len(file_data) / (1024 * 1024)
                max_mb = settings.PHOTO_MAX_SIZE / (1024 * 1024)
                return {
                    'valid': False,
                    'error': f'Archivo muy grande: {size_mb:.1f}MB. Máximo permitido: {max_mb}MB'
                }
            
            # Intentar abrir la imagen
            try:
                img = Image.open(io.BytesIO(file_data))
                img.verify()  # Verificar que no esté corrupta
                
                # Reabrir para obtener información (verify() cierra la imagen)
                img = Image.open(io.BytesIO(file_data))
                
                return {
                    'valid': True,
                    'format': img.format,
                    'size': img.size,
                    'mode': img.mode
                }
                
            except Exception as e:
                return {
                    'valid': False,
                    'error': f'Archivo de imagen inválido: {str(e)}'
                }
                
        except Exception as e:
            logger.error(f"Error validando imagen: {str(e)}")
            return {
                'valid': False,
                'error': 'Error interno validando imagen'
            }
    
    @staticmethod
    def extract_metadata(file_data: bytes, filename: str) -> Dict[str, Any]:
        """
        Extrae metadatos EXIF de la imagen
        """
        metadata = {
            'filename': filename,
            'file_size': len(file_data),
            'gps_coordinates': None,
            'datetime_taken': None,
            'camera_info': {},
            'image_info': {},
            'exif_data': {}
        }
        
        try:
            img = Image.open(io.BytesIO(file_data))
            
            # Información básica de la imagen
            metadata['image_info'] = {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.width,
                'height': img.height
            }
            
            # Extraer EXIF data si está disponible
            exif_data = img.getexif()
            
            if exif_data:
                # Datos EXIF básicos
                for tag_id, value in exif_data.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    metadata['exif_data'][tag_name] = str(value)
                
                # Buscar coordenadas GPS
                gps_info = ImageService._extract_gps_coordinates(exif_data)
                if gps_info:
                    metadata['gps_coordinates'] = gps_info
                
                # Buscar fecha de captura
                datetime_taken = ImageService._extract_datetime_taken(exif_data)
                if datetime_taken:
                    metadata['datetime_taken'] = datetime_taken
                
                # Información de la cámara
                camera_info = ImageService._extract_camera_info(exif_data)
                metadata['camera_info'] = camera_info
            
            # Si tenemos exifread disponible, intentar extraer más metadatos
            if EXIFREAD_AVAILABLE:
                try:
                    file_io = io.BytesIO(file_data)
                    tags = exifread.process_file(file_io, details=False)
                    
                    # Agregar tags adicionales que puedan ser útiles
                    for tag_name, tag_value in tags.items():
                        if tag_name not in metadata['exif_data']:
                            metadata['exif_data'][tag_name] = str(tag_value)
                            
                except Exception as e:
                    logger.warning(f"Error extrayendo metadatos con exifread: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error extrayendo metadatos: {str(e)}")
        
        return metadata
    
    @staticmethod
    def _extract_gps_coordinates(exif_data) -> Optional[Dict[str, float]]:
        """
        Extrae coordenadas GPS del EXIF
        """
        try:
            gps_info = exif_data.get_ifd(0x8825)  # GPS IFD
            
            if not gps_info:
                return None
            
            def convert_to_degrees(value):
                """Convierte coordenadas DMS a decimal"""
                if not value or len(value) != 3:
                    return None
                
                degrees = float(value[0])
                minutes = float(value[1])
                seconds = float(value[2])
                
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            # Obtener latitud
            lat = gps_info.get(2)  # GPSLatitude
            lat_ref = gps_info.get(1)  # GPSLatitudeRef
            
            # Obtener longitud
            lng = gps_info.get(4)  # GPSLongitude
            lng_ref = gps_info.get(3)  # GPSLongitudeRef
            
            if lat and lng:
                latitude = convert_to_degrees(lat)
                longitude = convert_to_degrees(lng)
                
                if latitude is not None and longitude is not None:
                    # Aplicar referencia (N/S para latitud, E/W para longitud)
                    if lat_ref and lat_ref.upper() == 'S':
                        latitude = -latitude
                    if lng_ref and lng_ref.upper() == 'W':
                        longitude = -longitude
                    
                    return {
                        'latitude': latitude,
                        'longitude': longitude
                    }
            
        except Exception as e:
            logger.warning(f"Error extrayendo GPS: {str(e)}")
        
        return None
    
    @staticmethod
    def _extract_datetime_taken(exif_data) -> Optional[str]:
        """
        Extrae la fecha de captura de la foto
        """
        try:
            # Buscar diferentes tags de fecha
            date_tags = [
                36867,  # DateTimeOriginal
                36868,  # DateTimeDigitized
                306,    # DateTime
            ]
            
            for tag in date_tags:
                if tag in exif_data:
                    return exif_data[tag]
            
        except Exception as e:
            logger.warning(f"Error extrayendo fecha: {str(e)}")
        
        return None
    
    @staticmethod
    def _extract_camera_info(exif_data) -> Dict[str, Any]:
        """
        Extrae información de la cámara
        """
        camera_info = {}
        
        try:
            # Mapeo de tags de cámara
            camera_tags = {
                'Make': 271,      # Fabricante
                'Model': 272,     # Modelo
                'Software': 305,  # Software
                'LensMake': 42035,
                'LensModel': 42036,
            }
            
            for name, tag_id in camera_tags.items():
                if tag_id in exif_data:
                    camera_info[name] = exif_data[tag_id]
            
            # Combinar make y model para device_info
            if 'Make' in camera_info and 'Model' in camera_info:
                camera_info['device'] = f"{camera_info['Make']} {camera_info['Model']}"
            
        except Exception as e:
            logger.warning(f"Error extrayendo info de cámara: {str(e)}")
        
        return camera_info
    
    @staticmethod
    def process_image(
        file_data: bytes, 
        max_dimension: Optional[int] = None,
        quality: int = 85,
        format_output: str = 'JPEG'
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Procesa una imagen: redimensiona y optimiza
        """
        try:
            img = Image.open(io.BytesIO(file_data))
            
            # Convertir HEIC a RGB si es necesario
            if img.format == 'HEIF' or format_output.upper() == 'JPEG':
                if img.mode in ('RGBA', 'LA', 'P'):
                    # Crear fondo blanco para transparencias
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            
            original_size = img.size
            
            # Redimensionar si es necesario
            if max_dimension and (img.width > max_dimension or img.height > max_dimension):
                img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            
            # Guardar la imagen procesada
            output_buffer = io.BytesIO()
            
            if format_output.upper() == 'JPEG':
                img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            else:
                img.save(output_buffer, format=format_output, optimize=True)
            
            processed_data = output_buffer.getvalue()
            
            processing_info = {
                'original_size': original_size,
                'final_size': img.size,
                'original_file_size': len(file_data),
                'final_file_size': len(processed_data),
                'compression_ratio': len(file_data) / len(processed_data) if len(processed_data) > 0 else 1,
                'format': format_output
            }
            
            return processed_data, processing_info
            
        except Exception as e:
            logger.error(f"Error procesando imagen: {str(e)}")
            raise
    
    @staticmethod
    def create_thumbnail(
        file_data: bytes, 
        size: Tuple[int, int] = None,
        quality: int = 85
    ) -> bytes:
        """
        Crea un thumbnail de la imagen
        """
        try:
            if size is None:
                size = settings.PHOTO_THUMBNAIL_SIZE
            
            img = Image.open(io.BytesIO(file_data))
            
            # Convertir a RGB si es necesario
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Crear thumbnail manteniendo aspect ratio
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Guardar como JPEG
            output_buffer = io.BytesIO()
            img.save(output_buffer, format='JPEG', quality=quality, optimize=True)
            
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Error creando thumbnail: {str(e)}")
            raise


# Instancia global del servicio
image_service = ImageService()