from functools import wraps
from django.utils.decorators import available_attrs
from django.http import HttpResponseForbidden
from django.core.exceptions import PermissionDenied
from django.contrib.auth.models import User
from guardian.shortcuts import get_perms


def check_authorization(perm, user, obj):
    return user.has_perm(perm, obj)


def list_authorizations(obj, user=None):
    if user is None:
        _p = [{'user': user.username, 'auth': get_perms(user, obj)} for user in User.objects.all() if len(get_perms(user, obj)) > 0]
        print _p
        return _p


def authorization_required(perm, fn=None, login_url=None, raise_exception=False):
    """
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
