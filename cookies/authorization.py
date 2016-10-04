from functools import wraps
from django.utils.decorators import available_attrs
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from guardian.shortcuts import get_perms


def check_authorization(perm, user, obj):
    return getattr(obj, 'created', None) == user or user.has_perm(perm, obj)


def list_authorizations(obj, user=None):
    """
    List authorizations for ``obj``.
    """
    if user is None:    # All authorizations for all users.
        return [{'user': user.username, 'auth': get_perms(user, obj)}
                for user in User.objects.all() if len(get_perms(user, obj)) > 0]
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
