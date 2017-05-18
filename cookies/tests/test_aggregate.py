import unittest, mock, shutil, tempfile, os
from cookies import aggregate
from cookies.models import *
from django.db import transaction



class TestAggregate(unittest.TestCase):
    def setUp(self):
        with transaction.atomic():
            self.user = User.objects.create(username='bob')
            self.supercollection = Collection.objects.create(name='supercollection')
            self.collection = Collection.objects.create(name='collection', part_of=self.supercollection)
            self.container = ResourceContainer.objects.create(created_by=self.user, part_of=self.collection)
            self.resource = Resource.objects.create(name='test resource', container=self.container)
            self.container.primary = self.resource
            self.container.save()

            self.container2 = ResourceContainer.objects.create(created_by=self.user, part_of=self.supercollection)
            self.resource2 = Resource.objects.create(name='test resource 2', container=self.container2)
            self.container2.primary = self.resource2
            self.container2.save()

            self.isPartOf, _ = Field.objects.get_or_create(uri='http://purl.org/dc/terms/isPartOf')

        def create_content_resource(resource, url, content_type):
            content = Resource.objects.create(content_resource=True, is_external=True, external_source=Resource.WEB, location=url, content_type=content_type, container=resource.container)
            ContentRelation.objects.create(for_resource=resource, content_resource=content, content_type=content_type, container=resource.container)

        for resource in [self.resource, self.resource2]:
            for i in xrange(3):
                r = Resource.objects.create(name='subordinate %i' % i, container=resource.container)
                Relation.objects.create(source=r, predicate=self.isPartOf, target=resource, container=resource.container)
                if i < 2:
                    create_content_resource(r, 'http://asdf.com/%i.txt' % i, 'application/pdf')
                    continue
                for j in xrange(2):
                    r2 = Resource.objects.create(name='sub-subordinate %i:%i' % (i, j), container=resource.container)
                    Relation.objects.create(source=r2, predicate=self.isPartOf, target=r, container=resource.container)
                    create_content_resource(r2, 'http://asdf.com/%i_%i.txt' % (i, j), 'text/plain')

    def test_aggregate_content_resources(self):
        """
        :func:`cookies.aggregate.aggregate_content_resources` should return a
        generator that yields all of the content resources attached to the
        passed set of resources.
        """
        agg = aggregate.aggregate_content_resources(iter([self.resource, self.resource2]))
        self.assertEqual(len(list(agg)), Resource.objects.filter(content_resource=True).count())

        for obj in aggregate.aggregate_content_resources(Resource.objects.filter(is_primary_for__isnull=False)):
            self.assertIsInstance(obj, Resource)
            self.assertTrue(obj.content_resource)

    def test_aggregate_content_resources_ctype(self):
        """
        Specifying ``content_type`` will limit to those with the correct
        content type.
        """
        qs = Resource.objects.filter(is_primary_for__isnull=False)
        agg = aggregate.aggregate_content_resources(qs, content_type='text/plain')
        self.assertEqual(len(list(agg)), Resource.objects.filter(content_resource=True, content_type='text/plain').count())

        agg = aggregate.aggregate_content_resources(qs, content_type='application/pdf')
        self.assertEqual(len(list(agg)),  Resource.objects.filter(content_resource=True, content_type='application/pdf').count())

    @mock.patch('cookies.accession.WebRemote.get')
    def test_aggregate_content(self, mock_get):
        """
        :func:`cookies.aggregate.aggregate_content_resources` should return a
        generator that yields raw content.
        """
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        qs = Resource.objects.filter(is_primary_for__isnull=False)
        agg = aggregate.aggregate_content(qs, content_type='text/plain')
        for raw in agg:
            self.assertEqual(raw, secret_message)

    @mock.patch('cookies.accession.WebRemote.get')
    def test_aggregate_content_with_proc(self, mock_get):
        """
        If ``proc`` is passed, then the return value of that function is
        returned instead.
        """
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        proc = lambda content, resource: content[:2]
        qs = Resource.objects.filter(is_primary_for__isnull=False)
        agg = aggregate.aggregate_content(qs, proc=proc, content_type='text/plain')
        for raw in agg:
            self.assertEqual(raw, secret_message[:2])

    @mock.patch('cookies.accession.WebRemote.get')
    def test_export(self, mock_get):
        """
        """
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        proc = lambda content, resource: content[:2]
        qs = Resource.objects.filter(is_primary_for__isnull=False)
        target_path = tempfile.mkdtemp()

        aggregate.export(qs, target_path, proc=proc, content_type='text/plain')

        for fname in os.listdir(target_path):
            if fname.endswith('.txt'):
                with open(os.path.join(target_path, fname)) as f:
                    self.assertEqual(f.read(), secret_message[:2])
        shutil.rmtree(target_path)


    @mock.patch('cookies.accession.WebRemote.get')
    def test_export_gz(self, mock_get):
        """
        """
        import smart_open
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        proc = lambda content, resource: content[:2]
        fname = lambda resource: '%i.txt.gz' % resource.id

        qs = Resource.objects.filter(is_primary_for__isnull=False)
        target_path = tempfile.mkdtemp()

        aggregate.export(qs, target_path, fname=fname, proc=proc,
                         content_type='text/plain')

        for fname in os.listdir(target_path):
            if fname.endswith('.txt.gz'):
                with smart_open.smart_open(os.path.join(target_path, fname)) as f:
                    self.assertEqual(f.read(), secret_message[:2])
        shutil.rmtree(target_path)

    @mock.patch('cookies.accession.WebRemote.get')
    def test_export_zip(self, mock_get):
        """
        """
        import smart_open
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        proc = lambda content, resource: content[:2]
        fname = lambda resource: '%i.txt' % resource.id

        qs = Resource.objects.filter(is_primary_for__isnull=False)
        target_path = tempfile.mkdtemp() + 'test.zip'

        aggregate.export_zip(qs, target_path, fname=fname, proc=proc,
                             content_type='text/plain')
        # TODO: actually open and evaluate the archive contents.

    @mock.patch('cookies.accession.WebRemote.get')
    def test_export_collection(self, mock_get):
        """
        """
        import smart_open, os, urlparse
        secret_message = 'nananana, hey hey'
        mock_get.return_value = secret_message
        proc = lambda content, resource: content[:2]
        def fname(resource):
            def get_collection_name(collection):
                if collection is None:
                    return 'resources'
                return get_collection_name(collection.part_of) + '/' + collection.name
            if resource.is_external:
                filename = urlparse.urlparse(resource.location).path.split('/')[-1]
            else:
                filename = os.path.split(resource.file.path)[-1]
            return get_collection_name(resource.container.part_of) + '/' + filename


        qs = Resource.objects.filter(is_primary_for__isnull=False)
        target_path = tempfile.mkdtemp() + 'test.zip'

        aggregate.export_zip(qs, target_path, fname=fname, proc=proc,
                             content_type='text/plain')
        # TODO: actually open and evaluate the archive contents.

    def tearDown(self):
        for model in [Resource, Relation, ContentRelation, ResourceContainer, User]:
            model.objects.all().delete()
