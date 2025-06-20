from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'roles', views.UserRoleViewSet)

app_name = 'usuarios'

urlpatterns = [
    path('', include(router.urls)),
    path('login/', views.UserViewSet.as_view({'post': 'login'}), name='login'),
    path('azure-login-url/', views.UserViewSet.as_view({'get': 'azure_login_url'}), name='azure_login_url'),
    path('azure-token/', views.UserViewSet.as_view({'post': 'azure_token'}), name='azure_token'),
]