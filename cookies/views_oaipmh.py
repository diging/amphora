from django.core.urlresolvers import reverse
from django.db.models import Min, Max
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect, Http404


from cookies.models import *

from oaipmh.server import BatchingServer, BatchingResumption
from oaipmh.interfaces import IBatchingOAI, IHeader, IIdentify
from oaipmh.error import CannotDisseminateFormatError, BadArgumentError

import pytz
import datetime
from lxml.etree import Element


METADATA_FORMATS = [
    ('oai_dc',
     'http://www.openarchives.org/OAI/2.0/oai_dc.xsd',
     'http://www.openarchives.org/OAI/2.0/oai_dc/'),
 ]


class JARSMetadataWriter(object):

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


class JARSIdentify(IIdentify):
    def repositoryName(self):
        """
        Name of repository.
        """
        return u'Amphora'

    def baseURL(self):
        """
        Base URL for OAI-PMH requests.
        """
        return reverse('oaipmh')

    def protocolVersion(self):
        """
        OAI-PMH protocol version (should always be '2.0')
        """
        return u'2.0'

    def adminEmails(self):
        """
        List of email addresses of repository administrators.
        """
        return u'erick.peirson@asu.edu'

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
        return u'no'

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


class JARSHeader(IHeader):
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
        return self.resource.created.astimezone(pytz.timezone('UTC')).replace(tzinfo=None)

    def setSpec(self):
        """
        A list of sets this record is a member of.
        """
        return [unicode(i) for i in self.resource.part_of.values_list('id', flat=True)]

    def isDeleted(self):
        """
        If true, record has been deleted.
        """
        return False


class JARSMetadata(object):
    def __init__(self, resource):
        self.resource = resource

    def element(self):
        return self.resource

    def getMap(self):
        elements = []
        for relation in self.resource.relations_from.all():
            elements.append((relation.predicate, relation.target.name))
        return elements

    def getField(self, name):
        return self.resource.relations_from.filter(predicate__uri=name)


class JARSBatchingOAI(IBatchingOAI):
    def _check_metadataPrefix(self, metadataPrefix):
        if metadataPrefix != 'oai_dc':
            raise CannotDisseminateFormatError('%s not implemented' % metadataPrefix)

    def _get_resources(self, setSpec=None, from_=None, until=None, cursor=0,
                       batch_size=10, **kwargs):
        queryset = Resource.objects.filter(content_resource=False)
        if setSpec is None:
            setSpec = kwargs.get('set', None)
        if setSpec is not None:
            queryset = queryset.filter(part_of__id=setSpec)

        if from_ is not None and until is not None:
            if from_ > until:
                raise BadArgumentError('``from`` cannot be later than ``until``')

        if from_ is not None:
            queryset = queryset.filter(created__gte=from_)
        if until is not None:
            queryset = queryset.filter(created__lte=until)

        return queryset.order_by('created')[cursor:cursor+batch_size]

    def getRecord(self, metadataPrefix, identifier):
        self._check_metadataPrefix(metadataPrefix)

    def identify(self):
        return JARSIdentify()

    def listIdentifiers(self, metadataPrefix, setSpec=None, from_=None, until=None,
                        cursor=0, batch_size=10, **kwargs):
        self._check_metadataPrefix(metadataPrefix)
        resources = self._get_resources(setSpec, from_, until, cursor, batch_size, **kwargs)
        return [JARSHeader(obj) for obj in resources]

    def listMetadataFormats(self, identifier=None):
        return METADATA_FORMATS

    def listRecords(self, metadataPrefix, setSpec=None, from_=None, until=None,
                    cursor=0, batch_size=10, **kwargs):
        print 'listRecords'
        self._check_metadataPrefix(metadataPrefix)
        print 'checked'
        resources = self._get_resources(setSpec, from_, until, cursor, batch_size, **kwargs)
        return [(JARSHeader(obj), JARSMetadata(obj), []) for obj in resources]

    def listSets(self):
        return [unicode(i) for i in Collection.objects.values_list('id', flat=True)]


def oaipmh(request):
    print [s.prefix for s in  Schema.objects.all()]
    server = BatchingServer(JARSBatchingOAI(), nsmap={schema.prefix: schema.uri for schema in Schema.objects.all()})
    server._tree_server._metadata_registry.registerWriter('oai_dc', JARSMetadataWriter())
    return HttpResponse(server.handleRequest(request.GET), content_type='application/xml')
