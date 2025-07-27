from django.urls import path
from . import views

app_name = 'recursos'

urlpatterns = [
    # URLs para Catálogos (dropdowns)
    path('machinery-catalog/', views.MachineryCatalogList.as_view(), name='machinery-catalog-list'),
    path('workforce-catalog/', views.WorkForceCatalogList.as_view(), name='workforce-catalog-list'),
    
    # URLs para Registros de Maquinaria
    path('machinery/', views.MachineryList.as_view(), name='machinery-list'),
    path('machinery/<int:pk>/', views.MachineryDetail.as_view(), name='machinery-detail'),
    
    # URLs para Registros de Fuerza Laboral
    path('workforce/', views.WorkForceList.as_view(), name='workforce-list'),
    path('workforce/<int:pk>/', views.WorkForceDetail.as_view(), name='workforce-detail'),
]