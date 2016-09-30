from cookies.models import *

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
                     qs=Relation.objects.all()):
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

    if all([value is None for value in [source, predicate, target]]):
        return qs.none()

    for field, qfield, value in [('source', 'source_instance_id', source),
                                 ('target', 'target_instance_id', target)]:
        if value is not None:

            if type(value) in [str, unicode]:
                qs = filter_by_generic_with_name(field, value, qs=qs)
            else:
                qs = qs.filter(qfield=getattr(value, 'id', value))

    if predicate is not None:
        if type(predicate) in [str, unicode]:
            qs = qs.filter(predicate__name__icontains=predicate)
        else:
            qs = qs.filter(predicate=getattr(predicate, 'id', predicate))

    try:
        _states = qs.distinct('id')
        bool(_states)    # Force evaluation... oh I don't know.
        return _states
    except NotImplementedError:
        return qs
