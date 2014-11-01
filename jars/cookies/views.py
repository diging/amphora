from django.shortcuts import render, render_to_response, get_object_or_404
from django.forms.extras.widgets import SelectDateWidget
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.db.models.query import QuerySet
import iso8601
import inspect

import autocomplete_light

from .forms import *
from .models import *

def resource(request, obj_id):
    resource = get_object_or_404(Resource, pk=obj_id)
    return render(request, 'resource.html', {'resource':resource})

def resource_list(request):
    resources = Resource.objects.filter(real_type__model__in=['localresource', 'remoteresource'])
    return render(request, 'resources.html', {'resources':resources})

def collection(request, obj_id):
    collection = get_object_or_404(Collection, pk=obj_id)
    return render(request, 'collection.html', {'collection':collection})


def collection_list(request):
    collections = Collection.objects.all()
    return render(request, 'collections.html', {'collections':collections})

def index(request):
    return render(request, 'index.html', {})
