import requests
import json
from django.conf import settings
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser, AllowAny
from django.contrib.auth import authenticate
from .models import User, UserRole
from .serializers import UserSerializer, UserRoleSerializer
from .permissions import HasRole, IsSameUserOrAdmin
from core import settings
from rest_framework_simplejwt.tokens import RefreshToken


if settings.DEBUG:
    from core.permissions_dev import AllowAnyInDev
    PermissionClass = AllowAnyInDev
    AdminPermissionClass = AllowAnyInDev
else:
    from .permissions import IsSameUserOrAdmin
    PermissionClass = IsSameUserOrAdmin
    AdminPermissionClass = IsAdminUser

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated] #Pruebas
    
    # def get_permissions(self):
    #     if settings.DEBUG:
    #         return [AllowAnyInDev()]
        
    #     if self.action in ['create', 'azure_login', 'azure_token']:
    #         return [AllowAny()]
    #     return super().get_permissions()
        
    #     # if self.action == 'create':
    #     #     return [IsAdminUser()]
    #     # return super().get_permissions()
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {"error": "Se requieren nombre de usuario y contraseña"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user = authenticate(username=username, password=password)
        
        if not user:
            return Response(
                {"error": "Credenciales inválidas"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        if not user.is_active:
            return Response(
                {"error": "Usuario desactivado"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        # Generar tokens JWT
        refresh = RefreshToken.for_user(user)
        
        return Response({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "roles": [user_role.role.name for user_role in user.roles.all()],  # Solo nombres
        "refresh": str(refresh),
        "access": str(refresh.access_token)
    })
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def azure_login_url(self, request):
        """
        Devuelve la URL para iniciar el flujo de autenticación con Azure External ID
        """
        # Construir la URL de autorización de Azure
        auth_url = (
            f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/authorize?"
            f"client_id={settings.AZURE_CLIENT_ID}&"
            f"response_type=code&"
            f"redirect_uri={settings.AZURE_REDIRECT_URI}&"
            f"response_mode=query&"
            f"scope={settings.AZURE_SCOPE}&"
            f"state=12345"  # Debería ser un valor aleatorio para seguridad
        )
        return Response({"login_url": auth_url})
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def azure_token(self, request):
        """
        Intercambia el código de autorización por tokens de acceso
        """
        code = request.data.get('code')
        if not code:
            return Response({"error": "Se requiere código de autorización"}, status=400)
        
        # Intercambiar el código por tokens
        token_url = f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID}/oauth2/v2.0/token"
        payload = {
            'client_id': settings.AZURE_CLIENT_ID,
            'client_secret': settings.AZURE_CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': settings.AZURE_REDIRECT_URI,
            'scope': settings.AZURE_SCOPE
        }
        
        response = requests.post(token_url, data=payload)
        
        if response.status_code != 200:
            return Response({"error": "Error al obtener token", "details": response.text}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        token_data = response.json()
        
        # Decodificar el token para obtener información del usuario
        import jwt
        from jwt.algorithms import RSAAlgorithm
        
        # Decodificar el token sin verificar para obtener los datos básicos
        id_token = token_data.get('id_token')
        try:
            # Solo decodificamos para obtener datos, la verificación real se hace en el Authentication
            token_payload = jwt.decode(id_token, options={"verify_signature": False})
            
            # Extraer información del usuario
            oid = token_payload.get('oid') or token_payload.get('sub')
            email = token_payload.get('email') or token_payload.get('preferred_username') or ''
            first_name = token_payload.get('given_name') or ''
            last_name = token_payload.get('family_name') or ''
            
            # Buscar o crear usuario
            user, created = User.objects.get_or_create(
                outter_id=oid,
                defaults={
                    'username': email.split('@')[0] if '@' in email else oid,
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'azure_tenant': settings.AZURE_TENANT_ID
                }
            )
            
            # Generar tokens JWT para el backend
            refresh = RefreshToken.for_user(user)
            
            # Devolver datos del usuario y tokens
            return Response({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "roles": [user_role.role.name for user_role in user.roles.all()],  # Solo nombres
            "azure_token": token_data,
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        })
            
        except Exception as e:
            return Response({"error": f"Error al procesar token: {str(e)}"}, 
                          status=status.HTTP_400_BAD_REQUEST)

class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.all()
    serializer_class = UserRoleSerializer
    permission_classes = [AdminPermissionClass]
