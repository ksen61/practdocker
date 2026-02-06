# 🆕 Фильтры
import django_filters
from .models import Department, DocumentRouteTemplate

class DepartmentFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    
    class Meta:
        model = Department
        fields = ['name']

class RouteFilter(django_filters.FilterSet):
    document_type = django_filters.NumberFilter(field_name='document_type__id')
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = DocumentRouteTemplate
        fields = ['document_type', 'is_active']
