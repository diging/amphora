from django.utils.datastructures import SortedDict
from rest_framework import renderers

from rest_framework_cj.renderers import CollectionJsonRenderer
from rest_framework.negotiation import BaseContentNegotiation, DefaultContentNegotiation
import magic

from .models import *

class CustomCollectionJsonRenderer(CollectionJsonRenderer):
    def _make_link(self, rel, data):
        """
        Extended to allow for additional link properties.
        """

        if type(data) is dict or type(data) is SortedDict:
            if 'href' not in data:
                raise ValueError('Link data must include href value')
            data['rel'] = rel
            return data
        return super(CustomCollectionJsonRenderer, self)._make_link(rel, data)

class ResourceContentRenderer(renderers.BaseRenderer):
    media_type = 'text/plain'
    format = 'resource_content'

    def render(self, data, media_type=None, renderer_context=None):
        # Don't display content for multiple items.
        if type(data) is not list:

            # If data includes an id (primary key) for an entity with an
            #  associated file, display its contents.
            entity = Entity.objects.get(pk=data['id']).cast()
            if hasattr(entity, 'file'):
                try:
                    content = entity.file.read()
                    return content
                    # Make sure that the content is indeed plain text.
                    if magic.from_buffer(content, mime=True) == 'text/plain':
                        return content.encode('utf-8')
                except:
                    pass
        return None


class ResourceContentNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix):
        if 'pk' in request.parser_context['kwargs']:
            if 'format' in request.GET:
                if request.GET['format'] == 'resource_content':
                    renderer = ResourceContentRenderer()
                    return (renderer, renderer.media_type)
        return super(ResourceContentNegotiation, self).select_renderer(
                                            request, renderers, format_suffix)