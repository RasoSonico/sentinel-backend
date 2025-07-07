"""
Tareas asíncronas para procesamiento de fotos
Este módulo puede usarse con Celery para procesar fotos en background
"""

import logging
from typing import Dict, Any
from django.conf import settings
from .blob_service import blob_service
from .image_service import image_service
from ..models import Photo

logger = logging.getLogger(__name__)


class PhotoProcessor:
    """
    Procesador de fotos que puede ejecutarse de forma síncrona o asíncrona
    """
    
    @staticmethod
    def process_uploaded_photo(photo_id: str) -> Dict[str, Any]:
        """
        Procesa una foto subida: extrae metadatos, crea thumbnail, etc.
        """
        try:
            photo = Photo.objects.get(id=photo_id)
            
            if photo.upload_status != 'COMPLETED':
                return {
                    'success': False,
                    'error': f'Foto en estado inválido: {photo.upload_status}'
                }
            
            # Obtener el blob client para descargar y procesar
            blob_client = blob_service.blob_service_client.get_blob_client(
                container=blob_service.container_name,
                blob=photo.blob_path
            )
            
            # Descargar imagen para procesamiento
            logger.info(f"Descargando imagen {photo.id} para procesamiento")
            image_data = blob_client.download_blob().readall()
            
            # Validar imagen
            validation = image_service.validate_image(image_data, photo.original_filename)
            if not validation['valid']:
                photo.upload_status = 'FAILED'
                photo.processing_notes = f"Imagen inválida: {validation['error']}"
                photo.save()
                return {
                    'success': False,
                    'error': validation['error']
                }
            
            # Extraer metadatos EXIF
            logger.info(f"Extrayendo metadatos de {photo.id}")
            metadata = image_service.extract_metadata(image_data, photo.original_filename)
            
            # Actualizar dimensiones de imagen
            if 'image_info' in metadata:
                image_info = metadata['image_info']
                photo.image_width = image_info.get('width', 0)
                photo.image_height = image_info.get('height', 0)
            
            # Actualizar coordenadas GPS si no las tenemos
            if not photo.has_gps and metadata.get('gps_coordinates'):
                gps = metadata['gps_coordinates']
                photo.latitude = gps['latitude']
                photo.longitude = gps['longitude']
                logger.info(f"GPS encontrado para {photo.id}: {gps['latitude']}, {gps['longitude']}")
            
            # Actualizar información de cámara
            if metadata.get('camera_info'):
                camera_info = metadata['camera_info']
                photo.camera_make = camera_info.get('Make', '')[:50]
                photo.camera_model = camera_info.get('Model', '')[:100]
                if not photo.device_model and 'device' in camera_info:
                    photo.device_model = camera_info['device'][:100]
            
            # Actualizar fecha de captura si no la tenemos
            if not photo.taken_at and metadata.get('datetime_taken'):
                try:
                    from datetime import datetime
                    taken_str = metadata['datetime_taken']
                    photo.taken_at = datetime.strptime(taken_str, '%Y:%m:%d %H:%M:%S')
                    logger.info(f"Fecha de captura encontrada para {photo.id}: {photo.taken_at}")
                except Exception as e:
                    logger.warning(f"Error parseando fecha de captura: {str(e)}")
            
            # Guardar metadatos EXIF completos
            photo.exif_data = metadata.get('exif_data', {})
            
            # Procesar imagen si es necesario (redimensionar)
            processed_data = image_data
            processing_info = {}
            
            if photo.image_width > settings.PHOTO_MAX_DIMENSION or photo.image_height > settings.PHOTO_MAX_DIMENSION:
                logger.info(f"Redimensionando imagen {photo.id}")
                processed_data, processing_info = image_service.process_image(
                    image_data,
                    max_dimension=settings.PHOTO_MAX_DIMENSION,
                    quality=settings.PHOTO_JPEG_QUALITY
                )
                
                # Si la imagen fue redimensionada, reemplazar en blob
                if processing_info.get('final_size') != processing_info.get('original_size'):
                    blob_service.upload_blob(
                        blob_path=photo.blob_path,
                        data=processed_data,
                        content_type='image/jpeg',
                        metadata={
                            'photo_id': str(photo.id),
                            'processed': 'true',
                            'original_size': f"{processing_info['original_size'][0]}x{processing_info['original_size'][1]}",
                            'final_size': f"{processing_info['final_size'][0]}x{processing_info['final_size'][1]}"
                        }
                    )
                    
                    # Actualizar dimensiones y tamaño
                    photo.image_width = processing_info['final_size'][0]
                    photo.image_height = processing_info['final_size'][1]
                    photo.file_size_bytes = processing_info['final_file_size']
            
            # Crear thumbnail
            logger.info(f"Creando thumbnail para {photo.id}")
            thumbnail_data = image_service.create_thumbnail(
                processed_data,
                size=settings.PHOTO_THUMBNAIL_SIZE,
                quality=settings.PHOTO_JPEG_QUALITY
            )
            
            # Generar ruta del thumbnail
            thumbnail_path = photo.blob_path
            
            # Insertar '_thumb' antes de la extensión
            if '.' in thumbnail_path:
                name, ext = thumbnail_path.rsplit('.', 1)
                thumbnail_path = f"{name}_thumb.jpg"
            else:
                thumbnail_path = f"{thumbnail_path}_thumb.jpg"
            
            # Subir thumbnail
            logger.info(f"Subiendo thumbnail para {photo.id}")
            thumbnail_url = blob_service.upload_blob(
                blob_path=thumbnail_path,
                data=thumbnail_data,
                content_type='image/jpeg',
                metadata={
                    'original_photo_id': str(photo.id),
                    'type': 'thumbnail',
                    'size': f"{settings.PHOTO_THUMBNAIL_SIZE[0]}x{settings.PHOTO_THUMBNAIL_SIZE[1]}"
                }
            )
            
            photo.thumbnail_blob_path = thumbnail_path
            photo.thumbnail_blob_url = thumbnail_url
            
            # Marcar como procesada
            photo.is_processed = True
            photo.processing_notes = 'Procesada exitosamente'
            if processing_info:
                photo.processing_notes += f" - Redimensionada de {processing_info['original_size']} a {processing_info['final_size']}"
            
            photo.save()
            
            logger.info(f"Foto {photo.id} procesada exitosamente")
            
            return {
                'success': True,
                'photo_id': str(photo.id),
                'metadata_extracted': bool(metadata),
                'gps_found': bool(metadata.get('gps_coordinates')),
                'thumbnail_created': True,
                'processing_info': processing_info
            }
            
        except Photo.DoesNotExist:
            error_msg = f"Foto {photo_id} no encontrada"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Error procesando foto {photo_id}: {str(e)}"
            logger.error(error_msg)
            
            # Intentar actualizar el estado de la foto
            try:
                photo = Photo.objects.get(id=photo_id)
                photo.processing_notes = error_msg
                photo.save()
            except:
                pass
            
            return {
                'success': False,
                'error': error_msg
            }
    
    @staticmethod
    def cleanup_failed_uploads(hours_old: int = 24) -> Dict[str, Any]:
        """
        Limpia fotos en estado PENDING o UPLOADING que sean muy antiguas
        """
        try:
            from django.utils import timezone
            from datetime import timedelta
            
            cutoff_time = timezone.now() - timedelta(hours=hours_old)
            
            # Buscar fotos antiguas en estados temporales
            old_photos = Photo.objects.filter(
                upload_status__in=['PENDING', 'UPLOADING'],
                uploaded_at__lt=cutoff_time
            )
            
            deleted_count = 0
            errors = []
            
            for photo in old_photos:
                try:
                    # Intentar eliminar blob si existe
                    if blob_service.blob_exists(photo.blob_path):
                        blob_service.delete_blob(photo.blob_path)
                    
                    # Eliminar thumbnail si existe
                    if photo.thumbnail_blob_path and blob_service.blob_exists(photo.thumbnail_blob_path):
                        blob_service.delete_blob(photo.thumbnail_blob_path)
                    
                    # Eliminar registro
                    photo.delete()
                    deleted_count += 1
                    
                except Exception as e:
                    errors.append(f"Error eliminando foto {photo.id}: {str(e)}")
            
            logger.info(f"Limpieza completada: {deleted_count} fotos eliminadas")
            
            return {
                'success': True,
                'deleted_count': deleted_count,
                'errors': errors
            }
            
        except Exception as e:
            error_msg = f"Error en limpieza: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    @staticmethod
    def regenerate_thumbnails(construction_id: int = None) -> Dict[str, Any]:
        """
        Regenera thumbnails para fotos que no los tengan
        """
        try:
            queryset = Photo.objects.filter(
                upload_status='COMPLETED',
                is_processed=True,
                thumbnail_blob_path__isnull=True
            )
            
            if construction_id:
                queryset = queryset.filter(construction_id=construction_id)
            
            processed_count = 0
            errors = []
            
            for photo in queryset:
                try:
                    # Descargar imagen original
                    blob_client = blob_service.blob_service_client.get_blob_client(
                        container=blob_service.container_name,
                        blob=photo.blob_path
                    )
                    
                    image_data = blob_client.download_blob().readall()
                    
                    # Crear thumbnail
                    thumbnail_data = image_service.create_thumbnail(
                        image_data,
                        size=settings.PHOTO_THUMBNAIL_SIZE,
                        quality=settings.PHOTO_JPEG_QUALITY
                    )
                    
                    # Generar ruta del thumbnail
                    thumbnail_path = photo.blob_path
                    if '.' in thumbnail_path:
                        name, ext = thumbnail_path.rsplit('.', 1)
                        thumbnail_path = f"{name}_thumb.jpg"
                    else:
                        thumbnail_path = f"{thumbnail_path}_thumb.jpg"
                    
                    # Subir thumbnail
                    thumbnail_url = blob_service.upload_blob(
                        blob_path=thumbnail_path,
                        data=thumbnail_data,
                        content_type='image/jpeg',
                        metadata={
                            'original_photo_id': str(photo.id),
                            'type': 'thumbnail'
                        }
                    )
                    
                    # Actualizar foto
                    photo.thumbnail_blob_path = thumbnail_path
                    photo.thumbnail_blob_url = thumbnail_url
                    photo.save()
                    
                    processed_count += 1
                    
                except Exception as e:
                    errors.append(f"Error procesando foto {photo.id}: {str(e)}")
            
            logger.info(f"Regeneración de thumbnails completada: {processed_count} procesados")
            
            return {
                'success': True,
                'processed_count': processed_count,
                'errors': errors
            }
            
        except Exception as e:
            error_msg = f"Error regenerando thumbnails: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }


# Si tienes Celery configurado, puedes descomentar esto:
"""
try:
    from celery import shared_task
    
    @shared_task(bind=True, max_retries=3)
    def process_photo_async(self, photo_id):
        try:
            return PhotoProcessor.process_uploaded_photo(photo_id)
        except Exception as exc:
            logger.error(f"Error en tarea asíncrona para foto {photo_id}: {str(exc)}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60, exc=exc)
            else:
                # Marcar como fallida después de reintentos
                try:
                    photo = Photo.objects.get(id=photo_id)
                    photo.processing_notes = f"Error después de {self.max_retries} reintentos: {str(exc)}"
                    photo.save()
                except:
                    pass
                raise
    
    @shared_task
    def cleanup_failed_uploads_async(hours_old=24):
        return PhotoProcessor.cleanup_failed_uploads(hours_old)
    
    @shared_task
    def regenerate_thumbnails_async(construction_id=None):
        return PhotoProcessor.regenerate_thumbnails(construction_id)

except ImportError:
    # Celery no está disponible
    pass
"""