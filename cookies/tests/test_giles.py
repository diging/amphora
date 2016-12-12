"""
TODO: these tests need some serious updating, including new sample responses.
"""

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser, User
from django.core.urlresolvers import reverse
from django.conf import settings

from cookies import giles
from cookies.models import *

from social.apps.django_app.default.models import UserSocialAuth

import unittest, mock, json, os
from collections import Counter

from cookies.admin import import_schema
os.environ.setdefault('LOGLEVEL', 'ERROR')

DATAPATH = 'cookies/tests/data/giles'


class MockResponse(object):
    def __init__(self, status_code, response_file):
        self.status_code = status_code
        with open(os.path.join(DATAPATH, response_file), 'r') as f:
            self.content = f.read()

    def json(self):
        return json.loads(self.content)


def mock_get_fileids(url, params={}, headers={}):
    with open('cookies/tests/data/giles_file_response_3.json', 'r') as f:
        return MockResponse(200, f.read())


class TestGetUserAuthorization(unittest.TestCase):
    """
    A user has logged in to Giles using a Github identity, and is using the same
    identity in JARS. Before we can upload to Giles on their behalf, we need
    to exchange the user's provider token for a short-lived Giles token.

    :func:`.giles.get_auth_token` should send a ``POST`` request to
    ``{giles}/rest/token`` with an Authorization header containing the
    JARS application ID.
    """

    def setUp(self):
        self.factory = RequestFactory()
        User.objects.all().delete()
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='nope',
        )
        self.auth = UserSocialAuth.objects.create(**{
            'user': self.user,
            'provider': 'github',
            'uid': 'asdf1234',
        })
        self.provider_token = 'fdsa5432'
        self.auth.extra_data['access_token'] = self.provider_token
        self.auth.save()


    def test_get_auth_token(self):
        """
        Test the API request method itself.
        """
        mock_get_auth_token = lambda *a, **k: MockResponse(200, 'token_ok.json')
        post = mock.Mock(side_effect=mock_get_auth_token)

        result = giles.get_auth_token(self.user, post=post)

        self.assertEqual(post.call_count, 1)
        # self.assertTrue()
        called_with = post.call_args
        args, kwargs = called_with
        self.assertEqual(args[0], '%s/rest/token' % settings.GILES,
                         "Should call the {giles}/rest/token endpoint")
        self.assertEqual(kwargs['headers']['Authorization'],
                         'token %s' % settings.GILES_APP_TOKEN,
                         "Should pass the Giles app token for JARS in the"
                         " Authorization header.")
        self.assertEqual(kwargs['data']['providerToken'],
                         self.provider_token,
                         "Should pass the user's provider token in the request")
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[1], dict)
        self.assertIn('token', result[1])

    def test_get_user_auth_token(self):
        """
        :func:`.giles.get_user_auth_token` is a convenience method for
        retrieving a Giles auth token for a :class:`.User`\.

        If there is no token, should call :func:`get_auth_token` for a new one.
        Otherwise, just return the existing token.
        """
        mock_get_auth_token = lambda *a, **k: MockResponse(200, 'token_ok.json')
        post = mock.Mock(side_effect=mock_get_auth_token)

        token = giles.get_user_auth_token(self.user, post=post)
        called_with = post.call_args
        args, kwargs = called_with

        self.assertEqual(post.call_count, 1)
        self.assertEqual(args[0], '%s/rest/token' % settings.GILES,
                         "Should call the {giles}/rest/token endpoint")

        token_again = giles.get_user_auth_token(self.user, post=post)

        self.assertEqual(post.call_count, 1,
                         "Should not call the endpoint a second time")
        self.assertEqual(token, token_again)



if __name__ == '__main__':
    unittest.main()
