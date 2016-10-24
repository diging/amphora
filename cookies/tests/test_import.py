import unittest, mock

from cookies.accession import IngesterFactory, IngestManager
from cookies.tests.mocks import MockFile, MockIngester
from cookies.models import *


class TestImport(unittest.TestCase):
    def setUp(self):
        self.factory = IngesterFactory()

    def test_import_factory(self):
        """

        """
        ingest_class = self.factory.get('cookies.tests.mocks.MockIngester')
        mock_file = MockFile()
        mock_file.read = mock.MagicMock(name='read')
        mock_file.read.return_value = [
            ({'name': 'Test',}, []),
            ({'name': 'Test2',}, [])
        ]
        ingester = ingest_class(mock_file)
        self.assertIsInstance(ingester, IngestManager)
        self.assertIsInstance(ingester.next(), Resource)
        self.assertEqual(mock_file.read.call_count, 1)
