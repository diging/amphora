import unittest, mock, json, os


import goat
os.environ.setdefault('GOAT_WAIT_INTERVAL', '0.001')


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


class TestGoatConcept(unittest.TestCase):
    @mock.patch('requests.get')
    def test_list(self, mock_get):
        with open('test_data/goat/concept_list_response.json', 'r') as f:
            mock_get.return_value = MockResponse(f.read(), 200)

        concepts = goat.GoatConcept.list()
        args, kwargs = mock_get.call_args

        self.assertEqual(mock_get.call_count, 1,
                         "Should make a single GET request.")
        self.assertEqual(goat.GOAT + '/concept/', args[0],
                         "Should call the ``/concept/`` endpoint.")
        self.assertEqual(len(concepts), 19,
                         "There should be 19 items in the result set.")
        for concept in concepts:
            self.assertIsInstance(concept, goat.GoatConcept,
                                  "Each of which should be a GoatConcept.")

    @mock.patch('requests.get')
    def test_search(self, mock_get):
        with open('test_data/goat/concept_search_results.json', 'r') as f:
            with open('test_data/goat/concept_search_created.json', 'r') as f2:
                mock_get.return_value = MockSearchResponse(mock_get, f2.read(), f.read(), 200)

        max_calls = 3

        concepts = goat.GoatConcept.search(q='Bradshaw')
        self.assertEqual(mock_get.call_count, max_calls,
                         "Should keep calling if status code 202 is received.")
        args, kwargs =  mock_get.call_args
        self.assertEqual(args[0], MockSearchResponse.url,
                         "Should follow the redirect URL.")
        self.assertEqual(len(concepts), 10,
                         "There should be 10 items in the result set.")
        for concept in concepts:
            self.assertIsInstance(concept, goat.GoatConcept,
                                  "Each of which should be a GoatConcept.")

    def test_create(self):
        concept = goat.GoatConcept(name='GoatTest', identifier='http://test.com/test/')
        concept.create()




if __name__ == '__main__':
    unittest.main()
