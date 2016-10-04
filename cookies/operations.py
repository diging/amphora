from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from cookies.models import *
from concepts.models import Concept

import jsonpickle, datetime


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



def merge_conceptentities(entities, master_id=None):
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
        entity.relations_from.update(source_type=conceptentity_type, source_instance_id=master.id)
        entity.relations_to.update(target_type=conceptentity_type, target_instance_id=master.id)

    to_merge.delete()
    return master
