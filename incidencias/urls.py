from django.urls import path
from . import views

app_name = 'incidencias'

urlpatterns = [
    # URLs para Catálogos (dropdowns)
    path('incident-types/', views.IncidentTypeListCreate.as_view(), name='incident-type-list'),
    path('incident-types/<int:pk>/', views.IncidentTypeDetail.as_view(), name='incident-type-detail'),
    
    path('incident-classifications/', views.IncidentClassificationListCreate.as_view(), name='incident-classification-list'),
    path('incident-classifications/<int:pk>/', views.IncidentClassificationDetail.as_view(), name='incident-classification-detail'),
    
    # URLs para Incidencias
    path('incidents/', views.IncidentListCreate.as_view(), name='incident-list'),
    path('incidents/<int:pk>/', views.IncidentDetail.as_view(), name='incident-detail'),
]