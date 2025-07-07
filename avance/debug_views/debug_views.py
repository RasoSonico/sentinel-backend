"""
Vista temporal para debug del módulo de Azure Blob Storage
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class BlobDebugAPIView(APIView):
    """
    Vista temporal para diagnosticar problemas con Azure Blob Storage
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        """
        Diagnóstico de configuración de Azure Blob Storage
        """
        try:
            from ..services.blob_service import blob_service
            
            # Verificar configuración
            config_check = {
                'account_name': blob_service.account_name,
                'container_name': blob_service.container_name,
                'connection_string_length': len(blob_service.connection_string) if blob_service.connection_string else 0,
                'has_account_key': bool(blob_service._get_account_key()),
            }
            
            # Verificar que el account key se extraiga correctamente
            try:
                account_key = blob_service._get_account_key()
                config_check['account_key_length'] = len(account_key)
                config_check['account_key_prefix'] = account_key[:10] + '...' if len(account_key) > 10 else account_key
            except Exception as e:
                config_check['account_key_error'] = str(e)
            
            # Intentar generar un SAS token de prueba
            try:
                test_blob_path = "debug/test_blob.txt"
                sas_data = blob_service.generate_upload_sas_token(test_blob_path, expiry_hours=1)
                
                config_check['sas_generation'] = 'SUCCESS'
                config_check['test_upload_url'] = sas_data.get('upload_url', '')
                config_check['test_sas_token'] = sas_data.get('sas_token', '')
                config_check['sas_token_length'] = len(sas_data.get('sas_token', ''))
                
                # Verificar si la URL contiene parámetros SAS
                upload_url = sas_data.get('upload_url', '')
                config_check['url_has_sv'] = '?sv=' in upload_url
                config_check['url_has_sig'] = '&sig=' in upload_url or '?sig=' in upload_url
                
            except Exception as e:
                config_check['sas_generation'] = 'ERROR'
                config_check['sas_error'] = str(e)
                logger.error(f"Error generando SAS de prueba: {str(e)}")
            
            return Response({
                'status': 'debug_info',
                'config': config_check,
                'settings': {
                    'AZURE_STORAGE_ACCOUNT_NAME': getattr(settings, 'AZURE_STORAGE_ACCOUNT_NAME', 'NOT_SET'),
                    'AZURE_PHOTOS_CONTAINER': getattr(settings, 'AZURE_PHOTOS_CONTAINER', 'NOT_SET'),
                    'connection_string_set': bool(getattr(settings, 'AZURE_BLOB_STORAGE_CONNECTION_STRING', '')),
                }
            })
            
        except Exception as e:
            logger.error(f"Error en debug: {str(e)}")
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)