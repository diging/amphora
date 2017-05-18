import requests, urllib, urlparse
from requests.packages.urllib3.exceptions import NewConnectionError


class GilesRemote(object):
    def __init__(self, giles_token, giles_endpoint, giles_provider,
                 provider_token_generator, access_token_generator):
        self.giles_token = giles_token
        self.giles_endpoint = giles_endpoint
        self.giles_provider = giles_provider
        self.provider_token_generator = provider_token_generator
        self.access_token_generator = access_token_generator

    def build_auth_headers(self):
        """
        Generates the authorization header for Giles requests.
        """
        access_token = self.access_token_generator(self.get_auth_token)
        print access_token
        return {'Authorization': 'token %s' % access_token}

    def get_auth_token(self):
        """
        Obtain and store a short-lived authorization token from Giles.

        See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
        """

        provider_token = self.provider_token_generator(self.giles_provider)

        path = '/'.join([self.giles_endpoint, 'rest', 'token'])

        headers = {'Authorization': 'token %s' % self.giles_token}
        data = {'providerToken': provider_token}
        try:
            response = requests.post(path, data=data, headers=headers)
        except NewConnectionError as E:
            raise IOError('Could not contact Giles at %s' % path)
        if response.status_code != 200:
            raise IOError('Giles responded with %i: %s' % (response.status_code, response.content))
        return response.json()['token']

    def sign_uri(self, target):
        """
        Add ``accessToken`` parameter to a Giles URI.
        """
        token = self.access_token_generator(self.get_auth_token)
        print token
        parts = list(tuple(urlparse.urlparse(target)))
        q = {k: v[0] for k, v in urlparse.parse_qs(parts[4]).iteritems()}
        q.update({'accessToken': token})
        print q
        parts[4] = urllib.urlencode(q)

        return urlparse.urlunparse(tuple(parts))

    def get(self, target):
        """
        """
        headers = self.build_auth_headers()
        response = requests.get(self.sign_uri(target), headers=headers)
        if response.status_code != 200:
            raise IOError('Giles responded with %i: %s' % (response.status_code, response.content))
        return response.content
