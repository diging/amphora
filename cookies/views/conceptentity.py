from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404

from cookies.models import *
from cookies.filters import *
from cookies import authorization as auth


def _get_entity_by_id(request, entity_id, *args):
    return get_object_or_404(ConceptEntity, pk=entity_id)


@auth.authorization_required(ResourceAuthorization.VIEW, _get_entity_by_id)
def entity_details(request, entity_id):
    entity = _get_entity_by_id(request, entity_id)
    template = 'entity_details.html'
    similar_entities = entities.suggest_similar(entity, qs=auth.apply_filter(ResourceAuthorization.EDIT, request.user, ConceptEntity.objects.all()))

    relations_from = entity.relations_from.all()
    relations_from = [(g[0].predicate, g) for g in metadata.group_relations(relations_from)]
    relations_to = entity.relations_to.all()
    relations_to = [(g[0].predicate, g) for g in metadata.group_relations(relations_to)]

    represents = entity.represents.values_list('entities__id', 'entities__name').distinct()
    represented_by = entity.identities.filter(~Q(representative=entity)).values_list('representative_id', 'representative__name').distinct()

    context = {
        'user_can_edit': request.user.is_staff,    # TODO: change this!
        'entity': entity,
        'similar_entities': similar_entities,
        'entity_type': ContentType.objects.get_for_model(ConceptEntity),
        'relations_from': relations_from,
        'relations_to': relations_to,
        'represents': represents,
        'represented_by': represented_by
    }
    return render(request, template, context)


def entity_list(request):
    """
    List view for :class:`.ConceptEntity`\.
    """
    qs = ConceptEntity.active.all()
    qs = qs.filter(Q(identities__isnull=True) | Q(represents__isnull=False))
    qs = auth.apply_filter(ResourceAuthorization.VIEW, request.user, qs)

    filtered_objects = ConceptEntityFilter(request.GET, queryset=qs)

    context = {
        'user_can_edit': request.user.is_staff,    # TODO: change this!
        'filtered_objects': filtered_objects,
    }
    return render(request, 'entity_list.html', context)





# Authorization is handled internally.
def entity_merge(request):
    """
    User can merge selected entities.
    """

    entity_ids = request.GET.getlist('entity', [])
    if len(entity_ids) <= 1:
        raise ValueError('')

    qs = ConceptEntity.objects.filter(pk__in=entity_ids)
    qs = auth.apply_filter(ResourceAuthorization.EDIT, request.user, qs)
    # q = auth.get_auth_filter('merge_conceptentities', request.user)
    if qs.count() < 2:
        # TODO: make this pretty and informative.
        return HttpResponseForbidden('Only the owner can do that')

    if request.GET.get('confirm', False) == 'true':
        master_id = request.GET.get('master', None)
        master = operations.merge_conceptentities(qs, master_id, user=request.user)
        return HttpResponseRedirect(reverse('entity-details', args=(master.id,)))

    context = {
        'entities': qs,
    }
    template = 'entity_merge.html'
    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_entity_by_id)
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

    context = {
        'entity': entity,
        'form': form,
    }
    template = 'entity_change.html'
    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_entity_by_id)
def entity_change_concept(request, entity_id):
    entity = _get_entity_by_id(request, entity_id)
    concepts = None
    if request.method == 'GET':
        initial_data = {}
        if entity.concept:
            initial_data.update({'uri': entity.concept.uri})
        if initial_data:
            form = ConceptEntityLinkForm(initial_data)    # Not a ModelForm.
        else:
            form = ConceptEntityLinkForm()

    if request.method == 'POST':
        #If the save button is clicked on the html page, the URI is obtained
        # from the text field and Concept object is created to be linked with
        # the entity.
        if 'save' in request.POST:
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

        #If the search button is clicked on the html page, the query text is
        # obtained and concept URIs are searched for. The results are displayed
        # on the html page.
        if 'search' in request.POST:
            print '::: search :::'
            form = ConceptEntityLinkForm(request.POST)
            search = ''
            if form.is_valid():
                print form.cleaned_data
                search = form.cleaned_data.get('search_input')

            try:
                #URIs are searched based on the input provided using BlackGoat API.
                concepts = operations.concept_search(search)
            except Exception as E:
                return HttpResponse(E,status=500)

    context = {
        'entity': entity,
        'form': form,
        'concepts_data': concepts,
    }

    template = 'entity_change_concept.html'
    return render(request, template, context)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_entity_by_id)
def entity_prune(request, entity_id):
    """
    Curator can remove duplicate :class:`.Relation` instances from a
    :class:`.ConceptEntity` instance.
    """
    entity = _get_entity_by_id(request, entity_id)
    operations.prune_relations(entity, request.user)
    return HttpResponseRedirect(entity.get_absolute_url())
