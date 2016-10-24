"""
"""

from django.contrib.contenttypes.models import ContentType

import unittest, mock, json

from cookies import operations
from cookies.models import *
from concepts.models import Concept


class TestPruneRelations(unittest.TestCase):
    def test_prune_relations_identical_target(self):
        resource_1 = Resource.objects.create(name='The first one')
        a_value = Value.objects.create()
        a_value.name = 'The value'
        a_value.save()
        some_predicate = Field.objects.create(name='related')
        for i in xrange(5):
            Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)

        operations.prune_relations(resource_1)
        resource_1.refresh_from_db()
        self.assertEqual(resource_1.relations_from.count(), 1)

    def test_prune_relations_same_value(self):
        resource_1 = Resource.objects.create(name='The first one')

        some_predicate = Field.objects.create(name='related')
        for i in xrange(5):
            a_value = Value.objects.create()
            a_value.name = 'The value'
            a_value.save()
            Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)

        operations.prune_relations(resource_1)
        resource_1.refresh_from_db()
        self.assertEqual(resource_1.relations_from.count(), 1)

    def test_prune_relations_same_value_and_friends(self):
        resource_1 = Resource.objects.create(name='The first one')

        some_predicate = Field.objects.create(name='related')
        for i in xrange(5):
            a_value = Value.objects.create()
            a_value.name = 'The value'
            a_value.save()
            Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
        for i in xrange(5):
            a_value = Value.objects.create()
            a_value.name = 'The other value'
            a_value.save()
            Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)

        operations.prune_relations(resource_1)
        resource_1.refresh_from_db()
        self.assertEqual(resource_1.relations_from.count(), 2)

    def test_prune_relations_same_value_different_predicate(self):
        resource_1 = Resource.objects.create(name='The first one')

        some_predicate = Field.objects.create(name='related')
        another_predicate = Field.objects.create(name='related!')
        for i in xrange(5):
            a_value = Value.objects.create()
            a_value.name = 'The value'
            a_value.save()
            Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
        for i in xrange(5):
            a_value = Value.objects.create()
            a_value.name = 'The value'
            a_value.save()
            Relation.objects.create(source=resource_1, predicate=another_predicate, target=a_value)

        operations.prune_relations(resource_1)
        resource_1.refresh_from_db()
        self.assertEqual(resource_1.relations_from.count(), 2)


class TestMergeConceptEntities(unittest.TestCase):
    def test_merge_two(self):
        """
        Only one :class:`.ConceptEntity` should remain.
        """
        for i in xrange(2):
            ConceptEntity.objects.create(name='entity %i' % i)
        entities = ConceptEntity.objects.all()
        count_before = ConceptEntity.objects.all().count()
        master = operations.merge_conceptentities(entities)
        count_after = ConceptEntity.objects.all().count()

        self.assertEqual(count_before - 1, count_after,
                         "merge_conceptentities() should delete all but one"
                         " of the original ConceptEntity instances.")
        self.assertIsInstance(master, ConceptEntity,
                              "merge_conceptentities should return a"
                              " ConceptEntity instance")

    def test_merge_N(self):
        """
        Only one :class:`.ConceptEntity` should remain from the original
        QuerySet.
        """

        N = 5    # This should pass for aribitrary N > 1.
        for i in xrange(N):
            # c = Concept.
            ConceptEntity.objects.create(name='entity %i' % i)
        entities = ConceptEntity.objects.all()
        count_before = ConceptEntity.objects.all().count()
        operations.merge_conceptentities(entities)
        count_after = ConceptEntity.objects.all().count()

        self.assertEqual(count_before - (N - 1), count_after,
                         "merge_conceptentities() should delete all but one"
                         " of the original ConceptEntity instances.")

    def test_merge_with_concept(self):
        """
        The remaining :class:`.ConceptEntity` should be associated with
        the one :class:`.Concept` in the queryset.
        """
        uri = 'http://f.ake'
        for i in xrange(5):
            c = ConceptEntity.objects.create(name='entity %i' % i)
            if i == 3:
                c.concept = Concept.objects.create(uri=uri)
                c.save()

        entities = ConceptEntity.objects.all()
        master = operations.merge_conceptentities(entities)
        self.assertEqual(master.concept.uri, uri,
                         "The concept for the master ConceptEntity was not"
                         " set correctly.")

    def test_cannot_merge_with_two_concepts(self):
        """

        """
        for i in xrange(5):
            c = ConceptEntity.objects.create(name='entity %i' % i)
            if i == 3 or i == 1:
                c.concept = Concept.objects.create(uri='http://f%i.ake' % i)
                c.save()

        entities = ConceptEntity.objects.all()
        with self.assertRaises(RuntimeError):
            operations.merge_conceptentities(entities)

    def test_cannot_merge_one(self):
        """
        Should raise a RuntimeError if less than two :class:`.ConceptEntity`
        instances are passed in the QuerySet.
        """
        ConceptEntity.objects.create(name='entity only')
        entities = ConceptEntity.objects.all()
        with self.assertRaises(RuntimeError):
            operations.merge_conceptentities(entities)

    def test_merge_updates_relations(self):
        """
        :class:`.Relation` instances that point to merged
        :class:`.ConceptEntity` instances should accrue  to the "master"
        :class:`.ConceptEntity`\.
        """
        N = 5
        ce1 = ConceptEntity.objects.create(name='the first one')
        ce2 = ConceptEntity.objects.create(name='the second one')
        predicate = Field.objects.get_or_create(name='predicate')[0]
        for i in xrange(N):
            Relation.objects.create(source=ce1, predicate=predicate, target=ce2)
        entities = ConceptEntity.objects.all()
        master = operations.merge_conceptentities(entities)

        self.assertEqual(master.relations_from.count(), N)
        self.assertEqual(master.relations_to.count(), N)

    def tearDown(self):
        ConceptEntity.objects.all().delete()
