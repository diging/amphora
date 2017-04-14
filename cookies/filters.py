from django.db.models import Q, Count

import django_filters

from cookies.models import *


class GilesUploadFilter(django_filters.FilterSet):
    class Meta:
        model = GilesUpload
        fields = ('state', 'created_by', 'created', 'updated')

    o = django_filters.OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('created', 'created'),
            ('updated', 'updated'),
        ),

        field_labels={
            'created': 'Created',
            'updated': 'updated',
        }
    )



class ConceptEntityFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(method='lookup_name_in_parts')
    entity_type = django_filters.ModelChoiceFilter(queryset=Type.objects.annotate(num_instances=Count('conceptentity')).filter(num_instances__gt=0))


    def lookup_name_in_parts(self, queryset, name, value):
        q = Q()
        for part in value.split():
            q &= Q(name__icontains=part)
        return queryset.filter(q)

    class Meta:
        model = ConceptEntity
        fields = ['name', 'uri', 'entity_type', 'created_by',]
        # order_by = (
        #     ('name', 'Name (ascending)'),
        #     ('-name', 'Name (descending)'),
        #     ('entity_type', 'Type (ascending)'),
        #     ('-entity_type', 'Type (descending)'),
        # )



class ResourceContainerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(method='lookup_name_in_parts')
    content = django_filters.CharFilter(name='primary__indexable_content',
                                        lookup_expr='icontains')

    entity_type = django_filters.ModelChoiceFilter(
        name='primary__entity_type',
        queryset=Type.objects.annotate(num_instances=Count('resource'))\
                             .filter(num_instances__gt=0)
    )

    tag = django_filters.CharFilter(method='filter_tag')

    def filter_tag(self, queryset, value):
        if not value:
            return queryset
        return queryset.filter(primary__tags__tag__id=value)

    def lookup_name_in_parts(self, queryset, name, value):
        q = Q()
        for part in value.split():
            q &= Q(primary__name__icontains=part)
        return queryset.filter(q)

    o = django_filters.OrderingFilter(
        # tuple-mapping retains order
        fields=(
            ('primary__name', 'name'),
            ('primary__entity_type', 'type'),
        ),

        field_labels={
            'name': 'Name',
            'type': 'Type',
        }
    )

    class Meta:
        model = Resource
        fields = ['name', 'entity_type', 'content', 'created_by']
        # order_by = (
        #     ('primary__name', 'Name (ascending)'),
        #     ('-primary__name', 'Name (descending)'),
        #     ('primary__entity_type', 'Type (ascending)'),
        #     ('-primary__entity_type', 'Type (descending)'),
        # )


class CollectionFilter(django_filters.FilterSet):
    class Meta:
        model = Collection
        fields = ['name', 'created_by']


class UserJobFilter(django_filters.FilterSet):
    complete = django_filters.CharFilter(method='filter_complete')

    def filter_complete(self, queryset, value):
        return queryset.filter(~Q(result=''))

    class Meta:
        model = UserJob
        fields = ['result_id', 'complete', 'created_by']
