from django.shortcuts import render, render_to_response, get_object_or_404
from django import forms
from django.forms.utils import ErrorList
from django.forms.extras.widgets import SelectDateWidget
from django.forms import formset_factory

from django.http import (JsonResponse, HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect, Http404, HttpResponseForbidden)
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import logout
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.template import RequestContext, loader
from django.db.models.query import QuerySet
from django.db.models import Q
from django.conf import settings

from celery.result import AsyncResult

from guardian.shortcuts import get_objects_for_user

import iso8601, urlparse, inspect, magic, requests, urllib3, copy, jsonpickle
from hashlib import sha1
import time, os, json, base64, hmac, urllib, datetime

# TODO: clean this up!!
from cookies.forms import *
from cookies.models import *
from cookies.filters import *
from cookies.tasks import *
from cookies.giles import *
from cookies import operations
# import (add_creation_metadata, merge_conceptentities,
#                                 merge_resources)
from cookies import metadata, authorization
from concepts.models import Concept


def _get_resource_by_id(request, resource_id, *args):
    return get_object_or_404(Resource, pk=resource_id)


def _get_collection_by_id(request, collection_id, *args):
    return get_object_or_404(Collection, pk=collection_id)


def _get_entity_by_id(request, entity_id, *args):
    return get_object_or_404(ConceptEntity, pk=entity_id)


def _ping_resource(path):
    try:
        response = requests.head(path)
    except requests.exceptions.ConnectTimeout:
        return False, {}
    return response.status_code == requests.codes.ok, response.headers


def check_authorization(request, instance, permission):
    authorized = request.user.has_perm('cookies.%s' % permission, instance)
    # TODO: simplify this.
    if instance.hidden or not (instance.public or authorized or instance.created_by == request.user):
        # TODO: render a real template for the error response.
        raise RuntimeError('')


def resource(request, obj_id):
    resource = get_object_or_404(Resource, pk=obj_id)
    try:
        check_authorization(request, resource, 'view_resource')
    except RuntimeError:
        return HttpResponse('You do not have permission to view this resource', status=401)
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
        Q(content_resource=False) & Q(is_part=False)
        & Q(hidden=False) & (Q(public=True) | Q(created_by_id=request.user.id)))

    # For now we use filters to achieve search functionality. At some point we
    #  should use a real search backend.
    #
    # TODO: implement a real search backend.
    filtered_objects = ResourceFilter(request.GET, queryset=queryset)

    context = RequestContext(request, {
        'filtered_objects': filtered_objects,
    })

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


@login_required
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


# class ResourceSearchView(SearchView):
#     """Class based view for thread-safe search."""
#     template = 'templates/search/search.html'
#     queryset = SearchQuerySet()
#     results_per_page = 20
#
#     def get_context_data(self, *args, **kwargs):
#         """Return context data."""
#         context = super(ResourceSearchView, self).get_context_data(*args, **kwargs)
#         sort_base = self.request.get_full_path().split('?')[0] + '?q=' + context['query']
#
#         context.update({
#             'sort_base': sort_base,
#         })
#         return context
#
#     def form_valid(self, form):
#
#         self.queryset = form.search()
#
#         context = self.get_context_data(**{
#             self.form_name: form,
#             'query': form.cleaned_data.get(self.search_field),
#             'object_list': self.queryset,
#             'search_results' : self.queryset,
#         })
#
#         return self.render_to_response(context)


@login_required
def create_resource(request):
    context = RequestContext(request, {
        'giles_upload_location': '/'.join([settings.GILES, 'files', 'upload'])
    })

    template = loader.get_template('create_resource.html')

    return HttpResponse(template.render(context))


@login_required
def create_resource_file(request):
    context = RequestContext(request, {})

    template = loader.get_template('create_resource_file.html')

    if request.method == 'GET':
        form = UserResourceFileForm()

    elif request.method == 'POST':

        form = UserResourceFileForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = request.FILES['upload_file']
            content = Resource.objects.create(**{
                'content_type': uploaded_file.content_type,
                'content_resource': True,
                'name': uploaded_file._name,
                'created_by': request.user,
            })
            operations.add_creation_metadata(content, request.user)
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
                content, created = Resource.objects.get_or_create(**{
                    'location': url,
                    'content_resource': True,
                    'defaults': {
                        'name': url,
                        'content_type': headers.get('Content-Type', None),
                        'created_by': request.user,
                    }
                })
                if created:
                    operations.add_creation_metadata(content, request.user)
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
            operations.add_creation_metadata(resource, request.user)
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
        qs = form.fields['collection'].queryset
        form.fields['collection'].queryset = qs.filter(created_by=request.user)
    elif request.method == 'POST':
        form = BulkResourceForm(request.POST, request.FILES)
        qs = form.fields['collection'].queryset
        form.fields['collection'].queryset = qs.filter(created_by=request.user)
        if form.is_valid():
            uploaded_file = request.FILES['upload_file']
            # File pointers aren't easily serializable; we need to farm this
            #  out to Celery.
            safe_data = {k: v for k, v in form.cleaned_data.iteritems()
                         if k != 'upload_file'}
            safe_data.update({'created_by': request.user})
            # result = handle_bulk(uploaded_file.temporary_file_path(),
            #                            safe_data)
            #

            # Currently we only support RDF here. This can be a naked RDF/XML
            #  document (from Zotero), or a zip archive containing RDF/XML and
            #  attachments.
            file_path = uploaded_file.temporary_file_path()
            file_name = request.FILES['upload_file'].name
            if not (file_name.endswith('.rdf') or file_name.endswith('.zip')):
                form.add_error('upload_file', 'Not a valid RDF document or ZIP archive.')
            else:
                result = handle_bulk.delay(file_path, safe_data, file_name)##.delay
                job = UserJob.objects.create(**{
                    'created_by': request.user,
                    'result_id': result.id,
                })

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
    template = loader.get_template('job_status.html')

    if job.result or async_result.status == 'SUCCESS' or async_result.status == 'FAILURE':
        if async_result.status == 'SUCCESS':
            result = async_result.get()
            job.result = jsonpickle.encode(result)
            job.save()
        else:
            try:
                result = jsonpickle.decode(job.result)
            except:
                return HttpResponse(template.render(context))

        return HttpResponseRedirect(reverse(result['view'], args=(result['id'], )))


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
    """
    """
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
            collection = form.cleaned_data.get('collection', None)
            name = form.cleaned_data.get('name', None)
            if not collection and name:
                collection = Collection.objects.create(**{
                    'created_by_id': request.user.id,
                    'name': name,
                })
                operations.add_creation_metadata(collection, request.user)
            session.collection = collection
            session.save()
            form.fields['collection'].initial = collection.id
            form.fields['name'].widget.attrs['disabled'] = True
    context.update({'form': form})
    template = loader.get_template('create_process_giles_upload.html')
    return HttpResponse(template.render(context))


VALUE_FORMS = dict([
    ('Int', MetadatumValueIntegerForm),
    ('Float', MetadatumValueFloatForm),
    ('Datetime', MetadatumValueDateTimeForm),
    ('Date', MetadatumValueDateForm),
    ('Text', MetadatumValueTextAreaForm),
    ('ConceptEntity', MetadatumConceptEntityForm),
    ('Resource', MetadatumResourceForm),
    ('Type', MetadatumTypeForm),
])


@login_required
def delete_resource_metadatum(request, resource_id, relation_id):
    resource = get_object_or_404(Resource, pk=resource_id)

    try:
        check_authorization(request, resource, 'edit_resource')
    except RuntimeError:
        return HttpResponse('You do not have permission to view this resource', status=401)
    relation = get_object_or_404(Relation, pk=relation_id)
    delete = request.GET.get('delete', False)
    if delete == 'confirm':
        relation.is_deleted = True
        relation.save()
        return HttpResponseRedirect(reverse('edit-resource-details', args=(resource.id,)) + '?tab=metadata')

    context = RequestContext(request, {
        'resource': resource,
        'relation': relation,
    })
    template = loader.get_template('delete_resource_metadatum.html')

    return HttpResponse(template.render(context))


@login_required
def create_resource_metadatum(request, resource_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    try:
        check_authorization(request, resource, 'edit_resource')
    except RuntimeError:
        return HttpResponse('You do not have permission to view this resource', status=401)

    if request.method == 'POST':
        form = MetadatumForm(request.POST)
        if form.is_valid():
            predicate = form.cleaned_data['predicate']
            target_class = form.cleaned_data['value_type']
            relation = Relation.objects.create(
                source=resource,
                predicate=predicate
            )
            return HttpResponseRedirect(reverse('edit-resource-metadatum', args=(resource.id, relation.id)) + '?target_class=' + target_class)
    else:
        form = MetadatumForm()
    context = RequestContext(request, {
        'resource': resource,
        'form': form,

    })
    template = loader.get_template('create_resource_metadatum.html')

    return HttpResponse(template.render(context))


@login_required
def edit_resource_metadatum(request, resource_id, relation_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    try:
        check_authorization(request, resource, 'edit_resource')
    except RuntimeError:
        return HttpResponse('You do not have permission to view this resource', status=401)
    relation = get_object_or_404(Relation, pk=relation_id)
    if request.method == 'GET':
        target_class = request.GET.get('target_class', None)
    else:
        target_class = request.POST.get('target_class', None)

    context = RequestContext(request, {
        'resource': resource,
        'relation': relation,
    })
    template = loader.get_template('edit_resource_metadatum.html')
    on_valid = request.GET.get('next', None)
    if on_valid:
        context.update({'next': on_valid})

    target_type = type(relation.target)
    initial_data = None

    if target_class is not None:
        form_class = VALUE_FORMS[target_class]
    elif target_type is Value:
        initial_data = relation.target.name
        dtype = type(initial_data)
        if dtype in [str, unicode]:
            form_class = MetadatumValueTextAreaForm
        elif type(initial_data) is int:
            form_class = MetadatumValueIntegerForm
        elif type(initial_data) is float:
            form_class = MetadatumValueFloatForm
        elif type(initial_data) is datetime.datetime:
            form_class = MetadatumValueDateTimeForm
        elif type(initial_data) is datetime.date:
            form_class = MetadatumValueDateForm
    elif target_type is ConceptEntity:
        form_class = MetadatumConceptEntityForm
        initial_data = relation.target.id
    elif target_type is Resource:
        form_class = MetadatumResourceForm
        initial_data = relation.target.id
    elif target_type is Type:
        form_class = MetadatumTypeForm
        initial_data = relation.target.id
    else:
        form_class = MetadatumValueTextAreaForm

    if request.method == 'GET':
        form_data = {'value': initial_data}
        if target_class is not None:
            form_data.update({'target_class': target_class})
        form = form_class(form_data)

    elif request.method == 'POST':
        form = form_class(request.POST)
        if form.is_valid():
            if target_class is not None:
                if target_class in ['Int', 'Float', 'Datetime', 'Date', 'Text']:
                    val = Value.objects.create()
                    val.name = form.cleaned_data['value']
                    relation.target = val
                else:
                    relation.target = form.cleaned_data['value']
                relation.save()
            elif target_type is Value:
                relation.target.name = form.cleaned_data['value']
                relation.target.save()
            elif target_type in [ConceptEntity, Resource, Type]:
                relation.target = form.cleaned_data['value']
            else:
                val = Value.objects.create()
                val.name = form.cleaned_data['value']
                relation.target = val
                relation.save()
            relation.target.save()

            if on_valid:
                return HttpResponseRedirect(on_valid + '?tab=metadata')
            return HttpResponseRedirect(reverse('edit-resource-details', args=(resource.id,)) + '?tab=metadata')

    context.update({'form': form})
    return HttpResponse(template.render(context))


@login_required
def edit_resource_details(request, resource_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    try:
        check_authorization(request, resource, 'edit_resource')
    except RuntimeError:
        return HttpResponse('You do not have permission to view this resource', status=401)
    context = RequestContext(request, {'resource': resource,})
    template = loader.get_template('edit_resource_details.html')

    context.update({'tab': request.GET.get('tab', 'details')})
    on_valid = request.GET.get('next', None)
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

        # formset = MetadataFormSet(initial=[{
        #     'field': relation.predicate,
        #     'value': relation.target.name,
        #     'relation_id': relation.id,
        #     'value_instance_id': relation.target.id,
        #     'value_content_type_id': ContentType.objects.get_for_model(relation.target.__class__).id
        # } for relation in resource.relations_from.all()], prefix='metadata')


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
        'metadata': resource.relations_from.filter(is_deleted=False),
        'resource': resource,
        'pages': resource.relations_from.filter(predicate_id=page_field.id),
    })
    return HttpResponse(template.render(context))


def list_metadata(request):
    """
    Users should be able to search/filter for metadata entries by subject,
    predicate, and/or object.
    """
    source = request.GET.get('source', None)
    predicate = request.GET.get('predicate', None)
    target = request.GET.get('target', None)
    offset = int(request.GET.get('offset', 0))
    size = int(request.GET.get('size', 20))
    qs = metadata.filter_relations(source=source if source else None,
                                   predicate=predicate if predicate else None,
                                   target=target if target else None)
    max_results = qs.count()
    current_path = request.get_full_path().split('?')[0]
    params = request.GET.copy()
    if 'offset' in params:
        del params['offset']
    base_path = current_path + '?' + params.urlencode()
    previous_offset = offset - size if offset - size >= 0 else -1
    next_offset = offset + size if offset + size < max_results else None

    context = RequestContext(request, {
        'relations': qs[offset:offset+size],
        'source': source,
        'predicate': predicate,
        'target': target,
        'offset': offset,
        'first_result': offset + 1,
        'last_result': min(offset + size, max_results),
        'next_url': base_path + '&offset=%i' % next_offset if next_offset else None,
        'previous_url': base_path + '&offset=%i' % previous_offset if previous_offset >= 0 else None,
        'size': size,
        'max_results': max_results,
    })
    template = loader.get_template('list_metadata.html')
    return HttpResponse(template.render(context))


def entity_details(request, entity_id):
    entity = get_object_or_404(ConceptEntity, pk=entity_id)
    template = loader.get_template('entity_details.html')
    context = RequestContext(request, {
        'user_can_edit': request.user.is_staff,    # TODO: change this!
        'entity': entity,
        'similar_entities': ConceptEntity.objects.filter(name__icontains=entity.name).filter(~Q(id=entity.id)),
    })
    return HttpResponse(template.render(context))


def entity_list(request):
    template = loader.get_template('entity_list.html')
    filtered_objects = ConceptEntityFilter(request.GET, queryset=ConceptEntity.objects.all())

    context = RequestContext(request, {
        'user_can_edit': request.user.is_staff,    # TODO: change this!
        'filtered_objects': filtered_objects,
    })
    return HttpResponse(template.render(context))



@authorization.authorization_required('view_authorizations', _get_resource_by_id)
def resource_authorization_list(request, resource_id):
    """
    Display permissions for a specific resource.
    """

    resource = get_object_or_404(Resource, pk=resource_id)
    can_change = authorization.check_authorization('change_authorizations', request.user, resource)

    context = RequestContext(request, {
        'can_change': can_change,
        'resource': resource,
        'authorizations': authorization.list_authorizations(resource),
    })
    template = loader.get_template('resource_authorization_list.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('change_authorizations', _get_resource_by_id)
def resource_authorization_create(request, resource_id):
    """
    Allow the user to add authorizations for a new user.

    This is kind of hacky, but will do for now.
    """

    resource = get_object_or_404(Resource, pk=resource_id)
    authorized_users = zip(*authorization.list_authorizations(resource))[0]
    authorized_users_ids = [user.id for user in authorized_users]
    unauthorized_users = User.objects.filter(~Q(pk__in=authorized_users_ids)).order_by('username')

    context = RequestContext(request, {
        'unauthorized_users': unauthorized_users,
        'resource': resource,
    })
    template = loader.get_template('resource_authorization_create.html')
    return HttpResponse(template.render(context))



@authorization.authorization_required('change_authorizations', _get_resource_by_id)
def resource_authorization_change(request, resource_id, user_id):
    """
    Change permissions on a resource for a specific user.
    """
    resource = get_object_or_404(Resource, pk=resource_id)
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'GET':
        form = AuthorizationForm(initial={
            'for_user': user,
            'authorizations': authorization.list_authorizations(resource, user)
        })
    elif request.method == 'POST':
        form = AuthorizationForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('for_user') != user:
                raise RuntimeError('Whoops, someone f***ed with the user.')

            authorization.update_authorizations(
                form.cleaned_data.get('authorizations'),
                form.cleaned_data.get('for_user'),
                resource,
            )
            return HttpResponseRedirect(reverse('resource-authorization-list', args=(resource.id,)))

    form.fields['for_user'].widget = forms.HiddenInput()
    context = RequestContext(request, {
        'for_user': user,
        'resource': resource,
        'form': form,
    })
    template = loader.get_template('resource_authorization_change.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('view_authorizations', _get_collection_by_id)
def collection_authorization_list(request, collection_id):
    """
    Display permissions for a specific :class:`.Collection` instance.
    """

    collection = get_object_or_404(Collection, pk=collection_id)
    can_change = authorization.check_authorization('change_authorizations', request.user, collection)

    context = RequestContext(request, {
        'can_change': can_change,
        'collection': collection,
        'authorizations': authorization.list_authorizations(collection),
    })
    template = loader.get_template('collection_authorization_list.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('change_authorizations', _get_collection_by_id)
def collection_authorization_change(request, collection_id, user_id):
    """
    Change permissions on a resource for a specific user.
    """
    collection = get_object_or_404(Collection, pk=collection_id)
    user = get_object_or_404(User, pk=user_id)

    if request.method == 'GET':
        form = CollectionAuthorizationForm(initial={
            'for_user': user,
            'authorizations': authorization.list_authorizations(collection, user)
        })
    elif request.method == 'POST':
        form = CollectionAuthorizationForm(request.POST)
        if form.is_valid():
            if form.cleaned_data.get('for_user') != user:
                raise RuntimeError('Whoops, someone f***ed with the user.')

            authorizations = form.cleaned_data.get('authorizations')
            for_user = form.cleaned_data.get('for_user')
            authorization.update_authorizations(
                authorizations, for_user, collection,
            )
            resource_auths = [auth.replace('collection', 'resource')
                              for auth in authorizations]
            for resource in collection.resources.all():
                authorization.update_authorizations(resource_auths, for_user, resource)

            return HttpResponseRedirect(reverse('collection-authorization-list', args=(collection.id,)))

    form.fields['for_user'].widget = forms.HiddenInput()
    context = RequestContext(request, {
        'for_user': user,
        'collection': collection,
        'form': form,
    })
    template = loader.get_template('collection_authorization_change.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('change_authorizations', _get_collection_by_id)
def collection_authorization_create(request, collection_id):
    """
    Allow the user to add authorizations for a new user.

    This is kind of hacky, but will do for now.
    """

    collection = get_object_or_404(Collection, pk=collection_id)
    authorized_users = zip(*authorization.list_authorizations(collection))[0]
    authorized_users_ids = [user.id for user in authorized_users]
    unauthorized_users = User.objects.filter(~Q(pk__in=authorized_users_ids)).order_by('username')

    context = RequestContext(request, {
        'unauthorized_users': unauthorized_users,
        'collection': collection,
    })
    template = loader.get_template('collection_authorization_create.html')
    return HttpResponse(template.render(context))


# Authorization is handled internally.
def entity_merge(request):
    entity_ids = request.GET.getlist('entity', [])
    if len(entity_ids) <= 1:
        raise ValueError('')

    qs = ConceptEntity.objects.filter(pk__in=entity_ids)
    q = authorization.get_auth_filter('merge_conceptentities', request.user)
    if qs.filter(q).count() > 0 and not request.user.is_superuser:
        # TODO: make this pretty and informative.
        return HttpResponseForbidden('Only the owner can do that')

    if request.GET.get('confirm', False) == 'true':
        master_id = request.GET.get('master', None)
        master = operations.merge_conceptentities(qs, master_id)
        return HttpResponseRedirect(reverse('entity-details', args=(master.id,)))

    context = RequestContext(request, {
        'entities': qs,
    })
    template = loader.get_template('entity_merge.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('is_owner', _get_entity_by_id)
def entity_change(request, entity_id):
    """
    Edit a :class:`.ConceptEntity` instance.
    """
    entity = _get_entity_by_id(request, entity_id)

    if request.method == 'GET':
        form = ConceptEntityForm(instance=entity)

    if request.method == 'POST':
        form = ConceptEntityForm(request.POST, instance=entity)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(entity.get_absolute_url())

    context = RequestContext(request, {
        'entity': entity,
        'form': form,
    })
    template = loader.get_template('entity_change.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('is_owner', _get_entity_by_id)
def entity_change_concept(request, entity_id):
    entity = _get_entity_by_id(request, entity_id)
    if request.method == 'GET':
        initial_data = {}
        if entity.concept:
            initial_data.update({'uri': entity.concept.uri})
        form = ConceptEntityLinkForm(initial_data)    # Not a ModelForm.

    if request.method == 'POST':
        form = ConceptEntityLinkForm(request.POST)
        if form.is_valid():
            uri = form.cleaned_data.get('uri')
            try:
                concept, _ = Concept.objects.get_or_create(uri=uri)
            except ValueError as E:
                errors = form._errors.setdefault("uri", ErrorList())
                errors.append(E.args[0])
                concept = None

            if concept:
                entity.concept = concept
                entity.save()
                return HttpResponseRedirect(entity.get_absolute_url())

    context = RequestContext(request, {
        'entity': entity,
        'form': form,
    })
    print form
    template = loader.get_template('entity_change_concept.html')
    return HttpResponse(template.render(context))


@authorization.authorization_required('change_resource', _get_resource_by_id)
def resource_prune(request, resource_id):
    """
    Curator can remove duplicate :class:`.Relation`\s from a
    :class:`.Resource`\.
    """
    resource = _get_resource_by_id(request, resource_id)
    operations.prune_relations(resource)
    return HttpResponseRedirect(resource.get_absolute_url())


def resource_merge(request):
    """
    Curator can merge resources.
    """
    resource_ids = request.GET.getlist('resource', [])
    if len(resource_ids) <= 1:
        raise ValueError('Need more than one resource')

    qs = Resource.objects.filter(pk__in=resource_ids)
    q = authorization.get_auth_filter('merge_resources', request.user)
    if qs.filter(q).count() > 0 and not request.user.is_superuser:
        # TODO: make this pretty and informative.
        return HttpResponseForbidden('Only the owner can do that')

    if request.GET.get('confirm', False) == 'true':
        master_id = request.GET.get('master', None)
        master = operations.merge_resources(qs, master_id)
        return HttpResponseRedirect(master.get_absolute_url())

    context = RequestContext(request, {
        'resources': qs,
    })
    template = loader.get_template('resource_merge.html')
    return HttpResponse(template.render(context))
