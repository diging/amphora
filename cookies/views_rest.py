from django.conf import settings
from django.conf.urls import url, include
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from rest_framework import routers, serializers, viewsets, reverse, renderers, mixins
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser, FileUploadParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route, api_view, parser_classes
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.authentication import TokenAuthentication


from guardian.shortcuts import get_objects_for_user
from django.db.models import Q

from cookies.http import HttpResponseUnacceptable, IgnoreClientContentNegotiation

import magic
import re

from cookies.models import *
from concepts.models import *
from cookies.exceptions import *
from cookies import authorization, tasks

logger = settings.LOGGER


class MultiSerializerViewSet(viewsets.ModelViewSet):
    serializers = {
        'default': None,
    }

    def get_serializer_class(self):
        return self.serializers.get(self.action, self.serializers['default'])


class ContentResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Resource
        fields = ('url', 'id', 'uri', 'name', 'public', 'content_location',
                  'is_external', 'external_source', 'is_local', 'is_remote')


class ContentRelationSerializer(serializers.HyperlinkedModelSerializer):
    content_resource = ContentResourceSerializer()
    class Meta:
        model = ContentRelation
        fields = ('id', 'content_resource', 'content_type', 'content_encoding')


class ConceptSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Concept
        fields = ('id', 'uri', 'label', 'description', 'authority')


class FieldSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Field
        fields = ('id', 'name')


class TargetResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ('id', 'url', 'name',)


class RelationSerializer(serializers.HyperlinkedModelSerializer):
    target = TargetResourceSerializer()
    predicate = FieldSerializer()

    class Meta:
        model = Relation
        fields = ('id', 'uri', 'url', 'name', 'target', 'predicate')


class PartResourceDetailSerializer(serializers.HyperlinkedModelSerializer):
    content = ContentRelationSerializer(many=True)

    class Meta:
        model = Resource
        fields = ('url', 'id', 'uri', 'name', 'public', 'content', 'file')


class PartSerializer(serializers.HyperlinkedModelSerializer):
    source = PartResourceDetailSerializer()
    predicate = FieldSerializer()

    class Meta:
        model = Relation
        fields = ('id', 'uri', 'url', 'name', 'source', 'predicate')


class ResourcePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        print 'has_object_permission::', request.user, authorization.list_authorizations(obj, request.user)
        authorized = authorization.check_authorization('view_resource', request.user, obj)
        return authorized or request.user.is_superuser

    def has_permission(self, request, view):
        print 'has_permission::', request, view
        return True


class CollectionPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        authorized = authorization.check_authorization('view_resource', request.user, obj)
        return authorized or request.user.is_superuser



class ResourceDetailSerializer(serializers.HyperlinkedModelSerializer):
    content = ContentRelationSerializer(many=True)
    relations_from = RelationSerializer(many=True)
    parts = PartSerializer(many=True)

    class Meta:
        model = Resource
        fields = ('url', 'id', 'uri', 'name', 'public', 'content',
                  'parts', 'relations_from',  'file', 'content_types')


class ResourceListSerializer(serializers.HyperlinkedModelSerializer):
    content = ContentRelationSerializer(many=True)

    class Meta:
        model = Resource
        fields = ('url', 'uri', 'name', 'public', 'content', 'id', 'content_types')


class CollectionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Collection
        fields = ('url', 'name', 'uri', 'public', 'size', 'id')


class CollectionDetailSerializer(serializers.HyperlinkedModelSerializer):
    resources = ResourceListSerializer(many=True, read_only=True)
    class Meta:
        model = Collection
        fields = ('url', 'id', 'name', 'resources', 'public')


class ConceptViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = Concept.objects.all()
    serializer_class = ConceptSerializer

    def get_queryset(self, *args, **kwargs):
        queryset = super(ConceptViewSet, self).get_queryset(*args, **kwargs)
        search = self.request.query_params.get('search', None)

        if search is not None:
            queryset = queryset.filter(label__icontains=search)

            try:
                tasks.search_for_concept.delay(search)
            except ConnectionError:
                logger.error("ConceptViewSet.get_queryset: there was an error"
                             " connecting to the redis message passing backend")
        return queryset


class CollectionViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    permission_classes = (CollectionPermission,)

    def get_queryset(self, *args, **kwargs):
        qs = super(CollectionViewSet, self).get_queryset(*args, **kwargs)
        return authorization.apply_filter(CollectionAuthorization.VIEW, self.request.user, qs)

    def retrieve(self, request, pk=None):
        queryset = self.get_queryset()
        collection = get_object_or_404(queryset, pk=pk)
        if not authorization.check_authorization(CollectionAuthorization.VIEW, request.user, collection):
            return HttpResponseForbidden('Nope')
        context = {'request': request}
        serializer = CollectionDetailSerializer(collection, context=context)
        return Response(serializer.data)


class RelationViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    parser_classes = (JSONParser,)

    def get_queryset(self):
        """
        Extended to provide authorization filtering.
        """
        qs = super(RelationViewSet, self).get_queryset()
        return authorization.apply_filter(ResourceAuthorization.VIEW, self.request.user, qs)


class FieldViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = Field.objects.all()
    serializer_class = FieldSerializer
    parser_classes = (JSONParser,)


class ResourceViewSet(MultiSerializerViewSet):
    parser_classes = (JSONParser,)
    queryset = Resource.objects.filter(hidden=False, content_resource=False)
    serializers = {
        'list': ResourceListSerializer,
        'retrieve':  ResourceDetailSerializer,
        'default':  ResourceListSerializer,
    }
    permission_classes = (ResourcePermission,)

    def retrieve(self, request, pk=None):

        return super(ResourceViewSet, self).retrieve(request, pk=pk)


    def get_queryset(self):
        """
        Extended to provide authorization filtering.
        """
        qs = super(ResourceViewSet, self).get_queryset()
        qs = authorization.apply_filter(ResourceAuthorization.VIEW, self.request.user, qs)

        if not self.kwargs.get('pk', None):
            qs = qs.filter(content_resource=False)
        uri = self.request.query_params.get('uri', None)
        if uri:
            qs = qs.filter(uri=uri)

        query = self.request.query_params.get('search', None)
        if query:
            qs = qs.filter(name__icontains=query)

        content_type = self.request.query_params.get('content_type')
        if content_type:
            qs = qs.filter(Q(content__content_resource__content_type=content_type))
        return qs


class ResourceContentView(APIView):
    parser_classes = (FileUploadParser, MultiPartParser)
    # authentication_classes = (TokenAuthentication,)
    permission_classes = (ResourcePermission,)

    # Allows us to work with Accept header directly.
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        """
        Serve up the file for a :class:`.Resource`
        """

        resource = get_object_or_404(Resource, pk=pk)

        # TODO: this could be more sophisticated.
        accept = re.split('[,;]', request.META['HTTP_ACCEPT'])

        # If the user wants the content of the original resource, great. If
        #  the user wants only plain text, and the original resource is not
        #  plain text, attempt to return any plain text that was extracted
        #  at ingest.
        if '*/*' not in accept and resource.content_type not in accept:
            if 'text/plain' in accept and resource.text_available:
                return HttpResponse(resource.indexable_content)

            # Fail miserably.
            msgpattern = u'No resource available with type in "{0}"'
            msg = msgpattern.format(request.META['HTTP_ACCEPT'])
            return HttpResponseUnacceptable(msg)

        # The file could live anywhere, so we just point the user in
        #  that direction.
        return HttpResponseRedirect(resource.file.url)

    def put(self, request, pk):
        """
        Update the file for a :class:`.Resource`
        """

        resource = get_object_or_404(Resource, pk=pk)

        # The file associated with a Resource cannot be overwritten. JARS
        #  does not support versioning.
        if resource.file._file:
            data = {
                "error": {
                    "status": 403,
                    "title": "Overwriting a Resource is not permitted.",
                }}
            return Response(data, status=403)

        resource.file = request.data['file']
        resource.content_type = request.data['file'].content_type
        resource.save()

        return Response(status=204)
