from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'constructions', views.ConstructionViewSet)
router.register(r'user-constructions', views.UserConstructionViewSet)
router.register(r'changes', views.ConstructionChangeControlViewSet)

app_name = 'obra'

urlpatterns = [
    path('', include(router.urls)),
    path('constructions/my/', views.ConstructionViewSet.as_view({'get': 'my_constructions'}), name='my-constructions'),
]