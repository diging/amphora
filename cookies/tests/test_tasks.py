import unittest, mock, tempfile, shutil, os

os.environ.setdefault('LOGLEVEL', 'ERROR')
from cookies import tasks
from cookies.models import *
from cookies.signals import send_pdfs_and_images_to_giles

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import signals


# class TestSendToGiles(unittest.TestCase):
#     def setUp(self):
#         User.objects.all().delete()
#         GilesUpload.objects.all().delete()
#         Resource.objects.all().delete()
#         ContentRelation.objects.all().delete()
#         signals.post_save.disconnect(receiver=send_pdfs_and_images_to_giles,
#                                      sender=ContentRelation)
#
#     @mock.patch('cookies.giles.send_to_giles')
#     def test_send_to_giles(self, mock_send_to_giles):
#         """
#         :func:`cookies.tasks.send_to_giles` dispatches a Giles upload, and
#         tracks the upload via a :class:`.GilesUpload` instance.
#         """
#         test_user = User.objects.create(username='test_user')
#         mock_send_to_giles.return_value = 200, {'id': 'id', 'checkUrl': 'http'}
#         upload = GilesUpload.objects.create()
#
#         tasks.send_to_giles('What', test_user, resource=None, public=True,
#                             gilesupload_id=upload.id)
#
#         self.assertEqual(mock_send_to_giles.call_count, 1,
#             "giles.send_to_giles() should be called.")
#
#         upload.refresh_from_db()
#         self.assertTrue(upload.sent is not None,
#             "The GilesUpload should be updated to reflect the fact that an"
#             " upload was performed.")
#         self.assertEqual(upload.upload_id, 'id',
#             "The GilesUpload should receive the upload ID returned by Giles.")
#         self.assertFalse(upload.resolved,
#             "The GilesUpload should not be resolved until Giles is done"
#             " processing the upload and returns a complete result.")
#
#     def tearDown(self):
#         User.objects.all().delete()
#         GilesUpload.objects.all().delete()
#         Resource.objects.all().delete()
#         ContentRelation.objects.all().delete()


# class TestSendGilesUploads(unittest.TestCase):
#     """
#     :func:`cookies.tasks.send_giles_uploads` is a periodic task that checks for
#     outstanding (not sent) :class:`.GilesUpload` instances, and (if possible)
#     sends the associated content to Giles.
#     """
#     def setUp(self):
#         User.objects.all().delete()
#         GilesUpload.objects.all().delete()
#         Resource.objects.all().delete()
#         ContentRelation.objects.all().delete()
#         signals.post_save.disconnect(receiver=send_pdfs_and_images_to_giles,
#                                      sender=ContentRelation)
#
#     @mock.patch('cookies.tasks.send_to_giles')
#     def test_send_giles_uploads_no_pending(self, mock_send_to_giles):
#         """
#         If there are no pending uploads, do nothing.
#         """
#         tasks.send_giles_uploads()
#         self.assertEqual(mock_send_to_giles.call_count, 0)
#
#     @mock.patch('cookies.tasks.send_to_giles')
#     def test_send_giles_uploads_one_pending_overmax(self, mock_send_to_giles):
#         """
#         If there are too many outstanding requests, do nothing.
#         """
#         # Create 20 outstanding requests, so that we are at max.
#         for i in xrange(settings.MAX_GILES_UPLOADS):
#             upload = GilesUpload.objects.create()
#             upload.sent = upload.created
#             upload.save()
#
#         upload = GilesUpload.objects.create()
#
#         tasks.send_giles_uploads()
#         self.assertEqual(mock_send_to_giles.call_count, 0,
#             "The resource should be not be sent to giles.")
#
#     @mock.patch('cookies.tasks.send_to_giles')
#     def test_send_giles_uploads_one_pending(self, mock_send_to_giles):
#         """
#         If there is an outstanding upload and there are fewer outstanding
#         requests than the max, should send to giles.
#         """
#         test_filename = 'TestFileName.pdf'
#         user = User.objects.create(username='TestUser')
#         test_resource = Resource.objects.create(name='TestResource',
#                                                 created_by=user)
#         content_resource = Resource.objects.create(name='ContentResource',
#                                                    content_resource=True,
#                                                    created_by=user)
#         content_resource.file.save(test_filename,
#                                    ContentFile("The test content"),
#                                    True)
#         ContentRelation.objects.create(for_resource=test_resource,
#                                        content_resource=content_resource)
#
#         upload = GilesUpload.objects.create(content_resource=content_resource)
#
#         tasks.send_giles_uploads()
#         self.assertEqual(mock_send_to_giles.call_count, 1,
#             "The resource should be sent to giles.")
#
#         args, kwargs = mock_send_to_giles.call_args
#
#         self.assertTrue(test_filename.split('.')[0] in args[0],
#             "The filename should be preserved.")
#         self.assertEqual(args[1], user,
#             "The ``creator`` should be the creator of the content resource.")
#         self.assertEqual(kwargs['resource'], test_resource,
#             "The ``resource`` should the 'master' resource instance.")
#         self.assertFalse(kwargs['public'],
#             "``public`` should be false, since Anonymous was not given rights.")
#         self.assertEqual(kwargs['gilesupload_id'], upload.id,
#             "The ``gilesupload_id`` should be the id of the GilesUpload.")
#
#         try:
#             shutil.rmtree(os.path.join(settings.MEDIA_ROOT, args[0].split('/')[0]))
#         except OSError:
#             pass
#
#     def tearDown(self):
#         User.objects.all().delete()
#         GilesUpload.objects.all().delete()
#         Resource.objects.all().delete()
#         ContentRelation.objects.all().delete()
