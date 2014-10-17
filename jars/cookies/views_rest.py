from django.conf.urls import url, include
from django.contrib.auth.models import User
from rest_framework import routers, serializers, viewsets, reverse

from .models import *

class ResourceSerializer(serializers.HyperlinkedModelSerializer):
    stored = serializers.Field(source='stored')
    metadata = serializers.SerializerMethodField('generate_metadata')
    content = serializers.SerializerMethodField('generate_content_field')
    
    class Meta:
        model = Resource
        readonly_fields = ('metadata',)
        fields = ('id', 'name', 'stored', 'metadata', 'content')

    def generate_metadata(self, obj):
        fields = {}
        for relation in obj.relations_from.all():
            # TODO: Should use the URI for field instead of name.
            field = relation.predicate.name
            value = relation.target.name
            
            if field in fields:
                if not type(fields[field]) is list:
                    fields[field] = [fields[field]]
                fields[field].append(value)
            else:
                fields[field] = value
        return fields

    def generate_content_field(self, obj):
        if obj.stored == 'Local':
            try:
                return obj.localresource.file.url
            except ValueError:
                return None

class RelationSerializer(serializers.HyperlinkedModelSerializer):
    source = serializers.HyperlinkedRelatedField(
        view_name='resource-detail',
    )
    target = serializers.HyperlinkedRelatedField(
        view_name='resource-detail',
    )
    
    class Meta:
        model = Relation
        fields = ('id', 'source', 'predicate', 'target')

class FieldSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Field
        fields = ('id', 'name')

class EntitySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Entity
        fields = ('id', 'name')

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer

class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer

class FieldViewSet(viewsets.ModelViewSet):
    queryset = Field.objects.all()
    serializer_class = FieldSerializer

class EntityViewSet(viewsets.ModelViewSet):
    queryset = Entity.objects.all()
    serializer_class = EntitySerializer
