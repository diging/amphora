import unittest, mock, json, os

os.environ.setdefault('LOGLEVEL', 'ERROR')

from cookies import metadata
from cookies.models import *


class MockQuerySet(object):
    def __init__(self, data):
        self.data = data


# class TestDecorators(unittest.TestCase):
#     def test_prepend_to_results(self):
#         """
#         :func:`metadata.prepend_to_results` should prepend a value to each
#         tuple in the iterable of tuples returned by the function that it
#         decorates.
#         """
#         test_value = 'A Value'
#         @metadata.prepend_to_results(test_value)
#         def returns_an_iterable_of_tuples():
#             return [(1, 2, 3) for i in xrange(5)]
#
#         values = returns_an_iterable_of_tuples()
#         self.assertEqual(len(values[0]), 4)
#         for vtuple in values:
#             self.assertEqual(vtuple[0], test_value)
#
#
# def _get_mock_qs():
#     qs = MockQuerySet([(1, 'Bob', 'Class'), (2, 'Aardvark', 'Type')])
#     qs.filter = mock.MagicMock(name='filter')
#     qs.filter.return_value = qs
#
#     qs.values_list = mock.MagicMock(name='values_list')
#     qs.values_list.return_value = qs.data
#
#     qs.none = mock.MagicMock(name='none')
#     qs.none.return_value = qs
#
#     qs.distinct = mock.MagicMock(name='distinct')
#     qs.distinct.return_value = qs
#     return qs
#
#
# class TestFilterRelations(unittest.TestCase):
#     def test_filter_by_predicate_id(self):
#         """
#         When called with ``predicate=<int>``, :func:`metadata.filter_relations`
#         should attempt to filter by pk.
#         """
#
#         qs = _get_mock_qs()
#         predicate_id = 1
#
#         relations = metadata.filter_relations(predicate=predicate_id, qs=qs)
#
#         qs.filter.assert_called_once_with(predicate=predicate_id)
#         self.assertEqual(qs.filter.call_count, 1)
#         self.assertIsInstance(relations, MockQuerySet)
#
#     def test_filter_by_predicate_instance(self):
#         """
#         When called with an object that has an ``id`` attribute,
#         :func:`metadata.filter_relations` should attempt to filter by pk
#         with the value of that attribute.
#         """
#
#         mock_id = 'what'
#         class MockObject(object):
#             def __init__(self):
#                 self.id = mock_id
#
#         qs = _get_mock_qs()
#         mockPredicate = MockObject()
#
#         relations = metadata.filter_relations(predicate=mockPredicate, qs=qs)
#
#         qs.filter.assert_called_once_with(predicate=mock_id)
#         self.assertEqual(qs.filter.call_count, 1)
#         self.assertIsInstance(relations, MockQuerySet)
#
#
#     def test_filter_get_resource_with_name(self):
#         """
#         """
#         qs = _get_mock_qs()
#         result = metadata.get_resource_with_name('bob', qs=qs)
#
#         self.assertIsInstance(result, list)
#         self.assertIsInstance(result[0], tuple)
#         self.assertEqual(result[0][0], 'Resource')
#         self.assertEqual(len(result[0]), len(qs.data[0]) + 1,
#                          "Value tuples should be larger than the original mock"
#                          " data, because the model name should be prepended.")
#         self.assertGreaterEqual(qs.filter.call_count, 1,
#                                 "The QuerySet's filter() method should be"
#                                 " called at least once.")
#         self.assertEqual(qs.values_list.call_count, 1)
#
#     def test_filter_get_conceptentity_with_name(self):
#         """
#         """
#         qs = _get_mock_qs()
#         result = metadata.get_conceptentity_with_name('bob', qs=qs)
#
#         self.assertIsInstance(result, list)
#         self.assertIsInstance(result[0], tuple)
#         self.assertEqual(result[0][0], 'ConceptEntity')
#         self.assertEqual(len(result[0]), len(qs.data[0]) + 1,
#                          "Value tuples should be larger than the original mock"
#                          " data, because the model name should be prepended.")
#         self.assertGreaterEqual(qs.filter.call_count, 1,
#                                 "The QuerySet's filter() method should be"
#                                 " called at least once.")
#         self.assertEqual(qs.values_list.call_count, 1)
#
#     def test_get_instances_with_name(self):
#         mock_getter_one = mock.MagicMock('mock_getter_one')
#         mock_getter_one.return_value = [('A', 'list'), ('of', 'tuples')]
#         mock_getter_two = mock.MagicMock('mock_getter_two')
#         mock_getter_two.return_value = [('Another', 'list'), ('of', 'tuples')]
#
#
#         result = metadata.get_instances_with_name('bob', getters=[mock_getter_one, mock_getter_two])
#
#         self.assertEqual(mock_getter_one.call_count, 1)
#         self.assertEqual(mock_getter_two.call_count, 1)
#         self.assertIsInstance(result, list)
#         self.assertEqual(len(result), 4)
#
#     def test_filter_relations_with_source_name(self):
#         Resource.objects.get_or_create(name='A Book')
#         qs = _get_mock_qs()
#         result = metadata.filter_relations(source='A Book', qs=qs)
#         self.assertEqual(qs.filter.call_count, 1)
#
#     def test_filter_relations_with_source_name_and_target_name(self):
#         Resource.objects.get_or_create(name='A Book')
#         Resource.objects.get_or_create(name='A Value')
#         qs = _get_mock_qs()
#         result = metadata.filter_relations(source='A Book', target='A Value', qs=qs)
#         self.assertEqual(qs.filter.call_count, 2)
#
#     def test_filter_relations_with_source_object_and_target_name(self):
#         qs = _get_mock_qs()
#         mock_resource,_ = Resource.objects.get_or_create(name='A Book')
#         mock_id = mock_resource.id
#         Resource.objects.get_or_create(name='A Value')
#         class MockObject(object):
#             def __init__(self):
#                 self.id = mock_id
#
#         mocksource = MockObject()
#
#         result = metadata.filter_relations(source=mocksource, target='A Value', qs=qs)
#         self.assertEqual(qs.filter.call_count, 2)
