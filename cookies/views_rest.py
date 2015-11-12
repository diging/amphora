from django.conf.urls import url, include
from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
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
                  'public', 'text_available')


class LocalResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = LocalResource
        fields = ('url', 'id', 'name','stored', 'content_location', 'public',
                  'text_available')


class RemoteResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = RemoteResource
        fields = ('url', 'id', 'name', 'stored', 'location', 'content_location',
                  'public', 'text_available')


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

    # Allows us to work with Accept header directly.
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        """
        Serve up the file for a :class:`.LocalResource`
        """

        resource = get_object_or_404(LocalResource, pk=pk)

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
        Update the file for a :class:`.LocalResource`
        """
        resource = get_object_or_404(LocalResource, pk=pk)

        # The file associated with a LocalResource cannot be overwritten. JARS
        #  does not support versioning.
        # print resource.file.__dict__
        
        if resource.file._file:
            data = {
                "error": {
                    "status": 403,
                    "title": "Overwriting a LocalResource is not permitted.",
                }}
            return Response(data, status=403)


        resource.file = request.data['file']
        resource.content_type = request.data['file'].content_type
        resource.save()

        return Response(status=204)
