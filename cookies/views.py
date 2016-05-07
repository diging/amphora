from django.shortcuts import render, render_to_response, get_object_or_404
from django.forms.extras.widgets import SelectDateWidget
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.db.models.query import QuerySet
from django.db.models import Q
from django.conf import settings

from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet


from guardian.shortcuts import get_objects_for_user

import iso8601
import inspect
import magic
from hashlib import sha1
import time, os, json, base64, hmac, urllib

from dal import autocomplete

from .forms import *
from .models import *


def resource(request, obj_id):
    resource = get_object_or_404(Resource, pk=obj_id)
    authorized = request.user.has_perm('cookies.view_resource', resource)
    if resource.hidden or not (resource.public or authorized):
        # TODO: render a real template for the error response.
        return HttpResponse('You do not have permission to view this resource',
                            status=401)
    return render(request, 'resource.html', {'resource':resource})


def resource_list(request):
    viewperm = get_objects_for_user(request.user, 'cookies.view_resource')\
                .values_list('id', flat=True)
    resources = Resource.objects.filter(
        Q(hidden=False)     # No hidden resources, ever
        & (Q(public=True)     # Either the resource is public, or...
            | Q(pk__in=viewperm)))  # The user has permission.
    return render(request, 'resources.html', {'resources':resources})


def collection(request, obj_id):
    collection = get_object_or_404(Collection, pk=obj_id)
    return render(request, 'collection.html', {'collection':collection})


def collection_list(request):
    collections = Collection.objects.all()
    return render(request, 'collections.html', {'collections':collections})


def index(request):
    return render(request, 'index.html', {})


def sign_s3(request):
    object_name = urllib.quote_plus(request.GET.get('file_name'))
    mime_type = request.GET.get('file_type')

    expires = int(time.time()+60*60*24)
    amz_headers = "x-amz-acl:public-read"

    # Generate a simple tree structure for storing files, based on the first
    #  five characters of the filename. E.g. asdf1234.jpg would be stored at
    #  {bucket}/a/s/d/f/1/asdf1234.jpg.
    e = min(len(object_name), 5)
    path = '/'.join([c for c in object_name[:e]])
    string_to_sign = "PUT\n\n%s\n%d\n%s\n/%s/%s/%s" % (mime_type, expires, amz_headers, settings.AWS_STORAGE_BUCKET_NAME, path, object_name)

    signature = base64.encodestring(hmac.new(settings.AWS_SECRET_ACCESS_KEY.encode(),
                                             string_to_sign.encode('utf8'),
                                             sha1).digest())
    signature = urllib.quote_plus(signature.strip())

    url = 'https://%s.s3.amazonaws.com/%s/%s' % (settings.AWS_STORAGE_BUCKET_NAME, path, object_name)

    content = {
        'signed_request': '%s?AWSAccessKeyId=%s&Expires=%s&Signature=%s' % (url, settings.AWS_ACCESS_KEY_ID, expires, signature),
        'url': url,
    }
    return JsonResponse(content)

def test_upload(request):
    return render(request, 'testupload.html', {})


class ResourceSearchView(SearchView):
    """Class based view for thread-safe search."""
    template = 'templates/search/search.html'
    queryset = SearchQuerySet()
    results_per_page = 20

    def get_context_data(self, *args, **kwargs):
        """Return context data."""
        context = super(ResourceSearchView, self).get_context_data(*args, **kwargs)
        sort_base = self.request.get_full_path().split('?')[0] + '?q=' + context['query']

        context.update({
            'sort_base': sort_base,
        })
        return context

    def form_valid(self, form):

        self.queryset = form.search()

        context = self.get_context_data(**{
            self.form_name: form,
            'query': form.cleaned_data.get(self.search_field),
            'object_list': self.queryset,
            'search_results' : self.queryset,
        })

        return self.render_to_response(context)
