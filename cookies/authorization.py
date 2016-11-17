from functools import wraps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db.models import Q, QuerySet
from django.http import HttpResponseForbidden
from django.utils.decorators import available_attrs

from guardian.shortcuts import (get_perms, remove_perm, assign_perm,
                                get_objects_for_user)
from guardian.utils import get_user_obj_perms_model

from cookies.models import *
from collections import defaultdict
from itertools import chain

logger = settings.LOGGER


AUTHORIZATIONS = [
    ('change_resource', 'Change resource'),
    ('view_resource', 'View resource'),
    ('delete_resource', 'Delete resource'),
    ('change_authorizations', 'Change authorizations'),
    ('view_authorizations', 'View authorizations'),
]

COLLECTION_AUTHORIZATIONS = [
    ('change_collection', 'Change collection'),
    ('view_resource', 'View collection'),
    ('delete_collection', 'Delete collection'),
    ('change_authorizations', 'Change authorizations'),
    ('view_authorizations', 'View authorizations'),
]

SHARED_AUTHORIZATIONS = [
    'change_authorizations',
    'view_authorizations',
]


def is_owner(user, obj):
    """
    Evaluates whether or not ``user`` is the owner of ``obj``. At the moment
    this just means that the user is the creator of the object, but we may
    switch to something more explicit later on.

    Parameters
    ----------
    user : :class:`django.contrib.auth.models.User`
    obj : Instance of :class:`django.models.Model` subclass.

    Returns
    -------
    bool
    """
    return getattr(obj, 'created_by', None) == user or user.is_superuser


def check_authorization(auth, user, obj):
    """
    Check whether ``user`` is authorized to perform ``auth`` on ``obj``.

    Parameters
    ----------
    auth : str
    user : :class:`.User`
    obj : Model instance

    Returns
    -------
    bool
    """
    if auth == 'is_owner':
        return is_owner(user, obj)
    auth = auth_label(auth, obj)
    return user.is_superuser or is_owner(user, obj) or user.has_perm(auth, obj)


def auth_label(auth, obj):
    """
    Convert a generic auth name to the name of a model-specific authorization.

    For example: ``view`` -> ``view_relation``

    If the auth is already model-specific, or there is no model-specificity for
    the auth name, returns the auth as passed.

    Parameters
    ----------
    auth : str
    obj : Model instance

    Returns
    -------
    str
    """
    _auth_map = {
        'view_conceptentity': 'view_entity',
    }
    if auth in SHARED_AUTHORIZATIONS or '_' in auth:    # Already labeled.
        return _auth_map.get(auth, auth)
    if isinstance(obj, ConceptEntity) and auth == 'view':
        return 'view_entity'
    elif isinstance(obj, Collection) and auth == 'view':
        return 'view_resource'
    model_label = type(obj).__name__.lower()
    return '%s_%s' % (auth, model_label)


def _propagate_to_resources(auths, user, obj, **kwargs):
    """
    Propagate authorizations from :class:`.Collection` instances to its
    related :class:`.Resource` instances.

    Parameters
    ----------
    auths : list
        A list of authorizations (str). Any authorizations not in this list
        will be removed from ``obj`` for ``user``.
    user : :class:`.User`
    obj : :class:`.Collection`
    by_user : :class:`.User`
        If provided, the ``change_authorizations`` auth will be enforced for
        this user.
    propagate : bool
        If ``True`` (default), authorizations will propagate to "children"
        of ``obj``. i.e. Collection -> Resource -> Relation -> ConceptEntity.

    Returns
    -------
    None
    """
    logger.debug('_propagate_to_resources: %s' % ', '.join(auths))
    by_user = kwargs.get('by_user', None)
    child_auths = map(lambda a: a.replace('collection', 'resource'), auths)
    children = obj.resources.all()
    if by_user:
        children = apply_filter(by_user, 'change_authorizations', children)
    logger.debug('child auths %s' % ', '.join(child_auths))
    update_authorizations(child_auths, user, children, **kwargs)


def _propagate_to_relations(auths, user, obj, **kwargs):
    """
    Propagate authorizations from :class:`.Resource` instances to its
    related :class:`.Relation` instances.

    Parameters
    ----------
    auths : list
        A list of authorizations (str). Any authorizations not in this list
        will be removed from ``obj`` for ``user``.
    user : :class:`.User`
    obj : :class:`.Resource`
    by_user : :class:`.User`
        If provided, the ``change_authorizations`` auth will be enforced for
        this user.
    propagate : bool
        If ``True`` (default), authorizations will propagate to "children"
        of ``obj``. i.e. Collection -> Resource -> Relation -> ConceptEntity.

    Returns
    -------
    None
    """
    by_user = kwargs.get('by_user', None)
    child_auths = map(lambda a: a.replace('resource', 'relation'), auths)
    children_from = obj.relations_from.all()
    children_to = obj.relations_to.all()
    if by_user:
        children_from = apply_filter(by_user, 'change_authorizations', children_from)
        children_to = apply_filter(by_user, 'change_authorizations', children_to)

    update_authorizations(child_auths, user, children_from, **kwargs)
    update_authorizations(child_auths, user, children_to, **kwargs)


def _propagate_to_content(auths, user, obj, **kwargs):
    by_user = kwargs.get('by_user', None)
    logger.debug(repr(kwargs))
    logger.debug(repr(auths))
    for relation in obj.content.all():
        update_authorizations(auths, user, relation.content_resource, **kwargs)



def _propagate_to_entities(auths, user, obj, **kwargs):
    """
    Propagate authorizations from :class:`.Relation` instances to ``source``
    and/or ``target`` :class:`.ConceptEntity` instances.

    Parameters
    ----------
    auths : list
        A list of authorizations (str). Any authorizations not in this list
        will be removed from ``obj`` for ``user``.
    user : :class:`.User`
    obj : :class:`.Relation`
    by_user : :class:`.User`
        If provided, the ``change_authorizations`` auth will be enforced for
        this user.
    propagate : bool
        If ``True`` (default), authorizations will propagate to "children"
        of ``obj``. i.e. Collection -> Resource -> Relation -> ConceptEntity.

    Returns
    -------
    None
    """
    by_user = kwargs.get('by_user', None)
    child_auths = map(lambda a: a.replace('relation', 'conceptentity'), auths)
    for field in ['source', 'target']:
        child = getattr(obj, field)
        if isinstance(child, ConceptEntity):
            if by_user:
                if check_authorization('change_authorizations', by_user, child):
                    continue
            update_authorizations(child_auths, user, child, **kwargs)


def _propagate_to_children(auths, user, obj, **kwargs):
    """
    Propagate authorizations to child objects.

    Parameters
    ----------
    auths : list
        A list of authorizations (str). Any authorizations not in this list
        will be removed from ``obj`` for ``user``.
    user : :class:`.User`
    obj : Model instance or :class:`.QuerySet`
    by_user : :class:`.User`
        If provided, the ``change_authorizations`` auth will be enforced for
        this user.
    propagate : bool
        If ``True`` (default), authorizations will propagate to "children"
        of ``obj``. i.e. Collection -> Resource -> Relation -> ConceptEntity.

    Returns
    -------
    None
    """
    if isinstance(obj, Collection):
        logger.debug('Collection -> Resources')
        _propagate_to_resources(auths, user, obj, **kwargs)
    elif isinstance(obj, Resource):
        logger.debug('Resource -> Relation')
        _propagate_to_relations(auths, user, obj, **kwargs)

        logger.debug('Resource -> Content')
        _propagate_to_content(auths, user, obj, **kwargs)
    elif isinstance(obj, Relation):
        logger.debug('Relation -> ConceptEntity')
        _propagate_to_entities(auths, user, obj,  **kwargs)
    elif isinstance(obj, ConceptEntity):
        logger.debug('ConceptEntity -> Relation')
        kwargs.pop('propagate', None)
        _propagate_to_relations(auths, user, obj, **kwargs)


def update_authorizations(auths, user, obj, **kwargs):
    """
    Replace the current authorizations for ``user`` on ``obj`` with ``auths``.

    Parameters
    ----------
    auths : list
        A list of authorizations (str). Any authorizations not in this list
        will be removed from ``obj`` for ``user``.
    user : :class:`.User`
    obj : Model instance or :class:`.QuerySet`
    by_user : :class:`.User`
        If provided, the ``change_authorizations`` auth will be enforced for
        this user.
    propagate : bool
        If ``True`` (default), authorizations will propagate to "children"
        of ``obj``. i.e. Collection -> Resource -> Relation -> ConceptEntity.

    Returns
    -------
    None
    """
    
    logger.debug('update authorizations for %s with %s for %s' % \
                 (repr(obj), ' '.join(auths), repr(user)))

    # ``auths`` may or may not have model-specific auth labels.
    labeled_auths = [auth_label(auth, obj) for auth in auths]

    by_user = kwargs.get('by_user', None)
    if by_user and isinstance(obj, QuerySet):
        obj = apply_filter(by_user, 'change_authorizations', obj)

    # There may be a variety of authorizations for the objects in the QuerySet,
    #  so we will visit all of the (few in number) authorizations, and remove
    #  or add accordingly.
    for auth in getattr(obj, 'model', obj).DEFAULT_AUTHS:   # obj may be a QS.
        if auth in labeled_auths:
            try:
                logger.debug('assign: %s' % auth)
                assign_perm(auth, user, obj)
            except ObjectDoesNotExist:
                msg = '"%s" not a valid auth for %s' % (auth, repr(obj))
                raise ValueError(msg)
        else:
            try:
                logger.debug('remove: %s' % auth)
                remove_perm(auth, user, obj)
            except ObjectDoesNotExist:
                msg = '"%s" not a valid auth for %s' % (auth, repr(obj))
                raise ValueError(msg)

    if kwargs.get('propagate', True):
        logger.debug('propagate')
        _propagate_to_children(auths, user, obj, **kwargs)


def list_authorizations(obj, user=None):
    """
    List authorizations for ``obj``.
    """
    if user is None:    # All authorizations for all users.
        _auths = defaultdict(list)
        _users = {obj.created_by.id: obj.created_by}
        _auths[obj.created_by.id].append('owns')


        for user in User.objects.all():
            _auths[user.id] += get_perms(user, obj)
            _users[user.id] = user

        return [(_users[user], auths) for user, auths in _auths.items() if auths]

    # Authorizations for a specific user.
    return get_perms(user, obj)


def authorization_required(perm, fn=None, login_url=None, raise_exception=False):
    """
    Decorator for views. Checks ``perm`` on an object ``fn`` for the requesting
    :class:`.User`\.
    """
    def decorator(view_func):

        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            obj = fn(request, *args, **kwargs) if callable(fn) else fn
            if not check_authorization(perm, request.user, obj):
                if raise_exception:
                    msg = '%s on %s not authorized for %s' % \
                          (perm, obj.__unicode__(), request.user.username)
                    raise PermissionDenied(msg)
                # TODO: make this pretty and informative.
                return HttpResponseForbidden('Nope.')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def apply_filter(user, auth, queryset):
    """
    Limit ``queryset`` to those objects for which ``user`` has ``permission``.

    Parameters
    ----------
    user : :class:`django.contrib.auth.models.User`
    permission : str
    queryset : :class:`django.db.models.QuerySet`

    Returns
    -------
    :class:`django.db.models.QuerySet`

    """
    # TODO: implement a more general way to correct these legacy auth names.
    if getattr(queryset, 'model', None) == Collection \
        and auth == 'view_collection':
        auth = 'view_resource'

    if user.is_superuser:
        return queryset
    if type(queryset) is list:
        return [obj for obj in queryset if check_authorization(auth, user, obj)]
    if auth == 'is_owner':
        return queryset.filter(created_by_id=user.id)
    return get_objects_for_user(user, auth, queryset)


def make_nonpublic(obj):
    """
    Convenience function for revoking public access all at once.
    """
    obj.update(public=False)
    anonymous, _ = User.objects.get_or_create(username='AnonymousUser')
    update_authorizations([], anonymous, obj)
