from django.conf.urls import url, include
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import routers, serializers, viewsets, reverse, renderers, mixins
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser, FileUploadParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route, api_view, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
import magic
from .models import *

class ContentField(serializers.Field):
    def to_representation(self, obj):
        return obj.url

    def to_internal_value(self, data):
        return data

class ResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Resource
        fields = ('url', 'name','stored', 'content_location')

class LocalResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = LocalResource
        fields = ('url', 'name','stored', 'content_location')
        
    def create(self, validated_data):
    
		inst = super(LocalResourceSerializer, self).create(validated_data)
		return inst
        
class RemoteResourceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = RemoteResource
        fields = ('url', 'name','stored', 'location', 'content_location')        


class ResourceViewSet(  mixins.RetrieveModelMixin,
                        mixins.ListModelMixin,
                        viewsets.GenericViewSet):
	parser_classes = (JSONParser,)                        
	queryset = Resource.objects.all()
	serializer_class = ResourceSerializer

class LocalResourceViewSet(viewsets.ModelViewSet):
	parser_classes = (JSONParser,)
	queryset = LocalResource.objects.all()
	serializer_class = LocalResourceSerializer
	parser_classes = (JSONParser,)
    
class RemoteResourceViewSet(viewsets.ModelViewSet):
	parser_classes = (JSONParser,)
	queryset = RemoteResource.objects.all()
	serializer_class = RemoteResourceSerializer        
    
class ResourceContentView(APIView):
	parser_classes = (FileUploadParser,MultiPartParser)
	authentication_classes = (TokenAuthentication,)
	permission_classes = (IsAuthenticated,)	
	
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

			response['Content-Disposition'] = 'attachment; filename="'+resource.file.name.split('/')[0]+'"'
		
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
					"title": "Overwriting LocalResource content is not permitted.",
				}}, status=403)

		resource.file = request.data['file']
		resource.save()

		return Response(status=204)