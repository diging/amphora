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
from guardian.models import Permission, UserObjectPermission

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
    return (isinstance(obj, Collection) and getattr(obj, 'created_by', None) == user) or user.is_superuser


def is_public(obj):
    return getattr(obj, 'public', False)


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

    if isinstance(obj, Resource):
        if getattr(obj, 'belongs_to', False):
            auth = auth_label(auth, obj.belongs_to)
            _authorized = check_authorization(auth, user, obj.belongs_to)
        else:
            if obj.content_resource:
                return check_authorization(auth, user, obj.parent.first().for_resource)

            # If the Resource has no Collection, only the owner or admin can
            #  access it.
            _authorized = False
    elif isinstance(obj, ConceptEntity):
        if getattr(obj, 'belongs_to', False):
            auth = auth_label(auth, obj.belongs_to)
            _authorized = check_authorization(auth, user, obj.belongs_to)
        resource_type = ContentType.objects.get_for_model(Resource)
        resource = obj.relations_to.filter(source_type=resource_type).first().source
        _authorized = check_authorization(auth, user, resource)
    elif isinstance(obj, Relation):
        if getattr(obj, 'belongs_to', False):
            auth = auth_label(auth, obj.belongs_to)
            _authorized = check_authorization(auth, user, obj.belongs_to)
        _authorized = check_authorization(auth, user, obj.source)
    elif isinstance(obj, Value):
        _check = lambda o: check_authorization(auth, user, o)
        _sources = [relation.source for relation in obj.relations_to.all() if not isinstance(relation.source, Value)]
        _targets = [relation.target for relation in obj.relations_from.all() if not isinstance(relation.target, Value)]
        _authorized = all(map(_check, _sources)) and all(map(_check, _targets)) and (_sources or _targets)
    elif obj is None:
        _authorized = False
    else:
        auth = auth_label(auth, obj)
        _authorized = user.has_perm(auth, obj)
    return user.is_superuser or is_owner(user, obj) or _authorized or (is_public(obj) and 'view' in auth)


def label_authorizations(auths, obj):
    return [auth_label(auth.split('_')[0], obj) for auth in auths]


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
    if auth in SHARED_AUTHORIZATIONS:    # Already labeled.
        return _auth_map.get(auth, auth)
    auth = auth.split('_')[0]
    if (isinstance(obj, ConceptEntity) or getattr(obj, 'model', None) is ConceptEntity) and auth == 'view':
        return 'view_entity'
    elif (isinstance(obj, Collection) or getattr(obj, 'model', None) is Collection) and auth == 'view':
        return 'view_resource'
    if isinstance(obj, QuerySet):
        model_label = obj.model.__name__.lower()
    else:
        model_label = type(obj).__name__.lower()
    return '%s_%s' % (auth, model_label)


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

    Returns
    -------
    None
    """


    # logger.debug('update authorizations for %s with %s for %s' % \
    #              (repr(obj), ' '.join(auths), repr(user)))

    # ``auths`` may or may not have model-specific auth labels.
    labeled_auths = label_authorizations(auths, obj)
    by_user = kwargs.get('by_user', None)
    if by_user and isinstance(obj, QuerySet):
        obj = apply_filter(by_user, 'change_authorizations', obj)

    if not (isinstance(obj, Collection) or isinstance(getattr(obj, 'model', None), Collection)):
        return
    # There may be a variety of authorizations for the objects in the QuerySet,
    #  so we will visit all of the (few in number) authorizations, and remove
    #  or add accordingly.
    for auth in getattr(obj, 'model', obj).DEFAULT_AUTHS:   # obj may be a QS.
        if auth in labeled_auths:
            try:
                # logger.debug('assign: %s' % auth)
                assign_perm(auth, user, obj)
            except ObjectDoesNotExist:
                msg = '"%s" not a valid auth for %s' % (auth, repr(obj))
                raise ValueError(msg)
        else:
            try:
                # logger.debug('remove: %s' % auth)
                remove_perm(auth, user, obj)
            except ObjectDoesNotExist:
                msg = '"%s" not a valid auth for %s' % (auth, repr(obj))
                raise ValueError(msg)


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

    As of 0.4 this depends entirely on the :class:`.Collection` to which
    objects belong.

    Parameters
    ----------
    user : :class:`django.contrib.auth.models.User`
    permission : str
    queryset : :class:`django.db.models.QuerySet`

    Returns
    -------
    :class:`django.db.models.QuerySet`

    """
    # Everything depends on the Collection now.
    auth = auth_label(auth, Collection.objects.first())
    if user.is_superuser:
        return queryset
    if type(queryset) is list:
        return [obj for obj in queryset if check_authorization(auth, user, obj)]
    if auth == 'is_owner':
        return queryset.filter(created_by_id=user.id)

    ctype = ContentType.objects.get_for_model(Collection)
    rtype = ContentType.objects.get_for_model(Resource)
    perm = Permission.objects.get(codename=auth, content_type_id=ctype)
    perms = UserObjectPermission.objects.filter(user_id=user.id,
                                                permission_id=perm.id,
                                                content_type_id=ctype.id)

    # For some reason Guardian stores related primary keys as strings; without
    #  mapping back to int this will cause Postgres to choke.
    collection_pks = map(int, perms.values_list('object_pk', flat=True))
    if queryset.model is Collection:
        return queryset.filter(pk__in=collection_pks)
    elif queryset.model is Resource:
        q = Q(belongs_to__id__in=collection_pks)
    else:    # Traverse back up to the Collection via its Resources.
        if queryset.model is ConceptEntity:
            q = Q(belongs_to__id__in=collection_pks)
            # q = Q(relations_to__source_instance_id__in=resources, relations_to__source_type=rtype) \
            #     | Q(relations_from__target_instance_id__in=resources, relations_from__target_type=rtype)
        elif queryset.model is Relation:
            q = Q(belongs_to__id__in=collection_pks)
            # q = Q(source_instance_id__in=resources) \
            #     | Q(target_instance_id__in=resources)
        elif queryset.model is Value:
            resources = Resource.objects.filter(belongs_to__id__in=collection_pks)\
                                        .values_list('id', flat=True)
            q = Q(relations_to__source_instance_id__in=resources)

    return queryset.filter(q).distinct()


def make_nonpublic(obj):
    """
    Convenience function for revoking public access all at once.
    """
    obj.update(public=False)
    anonymous, _ = User.objects.get_or_create(username='AnonymousUser')
    update_authorizations([], anonymous, obj)
