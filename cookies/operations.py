from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.conf import settings

from cookies.models import *
from concepts.models import Concept
from cookies import authorization

import jsonpickle, datetime
from itertools import groupby

from cookies.exceptions import *
logger = settings.LOGGER


def add_creation_metadata(resource, user):
    PROVENANCE = Field.objects.get(uri='http://purl.org/dc/terms/provenance')
    now = str(datetime.datetime.now())
    creation_message = u'Added by %s on %s' % (user.username, now)
    Relation.objects.create(**{
        'source': resource,
        'predicate': PROVENANCE,
        'target': Value.objects.create(**{
            '_value': jsonpickle.encode(creation_message),
        })
    })


def _transfer_all_relations(from_instance, to_instance_id, content_type):
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
    if user:
        relations_from = authorization.apply_filter(user, 'delete_relation', relations_from)
    _search_and_destroy(relations_from.order_by(*fields).values_list(*fields))

    fields = ['predicate_id', 'source_type', 'source_instance_id', 'id']
    relations_to = resource.relations_to.all()
    if user:
        relations_to = authorization.apply_filter(user, 'delete_relation', relations_to)
    _search_and_destroy(relations_to.order_by(*fields).values_list(*fields))



def merge_conceptentities(entities, master_id=None, delete=True):
    """
    Merge :class:`.ConceptEntity` instances in the QuerySet ``entities``.

    Any associated :class:`.Relation` instances will accrue to the ``master``
    instance, which is returned. All but the ``master`` instance will be
    deleted forever.

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

    if entities.count() < 2:
        raise RuntimeError("Need more than one ConceptEntity instance to merge")

    _concepts = list(set([v for v in entities.values_list('concept__uri', flat=True) if v]))
    if len(_concepts) > 1:
        raise RuntimeError("Cannot merge two ConceptEntity instances with"
                           " conflicting external concepts")
    _uri = _concepts[0] if _concepts else None

    if master_id:
        master = entities.get(pk=master_id)
    else:
        try:
            master = entities.first()
        except AssertionError:    # If a slice has already been taken.
            master = entities[0]
    if _uri is not None:
        master.concept = Concept.objects.get(uri=_uri)
        master.save()

    # Update all Relations.
    to_merge = entities.filter(~Q(pk=master.id))
    for entity in to_merge:
        _transfer_all_relations(entity, master.id, conceptentity_type)

    if delete:
        to_merge.delete()
    return master


def merge_resources(resources, master_id=None, delete=True, user=None):
    """
    """
    resource_type = ContentType.objects.get_for_model(Resource)
    if resources.count() < 2:
        raise RuntimeError("Need more than one Resource instance to merge")

    with_content = resources.filter(content_resource=True)

    if with_content.count() != 0 and with_content.count() != resources.count():
        raise RuntimeError("Cannot merge content and non-content resources")

    if user is None:
        user = User.objects.get(username='AnonymousUser')

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
