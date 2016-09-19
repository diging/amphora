from django.db.models import Q

import django_filters

from cookies.models import *


class ResourceFilter(django_filters.FilterSet):
    def __init__(self, *args, **kwargs):
        super(ResourceFilter, self).__init__(*args, **kwargs)

    name = django_filters.MethodFilter(action='lookup_name_in_parts')
    content = django_filters.CharFilter(name='indexable_content',
                                        lookup_type='icontains')


    def lookup_name_in_parts(self, queryset, value):
        q = Q()
        for part in value.split():
            q &= Q(name__icontains=part)
        return queryset.filter(q)

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
