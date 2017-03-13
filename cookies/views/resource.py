from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404

from cookies.models import *
from cookies.filters import *
from cookies.forms import *
from cookies.tasks import *
from cookies import giles, operations
from cookies import authorization as auth

import hmac, base64, time, urllib, datetime, mimetypes


def _get_resource_by_id(request, resource_id, *args):
    return get_object_or_404(Resource, pk=resource_id)


@auth.authorization_required(ResourceAuthorization.VIEW, _get_resource_by_id)
def resource(request, obj_id):
    """
    Display the resource with the given id
    """

    resource = _get_resource_by_id(request, obj_id)

    # Get a fresh Giles auth token, if needed.
    giles.get_user_auth_token(resource.created_by, fresh=True)
    context = {
        'resource':resource,
        'request': request,
        'part_of': resource.container.part_of,
        'relations_from': resource.relations_from.filter(is_deleted=False)
    }
    if request.GET.get('format', None) == 'json':
        return JsonResponse(ResourceDetailSerializer(context=context).to_representation(resource))
    return render(request, 'resource.html', context)


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
    """
    Display all :class:`.Resource` instances to which the user has access.
    """

    resources = auth.apply_filter(ResourceAuthorization.VIEW, request.user,
                                  ResourceContainer.active.all())

    predicate_ids = request.GET.getlist('predicate')
    target_ids = request.GET.getlist('target')
    target_type_ids = request.GET.getlist('target_type')

    if predicate_ids and target_ids and target_type_ids:
        for p, t, y in zip(predicate_ids, target_ids, target_type_ids):
            resources = resources.filter(
                primary__relations_from__predicate_id=p,
                primary__relations_from__target_instance_id=t,
                primary__relations_from__target_type_id=y
            )
    # For now we use filters to achieve search functionality. At some point we
    #  should use a real search backend.
    #
    # TODO: implement a real search backend.
    filtered_resources = ResourceContainerFilter(request.GET, queryset=resources)
    tags = filtered_resources.qs.order_by('primary__tags__tag__id')\
            .values_list('primary__tags__tag__id', 'primary__tags__tag__name')\
            .distinct('primary__tags__tag__id')

    context = {
        'filtered_objects': filtered_resources,
        'tags': filter(lambda tag: tag[0] is not None, tags),
    }
    return render(request, 'resources.html', context)


@login_required
def create_resource(request):
    context = {
        'giles_upload_location': '/'.join([settings.GILES, 'files', 'upload'])
    }

    return render(request, 'create_resource.html', context)


@login_required
def create_resource_file(request):
    context = {}

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
    return render(request, 'create_resource_file.html', context)


@login_required
def create_resource_url(request):
    context = {}

    if request.method == 'GET':
        form = UserResourceURLForm()

    elif request.method == 'POST':
        form = UserResourceURLForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data.get('url')
            exists, headers = operations.ping_remote_resource(url)
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
    return render(request, 'create_resource_url.html', context)


@login_required
def create_resource_details(request, content_id):
    content_resource = get_object_or_404(Resource, pk=content_id)
    context = {}
    if request.method == 'GET':
        form = UserResourceForm(initial={
            'name': content_resource.name,
            'uri': content_resource.location,
            'public': True,    # If the resource is already online, it's public.
        })
        form.fields['collection'].queryset = auth.apply_filter(*(
            CollectionAuthorization.ADD,
            request.user,
            form.fields['collection'].queryset
        ))
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
            container = ResourceContainer.objects.create(created_by=request.user, primary=resource, part_of=collection)

            operations.add_creation_metadata(resource, request.user)
            content_relation = ContentRelation.objects.create(**{
                'for_resource': resource,
                'content_resource': content_resource,
                'content_type': content_resource.content_type,
            })
            resource.container = container
            resource.save()
            content_resource.container = container
            content_resource.save()

            return HttpResponseRedirect(reverse('resource', args=(resource.id,)))

    context.update({
        'form': form,
        'content_resource': content_resource,
    })

    template = 'create_resource_details.html'

    return render(request, template, context)


@login_required
def create_resource_choose_giles(request):
    """
    Directs to US or DE servers.

    """
    # TODO: implement flag for bulk vs. single.
    context = {}

    template = 'create_resource_choose_giles.html'

    return render(request, template, context)


@login_required
def create_resource_bulk(request):
    """
    Zotero bulk upload.
    """

    context = {}
    if request.method == 'GET':
        form = BulkResourceForm()
        qs = form.fields['collection'].queryset
        form.fields['collection'].queryset = auth.apply_filter(*(
            CollectionAuthorization.ADD,
            request.user,
            form.fields['collection'].queryset
        ))
    elif request.method == 'POST':
        form = BulkResourceForm(request.POST, request.FILES)
        qs = form.fields['collection'].queryset
        form.fields['collection'].queryset = auth.apply_filter(*(
            CollectionAuthorization.ADD,
            request.user,
            form.fields['collection'].queryset
        ))
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
                form.add_error('upload_file',
                               'Not a valid RDF document or ZIP archive.')
            else:
                job = UserJob.objects.create(**{
                    'created_by': request.user,
                })
                result = handle_bulk.delay(file_path, safe_data, file_name, job)
                return HttpResponseRedirect(reverse('job-status', args=(result.id,)))


    template = 'create_resource_bulk.html'
    context.update({'form': form})
    return render(request, template, context)




@auth.authorization_required(ResourceAuthorization.EDIT, _get_resource_by_id)
def delete_resource_metadatum(request, resource_id, relation_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    relation = get_object_or_404(Relation, pk=relation_id)
    delete = request.GET.get('delete', False)
    if delete == 'confirm':
        relation.is_deleted = True
        relation.save()
        return HttpResponseRedirect(reverse('edit-resource-details', args=(resource.id,)) + '?tab=metadata')

    context = {
        'resource': resource,
        'relation': relation,
    }
    template = 'delete_resource_metadatum.html'

    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_resource_by_id)
def create_resource_metadatum(request, resource_id):
    resource = get_object_or_404(Resource, pk=resource_id)

    if request.method == 'POST':
        form = MetadatumForm(request.POST)
        if form.is_valid():
            predicate = form.cleaned_data['predicate']
            target_class = form.cleaned_data['value_type']
            relation = Relation.objects.create(
                source=resource,
                predicate=predicate,
                container = resource.container,
            )
            return HttpResponseRedirect(reverse('edit-resource-metadatum', args=(resource.id, relation.id)) + '?target_class=' + target_class)
    else:
        form = MetadatumForm()
    context = {
        'resource': resource,
        'form': form,
    }
    template = 'create_resource_metadatum.html'

    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_resource_by_id)
def edit_resource_metadatum(request, resource_id, relation_id):
    resource = get_object_or_404(Resource, pk=resource_id)
    relation = get_object_or_404(Relation, pk=relation_id)
    if request.method == 'GET':
        target_class = request.GET.get('target_class', None)
    else:
        target_class = request.POST.get('target_class', None)

    context = {
        'resource': resource,
        'relation': relation,
    }
    template = 'edit_resource_metadatum.html'
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
            if not relation.target.container:
                relation.target.container = resource.container
            relation.target.save()

            if on_valid:
                return HttpResponseRedirect(on_valid + '?tab=metadata')
            return HttpResponseRedirect(reverse('edit-resource-details', args=(resource.id,)) + '?tab=metadata')

    context.update({'form': form})
    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_resource_by_id)
def edit_resource_details(request, resource_id):
    resource = get_object_or_404(Resource, pk=resource_id)

    context = {'resource': resource,}
    template = 'edit_resource_details.html'

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
    return render(request, template, context)


def resource_merge(request):
    """
    Curator can merge resources.
    """
    resource_ids = request.GET.getlist('resource', [])
    if len(resource_ids) <= 1:
        raise ValueError('Need more than one resource')

    qs = Resource.objects.filter(pk__in=resource_ids)
    qs = auth.apply_filter(ResourceAuthorization.EDIT, request.user, qs)
    if qs.count() == 0:
        # TODO: make this pretty and informative.
        return HttpResponseForbidden('Only the owner can do that')

    if request.GET.get('confirm', False) == 'true':
        master_id = request.GET.get('master', None)
        master = operations.merge_resources(qs, master_id, user=request.user)
        return HttpResponseRedirect(master.get_absolute_url())

    context = {
        'resources': qs,
    }
    template = 'resource_merge.html'
    return render(request, template, context)




@login_required
def bulk_action_resource(request):
    """
    Curator can perform actions with resources selected.
    Input from user- Set of resources.
    On POST, User is presented with a set of collections to choose from.
    """
    resource_ids = request.POST.getlist('addresources', [])
    return HttpResponseRedirect(reverse('bulk-add-tag-to-resource') + "?" + '&'.join(["resource=%s" % r_id for r_id in resource_ids]))


@login_required
def bulk_add_tag_to_resource(request):
    """
    Adding tag to selected resources.
    """
    if request.method == 'GET':
        resource_ids = request.GET.getlist('resource', [])
        resources = auth.apply_filter(ResourceAuthorization.EDIT, request.user,
                                      Resource.objects.filter(pk__in=resource_ids))

        form = AddTagForm()
        form.fields['resources'].queryset = resources
        form.fields['resources'].initial = resources

    elif request.method == 'POST':
        form = AddTagForm(request.POST)
        resource_ids = eval(request.POST.get('resources', '[]'))
        resources = auth.apply_filter(ResourceAuthorization.EDIT, request.user, Resource.objects.filter(pk__in=resource_ids))

        if form.is_valid():
            tag = form.cleaned_data.get('tag', None)
            tag_name = form.cleaned_data.get('tag_name', None)
            resources = form.cleaned_data.get('resources')
            if not tag and tag_name:
                tag = Tag.objects.create(name=tag_name, created_by=request.user)
            ResourceTag.objects.bulk_create([
                ResourceTag(resource=resource, tag=tag, created_by=request.user)
                for resource in resources
            ])
            return HttpResponseRedirect(reverse('resources'))
    context = {
        'form': form,
        'resources': resources,
    }
    template = 'add_tag_to_resource.html'
    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.VIEW, _get_resource_by_id)
def resource_content(request, resource_id):
    """
    Serve up the raw content associated with a :class:`.Resource`\.

    This is not the most efficient way to serve files, but we need some kind of
    security layer here for non-public content.
    """
    resource = _get_resource_by_id(request, resource_id)
    if resource.content_type:
        content_type = resource.content_type
    else:
        content_type = 'application/octet-stream'

    if resource.file:
        try:
            with open(resource.file.path, 'rb') as f:
                return HttpResponse(f.read(), content_type=content_type)
        except IOError:    # Whoops....
            return HttpResponse('Hmmm....something went wrong.')
    elif resource.location:
        target = resource.location
        if 'giles' in target:
            user = resource.created_by

            if user:
                auth_token = giles.get_user_auth_token(user, fresh=True)
                target += '?accessToken=' + auth_token
        return HttpResponseRedirect(target)
    return HttpResponse('Nope')



@auth.authorization_required(ResourceAuthorization.EDIT, _get_resource_by_id)
def resource_prune(request, resource_id):
    """
    Curator can remove duplicate :class:`.Relation` instances from a
    :class:`.Resource` instance.
    """
    resource = _get_resource_by_id(request, resource_id)
    operations.prune_relations(resource, request.user)
    return HttpResponseRedirect(resource.get_absolute_url())


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
