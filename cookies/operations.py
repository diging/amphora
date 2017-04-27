from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, QuerySet
from django.conf import settings

from cookies.models import *
from concepts.models import Concept
from cookies import authorization

import jsonpickle, datetime, copy, requests
from itertools import groupby, combinations
from collections import Counter
import networkx as nx

import os

from cookies.exceptions import *

logger = settings.LOGGER



def add_creation_metadata(resource, user):
    """
    Convenience function for creating a provenance relation when a
    :class:`.User` adds a :class:`.Resource`\.

    Parameters
    ----------
    resource : :class:`.Resource`
    user : :class:`.User`
    """
    __provenance__, _ = Field.objects.get_or_create(uri=settings.PROVENANCE)
    _now = str(datetime.datetime.now())
    _creation_message = u'Added by %s on %s' % (user.username, _now)
    Relation.objects.create(**{
        'source': resource,
        'predicate': __provenance__,
        'target': Value.objects.create(**{
            '_value': jsonpickle.encode(_creation_message),
            'container': resource.container,
        }),
        'container': resource.container,
    })


def _transfer_all_relations(from_instance, to_instance, content_type):
    """
    Transfers relations from one model instance to another.

    Parameters
    ----------
    from_instance : object
        An instance of any model, usually a :class:`.Resource` or
        :class:`.ConceptEntity`\.
    to_instance :
    content_type : :class:`.ContentType`
        :class:`.ContentType` for the model of the instance that will inherit
        relations.
    """



    from_instance.relations_from.update(source_type=content_type,
                                        source_instance_id=to_instance.id)

    from_instance.relations_to.update(target_type=content_type,
                                      target_instance_id=to_instance.id)


def prune_relations(resource, user=None):
    """
    Search for and aggressively remove duplicate relations for a
    :class:`.Resource`\.

    Use at your own peril.

    Parameters
    ----------
    resource : :class:`.Resource`
    user : :class:`.User`
        If provided, data manipulation will be limited to by the authorizations
        attached to a specific user. Default is ``None`` (superuser auths).
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
                # We need to use this iterator twice, so we consume it now, and
                #  keep it around as a list.
                ct_r = list(ct_relations)

                for iid, id_relations in groupby(ct_relations, lambda o: o[2]):
                    _delete_dupes(list(id_relations))    # Target is the same.

                if ctype != value_type.id:    # Only applies to Value instances.
                    continue

                values = Value.objects.filter(pk__in=zip(*ct_r)[2]) \
                                      .order_by('id').values('id', '_value')

                key = lambda *o: o[0][1]['_value']
                for _, vl_r in groupby(sorted(zip(ct_r, values), key=key), key):
                    _delete_dupes(zip(*list(vl_r))[0])

    fields = ['predicate_id', 'target_type', 'target_instance_id', 'id']
    relations_from = resource.relations_from.all()
    if user and type(resource) is Resource:
        relations_from = authorization.apply_filter(ResourceAuthorization.EDIT, user, relations_from)
    _search_and_destroy(relations_from.order_by(*fields).values_list(*fields))

    fields = ['predicate_id', 'source_type', 'source_instance_id', 'id']
    relations_to = resource.relations_to.all()
    if user and type(resource) is Resource:
        relations_to = authorization.apply_filter(ResourceAuthorization.EDIT, user, relations_to)
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
        _uri = lambda qs: [concept.uri for obj in qs for concept in obj.concept.all()]#[getattr(o.concept, 'uri', None) for o in qs]
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
        master.concept.add(Concept.objects.get(uri=_uri))
        master.save()

    identity = Identity.objects.create(
        created_by = user,
        representative = master,
    )
    identity.entities.add(*entities)
    map(lambda e: e.identities.update(representative=master), entities)
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
        _transfer_all_relations(resource, master, resource_type)
        resource.content.all().update(for_resource=master)
        for rel in ['resource_set', 'conceptentity_set', 'relation_set', 'content_relations', 'value_set']:
            getattr(resource.container, rel).update(container_id=master.container.id)
        # for collection in resource.part_of.all():
        #     master.part_of.add(collection)

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

    collection.resources.add(*map(lambda r: r.container, resources))
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


def generate_collection_coauthor_graph(collection,
                                       author_predicate_uri="http://purl.org/net/biblio#authors"):
    """
    Create a graph describing co-occurrences of :class:`.ConceptEntity`
    instances linked to individual :class:`.Resource` instances via an
    authorship :class:`.Relation` instance.

    Parameters
    ----------
    collection : :class:`.Collection`
    author_predicate_uri : str
        Defaults to the Biblio #authors predicate. This is the predicate that
        will be used to identify author :class:`.Relation` instances.

    Returns
    -------
    :class:`networkx.Graph`
        Nodes will be :class:`.ConceptEntity` PK ids (int), edges will indicate
        co-authorship; each edge should have a ``weight`` attribute indicating
        the number of :class:`.Resource` instances on which the pair of CEs are
        co-located.
    """

    # This is a check to see if the collection parameter is an instance of the
    #  :class:`.Collection`. If it is not a RuntimeError exception is raised.
    if not isinstance(collection, Collection):
        raise RuntimeError("Invalid collection to export co-author data from")

    resource_type_id = ContentType.objects.get_for_model(Resource).id

    # This will hold node attributes for all ConceptEntity instances across the
    #  entire collection.
    node_labels = {}
    node_uris = {}

    # Since a particular pair of ConceptEntity instances may co-occur on more
    #  than one Resource in this Collection, we compile the number of
    #  co-occurrences prior to building the networkx Graph object.
    edges = Counter()

    # The co-occurrence graph will be comprised of ConceptEntity instances
    #  (identified by their PK ids. An edge between two nodes indicates that
    #  the two constituent CEs occur together on the same Resource (with an
    #  author Relation). A ``weight`` attribute on each edge will record the
    #  number of Resource instances on which each respective pair of CEs
    #  co-occur.
    for resource_id in collection.resourcecontainer_set.values_list('primary__id', flat=True):
        # We only need a few columns from the ConceptEntity table, from rows
        #  referenced by responding Relations.
        author_relations = Relation.objects\
                .filter(source_type_id=resource_type_id,
                        source_instance_id=resource_id,
                        predicate__uri=author_predicate_uri)\
                .prefetch_related('target')

        # If there are no author relations, there are no nodes to be created for
        #  the resource.
        if author_relations.count() <= 1:
            continue

        ids, labels, uris = zip(*list(set(((r.target.id, r.target.name, r.target.uri) for r in author_relations))))

        # It doesn't matter if we overwrite node attribute values, since they
        #  won't vary.
        node_labels.update(dict(zip(ids, labels)))
        node_uris.update(dict(zip(ids, uris)))

        # The keys here are ConceptEntity PK ids, which will be the primary
        #  identifiers used in the graph.
        for edge in combinations(ids, 2):
            edges[edge] += 1

    # Instantiate the Graph from the edge data generated above.
    graph = nx.Graph()
    for (u, v), weight in edges.iteritems():
        graph.add_edge(u, v, weight=weight)

    # This is more efficient than setting the node attribute as we go along.
    #  If there is only one author, there is no need to set node attributes as
    #  there is no co-authorship for that Collection.
    if len(node_labels.keys()) > 1:
        nx.set_node_attributes(graph, 'label', node_labels)
        nx.set_node_attributes(graph, 'uri', node_uris)

    return graph


def ping_remote_resource(path):
    """
    Check whether a remote resource is accessible.
    """
    try:
        response = requests.head(path)
    except requests.exceptions.ConnectTimeout:
        return False, {}
    return response.status_code == requests.codes.ok, response.headers
