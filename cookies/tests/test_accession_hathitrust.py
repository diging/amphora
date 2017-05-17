import unittest, mock, json

from cookies.accession import hathitrust
from cookies.accession import IngesterFactory
from cookies.models import *


class MockDataResponse(object):
    def __init__(self, status_code, data, content=None):
        self.status_code = status_code
        self.data = data
        if content:
            self.content = content
        else:
            self.content = json.dumps(data)

    def json(self):
        return self.data


class TestHathiTrust(unittest.TestCase):
    def setUp(self):
        Resource.objects.all().delete()
        ContentRelation.objects.all().delete()
        ConceptEntity.objects.all().delete()
        Relation.objects.all().delete()
        ResourceContainer.objects.all().delete()

    @mock.patch('requests.get')
    def test_get_content_metadata(self, mock_get):
        identifier = 'njp.32101044814968'
        with open('cookies/tests/data/hathitrust_volume_metadata.json') as f:
            mock_get.return_value = MockDataResponse(200, json.load(f))
        ingest = hathitrust.HathiTrustRemoteIngest([identifier], 'asdf', '1234')
        data = ingest.get_content_metadata(identifier)

        self.assertIsInstance(data, dict)
        self.assertEqual(mock_get.call_count, 1)

    @mock.patch('requests.get')
    def test_get_metadata(self, mock_get):
        identifier = 'njp.32101044814968'
        with open('cookies/tests/data/hathitrust_brief_volume_metadata.json') as f:
            mock_get.return_value = MockDataResponse(200, json.load(f))
        ingest = hathitrust.HathiTrustRemoteIngest([identifier], 'asdf', '1234')
        data = ingest.get_metadata(identifier)
        self.assertIsInstance(data, dict)
        self.assertEqual(len(data), 2)
        self.assertEqual(mock_get.call_count, 1)

    @mock.patch('requests.get')
    def test_process_metadata(self, mock_get):
        identifier = 'wu.89069276731'
        with open('cookies/tests/data/hathitrust_brief_volume_metadata.json') as f:
            mock_get.return_value = MockDataResponse(200, json.load(f))
        ingest = hathitrust.HathiTrustRemoteIngest([identifier], 'asdf', '1234')
        data = ingest.process_metadata(identifier, ingest.get_metadata(identifier))

        for key in ['http://purl.org/dc/elements/1.1/identifier',
                    'http://purl.org/dc/terms/created',
                    'uri',
                    'name',
                    'http://purl.org/dc/terms/accessRights',
                    'http://purl.org/dc/terms/rightsHolder',
                    'entity_type']:
            self.assertIn(key, data)

    @mock.patch('requests.get')
    def test_process_content_metadata(self, mock_get):
        identifier = 'hvd.32044106431737'
        side_effects = []
        with open('cookies/tests/data/hathitrust_brief_volume_metadata.json') as f:
            side_effects.append(MockDataResponse(200, json.load(f)))
        with open('cookies/tests/data/hathitrust_volume_metadata.json') as f:
            side_effects.append(MockDataResponse(200, json.load(f)))
        mock_get.side_effect = side_effects

        ingest = hathitrust.HathiTrustRemoteIngest([identifier], 'asdf', '1234')
        data = ingest.next()
        self.assertIsInstance(data, dict)

    @mock.patch('requests.get')
    def test_ingest(self, mock_get):
        identifier = 'hvd.32044106431737'
        side_effects = []
        with open('cookies/tests/data/hathitrust_brief_volume_metadata.json') as f:
            side_effects.append(MockDataResponse(200, json.load(f)))
        with open('cookies/tests/data/hathitrust_volume_metadata.json') as f:
            side_effects.append(MockDataResponse(200, json.load(f)))
        mock_get.side_effect = side_effects

        ingest = IngesterFactory().get('cookies.accession.hathitrust.HathiTrustRemoteIngest')([identifier], 'asdf', '1234')
        data = ingest.next()

        self.assertIsInstance(data, Resource)
        self.assertEqual(ResourceContainer.objects.count(), 1)
        self.assertEqual(Resource.objects.filter(content_resource=False).count(), 121)
        self.assertEqual(Resource.objects.filter(content_resource=True).count(), 66)

    def tearDown(self):
        Resource.objects.all().delete()
        ContentRelation.objects.all().delete()
        ConceptEntity.objects.all().delete()
        Relation.objects.all().delete()
        ResourceContainer.objects.all().delete()
