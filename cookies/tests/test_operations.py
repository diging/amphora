"""
"""

from django.contrib.contenttypes.models import ContentType

import unittest, mock, json

from cookies import operations
from cookies.models import *
from concepts.models import Concept
#
#
# class TestPruneRelations(unittest.TestCase):
#     def test_prune_relations_identical_target(self):
#         resource_1 = Resource.objects.create(name='The first one')
#         a_value = Value.objects.create()
#         a_value.name = 'The value'
#         a_value.save()
#         some_predicate = Field.objects.create(name='related')
#         for i in xrange(5):
#             Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
#
#         operations.prune_relations(resource_1)
#         resource_1.refresh_from_db()
#         self.assertEqual(resource_1.relations_from.count(), 1)
#
#     def test_prune_relations_same_value(self):
#         resource_1 = Resource.objects.create(name='The first one')
#
#         some_predicate = Field.objects.create(name='related')
#         for i in xrange(5):
#             a_value = Value.objects.create()
#             a_value.name = 'The value'
#             a_value.save()
#             Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
#
#         operations.prune_relations(resource_1)
#         resource_1.refresh_from_db()
#         self.assertEqual(resource_1.relations_from.count(), 1)
#
#     def test_prune_relations_same_value_and_friends(self):
#         resource_1 = Resource.objects.create(name='The first one')
#
#         some_predicate = Field.objects.create(name='related')
#         for i in xrange(5):
#             a_value = Value.objects.create()
#             a_value.name = 'The value'
#             a_value.save()
#             Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
#         for i in xrange(5):
#             a_value = Value.objects.create()
#             a_value.name = 'The other value'
#             a_value.save()
#             Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
#
#         operations.prune_relations(resource_1)
#         resource_1.refresh_from_db()
#         self.assertEqual(resource_1.relations_from.count(), 2)
#
#     def test_prune_relations_same_value_different_predicate(self):
#         resource_1 = Resource.objects.create(name='The first one')
#
#         some_predicate = Field.objects.create(name='related')
#         another_predicate = Field.objects.create(name='related!')
#         for i in xrange(5):
#             a_value = Value.objects.create()
#             a_value.name = 'The value'
#             a_value.save()
#             Relation.objects.create(source=resource_1, predicate=some_predicate, target=a_value)
#         for i in xrange(5):
#             a_value = Value.objects.create()
#             a_value.name = 'The value'
#             a_value.save()
#             Relation.objects.create(source=resource_1, predicate=another_predicate, target=a_value)
#
#         operations.prune_relations(resource_1)
#         resource_1.refresh_from_db()
#         self.assertEqual(resource_1.relations_from.count(), 2)
#
#
class TestMergeConceptEntities(unittest.TestCase):

    def setUp(self):
        for model in [ConceptEntity, User, Identity]:
            model.objects.all().delete()

    def test_merge_two(self):
        """
        Only one :class:`.ConceptEntity` should remain.
        """

        for i in xrange(2):
            ConceptEntity.objects.create(name='entity %i' % i)
        entities = ConceptEntity.objects.all()
        count_before = ConceptEntity.objects.all().count()
        master = operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))
        count_after = ConceptEntity.objects.all().count()

        self.assertEqual(count_before, count_after,
                         "No ConceptEntity instances should be deleted.")
        self.assertIsInstance(master, ConceptEntity,
                              "merge_conceptentities should return a"
                              " ConceptEntity instance")
        self.assertEqual(Identity.objects.count(), 1,
                         "Should create a new Identity")

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
        operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))
        count_after = ConceptEntity.objects.all().count()

        self.assertEqual(count_before, count_after,
                         "No ConceptEntity instances should be deleted.")

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
        master = operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))
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
            operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))

    def test_cannot_merge_one(self):
        """
        Should raise a RuntimeError if less than two :class:`.ConceptEntity`
        instances are passed in the QuerySet.
        """
        ConceptEntity.objects.create(name='entity only')
        entities = ConceptEntity.objects.all()
        with self.assertRaises(RuntimeError):
            operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))

    def tearDown(self):
        for model in [ConceptEntity, User, Identity]:
            model.objects.all().delete()
#
#
# class TestAddResourcesToCollection(unittest.TestCase):
#     def test_add_one(self):
#         """
#         Only one :class:`.Resource` instance should be added to a collection.
#         """
#         resource = Resource.objects.create(name='first_resource')
#         qs_resource = Resource.objects.all()
#         collection_before = Collection.objects.create(name='first_collection')
#         collection_after = operations.add_resources_to_collection(qs_resource, collection_before)
#
#         self.assertIn(resource, collection_after.resources.all(), "resource not added to collection\
#             add_resources_to_collection operation not performed")
#         self.assertIsInstance(collection_after, Collection,
#                               "add_resources_to_collection method should return a"
#                               " Collection instance")
#
#     def test_add_N(self):
#         """
#         All :class:`.Resource` instances should be added to collection
#         """
#
#         for i in xrange(5):
#             Resource.objects.create(name='resource_%i' % i)
#         resources = Resource.objects.all()
#         collection_before = Collection.objects.create(name='first_collection')
#         collection_after = operations.add_resources_to_collection(resources, collection_before)
#
#         self.assertIsInstance(collection_after, Collection,
#                               "Collection instance should be returned from"
#                               "add_resources_to_collection method")
#         for resource in resources:
#             self.assertIn(resource, collection_after.resources.all(), "%s not added to collection \
#                 add_resources_to_collection operation not performed" %resource.name)
#
#     def test_no_resource(self):
#         """
#         Should raise a RuntimeError if no :class:`.Resource`
#         instance is passed in the QuerySet.
#         """
#         resource = Resource.objects.all()
#         collection = Collection.objects.create(name='first_collection')
#         with self.assertRaises(RuntimeError):
#             operations.add_resources_to_collection(resource, collection)
#
#     def test_invalid_collection(self):
#         """
#         Should raise a RuntimeError if invalid :class:`.Collection`
#         instance is passed.
#         """
#         resource = Resource.objects.create(name='resource_1')
#         qs_resource = Resource.objects.all()
#         collection = resource
#         with self.assertRaises(RuntimeError):
#             operations.add_resources_to_collection(qs_resource, collection)
#
#     def tearDown(self):
#         Resource.objects.all().delete()
#         Collection.objects.all().delete()



class TestIsolationOperations(unittest.TestCase):
    def test_isolate_conceptentity(self):
        u = User.objects.create(username='TestUser')
        instance = ConceptEntity.objects.create(name='TestEntity', created_by=u)
        value = Value.objects.create()
        value.name = 'Test'
        value.save()
        Relation.objects.create(source=instance, target=value, predicate=Field.objects.create(name='Test'))

        resources = []
        for i in xrange(10):
            resource = Resource.objects.create(name='TestResource %i' % i, created_by=u)
            relation = Relation.objects.create(source=resource,
                                               target=instance,
                                               predicate=Field.objects.create(name='Test'))
            resources.append(resource)

        self.assertEqual(instance.relations_to.count(), 10)
        self.assertEqual(instance.relations_from.count(), 1)

        operations.isolate_conceptentity(instance)
        self.assertEqual(instance.relations_to.count(), 0)
        for resource in resources:
            self.assertEqual(resource.relations_from.count(), 1,
                             "Each Resource should have a single relation...")
            target = resource.relations_from.first().target
            self.assertIsInstance(target, ConceptEntity, "..to a ConceptEntity")
            self.assertEqual(target.relations_from.count(), 1,
                             "Relations from the original instance should also"
                             " be cloned...")
            alt_target = target.relations_from.first()
            self.assertEqual(alt_target.target.name, value.name,
                             "...along with the targets of those relations.")

        instance = ConceptEntity.objects.create(name='TestEntity', created_by=u)
        operations.isolate_conceptentity(instance)
