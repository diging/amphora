import django_filters

from cookies.models import *


class ResourceFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(name='name', lookup_type='icontains')
    content = django_filters.CharFilter(name='indexable_content',
                                        lookup_type='icontains')
    

    class Meta:
        model = Resource
        fields = ['name', 'entity_type', 'content']
