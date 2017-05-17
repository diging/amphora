"""
Accession manager for HathiTrust resources in the public domain.
"""

import oauthlib, requests
from itertools import groupby

from oauthlib import oauth1


class IngestError(IOError):
    pass


class HathiTrustRemote(object):
    BASE = 'https://babel.hathitrust.org/cgi/htd'
    METADATA = 'https://catalog.hathitrust.org/api/volumes/brief/htid/{htid}.json'

    def __init__(self, client_key, client_secret):
        self.session = oauth1.Client(client_key, client_secret=client_secret)

    def get(self, target, sign=True):
        if sign:
            target = self.sign_uri(target)
        response = requests.get(target)
        if response.status_code != 200:
            raise IngestError(response.content)
        return response

    def build_uri(self, identifier, page_number=None):
        """
        Generate a signable URI for an identifier.

        Parameters
        ----------
        identifier : str
            E.g. ``"njp.32101044814968"``
        page_number : int
            If provided, requests specific data about a page in the resource.
        """

        if page_number is not None:
            raise NotImplemented('Not there yet.')
        return '%s/volume/meta/%s?v=2&format=json' % (HathiTrustRemoteIngest.BASE, identifier)


    def sign_uri(self, uri):
        """
        For some strange reason, HathiTrust expect the authorization data
        to be passed as GET parameters rather than in the header. So, we do
        that.

        Parameters
        ----------
        uri : str
            Target path with parameters.

        Returns
        -------
        str
            Request-ready URI (use immediately).
        """
        signed_uri, headers, body = self.session.sign(uri)
        auth_raw = headers.get('Authorization')[6:]
        extra = dict([part.split('=') for part in auth_raw.split(', ')])
        extra_enc = '&'.join(['%s=%s' % (k, eval(v)) for k, v in extra.items()])
        return '%s&%s' % (uri, extra_enc)

    def get_metadata(self, identifier):
        """
        Retrieve brief metadata about ``identifier`` from the HathiTrust
        Metadata API.

        Parameters
        ----------
        identifier : str

        Returns
        -------
        dict
        """
        if identifier in self.metadata:
            return self.metadata.get(identifier)
        uri = self.METADATA.format(htid=identifier)
        response = self.get(uri)
        return response.json()

    def get_content_metadata(self, identifier):
        """
        Execute a call against the API for ``identifier``, returning raw
        JSON-decoded data about volume content.

        Parameters
        ----------
        identifier : str

        Returns
        -------
        dict

        """
        response = self.get(self.build_uri(identifier), sign=False)
        return response.json()



class HathiTrustRemoteIngest(HathiTrustRemote):
    """
    Ingest remote resources from HathiTrust.
    """

    BASE = 'https://babel.hathitrust.org/cgi/htd'
    METADATA = 'https://catalog.hathitrust.org/api/volumes/brief/htid/{htid}.json'

    def __init__(self, identifiers, client_key, client_secret, metadata={}):
        self.identifiers = map(str, identifiers)    # No surprises!
        self.metadata = metadata
        super(HathiTrustRemoteIngest, self).__init__(client_key, client_secret)

    def process_metadata(self, identifier, data):
        """
        Retrieve ingestable relations from an HT metadata record.

        Parameters
        ----------
        data : dict

        Returns
        -------
        dict
        """
        try:
            if len(data['records']) == 0:
                return {}
            htrn = data['records'].keys()[0]
            record = data['records'][htrn]
            item = data['items'][0]    # TODO: do they ever not return items?
            return {
                'http://purl.org/dc/elements/1.1/identifier': \
                      ['isbn:%s' % isbn for isbn in record['isbns']] \
                    + ['issn:%s' % issn for issn in record['issns']] \
                    + ['lccn:%s' % lccn for lccn in record['lccns']] \
                    + ['oclc:%s' % oclc for oclc in record['oclcs']],
                'http://purl.org/dc/terms/created': record['publishDates'],
                'uri': [item['itemURL']],
                'name': [' | '.join(record['titles'])],
                'http://purl.org/dc/terms/accessRights': [item['rightsCode']],
                'http://purl.org/dc/terms/rightsHolder': [item['orig']],
                'entity_type': ['http://purl.org/dc/dcmitype/Text']
            }
        except Exception as E:
            print E
            print data
            raise E

    def process_content_metadata(self, identifier, raw):
        """
        Process raw JSON-decoded content data for a single resource.

        Parameters
        ----------
        raw : dict
            Raw JSON-decoded data for a volume/meta resource.

        Returns
        -------
        """
        try:

            pgmap = raw.get('htd:pgmap', [])
            seqmap = raw.get('htd:seqmap', [])
            if len(pgmap) > 0 and 'htd:pg' in pgmap[0]:
                _key = lambda o: o['pgnum']
                page_data = pgmap[0]['htd:pg']
                page_numbers = set(map(_key, page_data))
                page_resources = {
                    pgnum: [d['content'] for d in group]
                    for pgnum, group in groupby(sorted(page_data, key=_key), key=_key)
                }
                return {
                    'http://purl.org/dc/terms/accessRights': [raw.get('htd:access_use_statement'), raw.get('htd:access_use')],
                    'http://purl.org/dc/terms/modified': [raw.get('updated')],
                    'http://purl.org/dc/terms/extent': ['%s pages' % raw.get('htd:numpages')],
                    'parts': [
                        {
                            'name': ['%s page %s' % (identifier, pagenum)],
                            'parts': [
                                {
                                    'name': ['%s page %s (part %s)' % (identifier, pagenum, partnum)],
                                    'uri': [self.BASE + '/volume/pagemeta/%s/%s?v=2&format=json' % (identifier, partnum)],
                                    'file': [{
                                        'location': [self.BASE + '/volume/pageocr/%s/%s?v=2' % (identifier, partnum)],
                                        'content_type': 'text/plain',
                                        'external_source': 'HT',
                                    }],
                                    'entity_type': ['http://purl.org/dc/dcmitype/Text']
                                }
                            for partnum in page_resources[pagenum]],
                            'entity_type': ['http://purl.org/net/biblio#Part']

                        }
                    for pagenum in page_numbers]
                }
            else:
                n_pages = int(raw.get('htd:numpages'))

                return {
                    'http://purl.org/dc/terms/accessRights': [raw.get('htd:access_use_statement'), raw.get('htd:access_use')],
                    'http://purl.org/dc/terms/modified': [raw.get('updated')],
                    'http://purl.org/dc/terms/extent': ['%s pages' % raw.get('htd:numpages')],
                    'parts': [
                        {
                            'name': ['%s page %i' % (identifier, pagenum)],
                            'uri': [self.BASE + '/volume/pagemeta/%s/%i?v=2&format=json' % (identifier, pagenum)],
                            'file': [{
                                'location': [self.BASE + '/volume/pageocr/%s/%i?v=2' % (identifier, pagenum)],
                                'content_type': 'text/plain',
                                'external_source': 'HT',
                            }],
                            'entity_type': ['http://purl.org/net/biblio#Part']
                        }
                    for pagenum in xrange(1, n_pages + 1)]
                }



        except Exception as E:
            print E
            print raw
            raise E


    def get_record(self, identifier):
        record = self.process_metadata(identifier, self.get_metadata(identifier))
        record.update(self.process_content_metadata(identifier, self.get_content_metadata(identifier)))
        return record

    def __len__(self):
        return len(self.identifiers)

    def __iter__(self):
        return self

    def next(self):
        try:
            next_identifier = self.identifiers.pop()
        except IndexError:    # Out of identifiers!
            raise StopIteration
        return self.get_record(next_identifier)
