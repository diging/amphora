from django.core.management.base import BaseCommand

from cookies.admin import import_schema
from cookies.models import ConceptEntity
from cookies import operations
import sys

class Command(BaseCommand):
    def handle(self, *args, **options):
        i = 0.
        N = ConceptEntity.objects.count()
        for entity in ConceptEntity.objects.all():
            i += 1.
            print '\r', 100.* i/N, '%',
            sys.stdout.flush()

            operations.isolate_conceptentity(entity)
