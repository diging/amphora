"""
These views support `Open Archives Initiative Protocol for Metadata Harvesting
(OAI-PMH) <https://www.openarchives.org/pmh/>`_.

Implements inferfaces from the `oaipmh <https://github.com/infrae/pyoai>`_
module.
"""

from django.core.urlresolvers import reverse
from django.db.models import Min, Max
from django.conf import settings
from django.http import (JsonResponse, HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect, Http404)

from cookies.models import *
import cookies.authorization as auth

from oaipmh.server import BatchingServer, BatchingResumption
from oaipmh.interfaces import IBatchingOAI, IHeader, IIdentify
from oaipmh.error import CannotDisseminateFormatError, BadArgumentError

import pytz, datetime
from lxml.etree import Element


METADATA_FORMATS = [
    ('oai_dc',
     'http://www.openarchives.org/OAI/2.0/oai_dc.xsd',
     'http://www.openarchives.org/OAI/2.0/oai_dc/'),
 ]


class AmphoraMetadataWriter(object):
    """
    Factory XML metadata writer. This was probably intended to be a singleton
    in the original design, but there's no real need for that in the current
    implementation.
    """
    def __call__(self, element, metadata):
        for field, value in metadata.getMap():
            tag = field.uri.split('/')[-1].split('#')[-1]

            e = Element(u'{%s}%s' % (field.namespace, tag))
            if type(value) is datetime.datetime:
                value = value.isoformat()
            elif type(value) not in [str, unicode]:
                value = unicode(value)
            e.text = value
            element.append(e)
        return element


class AmphoraIdentify(IIdentify):
    """
    Identification information for this Amphora instance.
    """
    def repositoryName(self):
        """
        Name of repository.
        """
        return settings.REPOSITORY_NAME

    def baseURL(self):
        """
        Base URL for OAI-PMH requests.
        """
        return reverse('oaipmh')

    def protocolVersion(self):
        """
        OAI-PMH protocol version (should always be '2.0').
        """
        return u'2.0'

    def adminEmails(self):
        """
        List of email addresses of repository administrators.
        """
        return settings.ADMIN_EMAIL

    def earliestDateStamp(self):
        """
        The datetime (datestamp) of the earliest record in repository.
        """
        return Resource.objects.annotate(Min('created')).order_by('created')[0]

    def deletedRecord(self):
        """
        Way the repository handles deleted records.
        Either 'no', 'transient' or 'persistent'.
        """
        return u'no'    # TODO: Is this correct?

    def granularity(self):
        """Datetime granularity of datestamps in repository.
        Either YYYY-MM-DD or YYYY-MM-DDThh:mm:ssZ
        """
        return u'YYYY-MM-DDThh:mm:ssZ'

    def compression(self):
        """
        List of types of compression schemes supported by repository.
        'identity' is the 'do-nothing' scheme.
        """
        return u'identity'


class AmphoraHeader(IHeader):
    """
    Header information for a single :class:`.Resource` instance.
    """
    def __init__(self, resource):
        self.resource = resource

    def identifier(self):
        """
        Repository-unique identifier of this record.
        """
        return unicode(self.resource.id)

    def datestamp(self):
        """
        Datetime of creation, last modification or deletion of the record.
        This can be used for selective harvesting.
        """
        return self.resource.created.astimezone(pytz.timezone('UTC'))\
                                    .replace(tzinfo=None)

    def setSpec(self):
        """
        A list of sets this record is a member of.
        """
        return map(unicode, self.resource.part_of.values_list('id', flat=True))

    def isDeleted(self):
        """
        If true, record has been deleted.
        """
        return self.resource.hidden


class AmphoraMetadata(object):
    """
    Metadata for a :class:`.Resource` instance.
    """
    def __init__(self, resource):
        self.resource = resource

    def element(self):
        return self.resource

    def getMap(self):
        return map(lambda r: (r.predicate, r.target.name),
                   self.resource.relations_from.all())

    def getField(self, uri):
        return self.resource.relations_from.filter(predicate__uri=uri)


class AmphoraBatchingOAI(IBatchingOAI):
    def _check_metadataPrefix(self, metadataPrefix):
        if metadataPrefix != 'oai_dc':
            raise CannotDisseminateFormatError('%s not implemented' % metadataPrefix)

    def _get_resources(self, setSpec=None, from_=None, until=None, cursor=0,
                       batch_size=10, **kwargs):
        qs = ResourceContainer.objects.filter(primary__is_deleted=False)
        qs = auth.apply_filter(ResourceAuthorization.VIEW, self.user, qs)

        if setSpec is None:
            setSpec = kwargs.get('set', None)
        if setSpec is not None:
            qs = qs.filter(part_of__id=setSpec)

        if from_ is not None and until is not None:
            if from_ > until:
                raise BadArgumentError('``from`` cannot be later than ``until``')

        if from_ is not None:
            qs = qs.filter(created__gte=from_)
        if until is not None:
            qs = qs.filter(created__lte=until)

        return qs.order_by('created')[cursor:cursor+batch_size]

    def getRecord(self, metadataPrefix, identifier):
        self._check_metadataPrefix(metadataPrefix)

    def identify(self):
        return AmphoraIdentify()

    def listIdentifiers(self, metadataPrefix, setSpec=None, from_=None,
                        until=None, cursor=0, batch_size=10, **kwargs):
        """
        Generate header information for responding :class:`.Resource` instances.
        """
        # Raise CannotDisseminateFormatError if the client asks for an
        #  unsuported format.
        self._check_metadataPrefix(metadataPrefix)
        return map(AmphoraHeader,
                   self._get_resources(setSpec, from_, until, cursor,
                                       batch_size, **kwargs))

    def listMetadataFormats(self, identifier=None):
        return METADATA_FORMATS

    def listRecords(self, metadataPrefix, setSpec=None, from_=None, until=None,
                    cursor=0, batch_size=10, **kwargs):
        """
        Generate full metadata records for responding :class:`.Resource`
        instances.
        """
        # Raise CannotDisseminateFormatError if the client asks for an
        #  unsuported format.
        self._check_metadataPrefix(metadataPrefix)
        return map(lambda r: (AmphoraHeader(r), AmphoraMetadata(r), []),
                   self._get_resources(setSpec, from_, until, cursor,
                                       batch_size, **kwargs))

    def listSets(self):
        """
        Generate a list of resource set identifiers.
        """
        # The closest thing that we have to a concept of a "set" is our
        #  ``Collection`` model.
        # TODO: verify that OAIPMH wants int identifiers here, and not URIs.
        qs = Collection.active.all()
        qs = auth.apply_filter(CollectionAuthorization.VIEW, self.user, qs)
        return map(unicode, qs.values_list('id', flat=True))


def oaipmh(request):
    """
    The heroic OAIPMH API view.
    """
    # TODO: Do we need to tell the world about every Schema in the system?
    _nsmap = dict(Schema.objects.values_list('prefix', 'uri'))

    # BatchingServer was probably intended to be a singleton, but that seems
    #  kind of silly in this case.
    oai = AmphoraBatchingOAI()
    oai.user = request.user    # We still need to enforce authorizations.
    server = BatchingServer(oai, nsmap=_nsmap)

    # TODO: Why are we accessing private properties so eggregiously?
    server._tree_server._metadata_registry\
                              .registerWriter('oai_dc', AmphoraMetadataWriter())

    return HttpResponse(server.handleRequest(request.GET),
                        content_type='application/xml')
