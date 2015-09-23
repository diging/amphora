from django.shortcuts import render, render_to_response, get_object_or_404
from django.forms.extras.widgets import SelectDateWidget
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.db.models.query import QuerySet
from django.db.models import Q

from guardian.shortcuts import get_objects_for_user

import iso8601
import inspect
import magic

import autocomplete_light

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
    viewperm = get_objects_for_user(request.user, 'cookies.view_resource')
    resources = Resource.objects.filter(
        Q(real_type__model__in=['localresource', 'remoteresource'])
        & Q(hidden=False)     # No hidden resources, ever
        & (Q(public=True)     # Either the resource is public, or...
            | Q(pk__in=[r.id for r in viewperm])))  # The user has permission.
    return render(request, 'resources.html', {'resources':resources})


def collection(request, obj_id):
    collection = get_object_or_404(Collection, pk=obj_id)
    return render(request, 'collection.html', {'collection':collection})


def collection_list(request):
    collections = Collection.objects.all()
    return render(request, 'collections.html', {'collections':collections})


def index(request):
    return render(request, 'index.html', {})
