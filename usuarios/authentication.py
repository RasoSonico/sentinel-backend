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
            
            # Paso 3: Debugging avanzado de la clave RSA
            logger.info("🔐 RSA KEY DEBUGGING:")
            
            try:
                # Método 1: Usando PyJWT
                logger.info("  🔄 Method 1: PyJWT RSAAlgorithm.from_jwk")
                rsa_key_pyjwt = jwt.algorithms.RSAAlgorithm.from_jwk(target_jwk)
                logger.info(f"  ✅ PyJWT key created: {type(rsa_key_pyjwt)}")
                
                # Método 2: Manual usando cryptography
                logger.info("  🔄 Method 2: Manual cryptography")
                from cryptography.hazmat.primitives import serialization
                from cryptography.hazmat.primitives.asymmetric import rsa
                
                # Extraer componentes de la clave
                n = base64.urlsafe_b64decode(target_jwk['n'] + '==')
                e = base64.urlsafe_b64decode(target_jwk['e'] + '==')
                
                # Convertir a enteros
                n_int = int.from_bytes(n, 'big')
                e_int = int.from_bytes(e, 'big')
                
                logger.info(f"  📊 n length: {len(n)} bytes")
                logger.info(f"  📊 e length: {len(e)} bytes") 
                logger.info(f"  📊 n_int: {str(n_int)[:50]}...")
                logger.info(f"  📊 e_int: {e_int}")
                
                # Crear clave pública
                public_numbers = rsa.RSAPublicNumbers(e_int, n_int)
                rsa_key_manual = public_numbers.public_key()
                logger.info(f"  ✅ Manual key created: {type(rsa_key_manual)}")
                
                # Comparar claves
                logger.info("  🔍 Comparing keys...")
                key1_pem = rsa_key_pyjwt.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                key2_pem = rsa_key_manual.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
                
                if key1_pem == key2_pem:
                    logger.info("  ✅ Keys are identical!")
                else:
                    logger.error("  ❌ Keys are different!")
                    logger.info(f"  🔍 PyJWT PEM: {key1_pem.decode()[:200]}...")
                    logger.info(f"  🔍 Manual PEM: {key2_pem.decode()[:200]}...")
                
            except Exception as key_error:
                logger.error(f"  ❌ Key creation error: {str(key_error)}")
                raise AuthenticationFailed(f'Cannot create RSA key: {str(key_error)}')
            
            # Paso 4: Debugging de verificación de firma
            logger.info("🔐 SIGNATURE VERIFICATION DEBUGGING:")
            
            # Estrategia A: Verificación paso a paso
            try:
                logger.info("  🔄 Strategy A: Step by step verification")
                
                # A1: Solo verificar que no está mal formado
                logger.info("    🔄 A1: Basic JWT structure")
                parts = token.split('.')
                if len(parts) != 3:
                    raise Exception("Invalid JWT structure")
                logger.info("    ✅ A1: JWT structure OK")
                
                # A2: Decodificar componentes
                logger.info("    🔄 A2: Decode components")
                header_decoded = json.loads(base64.urlsafe_b64decode(parts[0] + '=='))
                payload_decoded = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
                signature_bytes = base64.urlsafe_b64decode(parts[2] + '==')
                
                logger.info(f"    📝 Header: {header_decoded}")
                logger.info(f"    📦 Payload issuer: {payload_decoded.get('iss')}")
                logger.info(f"    🔏 Signature length: {len(signature_bytes)} bytes")
                logger.info("    ✅ A2: Components decoded OK")
                
                # A3: Verificar con diferentes opciones
                verification_options = [
                    # Opción 1: Completa
                    {
                        "audience": unverified_payload.get('aud'),
                        "issuer": unverified_payload.get('iss'),
                        "algorithms": [header.get('alg', 'RS256')],
                        "options": {"verify_exp": True}
                    },
                    # Opción 2: Sin audiencia
                    {
                        "audience": None,
                        "issuer": unverified_payload.get('iss'),
                        "algorithms": [header.get('alg', 'RS256')],
                        "options": {"verify_exp": True, "verify_aud": False}
                    },
                    # Opción 3: Solo firma
                    {
                        "audience": None,
                        "issuer": None,
                        "algorithms": [header.get('alg', 'RS256')],
                        "options": {"verify_exp": False, "verify_aud": False, "verify_iss": False}
                    },
                    # Opción 4: Diferentes issuers
                    {
                        "audience": unverified_payload.get('aud'),
                        "issuer": f"https://login.microsoftonline.com/{token_tenant_id}/v2.0",
                        "algorithms": [header.get('alg', 'RS256')],
                        "options": {"verify_exp": True}
                    }
                ]
                
                verified_payload = None
                successful_option = None
                
                for i, option in enumerate(verification_options):
                    try:
                        logger.info(f"    🔄 A3.{i+1}: Testing option {i+1}")
                        logger.info(f"      🎯 Audience: {option['audience']}")
                        logger.info(f"      🏢 Issuer: {option['issuer']}")
                        logger.info(f"      🔧 Options: {option['options']}")
                        
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
                        logger.info(f"    ✅ A3.{i+1}: SUCCESS!")
                        break
                        
                    except jwt.InvalidSignatureError as sig_err:
                        logger.error(f"    ❌ A3.{i+1}: Signature error: {str(sig_err)}")
                    except jwt.InvalidTokenError as token_err:
                        logger.error(f"    ❌ A3.{i+1}: Token error: {str(token_err)}")
                    except Exception as other_err:
                        logger.error(f"    ❌ A3.{i+1}: Other error: {str(other_err)}")
                
                if verified_payload:
                    logger.info(f"🎉 SIGNATURE VERIFICATION SUCCESSFUL with option {successful_option}!")
                else:
                    raise Exception("All verification options failed")
                    
            except Exception as verification_error:
                logger.error(f"❌ SIGNATURE VERIFICATION FAILED: {str(verification_error)}")
                
                # Fallback solo para desarrollo
                if settings.DEBUG:
                    logger.warning("⚠️ DEVELOPMENT: Using unverified payload")
                    verified_payload = unverified_payload
                else:
                    raise AuthenticationFailed('Signature verification failed')
            
            # Paso 5: Extraer y crear usuario
            oid = verified_payload.get('oid')
            email = verified_payload.get('email') or verified_payload.get('unique_name')
            
            if not oid:
                raise AuthenticationFailed('Missing user ID')
            
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
            
            logger.info(f"🎉 Authentication successful for: {user.username}")
            return (user, token)
            
        except AuthenticationFailed:
            raise
        except Exception as e:
            logger.error(f"💥 Authentication failed: {str(e)}")
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        return 'Bearer'