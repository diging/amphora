from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, HttpResponse, QueryDict

from django.shortcuts import render, get_object_or_404

from cookies.models import *
from cookies.filters import *
from cookies.forms import *
from cookies import authorization as auth
from django.utils.http import urlquote_plus
from itertools import groupby


def _get_collection_by_id(request, collection_id, *args):
    return get_object_or_404(Collection, pk=collection_id)


def collection_list(request):
    """
    Display the set of collections
    """

    queryset = Collection.objects.filter(content_resource=False, hidden=False, part_of__isnull=True)

    queryset = auth.apply_filter(ResourceAuthorization.VIEW, request.user, queryset)
    filtered_objects = CollectionFilter(request.GET, queryset=queryset)
    context = {
        'filtered_objects': filtered_objects,
    }

    return render(request, 'collections.html', context)


@auth.authorization_required(CollectionAuthorization.SHARE, _get_collection_by_id)
def collection_authorizations(request, collection_id):
    """
    Display the authorization policies for a :class:`.Collection`\.
    """

    collection = get_object_or_404(Collection, pk=collection_id)
    _key = lambda auth: auth.granted_to
    auths = groupby(sorted(auth.list_authorizations(collection), key=_key), key=_key)
    auths = [{'user': user, 'auths': list(_auths)} for user, _auths in auths]

    context = {
        'authorizations': auths,
        'collection': collection,
    }
    return render(request, 'collection_authorizations.html', context)

@auth.authorization_required(CollectionAuthorization.SHARE, _get_collection_by_id)
def collection_authorization_remove(request, collection_id, auth_id):
    """
    Remove an auth.
    """
    CollectionAuthorization.objects.filter(pk=auth_id).delete()
    return HttpResponseRedirect(reverse('collection-authorizations', args=(collection_id,)))


@auth.authorization_required(CollectionAuthorization.SHARE, _get_collection_by_id)
def collection_authorization_create(request, collection_id):
    """
    Create a new auth.
    """

    collection = get_object_or_404(Collection, pk=collection_id)

    if request.method == 'GET':
        form = auth.CollectionAuthorizationForm()
        form.fields['for_resource'].initial = collection_id
        form.fields['granted_by'].initial = request.user.id


    elif request.method == 'POST':
        form = auth.CollectionAuthorizationForm(request.POST)
        # form.fields['for_resource'].initial = collection_id
        # form.fields['granted_by'].initial = request.user.id

        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('collection-authorizations', args=(collection.id,)))

    context = {
        'form': form,
        'collection': collection,
    }
    return render(request, 'collection_authorization_create.html', context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_collection_by_id)
def collection_edit(request, obj_id):
    collection = _get_collection_by_id(request, obj_id)
    if request.method == 'GET':
        form = CollectionForm(instance=collection)
    elif request.method == 'POST':
        form = CollectionForm(request.POST, instance=collection)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('collection', args=(obj_id,)))
    context = {'form': form, 'collection': collection}
    return render(request, 'collection_edit.html', context)



@auth.authorization_required(ResourceAuthorization.VIEW, _get_collection_by_id)
def collection(request, obj_id):
    """
    Display the collection for the given id
    """

    collection = _get_collection_by_id(request, obj_id)

    resources = ResourceContainerFilter(request.GET, queryset=collection.resourcecontainer_set.all())

    # CollectionFilter(request.GET, queryset=qset_collections)
    collections = Collection.objects.filter(part_of=collection, hidden=False)
    params = QueryDict(request.GET.urlencode(), mutable=True)
    params['part_of'] = collection.id
    filter_parameters = urlquote_plus(params.urlencode())
    context = {
        'filtered_objects': resources,
        # 'filtered_objects': filtered_objects,
        'collection': collection,
        'request': request,
        'collections': collections,
        'filter_parameters': filter_parameters
        # 'tags': Tag.objects.filter(resource_tags__resource_id__in=filtered_objects.qs.values_list('id', flat=True)).distinct(),
    }

    return render(request, 'collection.html', context)


@login_required
def create_collection(request):
    """
    Curator can add collection.
    """
    context = {}

    parent_id = request.GET.get('parent_collection', None)
    template = 'create_collection.html'

    if request.method == 'GET':
        form = CollectionForm()
        form.fields['part_of'].queryset = auth.apply_filter(CollectionAuthorization.EDIT, request.user, form.fields['part_of'].queryset)
        if parent_id:
            parent_collection = _get_collection_by_id(request, int(parent_id))
            check_auth = auth.check_authorization(CollectionAuthorization.EDIT, request.user, parent_collection)
            if not check_auth:
                return HttpResponse('You do not have permission to edit this collection', status=401)
            form.fields['part_of'].initial = parent_collection

    if request.method == 'POST':
        form = CollectionForm(request.POST)
        form.fields['part_of'].queryset = auth.apply_filter(CollectionAuthorization.EDIT, request.user, form.fields['part_of'].queryset)

        if form.is_valid():

            form.instance.created_by = request.user
            instance = form.save()
            parent = form.cleaned_data.get('part_of')
            if parent:
                instance.part_of = parent
                instance.save()

            if form.cleaned_data.get('public'):
                CollectionAuthorization.objects.create(
                    for_resource = instance,
                    granted_by = request.user,
                    granted_to = None,
                    heritable = True,
                    policy = CollectionAuthorization.ALLOW,
                    action = CollectionAuthorization.VIEW
                )
            return HttpResponseRedirect(form.instance.get_absolute_url())

    context.update({
        'form': form
    })
    return render(request, template, context)



@auth.authorization_required(CollectionAuthorization.VIEW, _get_collection_by_id)
def export_coauthor_data(request, collection_id):
    """
    Exporting coauthor data from a collection detail view
    Parameters
    ----------
    collection_id : int
        The primary key of the :class:`.Collection` to use for the
        extraction of coauthor data.

    Returns
    -------
    A graphml file for the user to download
    """
    import networkx as nx

    context = {}

    if not collection_id:
        return HttpResponse('There is no collection selected for exporting coauthor data', status=401)

    # Prefetching resources and relations from collection db
    try:
        collection = Collection.objects.prefetch_related('resourcecontainer_set__primary__relations_from').get(id=collection_id)
    except Collection.DoesNotExist:
        return HttpResponse('There is no collection with the given id', status=404)

    # TODO: should only be able to use resources to which the user has access.
    try:
        graph = operations.generate_collection_coauthor_graph(collection)
    except RuntimeError:
        return HttpResponse('Invalid collection given to export co-author data', status=404)

    if graph.order() == 0:
        return HttpResponse('There are no author relations in the collection to\
                            extract co-author data', status=200)

    # Graphml file for the user to download
    time_now = '{:%Y-%m-%d%H:%M:%S}'.format(datetime.datetime.now())
    file_name = collection.name + time_now + ".graphml"
    nx.write_graphml(graph, file_name.encode('utf-8'))

    file = open(file_name.encode('utf-8'), 'r')
    response = HttpResponse(file.read(), content_type='application/graphml')
    response['Content-Disposition'] = 'attachment; filename="%s"' %file_name

    return response
