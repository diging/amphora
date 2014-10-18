from django.conf.urls import url, include
from django.contrib.auth.models import User
from rest_framework import routers, serializers, viewsets, reverse, renderers
from rest_framework_cj.fields import LinkField
import magic

from .models import *
from .api_renderers import *


class ResourceSerializer(serializers.HyperlinkedModelSerializer):
    stored = serializers.Field(source='stored')
    metadata = serializers.SerializerMethodField('generate_metadata')
    content = LinkField('generate_content_field')

    class Meta:
        model = Resource
        readonly_fields = ('metadata',)
        fields = ('url', 'id', 'name', 'stored', 'metadata', 'content')
    

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
                data = {
                    'href': self.fields['url']._value + "?format=resource_content",
                    'type': magic.from_buffer(obj.localresource.file.read(), mime=True),
                    }
                return data
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
        fields = ('url', 'id', 'source', 'predicate', 'target')

class FieldSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Field
        fields = ('url', 'id', 'name')

class EntitySerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Entity
        fields = ('url', 'id', 'name')

class ResourceViewSet(viewsets.ModelViewSet):
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    content_negotiation_class = ResourceContentNegotiation
    renderer_classes = (
        renderers.BrowsableAPIRenderer,
        CustomCollectionJsonRenderer,
        ResourceContentRenderer,
        )

    def get(self, request, format=None):
        return super(ResourceViewSet, self).get(request, format)


class RelationViewSet(viewsets.ModelViewSet):
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer

class FieldViewSet(viewsets.ModelViewSet):
    queryset = Field.objects.all()
    serializer_class = FieldSerializer

class EntityViewSet(viewsets.ModelViewSet):
    queryset = Entity.objects.all()
    serializer_class = EntitySerializer
