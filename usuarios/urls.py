from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'roles', views.RoleViewSet)
router.register(r'user-roles', views.UserRoleViewSet)

app_name = 'usuarios'

urlpatterns = [
    path('', include(router.urls)),
    path('me/', views.UserViewSet.as_view({'get': 'me'}), name='me')
]