from django.db.models import Q, Count

import django_filters

from cookies.models import *
from cookies import authorization


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



def get_collections(request):
    """
    Retrieve collections for which the current user has VIEW access.
    """
    return authorization.apply_filter(CollectionAuthorization.VIEW,
                                      request.user,
                                      Collection.objects.all())


class ConceptEntityFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(method='lookup_name_in_parts')
    entity_type = django_filters.ModelChoiceFilter(queryset=Type.objects.annotate(num_instances=Count('conceptentity')).filter(num_instances__gt=0))
    collection = django_filters.ModelChoiceFilter(queryset=get_collections, name='container__part_of', label='Collection')
    has_concept = django_filters.ChoiceFilter(choices=((True, 'Yes'), (False, 'No')), method='filter_has_concept', label='Has concept')
    has_predicate = django_filters.ModelChoiceFilter(queryset=Field.objects.annotate(num_instances=Count('instances')).filter(num_instances__gt=0), method='filter_has_predicate', label='Has relation')


    def filter_has_concept(self, queryset, name, value):
        if value is None:
            return queryset
        if value is True:
            return queryset.filter(concept__id__isnull=False)
        return queryset.exclude(concept__id__isnull=False)

    def filter_has_predicate(self, queryset, name, value):
        if value is None:
            return queryset
        try:
            queryset = queryset.filter(relations_from__predicate=value)
        except Exception as E:
            print str(E)

        return queryset

    def lookup_name_in_parts(self, queryset, name, value):
        q = Q()
        for part in value.split():
            q &= Q(name__icontains=part)
        return queryset.filter(q)


    class Meta:
        model = ConceptEntity
        fields = ['name', 'uri', 'entity_type', 'created_by',]



class ResourceContainerFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(method='lookup_name_in_parts')
    content = django_filters.CharFilter(name='primary__indexable_content',
                                        lookup_expr='icontains')
    part_of = django_filters.ModelChoiceFilter(name='part_of', queryset=Collection.objects.all())
    entity_type = django_filters.ModelChoiceFilter(
        name='primary__entity_type',
        queryset=Type.objects.annotate(num_instances=Count('resource'))\
                             .filter(num_instances__gt=0)
    )

    content_type = django_filters.MultipleChoiceFilter(choices=[(val, val) for val in ContentRelation.objects.values_list('content_type', flat=True).distinct('content_type')], method='filter_content_type')

    tag = django_filters.CharFilter(method='filter_tag')

    def filter_tag(self, queryset, value):
        if not value:
            return queryset
        return queryset.filter(primary__tags__tag__id=value)

    def filter_content_type(self, queryset, name, value):
        print value
        if not value:
            return queryset
        return queryset.filter(Q(content_relations__content_type__in=value)).distinct('id')

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
        fields = ['name', 'entity_type', 'content', 'created_by', 'part_of']
        strict = 'STRICTNESS.IGNORE'
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
