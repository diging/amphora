from __future__ import absolute_import

from celery import shared_task

import os, re, rdflib, zipfile, tempfile, codecs, chardet, unicodedata, iso8601
import shutil, copy
import xml.etree.ElementTree as ET

from django.conf import settings
logger = settings.LOGGER

from datetime import datetime

from cookies.models import *


# rdflib complains a lot.
logging.getLogger("rdflib").setLevel(logging.ERROR)


from rdflib import Graph, Literal, BNode, Namespace, RDF, URIRef
from rdflib.namespace import DC, FOAF, DCTERMS

BIB = Namespace('http://purl.org/net/biblio#')
RSS = Namespace('http://purl.org/rss/1.0/modules/link/')
ZOTERO = Namespace('http://www.zotero.org/namespaces/export#')

RESOURCE_CLASSES = [
    BIB.Illustration, BIB.Recording, BIB.Legislation, BIB.Document,
    BIB.BookSection, BIB.Book, BIB.Data, BIB.Letter, BIB.Report,
    BIB.Article, BIB.Thesis, BIB.Manuscript, BIB.Image,
    BIB.ConferenceProceedings
]


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
        (RDF.type, 'documentType'),
        (RSS.type, 'content_type'),
    ]

    def __init__(self, path, classes=copy.deepcopy(RESOURCE_CLASSES)):
        self.file_paths = {}
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
            else:
                self.file_paths[file_path] = temp_path

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
        self.classes = copy.deepcopy(classes)
        self.current_class = None
        self.current_entries = self.graph.subjects(ZOTERO.itemType)

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
        if isinstance(new_value, list):
            current_value += new_value
        else:
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

    def handle_content_type(self, predicate, node):
        return 'content_type', node

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
            if p == DC.identifier:
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
        if ident_type == DCTERMS.URI:
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
                p, o = 'link', self.file_paths.get(link_path, link_path)
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

        norm = lambda s: s.toPython()
        author_data = []
        for s, p, o in self.graph.triples((node, None, None)):
            if isinstance(o, BNode):
                forename_iter = self.graph.objects(o, FOAF.givenname)
                surname_iter = self.graph.objects(o, FOAF.surname)
                forename = u' '.join(map(norm, [n for n in forename_iter]))
                surname = u' '.join(map(norm, [n for n in surname_iter]))

                data = {
                    'name': ' '.join([forename, surname]),
                    'entity_type': FOAF.Person,
                    FOAF.givenname.toPython(): forename,
                    FOAF.surname.toPython(): surname,
                }
                if surname.startswith('http://'):
                    data.update({'uri': surname,})
                author_data.append(data)
        return predicate, author_data

    def process(self, entry):
        """
        Process all predicate/value pairs for a single ``entry``
        :class:`rdflib.BNode` representing a resource.
        """

        if entry is None:
            raise RuntimeError('entry must be a specific node')

        map(lambda p_o: self._set_value(*self.handle(*p_o)),
            self.graph.predicate_objects(entry))

    def __iter__(self):
        return self

    def next(self):
        next_entry = None
        while next_entry is None:
            next_entry = self.current_entries.next()
            for i in self.graph.objects(subject=next_entry):
                if str(i) == 'attachment':
                    next_entry = None
                    break

        self._new_entry()
        self.process(next_entry)
        return self.current.entry

    @property
    def current(self):
        return EntryWrapper(self.data[-1])

    def __len__(self):
        return sum([len(list(self._get_resources_nodes(cl))) for cl in self.classes])

    def __del__(self):
        """
        Remove temporary files.
        """
        if hasattr(self, 'dtemp'):
            shutil.rmtree(self.dtemp)
