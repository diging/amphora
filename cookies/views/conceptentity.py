from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404

from cookies.models import *
from concepts.models import *
from concepts import remote
from cookies.filters import *
from cookies.forms import *
from cookies import entities, metadata, operations
from cookies import authorization as auth

from itertools import groupby


def _get_entity_by_id(request, entity_id, *args):
    return get_object_or_404(ConceptEntity, pk=entity_id)


@auth.authorization_required(ResourceAuthorization.VIEW, _get_entity_by_id)
def entity_details(request, entity_id):
    entity = _get_entity_by_id(request, entity_id)
    template = 'entity_details.html'
    similar_entities = entities.suggest_similar(entity, qs=auth.apply_filter(ResourceAuthorization.VIEW, request.user, ConceptEntity.objects.all()))

    entity_ctype = ContentType.objects.get_for_model(ConceptEntity)

    relations_from = Relation.objects.filter(Q(source_type=entity_ctype, source_instance_id=entity_id) | Q(source_type=entity_ctype, source_instance_id__in=list(entity.represents.values_list('entities__id', flat=True)))).order_by('predicate')
    relations_from = auth.apply_filter(ResourceAuthorization.VIEW, request.user, relations_from)
    relations_from = [(predicate, [rel for rel in relations]) for predicate, relations in groupby(relations_from, key=lambda r: r.predicate)]

    relations_to = Relation.objects.filter(Q(target_type=entity_ctype, target_instance_id=entity_id) | Q(target_type=entity_ctype, target_instance_id__in=list(entity.represents.values_list('entities__id', flat=True)))).order_by('predicate')
    relations_to = auth.apply_filter(ResourceAuthorization.VIEW, request.user, relations_to)
    relations_to = [(predicate, [rel for rel in relations]) for predicate, relations in groupby(relations_to, key=lambda r: r.predicate)]

    represents = entity.represents.values_list('entities__id', 'entities__name', 'entities__container__primary__name').distinct()
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
def entity_edit_relation_as_table(request, entity_id, predicate_id):
    """
    Edit a :class:`.ConceptEntity` instance.
    """
    next_page = request.GET.get('next')
    entity = _get_entity_by_id(request, entity_id)
    predicate = get_object_or_404(Field, pk=predicate_id)
    entity_ctype = ContentType.objects.get_for_model(ConceptEntity)
    relations = Relation.objects.filter(source_type=entity_ctype,
                                        source_instance_id=entity_id,
                                        predicate=predicate,
                                        hidden=False)

    request_format = request.GET.get('format')
    if request_format == 'json':
        if request.method == 'GET':
            data = {'relations': []}
            for relation in relations:
                if isinstance(relation.target, Value):
                    data['relations'].append({
                        'id': relation.id,
                        'value': relation.target.name,
                        'type': relation.target._type,
                        'model': 'Value',
                        'data_source': relation.data_source
                    })
            return JsonResponse(data)


        elif request.method == 'POST':
            relation_id = request.POST.get('id')
            action = request.POST.get('action', 'update')
            target_model = request.POST.get('model')
            target_value = request.POST.get('value')
            target_type = request.POST.get('type')
            relation_data_source = request.POST.get('data_source')


            if relation_id:    # Update
                relation_instance = Relation.objects.get(pk=relation_id)
                assert relation_instance.predicate == predicate
                if action == 'delete':
                    relation_instance.delete()
                    return JsonResponse({})
            else:    # Create
                relation_instance = Relation(source=entity, predicate=predicate, container=entity.container)   # Unsaved!

            if target_model == 'Value':
                if relation_id:    # We can re-use the Value instance.
                    target_instance = relation_instance.target
                else:
                    target_instance = Value.objects.create()
                if target_type in ['unicode', 'str', 'int', 'float']:
                    target_instance.name = eval(target_type)(target_value)
                elif target_type == 'datetime':
                    target_instance.name = iso8601.parse_date(target_value)
                elif target_type == 'date':
                    target_instance.name = iso8601.parse_date(target_value).date
                target_instance.save()
            elif target_model == 'Resource':
                target_instance = Resource.objects.get(pk=int(target_value))
            elif target_model == 'Entity':
                target_instance = ConceptEntity.objects.get(pk=int(target_value))

            relation_instance.target = target_instance
            relation_instance.data_source = relation_data_source
            relation_instance.save()
            return JsonResponse({
                'id': relation_instance.id,
                'value': relation_instance.target.name,
                'type': relation_instance.target._type,
                'model': target_model,
                'data_source': relation_instance.data_source
            })

    context = {
        'entity': entity,
        'predicate': predicate,
        'relations': relations,
        'next': next_page
    }
    return render(request, 'entity_edit_relation_as_table.html', context)


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
