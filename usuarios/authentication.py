import jwt
import requests
import logging
import json
import base64
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
        
        if not auth_header:
            return None
            
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        logger.info(f"🔍 Starting authentication for token: {token[:30]}...")
        
        try:
            # Paso 1: Análisis completo del token
            header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": False}
            )
            
            logger.info("📋 COMPLETE TOKEN ANALYSIS:")
            logger.info(f"  📝 Header: {json.dumps(header, indent=2)}")
            logger.info(f"  📦 Payload keys: {list(unverified_payload.keys())}")
            logger.info(f"  🎯 Issuer: {unverified_payload.get('iss')}")
            logger.info(f"  👥 Audience: {unverified_payload.get('aud')}")
            logger.info(f"  🆔 App ID: {unverified_payload.get('appid')}")
            logger.info(f"  🏢 Tenant: {unverified_payload.get('tid')}")
            logger.info(f"  ⏰ Issued at: {unverified_payload.get('iat')}")
            logger.info(f"  ⏰ Expires: {unverified_payload.get('exp')}")
            logger.info(f"  🔑 Algorithm: {header.get('alg')}")
            logger.info(f"  🆔 Key ID: {header.get('kid')}")
            
            # Validaciones básicas
            token_tenant_id = unverified_payload.get('tid')
            if not token_tenant_id or token_tenant_id != settings.AZURE_TENANT_ID:
                raise AuthenticationFailed('Invalid tenant')
            
            # Verificar que el token viene de nuestra aplicación
            token_app_id = unverified_payload.get('appid')
            if not token_app_id or token_app_id != settings.AZURE_CLIENT_ID:
                logger.error(f"❌ Token from wrong application. Expected: {settings.AZURE_CLIENT_ID}, Got: {token_app_id}")
                raise AuthenticationFailed('Token from unauthorized application')
            
            current_time = int(datetime.now().timestamp())
            token_exp = unverified_payload.get('exp', 0)
            if token_exp < current_time:
                raise AuthenticationFailed('Token expired')
            
            # Paso 2: Obtener y analizar JWKS
            jwks_uri = f'https://login.microsoftonline.com/{token_tenant_id}/discovery/v2.0/keys'
            logger.info(f"🔑 Fetching JWKS from: {jwks_uri}")
            
            jwks_response = requests.get(jwks_uri, timeout=15)
            jwks_response.raise_for_status()
            jwks = jwks_response.json()
            
            logger.info(f"🔑 JWKS Analysis:")
            logger.info(f"  📊 Total keys: {len(jwks.get('keys', []))}")
            
            # Encontrar la clave específica
            kid = header.get('kid')
            target_jwk = None
            
            for i, jwk in enumerate(jwks.get('keys', [])):
                jwk_kid = jwk.get('kid')
                logger.info(f"  🗝️  Key {i}: kid={jwk_kid}, kty={jwk.get('kty')}, use={jwk.get('use')}, alg={jwk.get('alg')}")
                
                if jwk_kid == kid:
                    target_jwk = jwk
                    logger.info(f"  ✅ Target key found: {json.dumps(jwk, indent=4)}")
                    break
            
            if not target_jwk:
                raise AuthenticationFailed(f'Key {kid} not found')
            
            # Paso 3: Crear clave RSA
            try:
                rsa_key_pyjwt = jwt.algorithms.RSAAlgorithm.from_jwk(target_jwk)
                logger.info(f"✅ RSA key created successfully: {type(rsa_key_pyjwt)}")
            except Exception as key_error:
                logger.error(f"❌ Key creation error: {str(key_error)}")
                raise AuthenticationFailed(f'Cannot create RSA key: {str(key_error)}')
            
            # Paso 4: Verificación de firma con múltiples opciones
            logger.info("🔐 SIGNATURE VERIFICATION:")
            
            # Definir audiences válidos
            token_audience = unverified_payload.get('aud')
            valid_audiences = [
                f"api://{settings.AZURE_CLIENT_ID}",  # Formato api://client-id
                "api://sentinel-auth",                # Tu URI personalizada
                settings.AZURE_CLIENT_ID,             # Solo el client ID
                "00000003-0000-0000-c000-000000000000" # Microsoft Graph (temporal)
            ]
            
            logger.info(f"  🎯 Token audience: {token_audience}")
            logger.info(f"  ✅ Valid audiences: {valid_audiences}")
            
            # Verificar si el audience es válido
            if token_audience not in valid_audiences:
                logger.warning(f"⚠️ Unexpected audience: {token_audience}")
                # En producción, podrías querer rechazar el token aquí
                # Para desarrollo, continuamos
            
            # Definir issuers válidos
            token_issuer = unverified_payload.get('iss')
            valid_issuers = [
                f"https://sts.windows.net/{token_tenant_id}/",
                f"https://login.microsoftonline.com/{token_tenant_id}/v2.0"
            ]
            
            logger.info(f"  🏢 Token issuer: {token_issuer}")
            logger.info(f"  ✅ Valid issuers: {valid_issuers}")
            
            # Opciones de verificación flexibles
            verification_options = [
                # Opción 1: Sin verificar audience (más permisivo)
                {
                    "audience": None,
                    "issuer": token_issuer,
                    "algorithms": [header.get('alg', 'RS256')],
                    "options": {"verify_exp": True, "verify_aud": False}
                },
                # Opción 2: Solo firma (muy permisivo)
                {
                    "audience": None,
                    "issuer": None,
                    "algorithms": [header.get('alg', 'RS256')],
                    "options": {"verify_exp": True, "verify_aud": False, "verify_iss": False}
                },
                # Opción 3: Con audience original
                {
                    "audience": token_audience,
                    "issuer": token_issuer,
                    "algorithms": [header.get('alg', 'RS256')],
                    "options": {"verify_exp": True}
                },
                # Opción 4: Con issuer v2.0
                {
                    "audience": None,
                    "issuer": f"https://login.microsoftonline.com/{token_tenant_id}/v2.0",
                    "algorithms": [header.get('alg', 'RS256')],
                    "options": {"verify_exp": True, "verify_aud": False}
                }
            ]
            
            verified_payload = None
            successful_option = None
            
            for i, option in enumerate(verification_options):
                try:
                    logger.info(f"  🔄 Testing option {i+1}")
                    logger.info(f"    🎯 Audience: {option['audience']}")
                    logger.info(f"    🏢 Issuer: {option['issuer']}")
                    logger.info(f"    🔧 Options: {option['options']}")
                    
                    if option['audience'] and option['issuer']:
                        test_payload = jwt.decode(
                            token,
                            rsa_key_pyjwt,
                            algorithms=option['algorithms'],
                            audience=option['audience'],
                            issuer=option['issuer'],
                            options=option['options']
                        )
                    elif option['issuer']:
                        test_payload = jwt.decode(
                            token,
                            rsa_key_pyjwt,
                            algorithms=option['algorithms'],
                            issuer=option['issuer'],
                            options=option['options']
                        )
                    else:
                        test_payload = jwt.decode(
                            token,
                            rsa_key_pyjwt,
                            algorithms=option['algorithms'],
                            options=option['options']
                        )
                    
                    verified_payload = test_payload
                    successful_option = i + 1
                    logger.info(f"  ✅ SUCCESS with option {i+1}!")
                    break
                    
                except jwt.InvalidSignatureError as sig_err:
                    logger.error(f"    ❌ Option {i+1} signature error: {str(sig_err)}")
                except jwt.InvalidTokenError as token_err:
                    logger.error(f"    ❌ Option {i+1} token error: {str(token_err)}")
                except Exception as other_err:
                    logger.error(f"    ❌ Option {i+1} other error: {str(other_err)}")
            
            if not verified_payload:
                logger.error("❌ ALL VERIFICATION OPTIONS FAILED")
                
                # Solo en desarrollo, usar payload no verificado
                if settings.DEBUG:
                    logger.warning("⚠️ DEVELOPMENT MODE: Using unverified payload")
                    verified_payload = unverified_payload
                else:
                    raise AuthenticationFailed('Signature verification failed')
            else:
                logger.info(f"🎉 Token verified successfully with option {successful_option}")
            
            # Paso 5: Extraer información del usuario
            oid = verified_payload.get('oid')
            email = verified_payload.get('email') or verified_payload.get('unique_name')
            
            if not oid:
                raise AuthenticationFailed('Missing user ID in token')
            
            logger.info(f"👤 Creating/updating user - OID: {oid}, Email: {email}")
            
            # Crear o actualizar usuario
            user, created = User.objects.get_or_create(
                outter_id=oid,
                defaults={
                    'username': email.split('@')[0] if email and '@' in email else oid,
                    'email': email or '',
                    'first_name': verified_payload.get('given_name', ''),
                    'last_name': verified_payload.get('family_name', ''),
                    'azure_tenant': token_tenant_id
                }
            )
            
            # Actualizar información si el usuario ya existía
            if not created:
                user.email = email or user.email
                user.first_name = verified_payload.get('given_name', '') or user.first_name
                user.last_name = verified_payload.get('family_name', '') or user.last_name
                user.save()
            
            logger.info(f"🎉 Authentication successful for user: {user.username} ({'created' if created else 'updated'})")
            return (user, token)
            
        except AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f"💥 Authentication failed with unexpected error: {str(e)}")
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'