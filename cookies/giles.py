from django.conf import settings
from django.core.files import File

from cookies.models import *
from cookies.exceptions import *

import requests, os
from collections import defaultdict

_fix_url = lambda url: url.replace('http://', 'https://') if url is not None else None


def _get_file_data(raw_data):
    files = {}
    for obj in raw_data:
        key = obj.get('documentId')

        files[key] = obj
    return files


def handle_status_exception(func):
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)
        if response.status_code == 401:    # Auth token expired.
            try:
                user.giles_token.delete()
            except AssertionError:
                pass

            get_user_auth_token(user, **kwargs)
            user.refresh_from_db()
            # TODO: we could put some Exception handling here.
            return func(user, *args, **kwargs)
        elif response.status_code != requests.codes.ok and response.status_code != 202:
            message = 'Status %i, content: %s' % (response.status_code, response.content)
            logger.error(message)
            raise StatusException(response)
        return response
    return wrapper


def api_request(func):
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)
        return response.status_code, response.json()
    return wrapper


def _create_auth_header(user, **kwargs):
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    # token = user.social_auth.get(provider=provider).extra_data['access_token']
    token = get_user_auth_token(user)
    return {'Authorization': 'token %s' % token}


def get_user_auth_token(user, **kwargs):
    """
    Get the current auth token for a :class:`.User`\.

    If the user has no auth token, retrieve one and store it.

    Supports dependency injection.

    Parameters
    ----------
    user : :class:`django.contrib.auth.User`
    kwargs : kwargs

    Returns
    -------
    str
        Giles authorization token for ``user``.
    """
    fresh = kwargs.get('fresh', False)
    try:
        if user.giles_token and not fresh:
            return user.giles_token.token
    except AttributeError:    # RelatedObjectDoesNotExist.
        pass    # Will proceed to retrieve token.

    try:
        status_code, data = get_auth_token(user, **kwargs)
        user.giles_token =  GilesToken.objects.create(for_user=user, token=data["token"])
        user.save()
        return user.giles_token.token
    except Exception as E:
        template = "Failed to retrieve access token for user {u}"
        msg = template.format(u=user.username)
        if kwargs.get('raise_exception', False):
            raise E
        logger.error(msg)


# @handle_status_exception
@api_request
def get_auth_token(user, **kwargs):
    """
    Obtain and store a short-lived authorization token from Giles.

    See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
    """
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', settings.POST)
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    app_token = kwargs.get('app_token', settings.GILES_APP_TOKEN)

    path = '/'.join([giles, 'rest', 'token'])
    provider_token = user.social_auth.get(provider=provider)\
                                     .extra_data.get('access_token')
    return post(path, data={'providerToken': provider_token},
                headers={'Authorization': 'token %s' % app_token})


@api_request
@handle_status_exception
def send_to_giles(user, file_name, resource=None, public=True, **kwargs):
    """

    Parameters
    ----------
    user : :class:`.User`
    file_obj : file-like object
    giles : str
        Giles endpoint.
    post : callable
        POST method should return an object with properties ``status_code``
        (int) and ``content`` (unicode-like), and a method called ``json()``
        that returns a dict.
    resource : :class:`.Resource`
        If a :class:`.Resource` already exists for this document, then the
        file(s) sent to Giles will be linked to that :class:`.Resource` as
        content resources. Otherwise a new :class:`.Resource` will be created.

    Returns
    -------
    :class:`.Resource`

    """
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', settings.POST)

    path = '/'.join([giles, 'rest', 'files', 'upload'])
    headers = _create_auth_header(user, **kwargs)
    headers.update({
        # 'Content-Type': 'multipart/form-data',
    })
    logger.debug(str(headers))

    data = {'access': 'PUBLIC' if public else 'PRIVATE',}

    # POST request.
    files = {
        'files': (
            file_name,
              File(open(os.path.join(settings.MEDIA_ROOT, file_name.encode('utf-8')), 'rb')),
              'application/pdf'
          )
    }
    logger.debug(str(files))

    # Giles should respond with a token for each upload, which we should
    #  check periodically for completion (OCR takes longer than the Apache
    #  timeout).
    # import httplib as http_client
    # http_client.HTTPConnection.debuglevel = 1
    # requests_log = logging.getLogger("requests.packages.urllib3")
    # requests_log.setLevel(logging.DEBUG)
    # requests_log.propagate = True
    return post(path, headers=headers, files=files, data=data)


@api_request
@handle_status_exception
def check_upload_status(user, checkURL, **kwargs):
    """
    Poll Giles for the status of a POSTed upload.
    """
    giles = kwargs.get('giles', settings.GILES)
    get = kwargs.get('get', settings.GET)
    return get(checkURL, headers=_create_auth_header(user, **kwargs))


def get_file_details(user, upload_id, **kwargs):
    """
    Calls Giles back with ``uploadIds`` observed in
    :func:`.handle_giles_callback`\, and retrieves details about images that
    the user has uploaded to Giles.

    Parameters
    ----------
    user : :class:`.User`
    upload_id : str
        A unique ID generated by Giles that refers to a single uploaded.
        It is possible that the upload contained several images (e.g. pages
        extracted from a PDF).

    Optional
    --------
    giles : str
        Location of the Giles REST endpoint.
    get : callable
        Function for executing an HTTP GET request. Must return an object with
        properties ``status_code`` and ``content``, and method ``json()``.
    post : callable
        Function for executing an HTTP POST request. Must return an object with
        properties ``status_code`` and ``content``, and method ``json()``.
    app_token : str
        Application token provided by Giles.
    provider : str
        Third-party auth token provider to user for Giles authorization.
    raise_exception : bool
        If False, exceptions will be passed to logging at ERROR level.

    Returns
    -------
    dict
        Giles image file details. Keys are ``documentId``s (generated by Giles),
        values are lists of dicts, each containing details about an image
        file in that document.

    """
    giles = kwargs.get('giles', settings.GILES)
    get = kwargs.get('get', settings.GET)

    token = get_user_auth_token(user, **kwargs)

    path = '/'.join([giles, 'rest', 'files', 'upload', upload_id])
    response = get(path)
    if response.status_code == 401:
        retrieve_auth_token(user, **kwargs)
        return get_file_details(user, upload_id, **kwargs)
    elif response.status_code != requests.codes.ok:
        msg = 'Call to giles failed with %i: %s' (response.status_code,
                                                  response.content)
        if kwargs.get('raise_exception', False):
            raise RuntimeError(msg)
        logger.error(msg)

    return _get_file_data(response.json())


def process_file_upload(resource, creator, raw_data, **kwargs):
    giles = kwargs.get('giles', settings.GILES)

    file_details = _get_file_data(raw_data)

    for document_id, file_data in file_details.iteritems():
        _process_document_data(file_data, creator, resource=resource, **kwargs)



def _create_content_resource(parent_resource, resource_type, creator, uri, url,
                             public=True, **meta):
    """

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
        'entity_type': resource_type,
        'content_type': meta.get('content_type', None),
        'is_external': True,
        'external_source': Resource.GILES,
        'uri': uri
    })

    ContentRelation.objects.create(**{
        'for_resource': parent_resource,
        'content_resource': content_resource,
        'content_type': meta.get('content_type', None)
    })

    return content_resource


def _create_page_resource(parent_resource, page_nr, resource_type, creator, uri,
                          url, public=True, **meta):
    """

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
        'entity_type': resource_type,
        'public': public,
        'content_resource': False,
        'is_part': True,
        'is_external': True,
        'external_source': Resource.GILES,
    })

    Relation.objects.create(**{
        'source': resource,
        'target': parent_resource,
        'predicate': __part__,
    })
    return resource


def _process_document_data(data, creator, resource=None, **kwargs):

    giles = kwargs.get('giles', settings.GILES)
    __text__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Text')
    __image__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Image')
    __document__ = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')

    # Everything attached to this document will receive the same access
    #  value.
    public = data.get('access', 'PUBLIC') == 'PUBLIC'

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

    # Content resource for uploaded file.
    upload_data = data.get('uploadedFile')
    content_type = upload_data.get('content-type')
    resource_type = __text__ if content_type == 'application/pdf' else __image__
    resource_uri = '%s/files/%s' % (giles, upload_data.get('id'))

    # Content resoruce for extracted text, if available.
    text_data = data.get('extractedText', None)
    if text_data is not None:
        text_content_type = text_data.get('content-type')
        text_uri = '%s/files/%s' % (giles, text_data.get('id'))

    # Keep track of page resources so that we can populate ``next_page``.
    pages = defaultdict(dict)

    # Each page is represented by a Resource.
    for page_data in data.get('pages', []):
        page_nr = int(page_data.get('nr'))
        page_uri = '%s/documents/%s/%i' % (giles, document_id, page_nr)
        page_resource = _create_page_resource(resource, page_nr, __document__,
                                              creator, page_uri,
                                              _fix_url(page_data.get('url')),
                                              public=public)

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
                                     public=public,
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


def process_resources(user, file_details, **kwargs):
    """
    Once details have been retrieved concerning images uploaded to Giles, we
    need to create the appropriate metadata records (Resources). This function
    processes all of the file data associated with an upload,
    creating :class:`.Resource` instances and attendant :class:`.Relation`\s
    as needed.

    Parameters
    ----------
    user : :class:`.User`

    Returns
    -------
    None
    """

    for document_id, file_data in file_details.iteritems():
        _process_document_data(file_data, user, **kwargs)


def handle_giles_callback(request, **kwargs):
    """
    When a user has uploaded images to Giles, they may visit a callback URL that
    includes an ``uploadIds`` parameter. In order to obtain information about
    those uploaded images (e.g. URL, content type, etc) we call a Giles
    REST endpoint (see :func:`.get_file_details`).

    Parameters
    ----------
    request
    giles : str
        Location of the root Giles REST endpoint.
    get : callable
        Function for executing an HTTP GET request. Must return an object with
        properties ``status_code`` and ``content``, and method ``json()``.

    """

    upload_ids = request.GET.getlist('uploadids') + request.GET.getlist('uploadIds')
    if not upload_ids:
        raise ValueError('No upload ids in request')

    file_details = {}
    for uid in upload_ids:
        file_details.update(get_file_details(request.user, uid, **kwargs))

    process_resources(request.user, file_details)
    return
