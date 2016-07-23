from django.db.models import Q

import django_filters

from cookies.models import *


class ResourceFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(name='name', lookup_type='icontains')
    content = django_filters.CharFilter(name='indexable_content',
                                        lookup_type='icontains')

    class Meta:
        model = Resource
        fields = ['name', 'entity_type', 'content', 'created_by']


class CollectionFilter(django_filters.FilterSet):
    class Meta:
        model = Collection
        fields = ['name', 'created_by']


class UserJobFilter(django_filters.FilterSet):
    complete = django_filters.MethodFilter()

    def filter_complete(self, queryset, value):
        return queryset.filter(~Q(result=''))

    class Meta:
        model = UserJob
        fields = ['result_id', 'complete', 'created_by']
