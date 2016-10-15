from cookies.models import *
from cookies import authorization

from itertools import chain, groupby

from django.db.models import Q


def prepend_to_results(pre_value):
    """
    Prepend a value to each tuple in an iterable of tuples returned by the
    decorated function.

    The function itself should not be a generator.

    Parameters
    ----------
    pre_value : object
        Anything at all.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            return [(pre_value,) + vtuple for vtuple in func(*args, **kwargs)]
        return wrapper
    return decorator


@prepend_to_results('Resource')
def get_resource_with_name(name, qs=Resource.objects.all(),
                           filters={'content_resource': False},
                           fields=['id', 'name', 'entity_type'], **kwargs):
    """
    Get instances of :class:`.Resource` with ``name__istartswith={{name}}``.

    Parameters
    ----------
    name : str or unicode
    qs : :class:`django.db.models.query.QuerySet`
    filters : dict
    fields : list
    kwargs : kwargs

    Returns
    -------
    list
        A list of field values.
    """
    return qs.filter(**filters).filter(name__icontains=name).values_list(*fields)


@prepend_to_results('Resource')
def get_resource_with_uri(uri, qs=Resource.objects.all(),
                           filters={'content_resource': False},
                           fields=['id', 'name', 'entity_type'], **kwargs):
    """
    Get instances of :class:`.Resource` with ``uri={{uri}}``.

    Parameters
    ----------
    name : str or unicode
    qs : :class:`django.db.models.query.QuerySet`
    filters : dict
    fields : list
    kwargs : kwargs

    Returns
    -------
    list
        A list of field values.
    """
    return qs.filter(**filters).filter(uri=uri).values_list(*fields)


@prepend_to_results('ConceptEntity')
def get_conceptentity_with_name(name, qs=ConceptEntity.objects.all(),
                                filters={},
                                fields=['id', 'name', 'entity_type'], **kwargs):
    """
    Get instances of :class:`.ConceptEntity` with ``name__icontains={{name}}``.

    Parameters
    ----------
    name : str or unicode
    qs : :class:`django.db.models.query.QuerySet`
    filters : dict
    fields : list
    kwargs : kwargs

    Returns
    -------
    list
        A list of field values.
    """
    return qs.filter(**filters).filter(name__icontains=name).values_list(*fields)


@prepend_to_results('ConceptEntity')
def get_conceptentity_with_uri(uri, qs=ConceptEntity.objects.all(),
                                filters={},
                                fields=['id', 'name', 'entity_type'], **kwargs):
    """
    Get instances of :class:`.ConceptEntity` with ``uri={{uri}}``.

    Parameters
    ----------
    name : str or unicode
    qs : :class:`django.db.models.query.QuerySet`
    filters : dict
    fields : list
    kwargs : kwargs

    Returns
    -------
    list
        A list of field values.
    """
    q = Q(uri=uri) | Q(concept__uri=uri)
    return qs.filter(**filters).filter(q).values_list(*fields)


def get_instances_with_uri(uri, getters=[get_resource_with_uri,
                                         get_conceptentity_with_uri],
                            fields=['id', 'name', 'entity_type']):
    return list(chain(*[getter(uri, fields=fields) for getter in getters]))


def get_instances_with_name(name, getters=[get_resource_with_name,
                                           get_conceptentity_with_name],
                            fields=['id', 'name', 'entity_type']):
    """
    Get model instances with ``name``.

    Parameters
    ----------
    name : str or unicode
    fields : list

    Returns
    -------
    list
        A list of field values.
    """

    return list(chain(*[getter(name, fields=fields) for getter in getters]))


def filter_by_generic_with_uri(field, name, qs=Relation.objects.all()):
    instances = get_instances_with_uri(name, fields=['id'])
    if len(instances) == 0:
        return qs.none()

    _key = lambda vtuple: vtuple[0]
    q = Q()
    for model, values in groupby(sorted(instances, key=_key), key=_key):
        ctype = ContentType.objects.get_for_model(eval(model))
        _, ids = zip(*values)
        q |= (Q(**{'%s_type' % field: ctype}) & \
              Q(**{'%s_instance_id__in' % field: ids}))
    return qs.filter(q)


def filter_by_generic_with_name(field, name, qs=Relation.objects.all()):
    """
    Filter a :class:`.Relation` queryset for source or target instances with
    ``name``.

    Parameters
    ----------
    field : str or unicode
        ``source`` or ``target``.
    name : str or unicode

    Returns
    -------
    :class:`django.db.models.query.QuerySet`
    """
    instances = get_instances_with_name(name, fields=['id'])
    if len(instances) == 0:
        return qs.none()

    _key = lambda vtuple: vtuple[0]
    q = Q()
    for model, values in groupby(sorted(instances, key=_key), key=_key):
        ctype = ContentType.objects.get_for_model(eval(model))
        _, ids = zip(*values)
        q |= (Q(**{'%s_type' % field: ctype}) & \
              Q(**{'%s_instance_id__in' % field: ids}))
    return qs.filter(q)


def filter_relations(source=None, predicate=None, target=None,
                     qs=Relation.objects.all(), user=None):
    """
    Filter a :class:`.Relation` queryset by source, predicate, and/or object.

    Parameters
    ----------
    source
    predicate
    target

    Returns
    -------
    :class:`django.db.models.query.QuerySet`
    """
    if not user.is_superuser:
        qs = authorization.apply_filter(user, 'view_relation', qs)

    for field, qfield, value in [('source', 'source_instance_id', source),
                                 ('target', 'target_instance_id', target)]:
        if value is not None:
            if type(value) is ConceptEntity:
                qs.filter(**{'%s_instance_id': value.id, '%s_type': entity_type})
            elif type(value) in [str, unicode]:
                if value.startswith('http'):    # Treat as a URI.
                    qs = filter_by_generic_with_uri(field, value, qs=qs)
                else:
                    qs = filter_by_generic_with_name(field, value, qs=qs)
            else:
                qs = qs.filter(qfield=getattr(value, 'id', value))

    if predicate is not None:
        if type(predicate) in [str, unicode]:
            if predicate.startswith('http'):    # Treat as a URI.
                qs = qs.filter(predicate__uri=predicate)
            else:
                qs = qs.filter(predicate__name__icontains=predicate)
        else:
            qs = qs.filter(predicate=getattr(predicate, 'id', predicate))


    try:
        _states = qs.distinct('id')
        bool(_states)    # Force evaluation... oh I don't know.
        return _states
    except NotImplementedError:
        return qs


def group_relations(relations, by='predicate'):
    _key = lambda o: o.predicate
    return [(predicate, [r for r in group]) for predicate, group in groupby(sorted(relations, key=_key), key=_key)]
