# import django
# from django.test import TestCase, Client
# from django.test.client import RequestFactory
# from django.contrib.auth.models import User
# from django.contrib.admin.helpers import AdminForm
# from django.core.urlresolvers import reverse, resolve
#
# from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
#
# from cookies.forms import *
# from cookies.models import *
# from cookies.ingest import ZoteroRDFIngester
# from cookies.admin import import_schema
#
# #class SchemaFromRDF(TestCase):
# #    def test_class_generates_type(self):
# #        """
# #        RDF:Class and OWL:Class elements should result in new Type instances.
# #        """
# #
# #        # Biblio uses OWL:Class elements.
# #        import_schema("./cookies/static/cookies/schemas/biblio.rdf", 'Biblio')
# #
# #        biblio = Schema.objects.get(name='Biblio')
# #        self.assertGreater(biblio.types.count(), 0)
# #
# #    def test_cidoc_crm(self):
# #        import_schema("./cookies/static/cookies/schemas/cidoc_crm_v5.0.4_official_release.rdfs.xml", 'CIDOC CRM')
#
#
#
# class IngestZoteroRDF(TestCase):
#     def setUp(self):
#         self.ingester = ZoteroRDFIngester()
#         self.fp = open("../test_data/TestRDF.zip", "r")
#
#         import_schema("./cookies/static/cookies/schemas/22-rdf-syntax-ns.rdf", "RDF")
#         import_schema("./cookies/static/cookies/schemas/dcelements.rdf", "DCElements")
#         import_schema("./cookies/static/cookies/schemas/dcterms.rdf", "DCTerms")
#         import_schema("./cookies/static/cookies/schemas/biblio.rdf", "Biblio")
#         import_schema("./cookies/static/cookies/schemas/index.rdf", "FOAF")
#
#     def test_parse(self):
#         self.ingester.load(self.fp)
#         self.ingester.parse()
#
#         local = LocalResource.objects.filter(entity_type__name='Biblio.article')
#         remote = RemoteResource.objects.filter(entity_type__name='Biblio.article')
#
#         self.assertEqual(local.count(), 10)
#         self.assertEqual(remote.count(), 10)
# #
# #
# #
# #
# #
