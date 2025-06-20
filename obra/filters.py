# obra/filters.py
import django_filters
from .models import Construction, UserConstruction

class UserConstructionFilter(django_filters.FilterSet):
    role_name = django_filters.CharFilter(field_name='role__name')
    
    class Meta:
        model = UserConstruction
        fields = {
            'user': ['exact'],
            'construction': ['exact'],
            'role': ['exact'],
            'is_active': ['exact'],
        }