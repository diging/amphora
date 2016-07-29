from django.shortcuts import render, render_to_response, get_object_or_404
from django.forms.extras.widgets import SelectDateWidget
from django.forms import formset_factory

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.template import RequestContext, loader
from django.db.models.query import QuerySet
from django.db.models import Q
from django.conf import settings

from haystack.generic_views import SearchView
from haystack.query import SearchQuerySet
from celery.result import AsyncResult


from guardian.shortcuts import get_objects_for_user

import iso8601, urlparse, inspect, magic, requests, urllib3, copy, jsonpickle
from hashlib import sha1
import time, os, json, base64, hmac, urllib

from dal import autocomplete

from cookies.forms import *
from cookies.models import *
from cookies.filters import *
from cookies.tasks import *
from cookies.giles import *


def _ping_resource(path):
    try:
        response = requests.head(path)
    except requests.exceptions.ConnectTimeout:
        return False, {}
    return response.status_code == requests.codes.ok, response.headers


def resource(request, obj_id):
    resource = get_object_or_404(Resource, pk=obj_id)
    authorized = request.user.has_perm('cookies.view_resource', resource)
    # TODO: simplify this.
    if resource.hidden or not (resource.public or authorized or resource.created_by == request.user):
        # TODO: render a real template for the error response.
        return HttpResponse('You do not have permission to view this resource',
                            status=401)
    return render(request, 'resource.html', {'resource':resource})


def resource_by_uri(request):
    """
    Display details about a :class:`.Resource` identified by URI. If
    :class:`.Resource` is a ``content_resource``, displays details about the
    "parent".
    """
    uri = request.GET.get('uri', None)
    if uri is None:
        raise Http404('No resource URI provided')

    resource = get_object_or_404(Resource, uri=uri)
    if resource.content_resource:
        resource = resource.parent.first().for_resource
    return HttpResponseRedirect(reverse('resource', args=(resource.id,)))


def resource_list(request):
    # Either the resource is public, or owned by the requesting user.
    queryset = Resource.objects.filter(
        Q(content_resource=False)
        & Q(hidden=False) & (Q(public=True) | Q(created_by_id=request.user.id)))

    filtered_objects = ResourceFilter(request.GET, queryset=queryset)
    context = RequestContext(request, {
        'filtered_objects': filtered_objects,
    })
    print filtered_objects.data
    template = loader.get_template('resources.html')


    return HttpResponse(template.render(context))


def collection(request, obj_id):
    collection = get_object_or_404(Collection, pk=obj_id)
    if not collection.public and not collection.created_by == request.user:
        return HttpResponse('You do not have permission to view this resource',
                            status=401)

    filtered_objects = ResourceFilter(request.GET, queryset=collection.resources.filter(
        Q(content_resource=False)
        & Q(hidden=False) & (Q(public=True) | Q(created_by_id=request.user.id))
    ))
    context = RequestContext(request, {
        'filtered_objects': filtered_objects,
        'collection': collection
    })
    template = loader.get_template('collection.html')
    return HttpResponse(template.render(context))


def collection_list(request):
    queryset = Collection.objects.filter(
        Q(content_resource=False)\
        & Q(hidden=False) & (Q(public=True) | Q(created_by_id=request.user.id))
    )
    filtered_objects = CollectionFilter(request.GET, queryset=queryset)
    context = RequestContext(request, {
        'filtered_objects': filtered_objects,
    })
    template = loader.get_template('collections.html')

    return HttpResponse(template.render(context))


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


@login_required
def create_resource(request):
    context = RequestContext(request, {})

    template = loader.get_template('create_resource.html')

    return HttpResponse(template.render(context))


@login_required
def create_resource_file(request):
    context = RequestContext(request, {})

    template = loader.get_template('create_resource_file.html')

    if request.method == 'GET':
        form = UserResourceFileForm()

    elif request.method == 'POST':
        print request.FILES
        form = UserResourceFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['upload_file']
            content = Resource.objects.create(**{
                'content_type': uploaded_file.content_type,
                'content_resource': True,
                'name': uploaded_file._name,
                'created_by': request.user,
            })
            # The file upload handler needs the Resource to have an ID first,
            #  so we add the file after creation.
            content.file = uploaded_file
            content.save()
            return HttpResponseRedirect(reverse('create-resource-details',
                                                args=(content.id,)))

    context.update({'form': form})
    return HttpResponse(template.render(context))


@login_required
def create_resource_url(request):
    context = RequestContext(request, {})

    template = loader.get_template('create_resource_url.html')

    if request.method == 'GET':
        form = UserResourceURLForm()

    elif request.method == 'POST':
        form = UserResourceURLForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data.get('url')
            exists, headers = _ping_resource(url)
            if exists:
                content, _ = Resource.objects.get_or_create(**{
                    'location': url,
                    'content_resource': True,
                    'defaults': {
                        'name': url,
                        'content_type': headers.get('Content-Type', None),
                        'created_by': request.user,
                    }
                })
                return HttpResponseRedirect(reverse('create-resource-details',
                                                    args=(content.id,)))
            else:
                form.add_error('url', u'Could not access a resource at that' \
                                    + u' location. Please check the URL and' \
                                    + u' try again.')



    context.update({'form': form})
    return HttpResponse(template.render(context))


@login_required
def create_resource_details(request, content_id):
    content_resource = get_object_or_404(Resource, pk=content_id)
    context = RequestContext(request, {})
    if request.method == 'GET':
        form = UserResourceForm(initial={
            'name': content_resource.name,
            'uri': content_resource.location,
            'public': True,    # If the resource is already online, it's public.
        })
        # It wouldn't mean much for the user to indicate that the resource was
        #  non-public, given that we are accessing it over a public connection.
        # form.fields['public'].widget.attrs.update({'disabled': True})
    elif request.method == 'POST':
        form = UserResourceForm(request.POST)
        if form.is_valid():
            resource_data = copy.copy(form.cleaned_data)
            resource_data['entity_type'] = resource_data.pop('resource_type', None)
            collection = resource_data.pop('collection', None)
            resource_data['created_by'] = request.user
            resource = Resource.objects.create(**resource_data)
            content_relation = ContentRelation.objects.create(**{
                'for_resource': resource,
                'content_resource': content_resource,
                'content_type': content_resource.content_type,
            })

            if collection:
                collection.resources.add(resource)
                collection.save()

            return HttpResponseRedirect(reverse('resource', args=(resource.id,)))

    context.update({
        'form': form,
        'content_resource': content_resource,
    })

    template = loader.get_template('create_resource_details.html')

    return HttpResponse(template.render(context))


@login_required
def create_resource_choose_giles(request):
    """
    Directs to US or DE servers.

    """
    # TODO: implement flag for bulk vs. single.
    context = RequestContext(request, {})

    template = loader.get_template('create_resource_choose_giles.html')

    return HttpResponse(template.render(context))


@login_required
def create_resource_bulk(request):
    """
    Zotero bulk upload.
    """

    context = RequestContext(request, {})
    if request.method == 'GET':
        form = BulkResourceForm()
    elif request.method == 'POST':
        form = BulkResourceForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['upload_file']
            # TODO: validate file type.

            # Pickle can't handle file pointers.
            safe_data = {k: v for k, v in form.cleaned_data.iteritems()
                         if k != 'upload_file'}
            safe_data.update({'created_by': request.user})
            # result = handle_bulk(uploaded_file.temporary_file_path(),
            #                            safe_data)
            # 
            result = handle_bulk.delay(uploaded_file.temporary_file_path(),
                                       safe_data)

            job = UserJob.objects.create(**{
                'created_by': request.user,
                'result_id': result.id,
            })
            # result = handle_bulk.delay(uploaded_file, form.cleaned_data)

            return HttpResponseRedirect(reverse('job-status', args=(result.id,)))


    template = loader.get_template('create_resource_bulk.html')
    context.update({'form': form})
    return HttpResponse(template.render(context))


@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(request.GET.get('next', reverse('index')))


@login_required
def jobs(request):
    queryset = UserJob.objects.filter(created_by=request.user).order_by('-created')
    filtered_objects = UserJobFilter(request.GET, queryset=queryset)
    context = RequestContext(request, {
        'filtered_objects': filtered_objects,
    })
    template = loader.get_template('jobs.html')
    return HttpResponse(template.render(context))


@login_required
def job_status(request, result_id):
    job = get_object_or_404(UserJob, result_id=result_id)
    async_result = AsyncResult(result_id)
    context = RequestContext(request, {
        'job': job,
        'async_result': async_result,
    })

    print job.result
    if job.result or async_result.status == 'SUCCESS' or async_result.status == 'FAILURE':
        if async_result.status == 'SUCCESS':
            result = async_result.get()
            job.result = jsonpickle.encode(result)
            job.save()
        else:
            result = jsonpickle.decode(job.result)

        return HttpResponseRedirect(reverse(result['view'], args=(result['id'], )))

    template = loader.get_template('job_status.html')
    return HttpResponse(template.render(context))


@login_required
def handle_giles_upload(request):
    try:
        session = handle_giles_callback(request)
    except ValueError:
        return HttpResponseRedirect(reverse('create-resource'))

    return HttpResponseRedirect(reverse('create-process-giles', args=(session.id,)))


@login_required
def process_giles_upload(request, session_id):
    session = get_object_or_404(GilesSession, pk=session_id)
    context = RequestContext(request, {'session': session,})

    if request.method == 'GET':
        form = ChooseCollectionForm()
        form.fields['collection'].queryset = form.fields['collection'].queryset.filter(created_by_id=request.user.id)
        if session.collection:
            collection_id = session.collection
        else:
            collection_id = request.GET.get('collection_id', None)
        if collection_id:
            form.fields['collection'].initial = collection_id
            context.update({'collection_id': collection_id})

    elif request.method == 'POST':
        form = ChooseCollectionForm(request.POST)
        form.fields['collection'].queryset = form.fields['collection'].queryset.filter(created_by_id=request.user.id)
        if form.is_valid():
            session.collection = form.cleaned_data['collection']
            session.save()
    context.update({'form': form})
    template = loader.get_template('create_process_giles_upload.html')
    return HttpResponse(template.render(context))


@login_required
def edit_resource_details(request, resource_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    context = RequestContext(request, {'resource': resource,})
    template = loader.get_template('edit_resource_details.html')
    on_valid = request.GET.get('next', None)

    MetadataFormSet = formset_factory(MetadatumForm)

    if on_valid:
        context.update({'next': on_valid})

    if request.method == 'GET':
        form = UserEditResourceForm(initial={
            'name': resource.name,
            'resource_type': resource.entity_type,
            'public': resource.public,
            'uri': resource.uri,
            'namespace': resource.namespace,
        })

        formset = MetadataFormSet(initial=[{
            'field': relation.predicate,
            'value': relation.target.name,
            'value_id': relation.target.id,
        } for relation in resource.relations_from.all()], prefix='metadata')


    elif request.method == 'POST':
        form = UserEditResourceForm(request.POST)
        if form.is_valid():
            data = [
                ('name',  form.cleaned_data['name']),
                ('entity_type', form.cleaned_data['resource_type']),
                ('public', form.cleaned_data['public']),
                ('uri', form.cleaned_data['uri']),
                ('namespace', form.cleaned_data['namespace']),
            ]
            for field, value in data:
                setattr(resource, field, value)
            resource.save()

            if on_valid:
                return HttpResponseRedirect(on_valid)

    page_field = Field.objects.get(uri='http://xmlns.com/foaf/0.1/page')
    context.update({
        'form': form,
        'formset': formset,
        'resource': resource,
        'pages': resource.relations_from.filter(predicate_id=page_field.id),
    })


    return HttpResponse(template.render(context))
