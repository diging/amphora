from django.db.models import Q

from cookies.models import *

from itertools import chain, groupby
from Levenshtein import distance

_normalize = lambda s: s.replace('.', ' ').replace(',', ' ').lower().strip()
_tokenize = lambda s: [part for part in s.split() if len(part) > 2]


def suggest_similar(entity, qs=None):
    """
    Attempt to find :class:`.ConceptEntity` instances that are similar to
    ``entity``.

    Parameters
    ----------
    entity : :class:`.ConceptEntity`

    Returns
    -------
    list
        A list of :class:`.ConceptEntity` instances. Ordered by descending
        similarity.
    """

    # Get representative concepts for identities to which this entity is a
    #  subordinate party.

    rep_ids = Identity.objects.filter(entities=entity.id).values_list('representative', flat=True)
    ent_ids = list(Identity.objects.filter(entities=entity.id).values_list('entities__id', flat=True)) + list(Identity.objects.filter(representative_id=entity.id).values_list('entities__id', flat=True))

    identities = Identity.objects.filter(representative__id__in=rep_ids)
    if not qs:
        qs = ConceptEntity.objects.all()
    if entity.container:
        collection = entity.container.part_of
    elif entity.belongs_to:
        collection = entity.belongs_to
    else:
        collection = None
    if collection:
        qs = qs.filter(container__part_of=collection)
    name = _normalize(entity.name)
    suggestions = []
    # suggestions += [o.id ConceptEntity.objects.filter(Q(name__icontains=name) & ~Q(id=entity.id))

    name_parts = _tokenize(name)
    _id = lambda o: o.id
    _name = lambda o: o.name   #similar_entities = similar_entities.filter()
    _find = lambda part: qs.filter(Q(name__icontains=part) & ~Q(id=entity.id) & ~Q(identities__id__in=identities) & ~Q(pk__in=ent_ids) & ~Q(pk__in=rep_ids))
    for name, group in groupby(sorted(chain(*[_find(part) for part in name_parts]), key=_name), key=_name):
        for pk, subgroup in groupby(sorted(group, key=_id), key=_id):
            subgroup = [o for o in subgroup]
            suggestions.append((subgroup[0], len(subgroup)))
    _count = lambda o: o[1] - distance(name, _normalize(o[0].name))
    if len(suggestions) == 0:
        return []
    return list(zip(*sorted(suggestions, key=_count)[::-1])[0])
