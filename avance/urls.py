from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .photo_views.photo_views import (
    PhotoUploadAPIView,
    PhotoConfirmUploadAPIView,
    PhotoBulkUploadAPIView,
    PhotoViewSet,
    PhotoAnalyticsAPIView
)
from .debug_views.debug_views import BlobDebugAPIView
router = DefaultRouter()
router.register(r'planning', views.EstimationPlanningViewSet)
router.register(r'commitment-tracking', views.CommitmentTrackingViewSet)
router.register(r'photos', PhotoViewSet, basename='photos')

app_name = 'avance'

urlpatterns = [
    # Avance físico
    path('physical/', views.PhysicalListCreateView.as_view(), name='physical-list'),
    path('physical/<int:pk>/', views.PhysicalDetailView.as_view(), name='physical-detail'),
    path('physical/summary/', views.PhysicalProgressSummaryView.as_view(), name='physical-summary'),
    
    # Estimaciones (avance financiero)
    path('estimation/', views.EstimationListCreateView.as_view(), name='estimation-list'),
    path('estimation/<int:pk>/', views.EstimationDetailView.as_view(), name='estimation-detail'),
    path('estimation-item/', views.EstimationItemListCreateView.as_view(), name='estimation-item-list'),
    path('estimation-item/<int:pk>/', views.EstimationItemDetailView.as_view(), name='estimation-item-detail'),
    
    # Fotografías y Azure Blob Storage
    path('photos/upload/', PhotoUploadAPIView.as_view(), name='photo-upload'),
    path('photos/confirm-upload/', PhotoConfirmUploadAPIView.as_view(), name='photo-confirm-upload'),
    path('photos/bulk-upload/', PhotoBulkUploadAPIView.as_view(), name='photo-bulk-upload'),
    path('photos/analytics/', PhotoAnalyticsAPIView.as_view(), name='photo-analytics'),
    path('photos/debug/', BlobDebugAPIView.as_view(), name='photo-debug'),
    
    # Dashboard
    path('dashboard/', views.ProgressDashboardView.as_view(), name='progress-dashboard'),
    path('', include(router.urls)),
]