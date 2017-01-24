"""
"""

from django.contrib.contenttypes.models import ContentType

import unittest, mock, json, os
import networkx as nx

os.environ.setdefault('LOGLEVEL', 'ERROR')

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


class TestExportCoauthorData(unittest.TestCase):
    """ Testing export_coauthor_data in operations module.
        Takes :class: `.Collection` as input Parameter.
        Returns a graph that has co-author data for all
        :class: `.Resource` instances in a collection"""

    def test_collection_with_one_resource(self):
        """ Collection has only one resource instance.
        The nodes are authors of that resource.
        Edges connect each node to the other. """

        resource = Resource.objects.create(name='first_resource')
        value_1 = ConceptEntity.objects.create(name='Bradshaw')
        predicate_author = Field.objects.create(name='Authors', uri="http://purl.org/net/biblio#authors")
        relation = Relation.objects.create(source=resource, predicate=predicate_author, target=value_1)
        value_2 = ConceptEntity.objects.create(name='Conan')
        relation = Relation.objects.create(source=resource, predicate=predicate_author, target=value_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 2, 'Since there are two authors in the Collection,'
                         'there should be two nodes in the graph')
        self.assertEqual(set(nx.get_node_attributes(graph, 'name').values()), set(['Bradshaw', 'Conan']),
                         'The nodes do not match with the authors in the Collection')
        self.assertTrue(graph.has_edge(value_1.id, value_2.id), 'Since the authors are of the same resource,'
                        'there should be an edge between them')

    def test_collection_with_one_author(self):
        """ Collection has only one resource instance
        and one author for that resource.
        The graph has only one node and no edges. """

        resource = Resource.objects.create(name='first_resource')
        value = ConceptEntity.objects.create(name='Bradshaw')
        predicate_author = Field.objects.create(name='Authors', uri="http://purl.org/net/biblio#authors")
        relation = Relation.objects.create(source=resource, predicate=predicate_author, target=value)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 1, 'Since there is one author in the resource,'
                         'there should be one node in the graph')
        self.assertEqual(nx.get_node_attributes(graph, 'name').values(), ['Bradshaw'],
                         'The node does not match with the author in the resource')
        self.assertEqual(graph.size(), 0, 'Since there is only one resource,'
                         'there should be no edges in the graph')

    def test_collection_with_resources(self):
        """ Collection has two resource instances
        The nodes are all the authors of the resources.
        The edges are between the authors of the same resource. """

        resource_1 = Resource.objects.create(name='first_resource')
        predicate_author = Field.objects.create(name='Authors', uri="http://purl.org/net/biblio#authors")
        value_1 = ConceptEntity.objects.create(name='Bradshaw')
        relation = Relation.objects.create(source=resource_1, predicate=predicate_author, target=value_1)
        value_2 = ConceptEntity.objects.create(name='Conan')
        relation = Relation.objects.create(source=resource_1, predicate=predicate_author, target=value_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        value_3 = ConceptEntity.objects.create(name='Xiaomi')
        relation = Relation.objects.create(source=resource_2, predicate=predicate_author, target=value_3)
        value_4 = ConceptEntity.objects.create(name='Ned')
        relation = Relation.objects.create(source=resource_2, predicate=predicate_author, target=value_4)
        collection.native_resources.add(resource_2)
        collection.save()


        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 4, 'Since there are four authors in the Collection, there should be four'
                         'unique nodes in the resulting graph.')
        self.assertEqual(set(nx.get_node_attributes(graph, 'name').values()),
                         set(['Bradshaw', 'Conan', 'Xiaomi', 'Ned']),
                         'The nodes do not match with the authors in the Collection')
        self.assertTrue(graph.has_edge(value_1.id, value_2.id),
                        'There is no edge between the authors in the first resource')
        self.assertTrue(graph.has_edge(value_3.id, value_4.id),
                        'There is no edge between the authors in the second resource')

    def test_collection_with_no_resource(self):
        """ Collection has no resource instance
        The graph has no node and no edges. """

        collection = Collection.objects.create(name='first_collection')

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 0, 'Since there are no resources,'
                         'graph should be empty but has %d nodes' %graph.order())

    def test_collection_with_no_author_relations(self):
        """ Collection has no author relations.
        The graph has no node and no edges. """

        resource = Resource.objects.create(name='first_resource')
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 0, 'Since there are no author relations, graph should be empty but has %d nodes' %graph.order())


    def tearDown(self):
        Resource.objects.all().delete()
        Collection.objects.all().delete()
