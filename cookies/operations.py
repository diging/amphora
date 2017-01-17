from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet
from django.conf import settings

from cookies.models import *
from concepts.models import Concept
from cookies import authorization

import jsonpickle, datetime, copy
from itertools import groupby

import goat
import unittest, mock, json, os, sys

from cookies.exceptions import *
logger = settings.LOGGER


os.environ.setdefault('GOAT_WAIT_INTERVAL', '0.001')

goat.GOAT_APP_TOKEN = 'd22bbda9b5b507dc6cd032d80d6a3d299fda10fe'
goat.GOAT = 'http://127.0.0.1:8000'

class MockResponse(object):
    def __init__(self, content, status_code):
        self._status_code = status_code
        self.content = content

    def json(self):
        return json.loads(self.content)

    @property
    def status_code(self):
        return self._status_code


class MockSearchResponse(MockResponse):
    url = 'http://mock/url/'

    def __init__(self, parent, pending_content, success_content, max_calls=3,):
        self.max_calls = 3
        self.parent = parent
        self.pending_content = pending_content
        self.success_content = success_content

    def json(self):
        if self.parent.call_count < self.max_calls:
            return json.loads(self.pending_content)
        return json.loads(self.success_content)

    @property
    def status_code(self):
        if self.parent.call_count < self.max_calls:
            return 202
        return 200


def add_creation_metadata(resource, user):
    __provenance__, _ = Field.objects.get_or_create(uri='http://purl.org/dc/terms/provenance')
    now = str(datetime.datetime.now())
    creation_message = u'Added by %s on %s' % (user.username, now)
    Relation.objects.create(**{
        'source': resource,
        'predicate': __provenance__,
        'target': Value.objects.create(**{
            '_value': jsonpickle.encode(creation_message),
        })
    })


def _transfer_all_relations(from_instance, to_instance_id, content_type):
    """
    Traferring relations from one :class:`.Resource` instance to another
    """
    from_instance.relations_from.update(source_type=content_type,
                                        source_instance_id=to_instance_id)
    from_instance.relations_to.update(target_type=content_type,
                                      target_instance_id=to_instance_id)


def prune_relations(resource, user=None):
    """
    Search for and remove duplicate relations for a :class:`.Resource`\.
    """
    value_type = ContentType.objects.get_for_model(Value)

    def _search_and_destroy(relations):
        def _delete_dupes(objs):    # objs is an iterator of values() dicts.
            for obj in objs[1:]:    # Leave the first object.
                Relation.objects.get(pk=obj[-1]).delete()

        # We're looking for relations with the same predicate, whose
        #  complementary object is of the same type and is either identical or
        #  (if a Value) has the same value/content.
        for pred, pr_relations in groupby(relations, lambda o: o[0]):
            for ctype, ct_relations in groupby(pr_relations, lambda o: o[1]):
                # We need to use this iterator twice, so we'll solidify
                #  it as a list.
                ct_relations = [o for o in ct_relations]

                for iid, id_relations in groupby(ct_relations, lambda o: o[2]):
                    _delete_dupes(list(id_relations)) # Target is precisely the same.

                if ctype != value_type.id:    # Only applies to Value instances.
                    continue

                values = Value.objects.filter(pk__in=zip(*ct_relations)[2])\
                            .order_by('id').values('id', '_value')

                key = lambda *o: o[0][1]['_value']
                for value, vl_relations in groupby(sorted(zip(ct_relations, values), key=key), key):
                    v_relations = zip(*list(vl_relations))[0]
                    _delete_dupes(v_relations)    # Target has the same value.

    fields = ['predicate_id', 'target_type', 'target_instance_id', 'id']
    relations_from = resource.relations_from.all()
    if user and type(resource) is Resource:
        relations_from = authorization.apply_filter(user, 'delete_relation', relations_from)
    _search_and_destroy(relations_from.order_by(*fields).values_list(*fields))

    fields = ['predicate_id', 'source_type', 'source_instance_id', 'id']
    relations_to = resource.relations_to.all()
    if user and type(resource) is Resource:
        relations_to = authorization.apply_filter(user, 'delete_relation', relations_to)
    _search_and_destroy(relations_to.order_by(*fields).values_list(*fields))



def merge_conceptentities(entities, master_id=None, delete=True, user=None):
    """
    Merge :class:`.ConceptEntity` instances in the QuerySet ``entities``.

    As of 0.4, no :class:`.ConceptEntity` instances are deleted. Instead, they
    are added to an :class:`.Identity` instance. ``master`` will become the
    :prop:`.Identity.representative`\.

    Parameters
    ----------
    entities : QuerySet
    master_id : int
        (optional) The primary key of the :class:`.ConceptEntity` to use as the
        "master" instance into which the remaining instances will be merged.

    Returns
    -------
    master : :class:`.ConceptEntity`

    Raises
    ------
    RuntimeError
        If less than two :class:`.ConceptEntity` instances are present in
        ``entities``, or if more than one unique :class:`.Concept` is
        implicated.
    """
    conceptentity_type = ContentType.objects.get_for_model(ConceptEntity)
    if isinstance(entities, QuerySet):
        _len = lambda qs: qs.count()
        _uri = lambda qs: qs.values_list('concept__uri', flat=True)
        _get_master = lambda qs, pk: qs.get(pk=pk)
        _get_rep = lambda qs: qs.filter(represents__isnull=False).first()
        _first = lambda qs: qs.first()
    elif isinstance(entities, list):
        _len = lambda qs: len(qs)
        _uri = lambda qs: [getattr(o.concept, 'uri', None) for o in qs]
        _get_master = lambda qs, pk: [e for e in entities if e.id == pk].pop()
        _get_rep = lambda qs: [e for e in entities if e.represents.count() > 0].pop()
        _first = lambda qs: qs[0]


    if _len(entities) < 2:
        raise RuntimeError("Need more than one ConceptEntity instance to merge")

    _concepts = list(set([v for v in _uri(entities) if v]))
    if len(_concepts) > 1:
        raise RuntimeError("Cannot merge two ConceptEntity instances with"
                           " conflicting external concepts")
    _uri = _concepts[0] if _concepts else None

    master = None
    if master_id:    # If a master is specified, use it...
        try:
            master = _get_master(entities, pk)
        except:
            pass

    if not master:
        # Prefer entities that are already representative.
        try:
            master = _get_rep(entities)
        except:
            pass
    if not master:
        try:    # ...otherwise, try to use the first instance.
            master = _first(entities)
        except AssertionError:    # If a slice has already been taken.
            master = entities[0]

    if _uri is not None:
        master.concept = Concept.objects.get(uri=_uri)
        master.save()

    identity = Identity.objects.create(
        created_by = user,
        representative = master,
    )
    identity.entities.add(*entities)
    for ent in entities:
        ent.identities.update(representative=master)


    return master


def merge_resources(resources, master_id=None, delete=True, user=None):
    """
    Merge selected resources to a single resource.

    Parameters
    -------------
    resources : ``QuerySet``
        The :class:`.Resource` instances that will be merged.
    master_id : int
        (optional) The primary key of the :class:`.Resource` to use as the
        "master" instance into which the remaining instances will be merged.

    Returns
    -------
    master : :class:`.Resource`

    Raises
    ------
    RuntimeError
        If less than two :class:`.Resource` instances are present in
        ``resources``, or if :class:`.Resource` instances are not the
        same with respect to content.
    """

    resource_type = ContentType.objects.get_for_model(Resource)
    if resources.count() < 2:
        raise RuntimeError("Need more than one Resource instance to merge")

    with_content = resources.filter(content_resource=True)

    if with_content.count() != 0 and with_content.count() != resources.count():
        raise RuntimeError("Cannot merge content and non-content resources")

    if user is None:
        user, _ = User.objects.get_or_create(username='AnonymousUser')

    if master_id:
        master = resources.get(pk=master_id)
    else:
        master = resources.first()

    to_merge = resources.filter(~Q(pk=master.id))
    for resource in to_merge:
        _transfer_all_relations(resource, master.id, resource_type)
        resource.content.all().update(for_resource=master)
        for collection in resource.part_of.all():
            master.part_of.add(collection)

    prune_relations(master, user)

    master.save()
    if delete:
        to_merge.delete()
    return master


def add_resources_to_collection(resources, collection):
    """
    Adds selected resources to a collection.

    Number of resources should be greater than or equal to 1.
    And one collection has to be selected
    Returns the collection after making changes.

    Parameters
    -------------
    resources : ``QuerySet``
        The :class:`.Resource` instances that will be added to ``collection``.
    collection : :class:`.Collection`
        The :class:`.Collection` instance to which ``resources`` will be added.

    Returns
    ---------
    collection : :class:`.Collection`
        Updated :class:`.Collection` instance.

    Raises
    ------
    RuntimeError
        If less than one :class:`.Resource` instance is in queryset
        or if collection is not a :class:`.ConceptEntity` instance
    """
    if resources.count() < 1 :
        raise RuntimeError("Need at least one resource to add to collection.")

    if not isinstance(collection, Collection):
        raise RuntimeError("Invalid collection to add resources to.")

    collection.resources.add(*resources)
    collection.save()

    return collection


def isolate_conceptentity(instance):
    """
    Clone ``instance`` (and its relations) such that there is a separate
    :class:`.ConceptEntity` instance for each related :class:`.Resource`\.

    Prior to 0.3, merging involved actually combining records (and deleting all
    but one). As of 0.4, merging does not result in deletion or combination,
    but rather the reation of a :class:`.Identity`\.

    Parameters
    ----------
    instance : :class:`.ConceptEntity`
    """

    if instance.relations_to.count() <= 1:
        return
    entities = []
    for relation in instance.relations_to.all():
        clone = copy.copy(instance)
        clone.pk = None
        clone.save()

        relation.target = clone
        relation.save()

        for alt_relation in instance.relations_from.all():
            alt_relation_target = alt_relation.target
            cloned_relation_target = copy.copy(alt_relation_target)
            cloned_relation_target.pk = None
            cloned_relation_target.save()

            cloned_relation = copy.copy(alt_relation)
            cloned_relation.pk = None
            cloned_relation.save()

            cloned_relation.source = clone
            cloned_relation.target = cloned_relation_target
            cloned_relation.save()

        entities.append(clone)
    merge_conceptentities(entities, user=instance.created_by)

@mock.patch('requests.get')
def concept_search(text, mock_get):
    with open('cookies/tests/data/concept_search_results.json', 'r') as f:
            with open('cookies/tests/data/concept_search_created.json', 'r') as f2:
                mock_get.return_value = MockSearchResponse(mock_get, f2.read(), f.read(), 200)

    max_calls = 3

    concepts = goat.Concept.search(q=text)
    assert mock_get.call_count == max_calls, \
        "Should keep calling if status code 202 is received."
    args, kwargs =  mock_get.call_args
    assert args[0] == MockSearchResponse.url, \
        "Should follow the redirect URL."
    assert len(concepts) == 10, \
        "There should be 10 items in the result set."
    for concept in concepts:
        assert isinstance(concept, goat.Concept), \
            "Each of which should be a GoatConcept."

    return concepts
