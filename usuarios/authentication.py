import jwt
import requests
import logging
from datetime import datetime
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User

logger = logging.getLogger(__name__)

class AzureExternalIDAuthentication(authentication.BaseAuthentication):
    """
    Autenticación personalizada para validar tokens de Azure External ID
    """
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        logger.info(f"🔍 Starting authentication for token: {token[:30]}...")
        
        try:
            # Paso 1: Decodificar token sin verificar para análisis inicial
            header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            
            logger.info(f"📋 Token info - Tenant: {unverified_payload.get('tid')}, User: {unverified_payload.get('unique_name')}")
            logger.info(f"🎯 Audience: {unverified_payload.get('aud')}")
            logger.info(f"🏢 Issuer: {unverified_payload.get('iss')}")
            logger.info(f"🆔 App ID: {unverified_payload.get('appid')}")
            
            # Paso 2: Validaciones básicas
            token_tenant_id = unverified_payload.get('tid')
            if not token_tenant_id or token_tenant_id != settings.AZURE_TENANT_ID:
                raise AuthenticationFailed('Invalid tenant')
            
            current_time = int(datetime.now().timestamp())
            token_exp = unverified_payload.get('exp', 0)
            if token_exp < current_time:
                raise AuthenticationFailed('Token expired')
            
            # Paso 3: Obtener claves públicas de Azure AD
            jwks_uri = f'https://login.microsoftonline.com/{token_tenant_id}/discovery/v2.0/keys'
            jwks_response = requests.get(jwks_uri, timeout=15)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
            
            # Paso 4: Encontrar la clave correcta
            kid = header.get('kid')
            target_jwk = None
            
            for jwk in jwks.get('keys', []):
                if jwk.get('kid') == kid:
                    target_jwk = jwk
                    break
            
            if not target_jwk:
                raise AuthenticationFailed(f'Key {kid} not found in JWKS')
            
            # Paso 5: Crear clave RSA para verificación
            try:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(target_jwk)
                logger.info(f"🔑 RSA key created successfully for kid: {kid}")
            except Exception as key_error:
                logger.error(f"❌ Failed to create RSA key: {str(key_error)}")
                raise AuthenticationFailed('Cannot create RSA key')
            
            # Paso 6: Verificar firma del token
            try:
                verified_payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=['RS256'],
                    audience=unverified_payload.get('aud'),
                    issuer=unverified_payload.get('iss'),
                    options={"verify_exp": True}
                )
                logger.info("✅ Token signature verified successfully")
                
            except jwt.InvalidTokenError as e:
                logger.error(f"❌ Token verification failed: {str(e)}")
                
                # Fallback para desarrollo
                if settings.DEBUG:
                    logger.warning("⚠️ Using unverified payload in DEBUG mode")
                    verified_payload = unverified_payload
                else:
                    raise AuthenticationFailed('Token verification failed')
            
            # Paso 7: Extraer información del usuario y gestionar duplicados
            oid = verified_payload.get('oid')
            email = verified_payload.get('email') or verified_payload.get('unique_name')
            
            if not oid:
                raise AuthenticationFailed('Missing user ID (oid)')
            
            # Verificar si existe usuario con mismo username pero sin outter_id
            username_from_email = email.split('@')[0] if email and '@' in email else oid
            existing_user = User.objects.filter(
                username=username_from_email,
                outter_id__isnull=True
            ).first()
            
            if existing_user:
                # Vincular usuario existente con Azure AD
                logger.info(f"🔗 Linking existing user {existing_user.username} to Azure AD")
                existing_user.outter_id = oid
                existing_user.azure_tenant = token_tenant_id
                existing_user.email = email or existing_user.email
                existing_user.first_name = verified_payload.get('given_name', '') or existing_user.first_name
                existing_user.last_name = verified_payload.get('family_name', '') or existing_user.last_name
                existing_user.save()
                user = existing_user
                created = False
            else:
                # Crear nuevo usuario o obtener existente por outter_id
                user, created = User.objects.get_or_create(
                    outter_id=oid,
                    defaults={
                        'username': username_from_email,
                        'email': email or '',
                        'first_name': verified_payload.get('given_name', ''),
                        'last_name': verified_payload.get('family_name', ''),
                        'azure_tenant': token_tenant_id
                    }
                )
            
            action = "created" if created else "retrieved"
            logger.info(f"🎉 User {action}: {user.username} (ID: {user.id})")
            return (user, token)
            
        except AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f"💥 Authentication failed: {str(e)}")
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'