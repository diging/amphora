"""
"""

from django.contrib.contenttypes.models import ContentType

import unittest, mock, json, os
import networkx as nx

os.environ.setdefault('LOGLEVEL', 'ERROR')

from cookies import operations
from concepts import remote
from cookies.models import *
from concepts.models import Concept


class MockResponse(object):
    def __init__(self, content, status_code):
        self._status_code = status_code
        self.content = content

    def json(self):
        return json.loads(self.content)

    @property
    def status_code(self):
        return self._status_code


class MockSearchResponse(MockResponse):
    url = 'http://mock/url/'

    def __init__(self, parent, pending_content, success_content, max_calls=3,):
        self.max_calls = 3
        self.parent = parent
        self.pending_content = pending_content
        self.success_content = success_content

    def json(self):
        if self.parent.call_count < self.max_calls:
            return json.loads(self.pending_content)
        return json.loads(self.success_content)

    @property
    def status_code(self):
        if self.parent.call_count < self.max_calls:
            return 202
        return 200


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
                c.concept.add(Concept.objects.create(uri=uri))
                c.save()

        entities = ConceptEntity.objects.all()
        master = operations.merge_conceptentities(entities, user=User.objects.create(username='TestUser'))
        self.assertIn(uri, master.concept.values_list('uri', flat=True))

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


class TestExportCoauthorData(unittest.TestCase):
    """
    Class contains unit test cases for :func:`generate_collection_coauthor_graph`
    in operations module.

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
        container = ResourceContainer.objects.create(primary=resource)
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource, container=container,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource, container=container,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container)
        collection.save()

        graph = operations.generate_collection_coauthor_graph(collection)
        self.assertIsInstance(graph, nx.classes.graph.Graph)
        self.assertEqual(graph.order(), 2,
                         "Since there are two authors in the Collection,"
                         " there should be two nodes in the graph")
        self.assertEqual(set(nx.get_node_attributes(graph, 'label').values()),
                         set(['Bradshaw', 'Conan']),
                         "Each node should have a 'label' attribute, the value"
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
        container = ResourceContainer.objects.create(primary=resource)
        author = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate, target=author)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container)
        collection.save()

        graph = operations.generate_collection_coauthor_graph(collection)
        self.assertEqual(graph.order(), 0,
                         "Since there is one author in the only resource in the"
                         " collection, there should be no nodes in the graph"
                         " indicating no co-authorship")
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
        container_1 = ResourceContainer.objects.create(primary=resource_1)
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        container_2 = ResourceContainer.objects.create(primary=resource_2)
        author_3 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_3)
        author_4 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_4)
        collection.resourcecontainer_set.add(container_2)
        collection.save()


        graph = operations.generate_collection_coauthor_graph(collection)
        self.assertEqual(graph.order(), 4,
                         "Since there are four authors in the collection, there"
                         " should be four unique nodes in the resulting graph.")
        self.assertEqual(set(nx.get_node_attributes(graph, 'label').values()),
                         set(['Bradshaw', 'Conan', 'Xiaomi', 'Ned']),
                         "The nodes in the graph have a 'label' attribute that"
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

        graph = operations.generate_collection_coauthor_graph(collection)
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
        container = ResourceContainer.objects.create(primary=resource)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container)
        collection.save()

        graph = operations.generate_collection_coauthor_graph(collection)
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
        container_1 = ResourceContainer.objects.create(primary=resource_1)
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate, target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        container_2 = ResourceContainer.objects.create(primary=resource_2)
        author_3 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_3)
        author_4 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate, target=author_4)
        collection.resourcecontainer_set.add(container_2)
        collection.save()


        graph = operations.generate_collection_coauthor_graph(collection)
        names = nx.get_node_attributes(graph, 'label')
        self.assertEqual(author_1.name, names[author_1.id],
                         "The node and node attribute 'label' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_2.name, names[author_2.id],
                         "The node and node attribute 'label' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_3.name, names[author_3.id],
                         "The node and node attribute 'label' should correspond"
                         " to the ``id`` and ``name`` property of the"
                         " ``ConceptEntity`` that it represents")
        self.assertEqual(author_4.name, names[author_4.id],
                         "The node and node attribute 'label' should correspond"
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
        container = ResourceContainer.objects.create(primary=resource)
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate,
                                target=author_1)
        Relation.objects.create(source=resource,
                                predicate=self.author_predicate,
                                target=author_1)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container)
        collection.save()

        graph = operations.generate_collection_coauthor_graph(collection)
        self.assertEqual(graph.order(), 0,
                         "Since there are two authors in the Collection with"
                         " the same ConceptEntity instance, no node is created"
                         " as there is no co-authorship in the graph")
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
        container_1 = ResourceContainer.objects.create(primary=resource_1)
        author_1 = ConceptEntity.objects.create(name='Bradshaw')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate,
                                target=author_1)
        author_2 = ConceptEntity.objects.create(name='Conan')
        Relation.objects.create(source=resource_1,
                                predicate=self.author_predicate,
                                target=author_2)
        collection = Collection.objects.create(name='first_collection')
        collection.resourcecontainer_set.add(container_1)
        collection.save()
        resource_2 = Resource.objects.create(name='second_resource')
        container_2 = ResourceContainer.objects.create(primary=resource_2)
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate,
                                target=author_1)
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate,
                                target=author_2)
        author_5 = ConceptEntity.objects.create(name='Xiaomi')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate,
                                target=author_5)
        author_6 = ConceptEntity.objects.create(name='Ned')
        Relation.objects.create(source=resource_2,
                                predicate=self.author_predicate,
                                target=author_6)
        collection.resourcecontainer_set.add(container_2)
        collection.save()

        graph = operations.generate_collection_coauthor_graph(collection)
        self.assertEqual(graph[author_1.id][author_2.id]['weight'], 2,
                         "Since the ConceptEntity instances are authors in two"
                         " resources of the collection, the 'weight'"
                         " edge attribute should be 2")
        self.assertEqual(graph[author_5.id][author_6.id]['weight'], 1,
                         "Since the ConceptEntity instances are authors in only"
                         " one resource of the collection, the"
                         " 'weight' edge attribute should be 1")

    def test_invalid_collection(self):
        """
        This is a test case to check if :func:`generate_graph_coauthor_data`
        raises an exception for an invalid :class:`.Collection` instance.

        A RuntimeError is thrown from the function.
        """

        collection = Resource.objects.create(name='first_resource')
        self.assertRaises(RuntimeError, operations.generate_collection_coauthor_graph, collection)

    def tearDown(self):
        Resource.objects.all().delete()
        Collection.objects.all().delete()
        Relation.objects.all().delete()


class TestConceptSearch(unittest.TestCase):
    """
    Class contains unit test cases for :func:`concept_search` in operations
    module.

    The function takes str as input parameter. It returns a list of
    :class:`.GoatConcept` objects obtained from the search result of the
    BlackGoat API.
    """


    def test_concept_with_no_query(self):
        """
        When no query text is given and the search button is clicked,
        :func:`concept_search` returns an empty list.
        """

        concepts = remote.concept_search('')

        self.assertEqual(concepts, [])


    @mock.patch('concepts.remote.goat.requests.get')
    def test_concept_with_query(self, mock_get):
        """
        When query text is given and the search button is clicked,
        a dictionary of lists is obtained where each element in the list is a
        BlackGoat concept and the dictionary contains name, source and uri of
        the concept.
        """

        with open('cookies/tests/data/concept_search_results.json', 'r') as f:
            with open('cookies/tests/data/concept_search_created.json', 'r') as f2:
                mock_get.return_value = MockSearchResponse(mock_get, f2.read(), f.read(), 200)

        concepts = remote.concept_search('Bradshaw')
        for concept in concepts:
            self.assertTrue('name' in concept)
            self.assertTrue('source' in concept)
            self.assertTrue('uri' in concept)


    @mock.patch('concepts.remote.goat.Concept.search')
    def test_concept_with_exception(self, mock_search):
        """
        When BlackGoat client API throws an exception,
        it is raised as an exception to the function that calls it.
        """

        mock_search.side_effect = Exception

        self.assertRaises(Exception, remote.concept_search, 'Bradshaw')

    @mock.patch('concepts.remote.goat.Concept.search')
    def test_concept_with_no_output_from_goat(self, mock_search):
        """
        When BlackGoat client API does not return any value,
        :func:`.concept_search` returns an empty list.
        """

        mock_search.return_value = None

        self.assertEqual(remote.concept_search('Bradshaw'), [])
