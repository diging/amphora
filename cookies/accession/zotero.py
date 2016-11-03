from __future__ import absolute_import

from celery import shared_task

import os, re, rdflib, zipfile, tempfile, codecs, chardet, unicodedata, iso8601
import xml.etree.ElementTree as ET

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

from datetime import datetime

from cookies.models import *


# rdflib complains a lot.
logging.getLogger("rdflib").setLevel(logging.ERROR)

# RDF terms.
RDF = u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
DC = u'http://purl.org/dc/elements/1.1/'
FOAF = u'http://xmlns.com/foaf/0.1/'
PRISM = u'http://prismstandard.org/namespaces/1.2/basic/'
RSS = u'http://purl.org/rss/1.0/modules/link/'
BIBLIO = u'http://purl.org/net/biblio#'
ZOTERO = u'http://www.zotero.org/namespaces/export#'

URI_ELEM = rdflib.URIRef("http://purl.org/dc/terms/URI")
TYPE_ELEM = rdflib.term.URIRef(RDF + u'type')
VALUE_ELEM = rdflib.URIRef(RDF + u'value')
LINK_ELEM = rdflib.URIRef(RSS + u"link")
FORENAME_ELEM = rdflib.URIRef(FOAF + u'givenname')
SURNAME_ELEM = rdflib.URIRef(FOAF + u'surname')
VOL = rdflib.term.URIRef(PRISM + u'volume')
ISSUE = rdflib.term.URIRef(PRISM + u'number')
IDENT = rdflib.URIRef(DC + u"identifier")
TITLE = rdflib.term.URIRef(DC + u'title')
IDENTIFIER = rdflib.term.URIRef(DC + u'identifier')


BOOK = rdflib.term.URIRef(BIBLIO + 'Book')
JOURNAL = rdflib.term.URIRef(BIBLIO + 'Journal')
WEBSITE = rdflib.term.URIRef(ZOTERO + 'Website')

# TODO: We don't have the right relation types to support WEBSITE yet!
PARTOF_TYPES = [
    (BOOK, 'book'),
    (JOURNAL, 'journal'),
]

from rdflib import Graph, Literal, BNode, Namespace, RDF, URIRef
from rdflib.namespace import DC, FOAF, DCTERMS

BIB = Namespace('http://purl.org/net/biblio#')
RSS = Namespace('http://purl.org/rss/1.0/modules/link/')
ZOTERO = Namespace('http://www.zotero.org/namespaces/export#')

RESOURCE_CLASSES = [
    BIB.Illustration, BIB.Recording, BIB.Legislation, BIB.Document,
    BIB.BookSection, BIB.Book, BIB.Data, BIB.Letter, BIB.REPORT,
    BIB.Article, BIB.Thesis, BIB.Manuscript, BIB.Image,
    BIB.ConferenceProceedings,
]

class dobject(object):
    pass


class Paper(object):
    pass


def _cast(value):
    """
    Attempt to convert ``value`` to an ``int`` or ``float``. If unable, return
    the value unchanged.
    """

    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


class EntryWrapper(object):
    """
    Convenience wrapper for entries in :class:`.ZoteroIngest`\.
    """
    def __init__(self, entry):
        self.entry = entry

    def get(self, key, default=None):
        return self.entry.get(key, default)

    def __getitem__(self, key):
        return self.entry[key]

    def __setitem__(self, key, value):
        self.entry[key] = value


class ZoteroIngest(object):
    """
    Ingest Zotero RDF and attachments contained in a zip archive.

    Parameters
    ----------
    path : str
        Location of ZIP archive containing Zotero RDF and attachments.
    """
    handlers = [
        (DC.date, 'date'),
        (DCTERMS.dateSubmitted, 'date'),
        (DC.identifier, 'identifier'),
        (DCTERMS.abstract, 'abstract'),
        (BIB.authors, 'name'),
        (ZOTERO.seriesEditors, 'name'),
        (BIB.editors, 'name'),
        (BIB.contributors, 'name'),
        (ZOTERO.translators, 'name'),
        (RSS.link, 'link'),
        (DC.title, 'title'),
        (DCTERMS.isPartOf, 'isPartOf'),
        (BIB.pages, 'pages'),
        (ZOTERO.itemType, 'documentType')
    ]

    def __init__(self, path, classes=RESOURCE_CLASSES):
        if path.endswith('.zip'):
            self._unpack_zipfile(path)
        else:
            self.rdf = path
            self.zipfile = None

        self._correct_zotero_violation()
        self._init_graph(self.rdf, classes=classes)
        self.data = []    # All results will go here.

    def _unpack_zipfile(self, path):
        """
        Extract all files in the zipfile at ``path`` into a temporary directory.
        """
        self.zipfile = zipfile.ZipFile(path)
        self._init_dtemp()

        self.paths = []
        for file_path in self.zipfile.namelist():
            if path.startswith('.'):
                continue
            temp_path = self.zipfile.extract(file_path, self.dtemp)

            if temp_path.endswith('.rdf'):
                self.rdf = temp_path

    def _correct_zotero_violation(self):
        """
        Zotero produces invalid RDF, so we need to directly intervene before
        parsing the RDF document.
        """
        with open(self.rdf, 'r') as f:
            corrected = f.read().replace('rdf:resource rdf:resource',
                                         'link:link rdf:resource')
        with open(self.rdf, 'w') as f:
            f.write(corrected)

    def _init_graph(self, rdf_path, classes=RESOURCE_CLASSES):
        """
        Load the RDF document as a :class:`rdflib.Graph`\.
        """
        self.graph = rdflib.Graph()
        self.graph.parse(rdf_path)
        self.entries = []

        self.classes = classes
        self.current_class = None
        self.current_entries = None

    def _init_dtemp(self):
        self.dtemp = tempfile.mkdtemp()

    def _get_resources_nodes(self, resource_class):
        """
        Retrieve all nodes in the graph with type ``resource_class``.

        Parameters
        ----------
        resource_class : :class:`rdflib.URIRef`

        Returns
        -------
        generator
            Yields nodes.
        """
        return self.graph.subjects(RDF.type, resource_class)

    def _new_entry(self):
        """
        Start work on a new entry in the dataset.
        """
        self.data.append({})

    def _set_value(self, predicate, new_value):
        """
        Assign ``new_value`` to key ``predicate`` in the current entry.

        For the sake of consistency, each predicate in the entry corresponds to
        a list of values, even if only one value is present.
        """
        if not predicate:
            return

        try:
            current_value = self.current.get(predicate, [])
        except IndexError:
            raise RuntimeError("_new_entry() must be called before values"
                               " can be set.")
        current_value.append(new_value)
        self.current[predicate] = current_value

    def _get_handler(self, predicate):
        """
        Retrieve the handler defined for ``predicate``, if there is one.
        Otherwise, returns a callable that coerces any passed arguments to
        native Python types.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef` or str

        Returns
        -------
        instancemethod or lambda
            Callable that accepts a pair of positional arguments (presumed to
            be predicate and value) and returns a (predicate, value) tuple.
        """
        predicate = dict(self.handlers).get(predicate, predicate)
        handler_name = 'handle_{predicate}'.format(predicate=predicate)

        # If there is no defined handler, we minimally want to end up with
        #  native Python types. Returning a callable here avoids extra code.
        generic = lambda *args: map(self._to_python, args)
        return getattr(self, handler_name, generic)

    def _to_python(self, obj):
        """
        Ensure that any :class:`rdflib.URIRef` instances are coerced to a
        native Python type.
        """
        return obj.toPython() if hasattr(obj, 'toPython') else obj

    def handle(self, predicate, value):
        """
        Farm out any defined processing logic for a predicate/value pair.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef` or str
        value : :class:`.URIRef` or :class:`.BNode` or :class:`.Literal`

        Returns
        -------
        tuple
            Predicate, value.
        """
        predicate, value = self._get_handler(predicate)(predicate, value)
        return self._to_python(predicate), self._to_python(value)

    def handle_isPartOf(self, predicate, node):
        """
        Unpack DCTERMS.isPartOf relations, to extract journals names, books,
        etc.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef` or str
        value : :class:`.URIRef` or :class:`.BNode` or :class:`.Literal`

        Returns
        -------
        tuple

        """
        parent_document = []
        for p, o in self.graph.predicate_objects(node):
            if p == IDENT:
                # Zotero (in all of its madness) makes some identifiers, like
                #  DOIs, properties of Journals rather than the Articles to
                #  which they belong. The predicate for these relations
                #  is identifier, and the object contains both the identifier
                #  type and the identifier itself, eg.
                #       "DOI 10.1017/S0039484"
                try:
                    name, ident_value = tuple(unicode(o).split(' '))
                    if name.upper() in ['ISSN', 'ISBN']:
                        parent_document.append((unicode(p), unicode(o)))
                    elif name.upper() == 'DOI':
                        self._set_value(*self.handle(p, o))
                except ValueError:
                    pass
            elif p in [DC.title, DCTERMS.alternative, RDF.type]:
                parent_document.append(self.handle(p, o))
        return predicate, dict(parent_document)

    def handle_documentType(self, predicate, node):
        """
        ZOTERO.itemType should be used to populate Resource.entity_type.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef` or str
        value : :class:`.URIRef`

        Returns
        -------
        tuple
            Predicate, value.
        """
        return 'entity_type', node

    def handle_title(self, predicate, node):
        """
        DC.title should be used to populate Resource.name.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef` or str
        value : :class:`.URIRef`

        Returns
        -------
        tuple
            Predicate, value.
        """
        return 'name', node

    def handle_identifier(self, predicate, node):
        """
        Parse an ``DC.identifier`` node.

        If the identifier is an URI, we pull this out an assign it with a
        non-URI predicate; this will directly populate the ``Resource.uri``
        field in the database.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef`
        node : :class:`rdflib.BNode`

        Returns
        -------
        tuple
            Predicate and value.
        """

        identifier = self.graph.value(subject=node, predicate=RDF.value)
        ident_type = self.graph.value(subject=node, predicate=RDF.type)
        if ident_type == DC.URI:
            return 'uri', identifier
        return ident_type, identifier

    def handle_link(self, predicate, node):
        """
        rdf:link rdf:resource points to the resource described by a record.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef`
        node : :class:`rdflib.BNode`

        Returns
        -------
        tuple
            Predicate and value.
        """
        link_data = []
        for p, o in self.graph.predicate_objects(node):
            if p == DC.identifier:
                p, o = self.handle_identifier(p, o)
                p = 'url' if p == 'uri' else p
            elif p == RSS.link:
                link_path =  self._to_python(o).replace('file://', '')
                p, o = 'link', link_path
            else:
                p, o = self.handle(p, o)
            link_data.append((self._to_python(p), self._to_python(o)))
        return 'file', dict(link_data)

    def handle_date(self, predicate, node):
        """
        Attempt to coerce date to ISO8601.
        """
        node = node.toPython()
        try:
            return predicate, iso8601.parse_date(node)
        except iso8601.ParseError:
            for datefmt in ("%B %d, %Y", "%Y-%m", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    # TODO: remove str coercion.
                    return predicate, datetime.strptime(node, datefmt).date()
                except ValueError:
                    return predicate, node

    def handle_name(self, predicate, node):
        """
        Extract a concise surname, forename tuple from a composite person.

        Parameters
        ----------
        predicate : :class:`rdflib.URIRef`
        node : :class:`rdflib.BNode`

        Returns
        -------
        tuple
            Predicate and value.
        """
        forename_iter = self.graph.objects(node, FOAF.givenname)
        surname_iter = self.graph.objects(node, FOAF.surname)
        norm = lambda s: unicode(s).upper().replace('.', '')

        forename = u' '.join(map(norm, forename_iter))
        surname = u' '.join(map(norm, surname_iter))
        return predicate, (surname, forename)

    def process(self, entry):
        """
        Process all predicate/value pairs for a single ``entry``
        :class:`rdflib.BNode` representing a resource.
        """

        if entry is None:
            raise RuntimeError('entry must be a specific node')

        map(lambda p_o: self._set_value(*self.handle(*p_o)),
            self.graph.predicate_objects(entry))

    def next(self):
        next_entry = None
        while next_entry is None:
            try:
                next_entry = self.current_entries.next()
            except (StopIteration, AttributeError):
                try:
                    self.current_class = self.classes.pop()
                except IndexError:    # Out of classes.
                    raise StopIteration()
                self.current_entries = self._get_resources_nodes(self.current_class)

        self._new_entry()
        self.process(next_entry)
        return self.current.entry

    @property
    def current(self):
        return EntryWrapper(self.data[-1])


class BaseParser(object):
    """
    Base class for all data parsers. Do not instantiate directly.
    """

    def __init__(self, zfile, **kwargs):
        self.zipfile = zipfile.ZipFile(zfile)
        self.fnames = [ name for name in self.zipfile.namelist()
                            if not name.startswith('._') ]
        for fname in self.fnames:
            self.zipfile.extract(fname, '/tmp/')

        # Locate the RDF file.
        self.rdfname = [name for name in self.fnames
                        if name.lower().endswith('.rdf') ][0]

        self.path = self.zipfile.extract(self.rdfname, '/tmp/')

        self.data = []
        self.fields = set([])

        for k, v in kwargs.items():
            setattr(self, k, v)

        self.open()


    def new_entry(self):
        """
        Prepare a new data entry.
        """
        self.data.append(self.entry_class())

    def _get_handler(self, tag):
        handler_name = 'handle_{tag}'.format(tag=tag)
        names, fields = zip(*self.meta_elements)
        name_lookup = dict(zip([unicode(field) for field in fields], names))

        if hasattr(self, handler_name):
            return getattr(self, handler_name)
        else:
            if tag in name_lookup:
                handler_name = 'handle_{name}'.format(name=name_lookup[tag])
                if hasattr(self, handler_name):
                    return getattr(self, handler_name)
        return

    def set_value(self, tag, value):
        if hasattr(self, tag):
            current_value = getattr(self, tag)
            if type(current_value) is not list:
                setattr(self, tag, [current_value])
            setattr(self, tag, getattr(self, tag) + [value])

        setattr(self.data[-1], tag, value)

    def postprocess_entry(self):
        for field in self.fields:
            processor_name = 'postprocess_{0}'.format(field)
            if hasattr(self.data[-1], field) and hasattr(self, processor_name):
                getattr(self, processor_name)(self.data[-1])

        if hasattr(self, 'reject_if'):
            if self.reject_if(self.data[-1]):
                del self.data[-1]


class IterParser(BaseParser):
    entry_class = dobject
    """Model for data entry."""

    concat_fields = []
    """
    Multi-line fields here should be concatenated, rather than represented
    as lists.
    """

    tags = {}

    def __init__(self, *args, **kwargs):
        super(IterParser, self).__init__(*args, **kwargs)

        self.current_tag = None
        self.last_tag = None

        if kwargs.get('autostart', True):
            self.start()

    def parse(self):
        """

        """
        while True:        # Main loop.
            tag, data = self.next()
            if self.is_eof(tag):
                self.postprocess_entry()
                break

            self.handle(tag, data)
            self.last_tag = tag
        return self.data

    def start(self):
        """
        Find the first data entry and prepare to parse.
        """

        while not self.is_start(self.current_tag):
            self.next()
        self.new_entry()

    def handle(self, tag, data):
        """
        Process a single line of data, and store the result.

        Parameters
        ----------
        tag : str
        data :
        """

        if isinstance(data,unicode):
            data = unicodedata.normalize('NFKD', data)#.encode('utf-8','ignore')

        if self.is_end(tag):
            self.postprocess_entry()

        if self.is_start(tag):
            self.new_entry()

        if data is None or tag is None:
            return

        handler = self._get_handler(tag)
        if handler is not None:
            data = handler(data)

        if tag in self.tags:    # Rename the field.
            tag = self.tags[tag]

        # Multiline fields are represented as lists of values.
        if hasattr(self.data[-1], tag):
            value = getattr(self.data[-1], tag)
            if tag in self.concat_fields:
                value = ' '.join([value, unicode(data)])
            elif type(value) is list:
                value.append(data)
            elif value not in [None, '']:
                value = [value, data]
        else:
            value = data
        setattr(self.data[-1], tag, value)
        self.fields.add(tag)


class RDFParser(BaseParser):
    entry_elements = ['Document']
    meta_elements = []
    concat_fields = []

    def open(self):
        self.graph = rdflib.Graph()
        self.graph.parse(self.path)
        self.entries = []

        for element in self.entry_elements:
            query = 'SELECT * WHERE { ?p a ' + element + ' }'
            self.entries += [r[0] for r in self.graph.query(query)]

    def next(self):
        if len(self.entries) > 0:
            return self.entries.pop(0)

    def parse(self):
        meta_fields, meta_refs = zip(*self.meta_elements)

        while True:        # Main loop.
            entry = self.next()
            if entry is None:
                break

            self.new_entry()

            for s, p, o in self.graph.triples((entry, None, None)):
                # if p in meta_refs:  # Look for metadata fields.
                tag = unicode(p)
                # tag = meta_fields[meta_refs.index(p)]
                self.handle(tag, o)

            self.postprocess_entry()

        return self.data

    def handle(self, tag, data):
        handler = self._get_handler(tag)

        if handler is not None:
            data = handler(data)
        #
        # if tag in self.tags:
        #     tag_for_handler = self.tags[tag]

        if data is not None:
            # Multiline fields are represented as lists of values.
            if hasattr(self.data[-1], tag):
                value = getattr(self.data[-1], tag)
                if tag in self.concat_fields:
                    value = ' '.join([value, data])
                elif type(value) is list:
                    value.append(data)
                elif value not in [None, '']:
                    value = [value, data]
            else:
                value = data

            if type(value) is rdflib.term.Literal:
                value = value.toPython()
            setattr(self.data[-1], tag, value)

            self.fields.add(tag)


class ZoteroParser(RDFParser):
    """
    Reads Zotero RDF files.
    """

    entry_class = Paper
    entry_elements = ['bib:Illustration', 'bib:Recording', 'bib:Legislation',
                      'bib:Document', 'bib:BookSection', 'bib:Book', 'bib:Data',
                      'bib:Letter', 'bib:Report', 'bib:Article',
                      'bib:Manuscript', 'bib:Image',
                      'bib:ConferenceProceedings', 'bib:Thesis']


    tags = {
        # 'isPartOf': 'journal'
    }

    meta_elements = [
        ('date', rdflib.URIRef("http://purl.org/dc/elements/1.1/date")),
        ('identifier',
         rdflib.URIRef("http://purl.org/dc/elements/1.1/identifier")),
        ('abstract', rdflib.URIRef("http://purl.org/dc/terms/abstract")),
        ('authors_full', rdflib.URIRef("http://purl.org/net/biblio#authors")),
        ('seriesEditors',
         rdflib.URIRef("http://www.zotero.org/namespaces/export#seriesEditors")),
        ('editors', rdflib.URIRef("http://purl.org/net/biblio#editors")),
        ('contributors',
         rdflib.URIRef("http://purl.org/net/biblio#contributors")),
        ('translators',
         rdflib.URIRef("http://www.zotero.org/namespaces/export#translators")),
        ('link', rdflib.URIRef("http://purl.org/rss/1.0/modules/link/link")),
        ('title', rdflib.URIRef("http://purl.org/dc/elements/1.1/title")),
        ('isPartOf', rdflib.URIRef("http://purl.org/dc/terms/isPartOf")),
        ('pages', rdflib.URIRef("http://purl.org/net/biblio#pages")),
        ('documentType',
         rdflib.URIRef("http://www.zotero.org/namespaces/export#itemType"))]

    reject_if = lambda self, x: False

    def __init__(self, path, **kwargs):
        # name = os.path.split(path)[1]
        # path = os.path.join(path, '{0}.rdf'.format(name))
        super(ZoteroParser, self).__init__(path, **kwargs)

        self.full_text = {}     # Collect StructuredFeatures until finished.

    def open(self):
        """
        `Fix`es RDF validation issues. Zotero incorrectly uses ``rdf:resource`` as
        a child element for Attribute; ``rdf:resource`` should instead be used
        as an attribute of ``link:link``.
        """

        with open(self.path, 'r') as f:
            corrected = f.read().replace('rdf:resource rdf:resource',
                                         'link:link rdf:resource')
        with open(self.path, 'w') as f:
            f.write(corrected)

        super(ZoteroParser, self).open()



    def handle_authors_full(self, value):
        authors = [self.handle_author(o) for s, p, o
                   in self.graph.triples((value, None, None))]
        return [a for a in authors if a is not None]

    def handle_abstract(self, value):
        """
        Abstract handler.

        Parameters
        ----------
        value

        Returns
        -------
        abstract.toPython()
        Basically, RDF literals are casted to their corresponding Python data types.
        """
        return value.toPython()


    def handle_editors(self, value):
        return self.handle_authors_full(value)

    def handle_seriesEditors(self, value):
        return self.handle_authors_full(value)

    def handle_contributors(self, value):
        return self.handle_authors_full(value)

    def handle_translators(self, value):
        return self.handle_authors_full(value)



    def postprocess_pages(self, entry):
        if type(entry.pages) not in [tuple, list]:
            start = entry.pages
            end = None
        else:
            try: # ISISCB-395: Skip malformed page numbers.
                start, end = entry.pages
            except ValueError:
                setattr(entry, 'pagesFreeText', entry.pages)
                del entry.pages
                return
        setattr(entry, 'pageStart', start)
        setattr(entry, 'pageEnd', end)
        # del entry.pages


def read(path):
    """
    Read bibliographic data from Zotero RDF.

    Parameters
    ----------
    path : str
        Path to the RDF file created by Zotero.

    Returns
    -------
    list
    """

    parser = ZoteroParser(path, follow_links=False)
    papers = parser.parse()

    return papers
