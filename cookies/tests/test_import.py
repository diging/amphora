import unittest, mock, tempfile, types, os, datetime

from rdflib import Graph, Literal, BNode, Namespace, RDF, URIRef
from rdflib.namespace import DC, FOAF, DCTERMS

BIB = Namespace('http://purl.org/net/biblio#')
RSS = Namespace('http://purl.org/rss/1.0/modules/link/')
ZOTERO = Namespace('http://www.zotero.org/namespaces/export#')

from cookies.accession import IngesterFactory, IngestManager
from cookies.tests.mocks import MockFile, MockIngester
from cookies.models import *
from cookies.accession.zotero import ZoteroIngest


class TestImport(unittest.TestCase):
    def setUp(self):
        self.factory = IngesterFactory()

    def test_import_factory(self):
        """
        The IngesterFactory should return a wrapped object that supports
        iteration. Each iteration should yield a :class:`.Resource` instance.
        """
        ingest_class = self.factory.get('cookies.tests.mocks.MockIngester')
        mock_file = MockFile()
        mock_file.read = mock.MagicMock(name='read')
        mock_file.read.return_value = [
            {'name': 'Test',},
            {'name': 'Test2',},
        ]
        ingester = ingest_class(mock_file)
        self.assertIsInstance(ingester, IngestManager)
        self.assertIsInstance(ingester.next(), Resource)
        self.assertEqual(mock_file.read.call_count, 1)


class TestZoteroIngesterWithManager(unittest.TestCase):
    def setUp(self):
        self.resource_data = {
            'created_by': User.objects.create(username='TestUser')
        }
        User.objects.create(username='AnonymousUser')

    def test_ingest(self):

        factory = IngesterFactory()
        ingest_class = factory.get('cookies.accession.zotero.ZoteroIngest')
        ingester = ingest_class("test_data/TestRDF.rdf")

        ingester.set_resource_defaults(**self.resource_data)
        N = 0
        for resource in ingester:
            self.assertIsInstance(resource, Resource)
            N += 1
        self.assertEqual(N, 20, "Should create 20 resources from this RDF.")

    def tearDown(self):
        User.objects.all().delete()
        ConceptEntity.objects.all().delete()
        Resource.objects.all().delete()
        Relation.objects.all().delete()


class TestZoteroIngesterWithManagerZIP(unittest.TestCase):
    def setUp(self):
        self.resource_data = {
            'created_by': User.objects.create(username='TestUser')
        }
        User.objects.create(username='AnonymousUser')

    def test_ingest(self):
        factory = IngesterFactory()
        ingest_class = factory.get('cookies.accession.zotero.ZoteroIngest')
        ingester = ingest_class("test_data/TestRDF.zip")
        ingester.set_resource_defaults(**self.resource_data)

        N = 0
        for resource in ingester:
            self.assertIsInstance(resource, Resource)
            self.assertGreater(resource.content.count(), 0,
                "Each resource in this RDF should have some form of content.")
            N += 1
        self.assertEqual(N, 20, "Should create 20 resources from this RDF.")

    def tearDown(self):
        User.objects.all().delete()
        ConceptEntity.objects.all().delete()
        Resource.objects.all().delete()
        Relation.objects.all().delete()


class TestZoteroIngesterRDFOnly(unittest.TestCase):
    def test_parse_zotero_rdf(self):
        ingester = ZoteroIngest("test_data/TestRDF.rdf")

        data = ingester.next()
        self.assertIn('name', data)
        self.assertIn('entity_type', data)
        # import pprint
        #
        # pprint.pprint(data)


class TestZoteroIngesterWithLinks(unittest.TestCase):
    def setUp(self):
        self.location = "http://asdf.com/2/"
        self.link = "file:///some/path.pdf"

        self.g = Graph()
        self.doc = BNode()
        self.doc2 = BNode()
        self.ident = BNode()

        self.g.add((self.doc, DCTERMS.dateSubmitted, Literal("2014-10-30 18:04:59")))
        self.g.add((self.doc, ZOTERO.itemType, Literal("attachment")))
        self.g.add((self.doc, RDF.type, ZOTERO.Attachment))
        self.g.add((self.doc, DC.identifier, self.ident))
        self.g.add((self.doc, DC.title, Literal("PubMed Central Link")))
        self.g.add((self.doc, RSS.type, Literal("text/html")))

        self.g.add((self.ident, RDF.type, DCTERMS.URI))
        self.g.add((self.ident, RDF.value, URIRef(self.location)))

        self.g.add((self.doc2, RSS.link, Literal(self.link)))

        _, self.rdf_path = tempfile.mkstemp(suffix='.rdf')
        self.g.serialize(self.rdf_path, encoding='utf-8')

    def test_handle_link(self):
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g
        predicate, values = ingester.handle_link(RSS.link, self.doc)
        values = dict(values)
        self.assertIn('url', values)
        self.assertEqual(values['url'], self.location,
            "The URI of the link target should be interpreted as an URL.")
        self.assertIsInstance(values[DCTERMS.dateSubmitted.toPython()],
                              datetime.datetime,
            "dateSubmitted should be recast as a datetime object.")

    def test_handle_file(self):
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g
        predicate, values = ingester.handle_link(RSS.link, self.doc2)
        values = dict(values)
        self.assertIn('link', values)
        self.assertEqual(values['link'], self.link.replace('file://', ''))

    def tearDown(self):
        os.remove(self.rdf_path)


class TestZoteroIngester(unittest.TestCase):
    def setUp(self):
        self.test_uri = 'http://the.cool.uri/1'
        self.test_doi = '10.123/45678'
        self.date = Literal("1991")
        _, self.rdf_path = tempfile.mkstemp(suffix='.rdf')
        self.g = Graph()
        self.doc = BNode()
        self.ident = BNode()
        self.ident2 = BNode()

        self.g.add((self.doc, RDF.type, BIB.Article))
        self.g.add((self.doc, DC.date, self.date))
        self.g.add((self.doc, DC.title, Literal("A T\xc3\xa9st Title".decode('utf-8'))))
        self.g.add((self.doc, RSS.link, Literal(u"http://asdf.com")))
        self.g.add((self.doc, DC.identifier, self.ident))
        self.g.add((self.ident, RDF.type, DCTERMS.URI))
        self.g.add((self.ident, RDF.value, URIRef(self.test_uri)))
        self.g.add((self.doc, DC.identifier, self.ident2))
        self.g.add((self.ident2, RDF.type, BIB.doi))
        self.g.add((self.ident2, RDF.value, URIRef(self.test_doi)))
        self.g.serialize(self.rdf_path, encoding='utf-8')

    def test_load_graph(self):
        """
        Unit test for :meth:`ZoteroIngest.__init__` with RDF document only.
        """
        ingester = ZoteroIngest(self.rdf_path)
        self.assertIsInstance(ingester.graph, Graph,
            "When a path to an RDF document is passed to the constructor, an"
            " rdflib.Graph should be instantiated and populated.")
        self.assertEqual(len(ingester.graph), 10,
            "The Graph should be populated with 10 nodes.")

    def test_get_resources_nodes(self):
        """
        Unit test for :meth:`ZoteroIngest._get_resources_nodes`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        nodes = ingester._get_resources_nodes(BIB.Article)
        self.assertIsInstance(nodes, types.GeneratorType,
            "_get_resources_nodes Should return a generator object that yields"
            " rdflib.BNodes.")

        nodes = [n for n in nodes]
        self.assertIsInstance(nodes[0], BNode)
        self.assertEqual(len(nodes), 1, "There should be one Article node.")

    def test_new_entry(self):
        """
        Unit test for :meth:`ZoteroIngest._new_entry`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        before = len(ingester.data)
        ingester._new_entry()
        after = len(ingester.data)
        self.assertEqual(after, before + 1,
                         "A new entry should be added to ingester.data")

    def test_set_value(self):
        """
        Unit test for :meth:`ZoteroIngest._set_value`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        ingester._new_entry()
        ingester._set_value("key", "value")

        self.assertIn("key", ingester.data[-1],
            "_set_value should add the key to the current entry.")
        self.assertEqual(ingester.data[-1]["key"], ["value"],
            "_set_value should add the value to a list")

    def test_get_handler(self):
        """
        Unit test for :meth:`ZoteroIngest._get_handler`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        handler = ingester._get_handler(DC.identifier)
        self.assertIsInstance(handler, types.MethodType,
            "_get_handler should return an instance method if the predicate"
            "  has an explicit handler.")

        try:
            handler('one', 'two')
        except TypeError:
            self.fail("The returned handler should accept two arguments.")

        handler = ingester._get_handler("nonsense")
        self.assertIsInstance(handler, types.LambdaType,
            "_get_handler should return a lambda function if the predicate"
            "  does not have an explicit handler.")

        try:
            handler('one', 'two')
        except TypeError:
            self.fail("The returned handler should accept two arguments.")

    def test_handle_identifier(self):
        """
        Unit test for :meth:`ZoteroIngest.handle_identifier`\.
        """
        ingester = ZoteroIngest(self.rdf_path)

        # We want to intervene on our original graph here.
        ingester.graph = self.g
        result = ingester.handle_identifier(DC.identifier, self.ident)
        self.assertIsInstance(result, tuple,
            "Handlers should return tuples.")
        self.assertEqual(result[0], 'uri',
            "DCTERMS.URI identifiers should be used as first-class URIs.")
        self.assertEqual(result[1].toPython(), self.test_uri)

        result = ingester.handle_identifier(DC.identifier, self.ident2)
        self.assertIsInstance(result, tuple,
            "Handlers should return tuples.")
        self.assertEqual(result[0], BIB.doi)
        self.assertEqual(result[1].toPython(), self.test_doi)

    def test_handle_date(self):
        """
        Unit test for :meth:`ZoteroIngest.handle_date`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g

        predicate, value = ingester.handle_date(DC.date, self.date)
        self.assertIsInstance(value, datetime.datetime,
            "ISO-8601 compliant dates should be recast to datetime instances.")

    def test_handle_type(self):
        """
        Unit test for :meth:`ZoteroIngest.handle_documentType`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g

        predicate, value = ingester.handle_documentType(ZOTERO.itemType, "!")
        self.assertEqual(predicate, "entity_type",
            "ZOTERO.itemType should be flagged as the Resource.entity_type")

    def test_handle_title(self):
        """
        Unit test for :meth:`ZoteroIngest.handle_title`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g

        predicate, value = ingester.handle_title(DC.title, "!")
        self.assertEqual(predicate, "name",
            "DC.title should be flagged as the Resource.name")

    def test_handle(self):
        """
        Unit test for :meth:`ZoteroIngest.handle`\.
        """
        ingester = ZoteroIngest(self.rdf_path)
        ingester.graph = self.g
        ingester._new_entry()     # Need somewhere to put the value.
        predicate, value = ingester.handle(DC.identifier, self.ident)
        self.assertEqual(value, self.test_uri,
            "handle() should pass along the predicate and value to"
            " handle_identifier(), and return native Python types.")

        predicate, value = ingester.handle(DC.nonsense, "value")
        self.assertEqual(predicate, DC.nonsense.toPython(),
            "If there are no special handlers for the predicate, it should be"
            " returned as a native Python type.")
        self.assertEqual(value, "value",
            "So too with the corresponding value.")

    def tearDown(self):
        os.remove(self.rdf_path)
