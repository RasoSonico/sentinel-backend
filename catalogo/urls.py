from django.urls import path
from . import views

app_name = 'catalogo'

urlpatterns = [
    # URLs para Catálogo
    path('catalog/', views.CatalogList.as_view(), name='catalog-list'),
    path('catalog/<int:pk>/', views.CatalogDetail.as_view(), name='catalog-detail'),
    
    # URLs para Partida
    path('workitem/', views.WorkItemList.as_view(), name='workitem-list'),
    path('workitem/<int:pk>/', views.WorkItemDetail.as_view(), name='workitem-detail'),
    
    # URLs para Concepto
    path('concept/', views.ConceptList.as_view(), name='concept-list'),
    path('concept/<int:pk>/', views.ConceptDetail.as_view(), name='concept-detail'),
]