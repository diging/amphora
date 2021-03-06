from django.utils.translation import ugettext_lazy as _
from django.contrib.auth import login, authenticate
from django.core.cache import caches
from rest_framework import HTTP_HEADER_ENCODING, exceptions

import requests
from requests.auth import HTTPBasicAuth
from cookies.models import *
from social_django.models import UserSocialAuth
from django.conf import settings
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.authentication import TokenAuthentication
logger = settings.LOGGER
logger.setLevel('DEBUG')
GITHUB = 'https://api.github.com'


class GithubTokenBackend(BaseAuthentication):
    keyword = 'GithubToken'
    model = None

    def authenticate(self, request):
        """
        Authenticate a user by their GitHub ID.
        """
        auth = get_authorization_header(request).split()
        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            msg = _('Invalid token header. No credentials provided.')
            raise exceptions.AuthenticationFailed(msg)
        elif len(auth) > 2:
            msg = _('Invalid token header. Token string should not contain spaces.')
            raise exceptions.AuthenticationFailed(msg)

        try:
            token = auth[1].decode()
        except UnicodeError:
            msg = _('Invalid token header. Token string should not contain invalid characters.')
            raise exceptions.AuthenticationFailed(msg)
        user = GithubAuthenticationBackend().authenticate(token)
        if user:
            return user, None,
        return


class GithubAuthenticationBackend(object):
    def authenticate(self, token=None):
        path = "{github}/user".format(github=GITHUB)

        # There is no reason to re-authorize with Github every single time.
        cache = caches['default']
        data = cache.get('github_auth_%s' % token, None)
        if data is None:
            response = requests.get(path, headers={'Authorization': 'token %s' % token})
            if response.status_code == 404:   # Not a valid token.
                return

            data = response.json()
            cache.set('github_auth_%s' % token, data, 3600)
        github_user_id = data.get('id')
        try:
            auth = UserSocialAuth.objects.get(uid=github_user_id, provider='github')
        except UserSocialAuth.DoesNotExist: # No such user.
            return
        return auth.user

    def get_user(self, user_id):
        return User.objects.get(pk=user_id)

class AmphoraTokenAuthBackend(object):
    def authenticate(self, token=None):
        try:
            user, token = TokenAuthentication().authenticate_credentials(token)
        except exceptions.AuthenticationFailed:
            return
        return user

    def get_user(self, user_id):
        return User.objects.get(pk=user_id)

class GithubTokenBackendMiddleware(object):
    def __init__(self, get_response=None):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_request(self, request):
        if request.user.is_authenticated():
            return
        auth = get_authorization_header(request).split()
        if len(auth) < 2:
            return
        token = auth[1].decode()
        user = authenticate(token=token)
        if user:
            login(request, user)
        return
