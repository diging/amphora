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
    """
    Class contains unit test cases for :func:`export_coauthor_data` in
    operations module.

    The function takes :class:`.Collection` as input parameter. It returns a
    :class:`networkx.Graph` instance that has co-author data for all
    :class:`.Resource` instances in a collection.
    """

    def setUp(self):
        self.author_predicate = Field.objects.create(name='Authors', uri="http://purl.org/net/biblio#authors")

    def test_collection_with_one_resource(self):
        """
        This is a test case for a :class:`.Collection` that has only one
        :class:`.Resource` instance.

        The nodes are authors of that resource. Edges connect each node to the
        other as all are co-authors of the same resource.
        """

        resource = Resource.objects.create(name='first_resource')
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertIsInstance(graph, nx.classes.graph.Graph)
        self.assertEqual(graph.order(), 2,
                         "Since there are two authors in the Collection,"
                         " there should be two nodes in the graph")
        self.assertEqual(set(nx.get_node_attributes(graph, 'name').values()),
                         set(['Bradshaw', 'Conan']),
                         "Each node should have a 'name' attribute, the value"
                         " of which should correspond to the ``name`` property"
                         " of the ``ConceptEntity`` that it represents.")
        self.assertTrue(graph.has_edge(author_1.id, author_2.id),
                        "Since the authors are of the same resource in the Collection,"
                        " there should be an edge between them")

    def test_collection_with_one_author(self):
        """
        This is a test case for a :class:`.Collection` that has only one
        :class:`.Resource` instance and one author relation for that resource.

        The resultant graph has only one node of that author and no edges as
        there are no co-authors.
        """

        resource = Resource.objects.create(name='first_resource')
        author = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 1,
                         "Since there is one author in the only resource in the"
                         " collection, there should be one node in the graph")
        self.assertEqual(nx.get_node_attributes(graph, 'name').values(), ['Bradshaw'],
                         "The node in the graph has a 'name' attribute that"
                         " should correspond to the ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(graph.size(), 0,
                         "Since there is only one author relation in the"
                         " resource instance for that collection, there should"
                         " be no edges in the graph")

    def test_collection_with_resources(self):
        """
        This is a test case for a :class:`.Collection` that has two
        :class:`.Resource` instances.

        The nodes are all the authors of the resources.
        The edges are between the authors of the same resource.
        """

        resource_1 = Resource.objects.create(name='first_resource')
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        author_3 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_3)
        author_4 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_4)
        collection.native_resources.add(resource_2)
        collection.save()


        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 4,
                         "Since there are four authors in the collection, there"
                         " should be four unique nodes in the resulting graph.")
        self.assertEqual(set(nx.get_node_attributes(graph, 'name').values()),
                         set(['Bradshaw', 'Conan', 'Xiaomi', 'Ned']),
                         "The nodes in the graph have a 'name' attribute that"
                         " should match with the ``name`` property of the"
                         " ``ConceptEntity`` that it reperesents")
        self.assertTrue(graph.has_edge(author_1.id, author_2.id),
                        "The authors in the first resource should have an"
                        " edge between them as they are co-authors for that resource")
        self.assertTrue(graph.has_edge(author_3.id, author_4.id),
                        "The authors in the second resource should have an"
                        " edge between them as they are co-authors for that resource")

    def test_collection_with_no_resource(self):
        """
        This is a test case for a :class:`.Collection` that has no
        :class:`.Resource` instance.

        The resultant graph is an empty graph that has no nodes and no edges.
        """

        collection = Collection.objects.create(name='first_collection')

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 0,
                         "Since there are no resources in the collection,"
                         " graph should be empty but has %d nodes" %graph.order())

    def test_collection_with_no_author_relations(self):
        """
        This is a test case for a :class:`.Collection` that contains
        :class:`.Resource` instances that have no author relations.

        The resultant graph is an empty graph that has no nodes and no edges.
        """

        resource = Resource.objects.create(name='first_resource')
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 0,
                         "Since there are no author relations in any of the"
                         " resources in the collection, graph should be empty"
                         " but has %d nodes" %graph.order())

    def test_node_matches_node_attribute(self):
        """
        This is a test case to check if each node of the graph has the 'name'
        attribute that corresponds to the name property of the
        :class:`.ConceptEntity` instance.

        The nodes are all the authors of the resources.
        The edges are between the authors of the same resource.
        """

        resource_1 = Resource.objects.create(name='first_resource')
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        author_3 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_3)
        author_4 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_4)
        collection.native_resources.add(resource_2)
        collection.save()


        graph = operations.generate_graph_coauthor_data(collection)
        names = nx.get_node_attributes(graph, 'name')
        self.assertEqual(author_1.name, names[author_1.id],
                         "The node and node attribute 'name' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_2.name, names[author_2.id],
                         "The node and node attribute 'name' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_3.name, names[author_3.id],
                         "The node and node attribute 'name' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_4.name, names[author_4.id],
                         "The node and node attribute 'name' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")

    def test_author_relations_with_same_conceptentity(self):
        """
        This is a test case for a :class:`.Collection` that has only one
        :class:`.Resource` instance with mulitple author relations pointing to
        the same :class:`.ConceptEntity` instance.

        There is only node corresponding to the ConceptEntity of that resource.
        There are no edges as there is only one ConceptEntity instance.
        """

        resource = Resource.objects.create(name='first_resource')
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author_1)
        author_2 = author_1
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph.order(), 1,
                         "Since there are two authors in the Collection with"
                         " the same ConceptEntity instance, only one node is"
                         " created in the graph")
        self.assertEqual(set(nx.get_node_attributes(graph, 'name').values()),
                         set(['Bradshaw']),
                         "Each node should have a 'name' attribute, the value"
                         " of which should correspond to the ``name`` property"
                         " of the ``ConceptEntity`` that it represents.")
        self.assertEqual(graph.size(), 0,
                        "Since there is only one ConceptEntity instance, there"
                        " there should be no edges between them")

    def test_edge_attribute(self):
        """
        This is a test case to check if each edge of the graph has the
        'number_of_resources' attribute that corresponds to the number of
        resources the :class:`.ConceptEntity` instances have co-authored.

        The nodes are all the authors of the resources.
        The edges are between the authors of the same resource.
        """

        resource_1 = Resource.objects.create(name='first_resource')
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.native_resources.add(resource_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        author_3 = author_1
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_3)
        author_4 = author_2
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_4)
        author_5 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_5)
        author_6 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_6)
        collection.native_resources.add(resource_2)
        collection.save()

        graph = operations.generate_graph_coauthor_data(collection)
        self.assertEqual(graph[author_1.id][author_2.id]['number_of_resources'], 2,
                         "Since the ConceptEntity instances are authors in two"
                         " resources of the collection, the 'number_of_resources'"
                         " edge attribute should be 2")
        self.assertEqual(graph[author_5.id][author_6.id]['number_of_resources'], 1,
                         "Since the ConceptEntity instances are authors in only"
                         " one resource of the collection, the"
                         " 'number_of_resources' edge attribute should be 1")

    def test_invalid_collection(self):
        """
        This is a test case to check if :func:`generate_graph_coauthor_data`
        raises an exception for an invalid :class:`.Collection` instance.

        A RuntimeError is thrown from the function.
        """

        collection = Resource.objects.create(name='first_resource')
        self.assertRaises(RuntimeError, operations.generate_graph_coauthor_data, collection)

    def tearDown(self):
        Resource.objects.all().delete()
        Collection.objects.all().delete()
