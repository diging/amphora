from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.conf import settings
from django.db.models import Q

from cookies import operations
from cookies import authorization as auth
from cookies.models import *
from cookies.forms import ChooseCollectionForm, GilesLogForm
from cookies import giles
from cookies.filters import GilesUploadFilter


def _get_upload_by_id(request, upload_id, *args):
    return get_object_or_404(GilesUpload, pk=upload_id)


@login_required
def handle_giles_upload(request):
    """
    If the user uploaded a file directly through Giles, they may be redirected
    to Amphora to enter metadata. In that case, we don't yet know about this
    upload, and will need to create new resources from scratch.
    """
    upload_ids = request.GET.getlist('uploadids') + request.GET.getlist('uploadIds')
    if not upload_ids:
        raise RuntimeError('Seriously??')   # TODO: something more informative.

    for uid in upload_ids:
        tasks.check_giles_upload.delay(upload_id, request.user.username)

    _tail = '&'.join(['upload_id=%s' % uid for uid in upload_ids])
    return HttpResponseRedirect(reverse('giles-upload-status') + _tail)


@login_required
def giles_upload_status(request):
    """
    Display the current state of one or several :class:`.GilesUpload`\s.
    """
    upload_ids = request.GET.getlist('upload_id')
    context = {
        'uploads': [GilesUpload.objects.get(pk=uid) for uid in upload_ids]
    }
    return render(request, 'giles_upload_status.html', context)


@login_required
def set_giles_upload_collection(request, upload_id):
    """
    User can add a resource created from a :class:`.GilesUpload` to a
    :class:`.Collection`\.
    """
    upload = get_object_or_404(GilesUpload, upload_id=upload_id)
    if not upload.state == GilesUpload.DONE:
        raise RuntimeError('Not ready')
    if not upload.resource:
        raise RuntimeError('No resource')
    if upload.created_by != request.user:
        raise RuntimeError('WTF')    # TODO: say something more informative.

    context = {'upload': upload,}

    if request.method == 'GET':
        form = ChooseCollectionForm()

        # User can only add resources to collections for which they have ADD
        #  privileges.
        qs = auth.apply_filter(CollectionAuthorization.ADD, request.user,
                               form.fields['collection'].queryset)
        form.fields['collection'].queryset = qs

    elif request.method == 'POST':
        form = ChooseCollectionForm(request.POST)

        # User can only add resources to collections for which they have ADD
        #  privileges.
        qs = auth.apply_filter(CollectionAuthorization.ADD, request.user,
                               form.fields['collection'].queryset)
        form.fields['collection'].queryset = qs

        if form.is_valid():
            collection = form.cleaned_data.get('collection', None)
            name = form.cleaned_data.get('name', None)

            # The user has the option to create a new Collection by leaving the
            #  collection field blank and providing a name.
            if collection is None and name is not None:
                collection = Collection.objects.create(**{
                    'created_by_id': request.user.id,
                    'name': name,
                })
                operations.add_creation_metadata(collection, request.user)
            form.fields['collection'].initial = collection.id
            form.fields['name'].widget.attrs['disabled'] = True

            upload.resource.container.part_of = collection
            upload.resource.container.save()

    context.update({'form': form})
    return render(request, 'create_process_giles_upload.html', context)


@auth.authorization_required(ResourceAuthorization.EDIT, lambda resource_id: get_object_or_404(Resource, pk=resource_id))
def trigger_giles_submission(request, resource_id, relation_id):
    """
    Manually start the Giles upload process.
    """
    resource = _get_resource_by_id(request, resource_id)
    instance = resource.content.get(pk=relation_id)
    import mimetypes
    content_type = instance.content_resource.content_type or mimetypes.guess_type(instance.content_resource.file.name)[0]
    if instance.content_resource.is_local and instance.content_resource.file.name is not None:
        # All files should be sent.
        upload_pk = giles.create_giles_upload(resource.id, instance.id,
                                              request.user.username,
                                              settings.DELETE_LOCAL_FILES)


@staff_member_required
def test_giles(request):
    return render(request, 'test_giles.html', {})


@staff_member_required
def test_giles_configuration(request):
    return JsonResponse({'giles_endpoint': settings.GILES, 'giles_token': settings.GILES_APP_TOKEN[:10] + '...'})


@staff_member_required
def test_giles_is_up(request):
    import requests
    giles = settings.GILES
    response = requests.head(giles)
    context = {
        'response_code': response.status_code,
    }
    return JsonResponse(context)


@staff_member_required
def test_giles_can_upload(request):
    """
    Send a test file to Giles.
    """
    from django.core.files import File
    import os


    user = request.user
    resource = Resource.objects.create(name='test resource', created_by=user)
    container = ResourceContainer.objects.create(primary=resource, created_by=user)
    resource.container = container
    resource.save()
    file_path = os.path.join(settings.MEDIA_ROOT, 'test.ack')
    with open(file_path, 'w') as f:
        test_file = File(f)
        test_file.write('this is a test file')

    with open(file_path, 'r') as f:
        test_file = File(f)
        content_resource = Resource.objects.create(content_resource=True, file=test_file, created_by=user, container=container)
    content_relation = ContentRelation.objects.create(for_resource=resource, content_resource=content_resource, created_by=user, container=container)

    upload_pk = giles.create_giles_upload(resource.id, content_relation.id,
                                       user.username,
                                       delete_on_complete=True)
    giles.send_giles_upload(upload_pk, user.username)
    upload = GilesUpload.objects.get(pk=upload_pk)

    context = {
        'status': upload.state,
        'upload_id': upload.upload_id,
        'container_id': container.id,
    }
    return JsonResponse(context)


@staff_member_required
def test_giles_can_poll(request):
    upload_id = request.GET.get('upload_id')
    try:
        giles.check_upload_status(request.user.username, upload_id)
    except giles.StatusException:
        return JsonResponse({'status': 'FAILED'})
    upload = GilesUpload.objects.get(upload_id=upload_id)
    context = {
        'status': upload.state,
    }
    return JsonResponse(context)


@staff_member_required
def test_giles_can_process(request):
    upload_id = request.GET.get('upload_id')
    giles.process_upload(upload_id, request.user.username)
    upload = GilesUpload.objects.get(upload_id=upload_id)
    context = {
        'status': upload.state,
    }
    return JsonResponse(context)


@staff_member_required
def test_giles_cleanup(request):
    upload_id = request.GET.get('upload_id')
    container_id = request.GET.get('container_id')
    container = ResourceContainer.objects.get(pk=container_id)
    container.relation_set.all().delete()
    container.resource_set.all().delete()
    container.delete()

    try:
        GilesUpload.objects.get(upload_id=upload_id).delete()
    except GilesUpload.DoesNotExist:
        pass
    return JsonResponse({'status': 'ok'})

def _reupload_resources(request, form_data, filtered_objects):
    upload_type = form_data.get('upload_type')
    if upload_type == GilesLogForm.UPLOAD_ALL:
        resources = filtered_objects.qs
    else:
        resources = form_data.get('resources')

    # FIXME: We don't want to reupload documents in Enqueued/Assigned/Sent
    # state.
    auth_resources = auth.apply_filter(
        ResourceAuthorization.EDIT,
        request.user,
        resources).filter(~Q(state__in=(GilesUpload.PENDING, GilesUpload.DONE)))

    context = {}
    count_resources = resources.count()
    count_success = 0
    if auth_resources.count() > 0:
        count_success = auth_resources.update(state=GilesUpload.PENDING)
        context.update({
            'reuploads_success': count_success,
        })

    if count_resources > 0:
        context.update({
            'reuploads_skipped': (count_resources - count_success),
        })
    return context

def _change_priority(request, form_data, filtered_objects):
    priority = form_data.get('priority')

    resources = form_data.get('resources')
    count_resources = resources.count()
    auth_resources = auth.apply_filter(
        ResourceAuthorization.EDIT,
        request.user,
        resources).filter(state=GilesUpload.PENDING)

    context = {}
    count_success = 0
    if auth_resources.count() > 0:
        count_success = auth_resources.update(priority=priority)
        context.update({
            'priority_change_success': count_success,
        })

    if count_resources > 0:
        context.update({
            'priority_change_skipped': (count_resources - count_success),
        })
    return context


@login_required
def log(request):

    # FIXME: We don't want upload enabled for Enqueued/Assigned/Sent state.
    upload_enabled = lambda f: True if filtered_objects.data['state'] not in (GilesUpload.PENDING, GilesUpload.DONE) else False

    priority_changeable = lambda f: True if filtered_objects.data['state'] == GilesUpload.PENDING else False
    if request.method == 'GET':
        qs = auth.apply_filter(ResourceAuthorization.VIEW, request.user,
                               GilesUpload.objects.all())
        filtered_objects = GilesUploadFilter(request.GET, queryset=qs)
        context = {
            'filtered_objects': filtered_objects,
            'form': GilesLogForm(),
            'upload_enabled': upload_enabled(filtered_objects),
            'priority_changeable': priority_changeable(filtered_objects),
        }
        return render(request, 'giles_log.html', context)

    elif request.method == 'POST':
        qs = auth.apply_filter(ResourceAuthorization.VIEW, request.user,
                               GilesUpload.objects.all())
        filtered_objects = GilesUploadFilter(request.GET, queryset=qs)
        form = GilesLogForm(request.POST, queryset=filtered_objects.qs)
        if form.is_valid():
            form_data = form.cleaned_data
            if form_data.get('priority'):
                context = _change_priority(request, form_data, filtered_objects)
            else:
                context = _reupload_resources(request, form_data, filtered_objects)

            qs = auth.apply_filter(ResourceAuthorization.VIEW, request.user,
                                   GilesUpload.objects.all())
            filtered_objects = GilesUploadFilter(request.GET, queryset=qs)
            context.update({
                'filtered_objects': filtered_objects,
                'form': GilesLogForm(),
                'upload_enabled': upload_enabled(filtered_objects),
                'priority_changeable': priority_changeable(filtered_objects),
            })
            return render(request, 'giles_log.html', context)
        else:
            context = {
                'filtered_objects': filtered_objects,
                'form': form,
                'upload_enabled': upload_enabled(filtered_objects),
                'priority_changeable': priority_changeable(filtered_objects),
            }
            return render(request, 'giles_log.html', context)


@auth.authorization_required(ResourceAuthorization.VIEW, _get_upload_by_id)
def log_item(request, upload_id):
    upload = get_object_or_404(GilesUpload, pk=upload_id)
    return render(request, 'giles_log_item.html', {'upload': upload})
