from functools import wraps

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.utils.decorators import available_attrs

from guardian.shortcuts import get_perms, remove_perm, assign_perm

from collections import defaultdict


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


is_owner = lambda user, obj: getattr(obj, 'created_by', None) == user or user.is_superuser


def check_authorization(auth, user, obj):
    """
    Check whether ``user`` is authorized to perform ``auth`` on ``obj``.
    """
    if auth == 'is_owner':
        return is_owner(user, obj)
    if auth == 'view_resource' and getattr(obj, 'public', False):
        return True
    return user.is_superuser or is_owner(user, obj) or user.has_perm(auth, obj)


# TODO: build this out.
def get_auth_filter(auth, user):
    """
    """
    return ~Q(created_by=user)


def update_authorizations(auths, user, obj):
    for auth in set(get_perms(user, obj)) - set(auths):
        remove_perm(auth, user, obj)
    for auth in set(auths) - set(get_perms(user, obj)):
        assign_perm(auth, user, obj)


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
