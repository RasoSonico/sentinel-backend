# cronograma/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScheduleViewSet, ActivityViewSet, CriticalPathViewSet

router = DefaultRouter()
router.register(r'schedules', ScheduleViewSet)
router.register(r'activities', ActivityViewSet)
router.register(r'critical-path', CriticalPathViewSet)

urlpatterns = [
    path('', include(router.urls)),
]