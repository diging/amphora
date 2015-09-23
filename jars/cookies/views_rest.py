from django.conf.urls import url, include
from django.contrib.auth.models import User
from django.http import HttpResponse
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

import magic
from models import *


class ResourcePermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        authorized = request.user.has_perm('cookies.view_resource', obj)
        if obj.hidden or not (obj.public or authorized):
            return False
        return True


class ContentField(serializers.Field):
    def to_representation(self, obj):
        return obj.url

    def to_internal_value(self, data):
        return data


class ResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Resource
        fields = ('url', 'id', 'uri', 'name','stored', 'content_location',
                  'public')


class LocalResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = LocalResource
        fields = ('url', 'id', 'name','stored', 'content_location', 'public')


class RemoteResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = RemoteResource
        fields = ('url', 'id', 'name','stored', 'location', 'content_location',
                  'public')


class CollectionSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Collection
        fields = ('url', 'id', 'name', 'uri', 'public')


class CollectionDetailSerializer(serializers.HyperlinkedModelSerializer):
    resources = ResourceSerializer(many=True, read_only=True)
    class Meta:
        model = Collection
        fields = ('url', 'id', 'name', 'resources', 'public')


class CollectionViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    parser_classes = (JSONParser,)

    def retrieve(self, request, pk=None):
        queryset = self.get_queryset()
        collection = get_object_or_404(queryset, pk=pk)
        context = {'request': request}
        serializer = CollectionDetailSerializer(collection, context=context)
        return Response(serializer.data)


class ResourceViewSet(  mixins.RetrieveModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
    parser_classes = (JSONParser,)
    queryset = Resource.objects.all()
    serializer_class = ResourceSerializer
    permission_classes = (ResourcePermission,)

    def get_queryset(self):
        queryset = super(ResourceViewSet, self).get_queryset()
        uri = self.request.query_params.get('uri', None)
        if uri:
            queryset = queryset.filter(uri=uri)
        return queryset


class LocalResourceViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = LocalResource.objects.all()
    serializer_class = LocalResourceSerializer
    parser_classes = (JSONParser,)
    permission_classes = (ResourcePermission,)

    def get_queryset(self):
        queryset = super(LocalResourceViewSet, self).get_queryset()

        # Check permissions. For some reason ResourcePermission is not getting
        #  a vote here, so we'll have to do this for now.
        viewperm = get_objects_for_user(self.request.user,
                                        'cookies.view_resource')
        queryset = queryset.filter(
            Q(hidden=False)       # No hidden resources, ever
            & (Q(public=True)     # Either the resource is public, or...
                | Q(pk__in=[r.id for r in viewperm])))  # The user has permission.
        return queryset


class RemoteResourceViewSet(viewsets.ModelViewSet):
    parser_classes = (JSONParser,)
    queryset = RemoteResource.objects.all()
    serializer_class = RemoteResourceSerializer
    permission_classes = (ResourcePermission,)

    def get_queryset(self):
        queryset = super(RemoteResourceViewSet, self).get_queryset()

        # Check permissions. For some reason ResourcePermission is not getting
        #  a vote here, so we'll have to do this for now.
        viewperm = get_objects_for_user(self.request.user,
                                        'cookies.view_resource')
        queryset = queryset.filter(
            Q(hidden=False)       # No hidden resources, ever
            & (Q(public=True)     # Either the resource is public, or...
                | Q(pk__in=[r.id for r in viewperm])))  # The user has permission.
        return queryset


class ResourceContentView(APIView):
    parser_classes = (FileUploadParser,MultiPartParser)
    authentication_classes = (TokenAuthentication,)
    permission_classes = (ResourcePermission,)

    def get(self, request, pk):
        """
        Serve up the file for a :class:`.LocalResource`
        """

        resource = get_object_or_404(LocalResource, pk=pk)
        if request.method == 'GET':
            file = resource.file.storage.open(resource.file.name)
            content = file.read()
            content_type = magic.from_buffer(content)

            response = HttpResponse(content, content_type=content_type)

            cdpattern = 'attachment; filename="{fname}"'
            fname = resource.file.name.split('/')[0]    # TODO: make simpler.
            response['Content-Disposition'] = cdpattern.format(fname=fname)

            return response

    def put(self, request, pk):
        """
        Update the file for a :class:`.LocalResource`
        """

        resource = get_object_or_404(LocalResource, pk=pk)

        # Do not allow overwriting.
        if hasattr(resource.file, 'url'):
            return Response({
                "error": {
                    "status": 403,
                    "title": "Overwriting a LocalResource is not permitted.",
                }}, status=403)

        resource.file = request.data['file']
        resource.save()

        return Response(status=204)
