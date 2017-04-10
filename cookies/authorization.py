from functools import wraps
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.db.models import Q, QuerySet
from django.http import HttpResponseForbidden
from django.utils.decorators import available_attrs
from django import forms
from django.contrib.auth.models import AnonymousUser

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
    return getattr(obj, 'created_by', None) == user


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
    if not obj:
        return False

    if auth == 'is_owner':
        return is_owner(user, obj)
    if user.is_superuser:
        return True

    if isinstance(obj, Collection):
        if isinstance(user, AnonymousUser):
            _allow = CollectionAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj, policy=CollectionAuthorization.ALLOW).count() > 0
            _deny = CollectionAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj, policy=CollectionAuthorization.DENY).count() > 0
        else:
            _allow = CollectionAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj, policy=CollectionAuthorization.ALLOW).count() > 0
            _deny = CollectionAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj, policy=CollectionAuthorization.DENY).count() > 0
    else:
        if not isinstance(obj, ResourceContainer):
            obj = obj.container

        if isinstance(user, AnonymousUser):
            _allow = (ResourceAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj, policy=ResourceAuthorization.ALLOW).count() > 0\
                      or CollectionAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj.part_of, policy=CollectionAuthorization.ALLOW, heritable=True).count() > 0)\
                      and not CollectionAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj.part_of, policy=CollectionAuthorization.DENY, heritable=True).count() > 0
            _deny = ResourceAuthorization.objects.filter(action=auth, granted_to__isnull=True, for_resource=obj, policy=ResourceAuthorization.DENY).count() > 0
        else:
            _allow = (ResourceAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj, policy=ResourceAuthorization.ALLOW).count() > 0\
                      or CollectionAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj.part_of, policy=CollectionAuthorization.ALLOW, heritable=True).count() > 0)\
                      and not CollectionAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj.part_of, policy=CollectionAuthorization.DENY, heritable=True).count() > 0
            _deny = ResourceAuthorization.objects.filter(action=auth, granted_to=user, for_resource=obj, policy=ResourceAuthorization.DENY).count() > 0
    return (_allow and not _deny) or is_owner(user, obj)


def auth_model_for_obj(klass):
    if klass is Collection:
        return CollectionAuthorization
    return ResourceAuthorization


def apply_filter(auth, user, qs):
    """
    Filter a :class:`.QuerySet` using registered authorization policies.

    The presence of a DENY policy will override any ALLOW policies.

    Heritable policies on a Collection will override policies on constitutent
    resources. (TODO: Is that what we want? Maybe the opposite?)
    """
    if user.is_superuser:    # Superusers can see _everything_. Spoooooky.
        return qs

    if qs.model is Collection:
        if isinstance(user, AnonymousUser):
            allow = dict(authorizations__action=auth, authorizations__granted_to__isnull=True, authorizations__policy=ResourceAuthorization.ALLOW)
            deny = dict(authorizations__action=auth, authorizations__granted_to__isnull=True, authorizations__policy=ResourceAuthorization.DENY)
        else:
            allow = dict(authorizations__action=auth, authorizations__granted_to=user.id, authorizations__policy=ResourceAuthorization.ALLOW)
            deny = dict(authorizations__action=auth, authorizations__granted_to=user.id, authorizations__policy=ResourceAuthorization.DENY)

        q = Q(created_by=user.id) | (Q(**allow) & ~Q(**deny))
    elif qs.model is ResourceContainer:
        q = Q(created_by=user.id) | \
            ((Q(authorizations__action=auth, authorizations__granted_to=user.id, authorizations__policy=ResourceAuthorization.ALLOW) \
              | Q(part_of__authorizations__action=auth, part_of__authorizations__granted_to=user.id, part_of__authorizations__policy=ResourceAuthorization.ALLOW, part_of__authorizations__heritable=True)) \
             & ~(Q(authorizations__action=auth, authorizations__granted_to=user.id, authorizations__policy=ResourceAuthorization.DENY) \
                 | Q(part_of__authorizations__action=auth, part_of__authorizations__granted_to=user.id, part_of__authorizations__policy=ResourceAuthorization.DENY, part_of__authorizations__heritable=True)))
    else:
        q = Q(created_by=user.id) | \
            ((Q(container__authorizations__action=auth, container__authorizations__granted_to=user.id, container__authorizations__policy=ResourceAuthorization.ALLOW) \
              | Q(container__part_of__authorizations__action=auth, container__part_of__authorizations__granted_to=user.id, container__part_of__authorizations__policy=ResourceAuthorization.ALLOW, container__part_of__authorizations__heritable=True)) \
             & ~(Q(container__authorizations__action=auth, container__authorizations__granted_to=user.id, container__authorizations__policy=ResourceAuthorization.DENY) \
                 | Q(container__part_of__authorizations__action=auth, container__part_of__authorizations__granted_to=user.id, container__part_of__authorizations__policy=ResourceAuthorization.DENY, container__part_of__authorizations__heritable=True)))
    return qs.filter(q)


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


def list_authorizations(obj, user=None):
    if user:
        return obj.authorizations.filter(for_user=user)
    return obj.authorizations.all()


class AuthorizationForm(forms.ModelForm):
    model = ResourceAuthorization


class CollectionAuthorizationForm(forms.ModelForm):
    for_resource = forms.ModelChoiceField(queryset=Collection.objects.all(),
                                          widget=forms.widgets.HiddenInput)
    granted_by = forms.ModelChoiceField(queryset=User.objects.all(),
                                        widget=forms.widgets.HiddenInput)

    class Meta:
        model = CollectionAuthorization
        fields = '__all__'
