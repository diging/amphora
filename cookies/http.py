from django.http import HttpResponse
from rest_framework.negotiation import BaseContentNegotiation


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """
    Overrides DRF content negotation.

    See http://www.django-rest-framework.org/api-guide/content-negotiation/
    """
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)


class HttpResponseUnacceptable(HttpResponse):
    status_code = 406
