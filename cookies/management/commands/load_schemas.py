from django.core.management.base import BaseCommand

from cookies.admin import import_schema


class Command(BaseCommand):
    def handle(self, *args, **options):
        import_schema("./cookies/static/cookies/schemas/22-rdf-syntax-ns.rdf", "RDF")
        import_schema("./cookies/static/cookies/schemas/dcelements.rdf", "DCElements")
        import_schema("./cookies/static/cookies/schemas/dcterms.rdf", "DCTerms")
        import_schema("./cookies/static/cookies/schemas/biblio.rdf", "Biblio")
        import_schema("./cookies/static/cookies/schemas/index.rdf", "FOAF")
