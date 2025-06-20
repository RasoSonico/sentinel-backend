# cronograma/filters.py
import django_filters
from .models import Schedule, Activity

class ScheduleFilter(django_filters.FilterSet):
    construction = django_filters.NumberFilter(field_name='construction__id')  # Cambiado de UUIDFilter a NumberFilter
    name = django_filters.CharFilter(lookup_expr='icontains')
    is_active = django_filters.BooleanFilter()
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    class Meta:
        model = Schedule
        fields = ['construction', 'name', 'is_active']


class ActivityFilter(django_filters.FilterSet):
    schedule = django_filters.NumberFilter(field_name='schedule__id')  # Cambiado de UUIDFilter a NumberFilter
    name = django_filters.CharFilter(lookup_expr='icontains')
    start_date_after = django_filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_before = django_filters.DateFilter(field_name='start_date', lookup_expr='lte')
    end_date_after = django_filters.DateFilter(field_name='end_date', lookup_expr='gte')
    end_date_before = django_filters.DateFilter(field_name='end_date', lookup_expr='lte')
    
    class Meta:
        model = Activity
        fields = ['schedule', 'name']