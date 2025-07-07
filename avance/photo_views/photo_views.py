"""
Vistas para el módulo de fotografías y Azure Blob Storage
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import logging

from ..models import Photo, Physical
from obra.models import Construction
from ..photo_serializers.photo_serializers import (
    PhotoUploadRequestSerializer,
    PhotoConfirmUploadSerializer,
    PhotoMetadataSerializer,
    PhotoSerializer,
    PhotoListSerializer,
    PhotoBulkUploadRequestSerializer,
    PhotoAnalyticsSerializer
)
from ..services.blob_service import blob_service
from ..services.image_service import image_service

logger = logging.getLogger(__name__)


class PhotoUploadAPIView(APIView):
    """
    Vista para gestionar la subida de fotos mediante SAS tokens
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Genera SAS token para subida directa de foto
        """
        serializer = PhotoUploadRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Extraer datos validados
            data = serializer.validated_data
            
            # Obtener instancias relacionadas
            physical_advance = Physical.objects.get(id=data['physical_advance_id'])
            construction = Construction.objects.get(id=data['construction_id'])
            
            # Generar ID único para la foto
            photo_id = uuid.uuid4()
            
            # Generar ruta del blob
            blob_path = blob_service.generate_blob_path(
                obra_id=construction.id,
                avance_id=physical_advance.id,
                filename=data['filename']
            )
            
            # Generar SAS token para subida
            sas_data = blob_service.generate_upload_sas_token(blob_path, expiry_hours=2)
            
            # Crear registro de foto en estado PENDING
            photo = Photo.objects.create(
                id=photo_id,
                original_filename=data['filename'],
                blob_path=blob_path,
                file_size_bytes=data['file_size'],
                content_type=data['content_type'],
                image_width=0,  # Se actualizará después del procesamiento
                image_height=0,  # Se actualizará después del procesamiento
                upload_status='PENDING',
                uploaded_by=request.user,
                physical_advance=physical_advance,
                construction=construction,
                # Metadatos del cliente
                device_model=data.get('device_model', ''),
                latitude=data.get('latitude'),
                longitude=data.get('longitude'),
                gps_accuracy=data.get('gps_accuracy'),
                taken_at=data.get('taken_at')
            )
            
            # Actualizar estado a UPLOADING
            photo.upload_status = 'UPLOADING'
            photo.save()
            
            response_data = {
                'photo_id': str(photo.id),
                'upload_url': sas_data['upload_url'],
                'blob_path': sas_data['blob_path'],
                'expires_at': sas_data['expires_at'],
                'instructions': {
                    'method': 'PUT',
                    'headers': {
                        'x-ms-blob-type': 'BlockBlob',
                        'Content-Type': data['content_type']
                    },
                    'note': 'Usar PUT para subir el archivo directamente a upload_url'
                }
            }
            
            logger.info(f"SAS token generado para foto {photo.id} del usuario {request.user.username}")
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Physical.DoesNotExist:
            return Response(
                {'error': 'Avance físico no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Construction.DoesNotExist:
            return Response(
                {'error': 'Obra no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error generando SAS token: {str(e)}")
            return Response(
                {'error': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PhotoConfirmUploadAPIView(APIView):
    """
    Vista para confirmar que la subida se completó
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Confirma que la subida de foto se completó y procesa la imagen
        """
        serializer = PhotoConfirmUploadSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            data = serializer.validated_data
            photo = Photo.objects.get(id=data['photo_id'])
            
            # Verificar que el usuario tenga permisos
            if photo.uploaded_by != request.user:
                return Response(
                    {'error': 'No tienes permisos para confirmar esta foto'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            if data['upload_successful']:
                # Verificar que el blob existe
                if blob_service.blob_exists(photo.blob_path):
                    # Obtener propiedades del blob
                    blob_props = blob_service.get_blob_properties(photo.blob_path)
                    
                    if blob_props:
                        # Actualizar datos del archivo
                        photo.file_size_bytes = blob_props['size']
                        photo.blob_url = f"https://{blob_service.account_name}.blob.core.windows.net/{blob_service.container_name}/{photo.blob_path}"
                        
                        # Marcar como completada
                        photo.upload_status = 'COMPLETED'
                        photo.save()
                        
                        # Procesar imagen en background (puedes usar Celery aquí)
                        try:
                            self._process_uploaded_photo(photo)
                        except Exception as e:
                            logger.error(f"Error procesando foto {photo.id}: {str(e)}")
                            photo.processing_notes = f"Error en procesamiento: {str(e)}"
                            photo.save()
                        
                        return Response({
                            'message': 'Foto confirmada exitosamente',
                            'photo_id': str(photo.id),
                            'status': 'COMPLETED'
                        })
                    else:
                        photo.upload_status = 'FAILED'
                        photo.processing_notes = 'No se pudieron obtener propiedades del blob'
                        photo.save()
                        
                        return Response(
                            {'error': 'Error obteniendo propiedades del archivo'},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                else:
                    photo.upload_status = 'FAILED'
                    photo.processing_notes = 'Blob no encontrado después de la subida'
                    photo.save()
                    
                    return Response(
                        {'error': 'Archivo no encontrado en el servidor'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Subida falló
                photo.upload_status = 'FAILED'
                photo.processing_notes = data.get('error_message', 'Error desconocido en la subida')
                photo.save()
                
                return Response(
                    {'message': 'Subida marcada como fallida'},
                    status=status.HTTP_200_OK
                )
                
        except Photo.DoesNotExist:
            return Response(
                {'error': 'Foto no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error confirmando subida: {str(e)}")
            return Response(
                {'error': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _process_uploaded_photo(self, photo):
        """
        Procesa la foto subida: extrae metadatos, crea thumbnail, etc.
        """
        try:
            # Obtener el blob client para descargar y procesar
            blob_client = blob_service.blob_service_client.get_blob_client(
                container=blob_service.container_name,
                blob=photo.blob_path
            )
            
            # Descargar imagen para procesamiento
            image_data = blob_client.download_blob().readall()
            
            # Extraer metadatos EXIF
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
                    # Parsear fecha EXIF
                    taken_str = metadata['datetime_taken']
                    photo.taken_at = datetime.strptime(taken_str, '%Y:%m:%d %H:%M:%S')
                except:
                    pass
            
            # Guardar metadatos EXIF completos
            photo.exif_data = metadata.get('exif_data', {})
            
            # Crear thumbnail
            thumbnail_data = image_service.create_thumbnail(image_data)
            
            # Generar ruta del thumbnail
            thumbnail_path = photo.blob_path.replace('.', '_thumb.')
            if not thumbnail_path.lower().endswith('.jpg'):
                thumbnail_path = thumbnail_path.rsplit('.', 1)[0] + '_thumb.jpg'
            
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
            
            photo.thumbnail_blob_path = thumbnail_path
            photo.thumbnail_blob_url = thumbnail_url
            
            # Marcar como procesada
            photo.is_processed = True
            photo.processing_notes = 'Procesada exitosamente'
            photo.save()
            
            logger.info(f"Foto {photo.id} procesada exitosamente")
            
        except Exception as e:
            logger.error(f"Error procesando foto {photo.id}: {str(e)}")
            photo.processing_notes = f"Error en procesamiento: {str(e)}"
            photo.save()
            raise


class PhotoBulkUploadAPIView(APIView):
    """
    Vista para subida múltiple de fotos
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """
        Genera múltiples SAS tokens para subida de fotos
        """
        serializer = PhotoBulkUploadRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(
                {'error': 'Datos inválidos', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            photos_data = serializer.validated_data['photos']
            results = []
            
            for photo_data in photos_data:
                try:
                    # Procesar cada foto individualmente
                    individual_request = PhotoUploadRequestSerializer(data=photo_data)
                    if individual_request.is_valid():
                        # Lógica similar a PhotoUploadAPIView
                        physical_advance = Physical.objects.get(id=photo_data['physical_advance_id'])
                        construction = Construction.objects.get(id=photo_data['construction_id'])
                        
                        photo_id = uuid.uuid4()
                        blob_path = blob_service.generate_blob_path(
                            obra_id=construction.id,
                            avance_id=physical_advance.id,
                            filename=photo_data['filename']
                        )
                        
                        sas_data = blob_service.generate_upload_sas_token(blob_path, expiry_hours=2)
                        
                        photo = Photo.objects.create(
                            id=photo_id,
                            original_filename=photo_data['filename'],
                            blob_path=blob_path,
                            file_size_bytes=photo_data['file_size'],
                            content_type=photo_data['content_type'],
                            image_width=0,
                            image_height=0,
                            upload_status='PENDING',
                            uploaded_by=request.user,
                            physical_advance=physical_advance,
                            construction=construction,
                            device_model=photo_data.get('device_model', ''),
                            latitude=photo_data.get('latitude'),
                            longitude=photo_data.get('longitude'),
                            gps_accuracy=photo_data.get('gps_accuracy'),
                            taken_at=photo_data.get('taken_at')
                        )
                        
                        photo.upload_status = 'UPLOADING'
                        photo.save()
                        
                        results.append({
                            'photo_id': str(photo.id),
                            'filename': photo_data['filename'],
                            'upload_url': sas_data['upload_url'],
                            'blob_path': sas_data['blob_path'],
                            'expires_at': sas_data['expires_at'],
                            'success': True
                        })
                    else:
                        results.append({
                            'filename': photo_data.get('filename', 'unknown'),
                            'success': False,
                            'error': individual_request.errors
                        })
                        
                except Exception as e:
                    results.append({
                        'filename': photo_data.get('filename', 'unknown'),
                        'success': False,
                        'error': str(e)
                    })
            
            return Response({
                'results': results,
                'total_requested': len(photos_data),
                'successful': len([r for r in results if r.get('success', False)]),
                'failed': len([r for r in results if not r.get('success', False)])
            })
            
        except Exception as e:
            logger.error(f"Error en subida múltiple: {str(e)}")
            return Response(
                {'error': 'Error interno del servidor'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PhotoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para consultar fotos
    """
    queryset = Photo.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        'upload_status', 'construction', 'physical_advance', 
        'uploaded_by', 'is_processed'
    ]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PhotoListSerializer
        return PhotoSerializer
    
    def get_queryset(self):
        """Filtrar fotos según permisos del usuario"""
        user = self.request.user
        queryset = Photo.objects.select_related(
            'uploaded_by', 'physical_advance', 'construction'
        )
        
        # Filtros adicionales por query params
        construction_id = self.request.query_params.get('construction_id')
        if construction_id:
            queryset = queryset.filter(construction_id=construction_id)
        
        date_from = self.request.query_params.get('date_from')
        if date_from:
            queryset = queryset.filter(uploaded_at__date__gte=date_from)
        
        date_to = self.request.query_params.get('date_to')
        if date_to:
            queryset = queryset.filter(uploaded_at__date__lte=date_to)
        
        has_gps = self.request.query_params.get('has_gps')
        if has_gps is not None:
            if has_gps.lower() == 'true':
                queryset = queryset.filter(latitude__isnull=False, longitude__isnull=False)
            else:
                queryset = queryset.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))
        
        return queryset.order_by('-uploaded_at')
    
    @action(detail=True, methods=['patch'])
    def update_metadata(self, request, pk=None):
        """
        Actualiza metadatos de una foto
        """
        photo = self.get_object()
        
        # Verificar permisos
        if photo.uploaded_by != request.user and not request.user.is_staff:
            return Response(
                {'error': 'No tienes permisos para editar esta foto'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = PhotoMetadataSerializer(data=request.data)
        if serializer.is_valid():
            # Actualizar campos permitidos
            for field, value in serializer.validated_data.items():
                setattr(photo, field, value)
            
            photo.save()
            
            return Response(PhotoSerializer(photo, context={'request': request}).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'])
    def delete_photo(self, request, pk=None):
        """
        Elimina una foto y su blob asociado
        """
        photo = self.get_object()
        
        # Verificar permisos
        if photo.uploaded_by != request.user and not request.user.is_staff:
            return Response(
                {'error': 'No tienes permisos para eliminar esta foto'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Eliminar blobs de Azure
            blob_service.delete_blob(photo.blob_path)
            if photo.thumbnail_blob_path:
                blob_service.delete_blob(photo.thumbnail_blob_path)
            
            # Eliminar registro de BD
            photo.delete()
            
            return Response({'message': 'Foto eliminada exitosamente'})
            
        except Exception as e:
            logger.error(f"Error eliminando foto {pk}: {str(e)}")
            return Response(
                {'error': 'Error eliminando foto'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PhotoAnalyticsAPIView(APIView):
    """
    Vista para estadísticas de fotos
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Retorna estadísticas de fotos
        """
        serializer = PhotoAnalyticsSerializer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        queryset = Photo.objects.all()
        
        # Aplicar filtros
        if data.get('construction_id'):
            queryset = queryset.filter(construction_id=data['construction_id'])
        
        if data.get('date_from'):
            queryset = queryset.filter(uploaded_at__date__gte=data['date_from'])
        
        if data.get('date_to'):
            queryset = queryset.filter(uploaded_at__date__lte=data['date_to'])
        
        # Calcular estadísticas
        stats = queryset.aggregate(
            total_photos=Count('id'),
            total_size_mb=Sum('file_size_bytes') / (1024 * 1024),
            completed_uploads=Count('id', filter=Q(upload_status='COMPLETED')),
            failed_uploads=Count('id', filter=Q(upload_status='FAILED')),
            photos_with_gps=Count('id', filter=Q(latitude__isnull=False, longitude__isnull=False)),
            avg_file_size_mb=Avg('file_size_bytes') / (1024 * 1024)
        )
        
        # Estadísticas por estado
        status_stats = queryset.values('upload_status').annotate(
            count=Count('id')
        ).order_by('upload_status')
        
        # Estadísticas por construcción
        construction_stats = queryset.values(
            'construction__id', 'construction__name'
        ).annotate(
            photo_count=Count('id'),
            total_size_mb=Sum('file_size_bytes') / (1024 * 1024)
        ).order_by('-photo_count')[:10]  # Top 10
        
        # Estadísticas por usuario
        user_stats = queryset.values(
            'uploaded_by__id', 'uploaded_by__username'
        ).annotate(
            photo_count=Count('id'),
            total_size_mb=Sum('file_size_bytes') / (1024 * 1024)
        ).order_by('-photo_count')[:10]  # Top 10
        
        return Response({
            'overview': {
                'total_photos': stats['total_photos'] or 0,
                'total_size_mb': round(stats['total_size_mb'] or 0, 2),
                'completed_uploads': stats['completed_uploads'] or 0,
                'failed_uploads': stats['failed_uploads'] or 0,
                'photos_with_gps': stats['photos_with_gps'] or 0,
                'avg_file_size_mb': round(stats['avg_file_size_mb'] or 0, 2),
                'success_rate': round(
                    (stats['completed_uploads'] / stats['total_photos'] * 100) 
                    if stats['total_photos'] > 0 else 0, 1
                ),
                'gps_rate': round(
                    (stats['photos_with_gps'] / stats['total_photos'] * 100) 
                    if stats['total_photos'] > 0 else 0, 1
                )
            },
            'by_status': list(status_stats),
            'by_construction': list(construction_stats),
            'by_user': list(user_stats)
        })