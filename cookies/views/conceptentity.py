from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404

from cookies.models import *
from concepts.models import *
from concepts import remote
from cookies.filters import *
from cookies.forms import *
from cookies import entities, metadata, operations
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
def entity_add_concept(request, entity_id):
    uri = request.GET.get('uri', None)
    label = request.GET.get('label', None)
    q = request.GET.get('q', '')
    if uri is not None:
        concept, _ = remote.get_or_create(uri)
        # concept, _ = Concept.objects.get_or_create(uri=uri, defaults={'label': label})
        entity = ConceptEntity.objects.get(pk=entity_id)
        entity.concept.add(concept)

    return HttpResponseRedirect(reverse('entity-change-concept', args=(entity_id,)) + '?q=%s' % q)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_entity_by_id)
def entity_remove_concept(request, entity_id):
    uri = request.GET.get('uri', None)
    q = request.GET.get('q', '')
    if uri is not None:
        concept = get_object_or_404(Concept, uri=uri)
        entity = ConceptEntity.objects.get(pk=entity_id)
        entity.concept.remove(concept)
    return HttpResponseRedirect(reverse('entity-change-concept', args=(entity_id,)) + '?q=%s' % q)


@auth.authorization_required(ResourceAuthorization.EDIT, _get_entity_by_id)
def entity_change_concept(request, entity_id):
    entity = _get_entity_by_id(request, entity_id)
    associated_concepts = entity.concept.values('uri', 'label', 'authority')
    concepts = []

    #If the search button is clicked on the html page, the query text is
    # obtained and concept URIs are searched for. The results are displayed
    # on the html page.
    if 'q' in request.GET:
        form = ConceptEntityLinkForm(request.GET)
        search = ''
        if form.is_valid():
            q = form.cleaned_data.get('q')

        _associated_uris = map(lambda o: o['uri'], associated_concepts)
        concepts = filter(lambda c: c['uri'] not in _associated_uris,
                          remote.concept_search(q))
    else:
        initial_data = {}
        q = ''
        form = ConceptEntityLinkForm()

    context = {
        'entity': entity,
        'form': form,
        'concepts_data': concepts,
        'associated_concepts': associated_concepts,
        'q': q,
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
