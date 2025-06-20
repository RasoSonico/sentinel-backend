from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'planning', views.EstimationPlanningViewSet)
router.register(r'commitment-tracking', views.CommitmentTrackingViewSet)

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
    
    # Dashboard
    path('dashboard/', views.ProgressDashboardView.as_view(), name='progress-dashboard'),
    path('', include(router.urls)),
]