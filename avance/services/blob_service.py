"""
Servicio para gestión de Azure Blob Storage
Implementa las mejores prácticas de Microsoft para manejo de blobs
"""

import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

from azure.storage.blob import (
    BlobServiceClient, 
    BlobSasPermissions, 
    generate_blob_sas,
    ContentSettings
)
from azure.core.exceptions import AzureError
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AzureBlobService:
    """
    Servicio para interactuar con Azure Blob Storage
    """
    
    def __init__(self):
        self.connection_string = settings.AZURE_BLOB_STORAGE_CONNECTION_STRING
        self.container_name = settings.AZURE_PHOTOS_CONTAINER
        self.account_name = settings.AZURE_STORAGE_ACCOUNT_NAME
        
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
            self.container_client = self.blob_service_client.get_container_client(
                self.container_name
            )
        except Exception as e:
            logger.error(f"Error inicializando Azure Blob Service: {str(e)}")
            raise
    
    def generate_blob_path(self, obra_id: int, avance_id: int, filename: str) -> str:
        """
        Genera la ruta del blob siguiendo la estructura definida:
        /{hash3}-obra-{obra_id}/{año}/{mes}/{timestamp}_{avance_id}_{filename}
        """
        now = timezone.now()
        
        # Generar hash de 3 caracteres basado en obra_id
        hash_input = f"obra-{obra_id}".encode('utf-8')
        hash_3 = hashlib.md5(hash_input).hexdigest()[:3]
        
        # Generar timestamp
        timestamp = int(now.timestamp())
        
        # Limpiar filename de caracteres especiales
        safe_filename = self._sanitize_filename(filename)
        
        # Construir la ruta con año y mes separados
        year = now.strftime("%Y")
        month = now.strftime("%m")
        folder = f"{hash_3}-obra-{obra_id}/{year}/{month}"
        blob_name = f"{timestamp}_{avance_id}_{safe_filename}"
        
        return f"{folder}/{blob_name}"
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Limpia el nombre del archivo de caracteres especiales
        """
        # Mantener solo caracteres alfanuméricos, puntos, guiones y guiones bajos
        import re
        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)
        return safe_name
    
    def generate_upload_sas_token(
        self, 
        blob_path: str, 
        expiry_hours: int = 1
    ) -> Dict[str, Any]:
        """
        Genera un SAS token para subida directa desde el cliente
        """
        try:
            # Definir permisos para escritura
            sas_permissions = BlobSasPermissions(
                read=False,
                write=True,
                delete=False,
                create=True
            )
            
            # Definir expiración
            expiry_time = timezone.now() + timedelta(hours=expiry_hours)
            
            # Generar el SAS token
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_path,
                account_key=self._get_account_key(),
                permission=sas_permissions,
                expiry=expiry_time,
                start=timezone.now(),  # Agregar tiempo de inicio
                protocol='https'  # Forzar HTTPS
            )
            
            # Construir la URL completa
            blob_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_path}"
            upload_url = f"{blob_url}?{sas_token}"
            
            # Logging detallado para debug
            logger.info(f"🔍 SAS Token Debug:")
            logger.info(f"   Account: {self.account_name}")
            logger.info(f"   Container: {self.container_name}")
            logger.info(f"   Blob path: {blob_path}")
            logger.info(f"   SAS token length: {len(sas_token)}")
            logger.info(f"   SAS token preview: {sas_token[:50]}...")
            logger.info(f"   Upload URL: {upload_url}")
            logger.info(f"   URL contains ?sv=: {'?sv=' in upload_url}")
            logger.info(f"   URL contains &sig=: {'&sig=' in upload_url}")
            
            return {
                'upload_url': upload_url,
                'blob_path': blob_path,
                'blob_url': blob_url,
                'sas_token': sas_token,
                'expires_at': expiry_time.isoformat(),
                'container': self.container_name
            }
            
        except Exception as e:
            logger.error(f"Error generando SAS token: {str(e)}")
            raise
    
    def generate_read_sas_token(
        self, 
        blob_path: str, 
        expiry_hours: int = 24
    ) -> str:
        """
        Genera un SAS token para lectura de un blob
        """
        try:
            sas_permissions = BlobSasPermissions(
                read=True,
                write=False,
                delete=False
            )
            
            expiry_time = timezone.now() + timedelta(hours=expiry_hours)
            
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_path,
                account_key=self._get_account_key(),
                permission=sas_permissions,
                expiry=expiry_time
            )
            
            blob_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_path}"
            return f"{blob_url}?{sas_token}"
            
        except Exception as e:
            logger.error(f"Error generando SAS token de lectura: {str(e)}")
            raise
    
    def upload_blob(
        self, 
        blob_path: str, 
        data: bytes, 
        content_type: str = 'image/jpeg',
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Sube un blob directamente desde el backend
        """
        try:
            content_settings = ContentSettings(content_type=content_type)
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.upload_blob(
                data,
                content_settings=content_settings,
                metadata=metadata or {},
                overwrite=True
            )
            
            return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_path}"
            
        except Exception as e:
            logger.error(f"Error subiendo blob: {str(e)}")
            raise
    
    def delete_blob(self, blob_path: str) -> bool:
        """
        Elimina un blob
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            blob_client.delete_blob()
            return True
            
        except Exception as e:
            logger.error(f"Error eliminando blob {blob_path}: {str(e)}")
            return False
    
    def blob_exists(self, blob_path: str) -> bool:
        """
        Verifica si un blob existe
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Error verificando existencia del blob {blob_path}: {str(e)}")
            return False
    
    def get_blob_properties(self, blob_path: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene las propiedades de un blob
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            properties = blob_client.get_blob_properties()
            
            return {
                'size': properties.size,
                'content_type': properties.content_settings.content_type,
                'last_modified': properties.last_modified,
                'etag': properties.etag,
                'metadata': properties.metadata
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo propiedades del blob {blob_path}: {str(e)}")
            return None
    
    def _get_account_key(self) -> str:
        """
        Extrae la account key del connection string
        """
        try:
            # Parse del connection string para extraer AccountKey
            parts = self.connection_string.split(';')
            for part in parts:
                part = part.strip()  # Quitar espacios
                if part.startswith('AccountKey='):
                    account_key = part.split('=', 1)[1]
                    logger.info(f"Account key extraída exitosamente (longitud: {len(account_key)})")
                    return account_key
            
            # Logging adicional para debug
            logger.error(f"Connection string parts: {parts}")
            raise ValueError("AccountKey no encontrada en connection string")
            
        except Exception as e:
            logger.error(f"Error extrayendo account key: {str(e)}")
            raise


# Instancia global del servicio
blob_service = AzureBlobService()