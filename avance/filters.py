# avance/filters.py
import django_filters
from .models import Estimation, EstimationDetail, CommitmentTracking

class EstimationFilter(django_filters.FilterSet):
    construction = django_filters.NumberFilter(field_name='construction__id')
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_planned = django_filters.BooleanFilter()
    based_on_schedule = django_filters.BooleanFilter()
    status = django_filters.CharFilter()
    period_start_after = django_filters.DateFilter(field_name='period_start', lookup_expr='gte')
    period_start_before = django_filters.DateFilter(field_name='period_start', lookup_expr='lte')
    period_end_after = django_filters.DateFilter(field_name='period_end', lookup_expr='gte')
    period_end_before = django_filters.DateFilter(field_name='period_end', lookup_expr='lte')
    
    class Meta:
        model = Estimation
        fields = ['construction', 'name', 'is_planned', 'based_on_schedule', 'status']