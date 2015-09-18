jfrom django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.core.files import File
from os.path import basename

from .models import *
import rdflib
from zipfile import ZipFile
from os.path import basename


import logging, logging.handlers
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')
# Adding system handler
console = logging.StreamHandler()
console.setLevel("DEBUG")
logger.addHandler(console)


class BaseIngester(object):
    pass


class ZoteroRDFIngester(BaseIngester):
    def load(self, file):
        """

        Parameters
        ----------
        file : file
            Expects a zip file.

        """

        self.zipfile = ZipFile(file)
        self.fnames = [ name for name in self.zipfile.namelist()
                            if not basename(name).startswith('._') ]
        # To check logging
        logger.debug("==Check logging==")
        for fname in self.fnames:
            logger.debug(fname)
            self.zipfile.extract(fname, '/tmp/')

        # Locate the RDF file.
        self.rdfname = [ name for name in self.fnames
                            if name.endswith('.rdf') ][0]
        self.rdfpath = self.zipfile.extract(self.rdfname, '/tmp/')

    def fix_rdf(self):
        """
        Fix validation issues. Zotero incorrectly uses rdf:resource as a
        child element for Attribute; rdf:resource should instead be used
        as an attribute of link:link.
        """

        with open(self.rdfpath, 'r') as f:
            raw_rdf = f.read()
        raw_rdf = raw_rdf.replace(  'rdf:resource rdf:resource',
                                    'link:link rdf:resource'    )
        with open(self.rdfpath, 'w') as f:
            f.write(raw_rdf)

    def parse(self):
        """
        Handle RDF content.
        """

        self.fix_rdf()

        # Load the RDF triples.
        self.graph = rdflib.Graph()
        self.graph.parse(self.rdfpath)

        BIB = rdflib.Namespace("http://purl.org/net/biblio#")

        # bib_types and rdf_types contain class names that Zotero uses for
        #  resources.
        bib_types = [   'Illustration', 'Recording', 'Legislation', 'Document',
                        'BookSection', 'Book', 'Data', 'Letter', 'Report',
                        'Article', 'Manuscript', 'Image',
                        'ConferenceProceedings', 'Thesis'   ]
        rdf_types = [   'Document', ]

        # Define various RDF elements for ease of expression.
        date_elem = rdflib.URIRef("http://purl.org/dc/elements/1.1/date")
        authors_elem = rdflib.URIRef("http://purl.org/net/biblio#authors")
        identifier_elem = rdflib.URIRef("http://purl.org/dc/elements/1.1/identifier")
        link_elem = rdflib.URIRef("http://purl.org/rss/1.0/modules/link/link")
        title_elem = rdflib.URIRef("http://purl.org/dc/elements/1.1/title")

        for btype in bib_types:
            articles = [ r[0] for r in self.graph.query('SELECT * WHERE { ?p a bib:'+btype+' }')]
            debug('Found {0} {1} elements'.format(len(articles), btype))

            # Don't bother loading the Type unless there are Resources to be
            #  created -- reduce DB load.
            if len(articles) > 0:

                # Generate a Type for this Resource.
                rtype = Type.objects.get_or_create(name='Biblio.'+btype.lower())[0]
                debug('loaded Type {0} in Schema {1}'.format(rtype, rtype.schema))

            for article in articles:
                fp, name, authors, pubdate, identifier = None, None, None, None, None
                for s,p,o in self.graph.triples( ( article, None, None)):

                    # If possible, load the Field for this predicate.
                    try:
                        predicate = Field.objects.get(uri=str(p))
                    except ObjectDoesNotExist:
                        predicate = None

                    if p == title_elem:
                        name = self._handle_title(o)

                    if p == link_elem:
                        f = self._handle_link(o)
                        if f: fp = f

                    # Load or generate an Entity for each author.
                    if p == authors_elem:
                        authors = self._handle_authors(o)

                    if p == date_elem:
                        pubdate = self._handle_date(o)

                    if p == identifier_elem:
                        identifier = self._handle_identifier(o)

                # Only proceed if we successfully found a name.
                if name:

                    # If a file is present, create a LocalResource.
                    if fp:
                        resource = LocalResource(name=name, entity_type=rtype)
                        resource.save()
                        resource.file.save(
                            fp.split('/')[-1], File(open(fp, 'r')), True)
                        debug(
                            'created LocalResource {0}, with file {1}'.format(
                                resource, resource.file)    )

                    # Otherwise, use the identifier to create a RemoteResource.
                    elif identifier:
                        resource = RemoteResource(
                            name=name, url=identifier, entity_type=rtype    )
                        resource.save()
                        logger.debug(
                            'created RemoteResource {0}, with URL {1}'.format(
                                resource, resource.url)    )

                    # Generate DC.Creator metadata.
                    for author in authors:
                        if author is not None:
                            pred = Field.objects.get(
                                    uri='http://purl.org/dc/terms/creator')

                            rel = Relation(
                                source=resource,
                                predicate=pred,
                                target=author,
                            )
                            rel.save()

    def _handle_title(self, ref):
        return str(ref)

    def _handle_link(self, ref):
        link_elem = rdflib.URIRef("http://purl.org/rss/1.0/modules/link/link")
        for s,p,o in self.graph.triples( (ref, None, None) ):
            if p == link_elem:
                return str(o).replace('file://', '')

    def _handle_identifier(self, ref):
        value_elem = rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#value')
        return str([ (s,p,o)
                        for s,p,o
                        in self.graph.triples( (ref, value_elem, None) )][0][2])


    def _handle_date(self, ref):
        try:
            with transaction.atomic():
                _pubdate = DateTimeValue()
                _pubdate.name = _pubdate._convert(str(ref))
                try:
                    pubdate = DateTimeValue.objects.get(name=_pubdate.name)
                except ObjectDoesNotExist:
                    pubdate = _pubdate
                    pubdate.save()
            return pubdate
        except ValidationError: # Raised when the date isn't ISO8601.
            # We'll try again once, using just use the year.
            with transaction.atomic():
                _pubdate = DateTimeValue()
                _pubdate.name = _pubdate._convert(str(ref)[0:4])
                try:
                    pubdate = DateTimeValue.objects.get(name=_pubdate.name)
                except ObjectDoesNotExist:
                    pubdate = _pubdate
                    pubdate.save()
                pubdate.save()
            return pubdate

    def _handle_authors(self, ref):
        return [ self._handle_author(_o)
                    for _s,_p,_o
                    in self.graph.triples( (ref, None, None)) ]


    def _handle_author(self, ref):
        givenname_elem = rdflib.URIRef('http://xmlns.com/foaf/0.1/givenname')
        surname_elem = rdflib.URIRef('http://xmlns.com/foaf/0.1/surname')
        type_elem = rdflib.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')

        givenname, surname, type_uri = None, None, None
        for s_, p_, o_ in self.graph.triples( (ref, None, None)):
            if p_ == givenname_elem: givenname = str(o_)
            elif p_ == surname_elem: surname = str(o_)
            elif p_ == type_elem: type_uri = str(o_)

        if givenname or surname:
            fullname = '{0} {1}'.format(givenname, surname)
            author_entity, created = Entity.objects.get_or_create(name=fullname)

            if created:
                try:
                    type_obj = Type.objects.get(uri=type_uri)
                except ObjectDoesNotExist:
                    type_obj = Type.objects.get_or_create(name="Person")[0]

                author_entity.entity_type = type_obj
                author_entity.save()

            # The author Entity may have already been instantiated as a
            #  subclass.
            return author_entity.cast()


    def ingest(self):
        pass
