from django.db.models import Q, Count

import django_filters

from cookies.models import *


class ConceptEntityFilter(django_filters.FilterSet):
    name = django_filters.MethodFilter(action='lookup_name_in_parts')
    entity_type = django_filters.ModelChoiceFilter(queryset=Type.objects.annotate(num_instances=Count('conceptentity')).filter(num_instances__gt=0))


    def lookup_name_in_parts(self, queryset, value):
        q = Q()
        for part in value.split():
            q &= Q(name__icontains=part)
        return queryset.filter(q)

    class Meta:
        model = ConceptEntity
        fields = ['name', 'uri', 'entity_type', 'created_by',]
        order_by = (
            ('name', 'Name (ascending)'),
            ('-name', 'Name (descending)'),
            ('entity_type', 'Type (ascending)'),
            ('-entity_type', 'Type (descending)'),
        )



class ResourceFilter(django_filters.FilterSet):
    name = django_filters.MethodFilter(action='lookup_name_in_parts')
    content = django_filters.CharFilter(name='indexable_content',
                                        lookup_type='icontains')

    entity_type = django_filters.ModelChoiceFilter(
        queryset=Type.objects.annotate(num_instances=Count('resource'))\
                             .filter(num_instances__gt=0)
    )

    tag = django_filters.MethodFilter(action='filter_tag')

    def filter_tag(self, queryset, value):
        return queryset.filter(tags__tag__id=value)

    def lookup_name_in_parts(self, queryset, value):
        q = Q()
        for part in value.split():
            q &= Q(name__icontains=part)
        return queryset.filter(q)

    class Meta:
        model = Resource
        fields = ['name', 'uri', 'entity_type', 'content', 'created_by']
        order_by = (
            ('name', 'Name (ascending)'),
            ('-name', 'Name (descending)'),
            ('entity_type', 'Type (ascending)'),
            ('-entity_type', 'Type (descending)'),
        )


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
