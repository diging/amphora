from django.core.management.base import BaseCommand

from cookies.admin import import_schema


class Command(BaseCommand):
    def handle(self, *args, **options):
        import_schema("./cookies/static/cookies/schemas/22-rdf-syntax-ns.rdf", "RDF", prefix='rdf', namespace='http://www.w3.org/1999/02/22-rdf-syntax-ns')
        import_schema("./cookies/static/cookies/schemas/dcelements.rdf", "DCElements", prefix='dc', namespace='http://purl.org/dc/elements/1.1/')
        import_schema("./cookies/static/cookies/schemas/dcterms.rdf", "DCTerms", prefix='dcterms', namespace='http://purl.org/dc/terms/')
        import_schema("./cookies/static/cookies/schemas/biblio.rdf", "Biblio", prefix='bib', namespace='http://purl.org/net/biblio#')
        import_schema("./cookies/static/cookies/schemas/index.rdf", "FOAF", prefix='foaf', namespace='http://xmlns.com/foaf/0.1/')
