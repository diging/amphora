"""
TODO: these tests need some serious updating, including new sample responses.
"""

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser, User
from django.core.urlresolvers import reverse
from django.conf import settings

from cookies import giles
from cookies.models import *

from social_django.models import UserSocialAuth

import unittest, mock, json, os
from collections import Counter

from cookies.admin import import_schema
os.environ.setdefault('LOGLEVEL', 'ERROR')

DATAPATH = 'cookies/tests/data/giles'


class MockResponse(object):
    def __init__(self, status_code, response_file):
        self.status_code = status_code
        with open(os.path.join(DATAPATH, response_file), 'r') as f:
            self.content = f.read()

    def json(self):
        return json.loads(self.content)


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


def mock_get_fileids(url, params={}, headers={}):
    with open('cookies/tests/data/giles_file_response_3.json', 'r') as f:
        return MockFileResponse(200, f.read())


class MockResponse401(object):
    def __init__(self):
        self.return_value = None
        self.call_count = 0

    def __call__(self, *args, **kwargs):
        if self.call_count == 0 and args[0] == '/'.join([settings.GILES, 'rest', 'files', 'upload']):
            response = MockDataResponse(401, 'Nope', content='Nope')
        elif self.call_count == 1 and args[0] == '/'.join([settings.GILES, 'rest', 'token']):
            response = MockResponse(200, 'token_ok.json')
        elif self.call_count == 2 and args[0] == '/'.join([settings.GILES, 'rest', 'files', 'upload']):
            response = self.return_value
        else:
            response = MockDataResponse(401, 'Nope', content='Nope')
        self.call_count += 1
        return response




class TestGetUserAuthorization(unittest.TestCase):
    """
    A user has logged in to Giles using a Github identity, and is using the same
    identity in JARS. Before we can upload to Giles on their behalf, we need
    to exchange the user's provider token for a short-lived Giles token.

    :func:`.giles.get_auth_token` should send a ``POST`` request to
    ``{giles}/rest/token`` with an Authorization header containing the
    JARS application ID.
    """

    def setUp(self):
        self.factory = RequestFactory()
        User.objects.all().delete()
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='nope',
        )
        self.auth = UserSocialAuth.objects.create(**{
            'user': self.user,
            'provider': 'github',
            'uid': 'asdf1234',
        })
        self.provider_token = 'fdsa5432'
        self.auth.extra_data['access_token'] = self.provider_token
        self.auth.save()


    def test_get_auth_token(self):
        """
        Test the API request method itself.
        """
        mock_get_auth_token = lambda *a, **k: MockResponse(200, 'token_ok.json')
        post = mock.Mock(side_effect=mock_get_auth_token)

        result = giles.get_auth_token(self.user, post=post)

        self.assertEqual(post.call_count, 1)
        # self.assertTrue()
        called_with = post.call_args
        args, kwargs = called_with
        self.assertEqual(args[0], '%s/rest/token' % settings.GILES,
                         "Should call the {giles}/rest/token endpoint")
        self.assertEqual(kwargs['headers']['Authorization'],
                         'token %s' % settings.GILES_APP_TOKEN,
                         "Should pass the Giles app token for JARS in the"
                         " Authorization header.")
        self.assertEqual(kwargs['data']['providerToken'],
                         self.provider_token,
                         "Should pass the user's provider token in the request")
        self.assertIsInstance(result, tuple)
        self.assertIsInstance(result[1], dict)
        self.assertIn('token', result[1])

    def test_get_user_auth_token(self):
        """
        :func:`.giles.get_user_auth_token` is a convenience method for
        retrieving a Giles auth token for a :class:`.User`\.

        If there is no token, should call :func:`get_auth_token` for a new one.
        Otherwise, just return the existing token.
        """
        mock_get_auth_token = lambda *a, **k: MockResponse(200, 'token_ok.json')
        post = mock.Mock(side_effect=mock_get_auth_token)

        token = giles.get_user_auth_token(self.user, post=post)
        called_with = post.call_args
        args, kwargs = called_with

        self.assertEqual(post.call_count, 1)
        self.assertEqual(args[0], '%s/rest/token' % settings.GILES,
                         "Should call the {giles}/rest/token endpoint")

        token_again = giles.get_user_auth_token(self.user, post=post)

        self.assertEqual(post.call_count, 1,
                         "Should not call the endpoint a second time")
        self.assertEqual(token, token_again)


class CreateGilesUpload(unittest.TestCase):
    def setUp(self):
        from django.core.files import File

        Resource.objects.all().delete()
        ContentRelation.objects.all().delete()
        User.objects.all().delete()
        GilesUpload.objects.all().delete()
        Type.objects.all().delete()
        Field.objects.all().delete()

        self.user = User.objects.create(username='Bob')
        GilesToken.objects.create(for_user=self.user, token='asdf1234')
        self.auth = UserSocialAuth.objects.create(**{
            'user': self.user,
            'provider': 'github',
            'uid': 'asdf1234',
        })
        self.user.refresh_from_db()
        self.resource = Resource.objects.create(name='bob resource', created_by=self.user)
        self.container = ResourceContainer.objects.create(primary=self.resource, created_by=self.user)
        self.resource.container = self.container
        self.resource.save()
        self.file_path = os.path.join(settings.MEDIA_ROOT, 'test.ack')

        with open(self.file_path, 'w') as f:
            test_file = File(f)
            test_file.write('asdf')

        with open(self.file_path, 'r') as f:
            test_file = File(f)
            self.content_resource = Resource.objects.create(content_resource=True, file=test_file, created_by=self.user, container=self.container)
        self.content_relation = ContentRelation.objects.create(for_resource=self.resource, content_resource=self.content_resource, created_by=self.user, container=self.container)

    def test_create_giles_upload(self):
        """
        Creates a new :class:`.GilesUpload`\.
        """

        import jsonpickle

        pk = giles.create_giles_upload(self.resource.id, self.content_relation.id, self.user.username)
        self.assertIsInstance(pk, int)
        try:
            upload = GilesUpload.objects.get(pk=pk)
        except GilesUpload.DoesNotExist:
            self.fail('Did not create a GilesUpload instance')

        self.assertEqual(upload.state, GilesUpload.PENDING)
        self.assertEqual(upload.file_path, self.content_resource.file.name)
        self.assertEqual(upload.created_by, self.user)
        self.assertEqual(len(jsonpickle.decode(upload.on_complete)), 2)

    @mock.patch('cookies.giles.POST')
    def test_send_to_giles(self, mock_post):
        """
        Sends a file indicated in a :class:`.GilesUpload` to Giles.
        """
        upload_id = "PROGQ3Fm2J"
        mock_post.return_value = MockDataResponse(200, {
            "id": upload_id,
            "checkUrl":"http://giles/giles/rest/files/upload/check/PROGQ3Fm2J"
        })
        pk = giles.create_giles_upload(self.resource.id, self.content_relation.id, self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        giles.send_giles_upload(pk, self.user.username)

        upload.refresh_from_db()
        self.assertEqual(upload.state, GilesUpload.SENT)
        self.assertEqual(upload.upload_id, upload_id)
        self.assertEqual(mock_post.call_count, 1)
        args, kwargs = mock_post.call_args
        self.assertIn('files', kwargs)
        self.assertIn('data', kwargs)
        self.assertIn('headers', kwargs)

    @mock.patch('cookies.giles.POST')
    def test_send_to_giles_500(self, mock_post):
        """
        If Giles response with a 500 server error, the GilesUpdate state should
        be set to SEND_ERROR.
        """
        message = 'blargh'
        mock_post.return_value = MockDataResponse(500, message, content=message)
        pk = giles.create_giles_upload(self.resource.id,
                                       self.content_relation.id,
                                       self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        giles.send_giles_upload(pk, self.user.username)

        self.assertEqual(mock_post.call_count, 1)
        upload.refresh_from_db()
        self.assertEqual(upload.state, GilesUpload.SEND_ERROR)
        self.assertIn(message, upload.message)

    @mock.patch('cookies.giles.POST')
    def test_send_to_giles_503(self, mock_post):
        """
        If Giles response with a 503 server error, the GilesUpdate state should
        be set to SEND_ERROR.
        """
        message = 'blargh'
        mock_post.return_value = MockDataResponse(503, message, content=message)
        pk = giles.create_giles_upload(self.resource.id,
                                       self.content_relation.id,
                                       self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        giles.send_giles_upload(pk, self.user.username)

        self.assertEqual(mock_post.call_count, 1)
        upload.refresh_from_db()
        self.assertEqual(upload.state, GilesUpload.SEND_ERROR)
        self.assertIn(message, upload.message)

    @mock.patch('cookies.giles.POST', new_callable=MockResponse401)
    def test_send_to_giles_401(self, mock_post):
        """
        When we attempt to send a GilesUpload, if a 401 unauthorized is returned
        we should get a new auth token and try again.
        """
        upload_id = "PROGQ3Fm2J"
        mock_post.return_value = MockDataResponse(200, {
            "id": upload_id,
            "checkUrl":"http://giles/giles/rest/files/upload/check/PROGQ3Fm2J"
        })

        pk = giles.create_giles_upload(self.resource.id,
                                       self.content_relation.id,
                                       self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        giles.send_giles_upload(pk, self.user.username)

        self.assertEqual(mock_post.call_count, 3)
        upload.refresh_from_db()
        self.assertEqual(upload.state, GilesUpload.SENT)

    @mock.patch('cookies.giles.POST')
    @mock.patch('cookies.giles.GET')
    def test_check_upload_status(self, mock_get, mock_post):
        mock_get.return_value = MockDataResponse(202, {
            "msg":"Upload in progress. Please check back later.",
            "msgCode":"010"
        })

        upload_id = "PROGQ3Fm2J"
        mock_post.return_value = MockDataResponse(200, {
            "id": upload_id,
            "checkUrl":"http://giles/giles/rest/files/upload/check/PROGQ3Fm2J"
        })
        pk = giles.create_giles_upload(self.resource.id, self.content_relation.id, self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        giles.send_giles_upload(pk, self.user.username)
        giles.check_upload_status(self.user.username, upload_id)
        upload.refresh_from_db()

        self.assertEqual(upload.state, GilesUpload.SENT)
        self.assertEqual(upload.upload_id, upload_id)
        self.assertEqual(mock_get.call_count, 1)
        args, kwargs = mock_get.call_args
        self.assertTrue(args[0].endswith(upload_id))
        self.assertIn('headers', kwargs)
        self.assertIn('Authorization', kwargs['headers'])


    @mock.patch('cookies.giles.POST')
    @mock.patch('cookies.giles.GET')
    def test_process_upload_unknown(self, mock_get, mock_post):
        __text__ = Type.objects.create(uri='http://purl.org/dc/dcmitype/Text')
        __image__ = Type.objects.create(uri='http://purl.org/dc/dcmitype/Image')
        __document__ = Type.objects.create(uri='http://xmlns.com/foaf/0.1/Document')
        __part__ = Field.objects.create(uri='http://purl.org/dc/terms/isPartOf')

        mock_get.return_value = MockDataResponse(200, [{
          "documentId" : "DOC123edf",
          "uploadId" : "UPxx456",
          "uploadedDate" : "2016-09-20T14:03:00.152Z",
          "access" : "PRIVATE",
          "uploadedFile" : {
            "filename" : "uploadedFile.pdf",
            "id" : "FILE466tgh",
            "url" : "http://your-giles-host.net/giles/rest/files/FILE466tgh/content",
            "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf",
            "content-type" : "application/pdf",
            "size" : 3852180
          },
          "extractedText" : {
            "filename" : "uploadedFile.pdf.txt",
            "id" : "FILE123cvb",
            "url" : "http://your-giles-host.net/giles/rest/files/FILE123cvb/content",
            "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.txt",
            "content-type" : "text/plain",
            "size" : 39773
          },
          "pages" : [ {
            "nr" : 0,
            "image" : {
              "filename" : "uploadedFile.pdf.0.tiff",
              "id" : "FILEYUI678",
              "url" : "http://your-giles-host.net/giles/rest/digilib?fn=username%FILEYUI678%2FDOC123edf0%2FuploadedFile.pdf.0.tiff",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.tiff",
              "content-type" : "image/tiff",
              "size" : 2032405
            },
            "text" : {
              "filename" : "uploadedFile.pdf.0.txt",
              "id" : "FILE789UIO",
              "url" : "http://your-giles-host.net/giles/rest/files/FILE789UIO/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.txt",
              "content-type" : "text/plain",
              "size" : 4658
            },
            "ocr" : {
              "filename" : "uploadedFile.pdf.0.tiff.txt",
              "id" : "FILE789U12",
              "url" : "http://your-giles-host.net/giles/rest/files/FILE789U12/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.tiff.txt",
              "content-type" : "text/plain",
              "size" : 4658
            }
          }, {
            "nr" : 1,
            "image" : {
              "filename" : "uploadedFile.pdf.1.tiff",
              "id" : "FILE045tyhG",
              "url" : "http://your-giles-host.net/giles/rest/digilib?fn=username%2FFILE045tyhG%2FDOC123edf0%2FuploadedFile.pdf.1.tiff",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.1.tiff",
              "content-type" : "image/tiff",
              "size" : 2512354
            },
            "text" : {
              "filename" : "uploadedFile.pdf.1.txt",
              "id" : "FILEMDSPfeVm",
              "url" : "http://your-giles-host.net/giles/rest/files/FILEMDSPfeVm/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.1.txt",
              "content-type" : "text/plain",
              "size" : 5799
            },
            "ocr" : {
              "filename" : "uploadedFile.pdf.1.tiff.txt",
              "id" : "FILEMDSPfe12",
              "url" : "http://your-giles-host.net/giles/rest/files/FILEMDSPfe12/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.1.tiff.txt",
              "content-type" : "text/plain",
              "size" : 5799
            }
          }]}])

        upload_id = "UPxx456"
        giles.process_upload(upload_id, self.user.username)
        upload = GilesUpload.objects.get(upload_id=upload_id)

        self.assertEqual(upload.state, GilesUpload.DONE)
        self.assertTrue(upload.resource is not None)

        self.assertEqual(upload.resource.relations_to.count(), 2)
        self.assertEqual(upload.resource.content.count(), 2)

        for cr in upload.resource.content.all():
            self.assertFalse(cr.content_resource.public)

    @mock.patch('cookies.giles.POST')
    @mock.patch('cookies.giles.GET')
    def test_process_upload_known(self, mock_get, mock_post):
        __text__ = Type.objects.create(uri='http://purl.org/dc/dcmitype/Text')
        __image__ = Type.objects.create(uri='http://purl.org/dc/dcmitype/Image')
        __document__ = Type.objects.create(uri='http://xmlns.com/foaf/0.1/Document')
        __part__ = Field.objects.create(uri='http://purl.org/dc/terms/isPartOf')

        mock_get.return_value = MockDataResponse(200, [{
          "documentId" : "DOC123edf",
          "uploadId" : "UPxx456",
          "uploadedDate" : "2016-09-20T14:03:00.152Z",
          "access" : "PRIVATE",
          "uploadedFile" : {
            "filename" : "uploadedFile.pdf",
            "id" : "FILE466tgh",
            "url" : "http://your-giles-host.net/giles/rest/files/FILE466tgh/content",
            "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf",
            "content-type" : "application/pdf",
            "size" : 3852180
          },
          "extractedText" : {
            "filename" : "uploadedFile.pdf.txt",
            "id" : "FILE123cvb",
            "url" : "http://your-giles-host.net/giles/rest/files/FILE123cvb/content",
            "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.txt",
            "content-type" : "text/plain",
            "size" : 39773
          },
          "pages" : [ {
            "nr" : 0,
            "image" : {
              "filename" : "uploadedFile.pdf.0.tiff",
              "id" : "FILEYUI678",
              "url" : "http://your-giles-host.net/giles/rest/digilib?fn=username%FILEYUI678%2FDOC123edf0%2FuploadedFile.pdf.0.tiff",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.tiff",
              "content-type" : "image/tiff",
              "size" : 2032405
            },
            "text" : {
              "filename" : "uploadedFile.pdf.0.txt",
              "id" : "FILE789UIO",
              "url" : "http://your-giles-host.net/giles/rest/files/FILE789UIO/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.txt",
              "content-type" : "text/plain",
              "size" : 4658
            },
            "ocr" : {
              "filename" : "uploadedFile.pdf.0.tiff.txt",
              "id" : "FILE789U12",
              "url" : "http://your-giles-host.net/giles/rest/files/FILE789U12/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.0.tiff.txt",
              "content-type" : "text/plain",
              "size" : 4658
            }
          }, {
            "nr" : 1,
            "image" : {
              "filename" : "uploadedFile.pdf.1.tiff",
              "id" : "FILE045tyhG",
              "url" : "http://your-giles-host.net/giles/rest/digilib?fn=username%2FFILE045tyhG%2FDOC123edf0%2FuploadedFile.pdf.1.tiff",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.1.tiff",
              "content-type" : "image/tiff",
              "size" : 2512354
            },
            "text" : {
              "filename" : "uploadedFile.pdf.1.txt",
              "id" : "FILEMDSPfeVm",
              "url" : "http://your-giles-host.net/giles/rest/files/FILEMDSPfeVm/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.1.txt",
              "content-type" : "text/plain",
              "size" : 5799
            },
            "ocr" : {
              "filename" : "uploadedFile.pdf.1.tiff.txt",
              "id" : "FILEMDSPfe12",
              "url" : "http://your-giles-host.net/giles/rest/files/FILEMDSPfe12/content",
              "path" : "username/UPxx456/DOC123edf/uploadedFile.pdf.1.tiff.txt",
              "content-type" : "text/plain",
              "size" : 5799
            }
          }]}])

        upload_id = "UPxx456"
        mock_post.return_value = MockDataResponse(200, {
            "id": upload_id,
            "checkUrl":"http://giles/giles/rest/files/upload/check/PROGQ3Fm2J"
        })
        pk = giles.create_giles_upload(self.resource.id, self.content_relation.id, self.user.username)
        giles.send_giles_upload(pk, self.user.username)
        upload = GilesUpload.objects.get(pk=pk)
        fpath = upload.file_path
        self.assertTrue(os.path.exists(os.path.join(settings.MEDIA_ROOT, fpath)))

        giles.process_upload(upload_id, self.user.username)
        upload = GilesUpload.objects.get(upload_id=upload_id)

        self.assertEqual(upload.state, GilesUpload.DONE)
        self.assertEqual(upload.resource, self.resource)

        self.assertEqual(upload.resource.relations_to.count(), 2)
        self.assertEqual(upload.resource.content.count(), 3)
        self.assertEqual(upload.resource.content.filter(is_deleted=False).count(), 2)
        deleted_resource = upload.resource.content.filter(is_deleted=True).first().content_resource
        self.assertFalse(os.path.exists(os.path.join(settings.MEDIA_ROOT, fpath)))

        for cr in upload.resource.content.all():
            self.assertFalse(cr.content_resource.public)


    def tearDown(self):
        Resource.objects.all().delete()
        ContentRelation.objects.all().delete()
        User.objects.all().delete()
        GilesUpload.objects.all().delete()
        Type.objects.all().delete()
        Field.objects.all().delete()



class TestHandleStatusException(unittest.TestCase):
    """
    Tests related to the :func:`cookies.giles.handle_status_exception`
    decorator.
    """
    def setUp(self):
        self.factory = RequestFactory()
        User.objects.all().delete()
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='nope',
        )
        self.auth = UserSocialAuth.objects.create(**{
            'user': self.user,
            'provider': 'github',
            'uid': 'asdf1234',
        })
        self.provider_token = 'fdsa5432'
        self.auth.extra_data['access_token'] = self.provider_token
        self.auth.save()

    @mock.patch('cookies.giles.POST')
    def test_handle_status_exception(self, mock_post):
        """
        When a decorated function returns a response with status 401, a call to
        the token endpoint should automatically be made, and the decorated
        function should be called again.
        """
        mock_post.return_value = MockResponse(200, 'token_ok.json')

        jup = MockResponse401()    # Simulates re-auth process.
        jup.return_value = MockDataResponse(200, 'Yes', content='Yes')

        @giles.handle_status_exception
        def func(arg):
            return jup(arg)

        func(self.user.username)

        self.assertEqual(jup.call_count, 2,
                         "That's a total of two calls to the decorated"
                         " function.")
        self.assertEqual(mock_post.call_count, 1,
                         "And one call to the token endpoint.")

    def tearDown(self):
        Resource.objects.all().delete()
        ContentRelation.objects.all().delete()
        User.objects.all().delete()
        GilesUpload.objects.all().delete()
        Type.objects.all().delete()
        Field.objects.all().delete()



if __name__ == '__main__':
    unittest.main()
