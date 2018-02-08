"""
This module provides methods for interacting with Giles.
"""


from django.conf import settings
from django.core.files import File
from  django.core.exceptions import ObjectDoesNotExist

from cookies.models import *
from cookies import models    # TODO: wtf.
from cookies.exceptions import *

import requests, os, jsonpickle, urllib, urlparse
from datetime import datetime, timedelta
from django.utils import timezone
from collections import defaultdict

_fix_url = lambda url: url#url.replace('http://', 'https://') if url is not None else None

GET = requests.get
POST = requests.post
ACCEPTED = 202

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)


class StatusException(Exception):
    def __init__(self, response):
        self.message = 'Encountered status %i: %s' % (response.status_code, response.content)
        self.response = response
        self.status_code = response.status_code

    def __str__(self):
        return repr(self.message)


class UserHasNoProviderToken(Exception):
    pass


def handle_status_exception(func):
    """
    Decorator for functions that call Giles. Provides automatic token refresh,
    and raises a :class:`.StatusException` for non-200-series HTTP status codes.
    """
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)

        if type(user) in [str, unicode]:    # May be a username, rather than a User.
            user = User.objects.get(username=user)

        if response.status_code == 401:    # Auth token expired.
            try:
                user.giles_token.delete()
            except (AssertionError, ObjectDoesNotExist):
                pass
            except Exception as E:
                raise

            get_user_auth_token(user, fresh=True, **kwargs)
            user.refresh_from_db()
            response  = func(user, *args, **kwargs)
            logger.debug('response %s: %s' % (response.status_code, response.content))
            return response
        elif response.status_code != requests.codes.ok and response.status_code != 202:
            logger.error('Giles responded with status %i: content: %s' % \
                         (response.status_code, response.content))
            raise StatusException(response)
        return response
    return wrapper


def api_request(func):
    """
    Convenience decorator for functions that call Giles. Automatically pulls
    out the status code and JSON data from the response.
    """
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)
        return response.status_code, response.json()
    return wrapper


def _create_auth_header(user, **kwargs):
    """
    Convenience function for generating the authorization header for Giles
    requests.
    """
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    return {'Authorization': 'token %s' % get_user_auth_token(user)}


def get_user_auth_token(user, **kwargs):
    """
    Get the current auth token for a :class:`.User`\. If the user has no auth
    token, retrieves one and stores it.

    Parameters
    ----------
    user : :class:`django.contrib.auth.User`
    kwargs : kwargs

    Returns
    -------
    str
        Giles authorization token for ``user``.
    """
    fresh = kwargs.pop('fresh', False)
    logger.debug('get_user_auth_token:: for %s' % user.username)

    try:
        _expiry = timezone.now() - timedelta(minutes=settings.GILES_TOKEN_EXPIRATION)
        if not fresh and user.giles_token.created > _expiry:
            return user.giles_token.token
    except (AttributeError, ObjectDoesNotExist):    # RelatedObjectDoesNotExist.
        pass    # Will proceed to retrieve token.

    data = None
    try:
        try:    # Delete the old token first.
            user.giles_token.delete()
        except (AssertionError, ObjectDoesNotExist):
            pass

        status_code, data = get_auth_token(user, **kwargs)
        user.giles_token = GilesToken.objects.create(for_user=user, token=data["token"])
        user.save()
        return user.giles_token.token
    except Exception as E:
        logger.error("Failed to retrieve access token for %s: %s" % \
                     (user.username, str(E)))
        import json
        logger.error(json.dumps(data))
        if kwargs.get('raise_exception', False):
            raise E


@api_request
def get_auth_token(user, **kwargs):
    """
    Obtain and store a short-lived authorization token from Giles.

    See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
    """
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', POST)
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    app_token = kwargs.get('app_token', settings.GILES_APP_TOKEN)

    path = '/'.join([giles, 'rest', 'token'])
    try:
        provider_token = user.social_auth.get(provider=provider)\
                                         .extra_data.get('access_token')
    except ObjectDoesNotExist:
        raise UserHasNoProviderToken('User %s has no token for provider %s' % \
                                     (user.username, provider))

    return post(path, data={'providerToken': provider_token},
                headers={'Authorization': 'token %s' % app_token})


@api_request
@handle_status_exception
def send_to_giles(username, file_name, public=False, **kwargs):
    """
    Send a file to Giles.

    Parameters
    ----------
    username : str
        The owner of the file. This will be used to select the authorization
        token, and the resource will permanently belong to this user in Giles.
    file_name : str
        File path relative to MEDIA_ROOT.
    public : bool
        Whether or not the file should be publically accessible on Giles. The
        current approach is to set all files to private, and then provide
        paths with short-lived Giles tokens to individual users on a
        case-by-case basis.

    Returns
    -------
    :class:`requests.Response`

    """
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', POST)

    path = '/'.join([giles, 'rest', 'files', 'upload'])
    headers = _create_auth_header(user, **kwargs)
    # headers.update({ 'Content-Type': 'multipart/form-data', })

    data = {'access': 'PUBLIC' if public else 'PRIVATE',}
    _full_path = os.path.join(settings.MEDIA_ROOT, file_name.encode('utf-8'))
    # POST payload.
    files = {
        'files': ( file_name, File(open(_full_path, 'rb')), 'application/pdf')
    }

    # Giles should respond with a token for each upload, which we should
    #  check periodically for completion (OCR takes longer than the Apache
    #  timeout).
    # import httplib as http_client
    # http_client.HTTPConnection.debuglevel = 1
    # requests_log = logging.getLogger("requests.packages.urllib3")
    # requests_log.setLevel(logging.DEBUG)
    # requests_log.propagate = True
    return post(path, headers=headers, files=files, data=data)


def create_giles_upload(resource_id, content_relation_id, username,
                        delete_on_complete=True):
    """
    Create a new pending :class:`.GilesUpload` for a :class:`.Resource`\.

    No files will have been sent at this point -- a worker will add this upload
    to the queue.

    Parameters
    ----------
    resource_id : int
        This :class:`.Resource` will be associated with the upload.
    content_relation_id : int
    username : str
    delete_on_complete : bool
        If True, the local file will be removed once Giles has fully processed
        the upload; the content resource will be flagged as deleted.

    Returns
    -------
    int
        The ID of the :class:`.GilesUpload`\.
    """
    resource = Resource.objects.get(pk=resource_id)
    content_relation = ContentRelation.objects.get(pk=content_relation_id)
    content_resource = content_relation.content_resource
    user = User.objects.get(username=username)

    if resource.created_through == Resource.INTERFACE_WEB:
        priority = GilesUpload.PRIORITY_MEDIUM
    elif resource.created_through == Resource.INTERFACE_API:
        priority = GilesUpload.PRIORITY_LOW
    else:
        priority = GilesUpload.PRIORITY_MEDIUM

    data = {
        'resource':resource,
        'file_path': content_resource.file.name,
        'state': GilesUpload.PENDING,
        'created_by': user,
        'priority': priority,
    }

    if delete_on_complete:
        data.update({
            'on_complete': jsonpickle.encode([
                ('Resource', content_resource.id, 'delete'),
                ('ContentRelation', content_relation_id, 'delete'),
            ])
        })

    return GilesUpload.objects.create(**data).id



def send_giles_upload(upload_pk, username):
    """
    Send data for a pending :class:`.GilesUpload`\.

    If successfuly, transitions state from PENDING to SENT. If an exception is
    raised, transitions state from PENDING to SEND_ERROR.

    Parameters
    ----------
    upload_pk : int
    username : str
    """
    upload = GilesUpload.objects.get(pk=upload_pk)

    # This will trigger an actual upload, and we don't want to do it twice.
    if not upload.state in [GilesUpload.PENDING, GilesUpload.ENQUEUED]:
        return

    try:
        code, result = send_to_giles(username, upload.file_path, public=False)
        if code != 200:
            raise RuntimeError('Giles returned HTTP {}'.format(code))
        upload.upload_id = result['id']
        upload.state = GilesUpload.SENT
    except AttributeError as E:
        message = str(result)
        logger.error("Giles returned an uninterpretable message when sending"
                     " upload %i: %s" % (upload.id, message))
        upload.message = message
        upload.state = GilesUpload.SEND_ERROR
    except Exception as E:    # TODO: be more specific.
        logger.error('Encountered exception when sending upload %i: %s' % \
                     (upload.id, str(E)))
        upload.message = str(E)
        upload.state = GilesUpload.SEND_ERROR
    upload.save()


@api_request
@handle_status_exception
def check_upload_status(username, upload_id , **kwargs):
    """
    Poll Giles for the status of a POSTed upload.

    Parameters
    ----------
    username : str
        This must be the same user on whose behalf we uploaded the file.
    upload_id : str
        The "poll id" that Giles returned upon upload.
    kwargs : kwargs
        Can inject ``giles`` (base path for Giles instance) and ``get``
        (callable that accepts an URL and ``headers`` kwarg).

    Returns
    -------
    :class:`requests.Response`
    """
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    get = kwargs.get('get', GET)
    checkURL = giles + '/rest/files/upload/check/%s' % upload_id
    return get(checkURL, headers=_create_auth_header(user, **kwargs))


def _create_content_resource(parent_resource, resource_type, creator, uri, url,
                             public=False, **meta):
    """
    Helper function for creating appropriate resources and relations after
    Giles successfully processes an upload.

    Parameters
    ----------
    parent_resource : :class:`.Resource` instance
        Represents the document/object of which the content resource (to be
        created) is a digital surrogate.
    resource_type : :class:`.Type` instance
    creator : :class:`.User`
        The person responsible for adding the content to Giles.
    uri : str
        Identifier for the content resource. Should usually be
        ``{giles}/files/{file_id}``.
    url : str
        Location of the content.
    public : bool
        Whether or not this record should be public in JARS. This should match
        the setting for this resource in Giles, otherwise things might get
        weird.
    meta : kwargs
        Can provide any of the following:
          - ``name`` : Human-readable name (for display).
          - ``file_id`` : Giles identifier.
          - ``path`` : Digilib-style image path.
          - ``size`` : (int) Dimensionless.
          - ``content_type`` : Should be a valid MIME-type (but not enforced).

    Returns
    -------
    :class:`.Resource`
        The content resource.
    """
    url = _fix_url(url)
    # This is the page image.
    content_resource = Resource.objects.create(**{
        'name': meta.get('name', url),
        'location': url,
        'public': public,
        'content_resource': True,
        'created_by_id': creator.id,
        'created_through': parent_resource.created_through,
        'entity_type': resource_type,
        'content_type': meta.get('content_type', None),
        'is_external': True,
        'external_source': Resource.GILES,
        'uri': uri,
        'container': parent_resource.container,
    })

    ContentRelation.objects.create(**{
        'for_resource': parent_resource,
        'content_resource': content_resource,
        'content_type': meta.get('content_type', None),
        'container': parent_resource.container,
    })

    return content_resource


def _create_page_resource(parent_resource, page_nr, resource_type, creator, uri,
                          url, public=False, **meta):
    """
    Helper function for creating appropriate resources and relations after
    Giles successfully processes an upload.

    Parameters
    ----------
    parent_resource : :class:`.Resource` instance
    page_nr : int
    resource_type : :class:`.Type` instance
    creator : :class:`.User`
        The person responsible for adding the content to Giles.
    uri : str
        Identifier for the content resource. Should usually be
        ``{giles}/files/{file_id}``.
    url : str
        Location of the content.
    public : bool
        Whether or not this record should be public in JARS. This should match
        the setting for this resource in Giles, otherwise things might get
        weird.
    meta : kwargs
    """
    __part__ = Field.objects.get(uri='http://purl.org/dc/terms/isPartOf')

    resource = Resource.objects.create(**{
        'name': '%s, page %i' % (parent_resource.name, page_nr),
        'created_by_id': creator.id,
        'created_through': parent_resource.created_through,
        'entity_type': resource_type,
        'public': public,
        'content_resource': False,
        'is_part': True,
        'is_external': True,
        'external_source': Resource.GILES,
        'container': parent_resource.container,
    })

    Relation.objects.create(**{
        'source': resource,
        'target': parent_resource,
        'predicate': __part__,
        'container': parent_resource.container,
        'sort_order': int(page_nr),
    })
    return resource


def process_on_complete(on_complete):
    """
    Perform post-processing actions.

    These are set when a :class:`.GilesUpload` is created. Currently only
    supports ``'delete'`` action, which sets ``is_deleted`` and permanently
    deletes any attached files in the filesystem.

    Parameters
    ----------
    on_complete : list
        Should be a list of 3-tuples: ``(model, pk, action)``.
    """

    def _delete(obj):
        if getattr(obj, 'file', None):
            path = os.path.join(settings.MEDIA_ROOT, obj.file.name)
            if os.path.isfile(path):
                os.remove(path)
        obj.file = None
        obj.is_deleted = True
        obj.save()

    _actions = {'delete': _delete}
    for model, pk, action in on_complete:
        obj = getattr(models, model).objects.get(pk=pk)
        _actions.get(action, (lambda o: o))(obj)


def process_upload(upload_id, username):
    """
    Given a Giles upload id, attempt to retrieve file details and create local
    data structures (if ready).

    Transitions state from SENT to DONE, or (if there are exceptions) one of
    the error states.

    Parameters
    ----------
    upload_id : str
        The "poll id" returned by Giles when the file was uploaded.
    username : str
        This must be the same user on whose behalf we uploaded the file.
    """
    import datetime, jsonpickle
    from django.utils import timezone

    user = User.objects.get(username=username)

    # The upload may or may not have originated in Amphora.
    _defaults = {'created_by': user, 'state': GilesUpload.SENT}
    upload, _created = GilesUpload.objects.get_or_create(upload_id=upload_id,
                                                         defaults=_defaults)

    if not _created and upload.created_by != user:
        raise RuntimeError('Upload was made on behalf of a different user')

    upload.last_checked = timezone.now()    # TODO: this is probably redundant.
    try:
        code, data = check_upload_status(username, upload_id)
    except Exception as E:
        upload.message = str(E)
        upload.state = GilesUpload.GILES_ERROR
        upload.save()
        return

    if code == ACCEPTED:    # Giles is still processing the upload.
        upload.state = GilesUpload.SENT
        upload.save()
        return

    try:
        # If Giles is done processing the upload, details about the resulting
        #  files are returned.
        resource = process_details(data, upload_id, username)
        if not upload.resource:
            upload.resource = resource
            upload.save()
    except Exception as E:    # We f***ed something up.
        upload.message = str(E)
        upload.state = GilesUpload.PROCESS_ERROR
        upload.save()
        return

    # Depending on configuration, we may want to do things like delete local
    #  copies of files.
    if upload.on_complete:
        try:
            process_on_complete(jsonpickle.decode(upload.on_complete))
        except Exception as E:
            upload.message = str(E)
            upload.state = GilesUpload.CALLBACK_ERROR
            upload.save()
            return

    # Woohoo!
    upload.state = GilesUpload.DONE
    upload.message = jsonpickle.encode(data)
    upload.save()


def process_details(data, upload_id, username):
    """
    Process document data from Giles.

    Paramters
    ---------
    data : dict
    upload_id : str
        The original poll ID returned by Giles upon upload.
    username : str

    Returns
    -------
    :class:`.Resource`
    """

    if isinstance(data, list):
        if len(data) == 0:
            raise ValueError('data is empty')
        data = data[0]

    upload = GilesUpload.objects.get(upload_id=upload_id)
    resource = upload.resource    # This is the master resource.
    creator = User.objects.get(username=username)

    giles = settings.GILES
    __text__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Text')
    __image__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Image')
    __document__ = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')

    document_id = data.get('documentId')

    # We may already have a master Resource, e.g. if we POSTed a file from a
    #  Zotero batch-ingest and have been awaiting processing by Giles.
    if resource is None:
        resource, created = Resource.objects.get_or_create(
            name = document_id,
            defaults = {
                'created_by_id': creator.id,
                'entity_type': __document__,
                'uri': '%s/documents/%s' % (giles, document_id),
                'content_resource': False,
                'is_external': True,
                'external_source': Resource.GILES,
            })
        container = ResourceContainer.objects.create(primary=resource,
                                                     created_by=creator)
        resource.container = container
        resource.save()

    # Content resource for uploaded file.
    upload_data = data.get('uploadedFile')
    content_type = upload_data.get('content-type')
    resource_type = __text__ if content_type == 'application/pdf' else __image__
    # resource_uri = '%s/files/%s' % (giles, upload_data.get('id'))
    resource_uri = upload_data.get('url')
    _create_content_resource(resource, resource_type, creator, resource_uri,
                             resource_uri, content_type=content_type)

    # Content resoruce for extracted text, if available.
    text_data = data.get('extractedText', None)
    if text_data is not None:
        text_content_type = text_data.get('content-type')
        # text_uri = '%s/files/%s' % (giles, text_data.get('id'))
        text_uri = text_data.get('url')
        _create_content_resource(resource, __text__, creator, text_uri,
                                 text_uri, content_type=text_content_type)

    # Keep track of page resources so that we can populate ``next_page``.
    pages = defaultdict(dict)

    # Each page is represented by a Resource.
    for page_data in data.get('pages', []):
        page_nr = int(page_data.get('nr'))
        page_uri = '%s/documents/%s/%i' % (giles, document_id, page_nr)
        page_resource = _create_page_resource(resource, page_nr, __document__,
                                              creator, page_uri,
                                              _fix_url(page_data.get('url')),
                                              public=False)

        pages[page_nr]['resource'] = page_resource

        # Each page resource can have several content resources.
        for fmt in ['image', 'text']:
            # We may not have both formats for each page.
            fmt_data = page_data.get(fmt, None)
            if fmt_data is None:
                continue

            page_fmt_uri = '%s/files/%s' % (giles, fmt_data.get('id'))
            pages[page_nr][fmt] = _create_content_resource(page_resource,
                                     __image__ if fmt == 'image' else __text__,
                                     creator, page_fmt_uri,
                                     _fix_url(fmt_data.get('url')),
                                     public=False,
                                     content_type=fmt_data.get('content-type'),
                                     name='%s (%s)' % (page_resource.name, fmt))

        # Populate the ``next_page`` field for pages, and for their content
        #  resources.
        for i in sorted(pages.keys())[:-1]:
            for fmt in ['resource', 'image', 'text']:
                if fmt not in pages[i]:
                    continue
                pages[i][fmt].next_page = pages[i + 1][fmt]
                pages[i][fmt].save()

    return resource


def format_giles_url(url, username, dw=300):
    """
    Adds ``accessToken`` and ``dw`` parameters to ``url``.

    Parameters
    ----------
    url : str
        This should be an URL for content in Giles.
    username : str
        Name of the user who owns (or has Giles-level rights) to the resource.
        Will be used to select the Giles access token.
    dw : int
        Display width (for images); for Digilib.

    Returns
    -------
    str
        URL with auth token and display width GET parameters.
    """

    user = User.objects.get(username=username)
    parts = list(tuple(urlparse.urlparse(url)))
    q = {k: v[0] for k, v in urlparse.parse_qs(parts[4]).iteritems()}
    q.update({'accessToken': get_user_auth_token(user), 'dw': dw})
    parts[4] = urllib.urlencode(q)
    return urlparse.urlunparse(tuple(parts))
