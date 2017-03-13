from django.conf import settings
from django.core.files import File

from cookies.models import *
from cookies.exceptions import *

import requests, os, jsonpickle
from collections import defaultdict

_fix_url = lambda url: url.replace('http://', 'https://') if url is not None else None


ACCEPTED = 202


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
        try:
            user.giles_token.delete()
        except:
            pass
        user.giles_token = GilesToken.objects.create(for_user=user, token=data["token"])
        user.save()
        return user.giles_token.token
    except Exception as E:

        template = "Failed to retrieve access token for user {u}"
        msg = template.format(u=user.username)
        if kwargs.get('raise_exception', False):
            raise E
        logger.error(msg)
        logger.error(str(E))


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
def send_to_giles(username, file_name, public=True, **kwargs):
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
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', settings.POST)

    path = '/'.join([giles, 'rest', 'files', 'upload'])
    headers = _create_auth_header(user, **kwargs)
    headers.update({
        # 'Content-Type': 'multipart/form-data',
    })

    data = {'access': 'PUBLIC' if public else 'PRIVATE',}

    # POST request.
    files = {
        'files': (
            file_name,
              File(open(os.path.join(settings.MEDIA_ROOT, file_name.encode('utf-8')), 'rb')),
              'application/pdf'
          )
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

    Parameters
    ----------
    resource_id : int
        This :class:`.Resource` will be associated with the upload.
    content_relation_id : int
    username : str
    delete_on_complete : bool
        If True, the local file will be removed upon successful completion, and
        the content resource will be set to ``is_deleted=True``\.

    Returns
    -------
    int
        The pk-id of the :class:`.GilesUpload`\. No files will have been sent
        at this point -- a worker will add this upload to the queue, and update
        the record accordingly.
    """
    resource = Resource.objects.get(pk=resource_id)
    content_relation = ContentRelation.objects.get(pk=content_relation_id)
    content_resource = content_relation.content_resource
    user = User.objects.get(username=username)

    data = {
        'resource':resource,
        'file_path': content_resource.file.name,
        'state': GilesUpload.PENDING,
        'creator': user,
    }
    if delete_on_complete:
        data.update({
            'on_complete': jsonpickle.encode([
                ('Resource', content_resource.id, 'delete'),
                ('ContentRelation', content_relation_id, 'delete'),
            ])
        })
    upload = GilesUpload.objects.create(**data)
    return upload.id


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
        'container': parent_resource.container,
    })

    Relation.objects.create(**{
        'source': resource,
        'target': parent_resource,
        'predicate': __part__,
        'container': container,
    })
    return resource


def format_giles_url(url, username, dw=300):
    """
    Adds ``accessToken`` and ``dw`` parameters to ``url``.
    """
    import urllib, urlparse
    user = User.objects.get(username=username)
    parts = tuple(urlparse.urlparse(url))
    q = urlparse.parse_qs(parts[3])
    q.update({
        'accessToken': get_user_auth_token(user),
        'dw': dw,
    })
    parts[3] = urllib.urlencode(q)
    return urlparse.urlunparse(parts)


@api_request
@handle_status_exception
def check_upload_status(upload_id, username, **kwargs):
    """
    Poll Giles for the status of a POSTed upload.
    """
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    get = kwargs.get('get', settings.GET)
    checkURL = giles + '/rest/files/upload/%s' % upload_id
    return get(checkURL, headers=_create_auth_header(user, **kwargs))


def process_on_complete(on_complete):
    """
    Perform post-processing actions.

    Currently only supports ``'delete'`` action, which sets ``is_deleted`` and
    permanently deletes any attached files in the filesystem.

    Parameters
    ----------
    on_complete : list
        Should be a list of 3-tuples: ``(model, pk, action)``.
    """

    from cookies import models
    import os
    def _delete(obj):
        if obj.file and os.path.isfile(obj.file.path):
            os.remove(obj.file.path)
        obj.file = None
        obj.is_deleted = True
        obj.save()

    _actions = {'delete': _delete}
    for model, pk, action in on_complete:
        obj = getattr(models, model).objects.get(pk=pk)
        _actions.get(action, (lambda o: o))(obj)


def process_upload(upload_id, username):
    """
    Given a Giles upload id, attempt to retrieve file details and create
    local data structures (if ready).

    Transitions state from SENT to DONE, or (if there are exceptions) to
    GILES_ERROR, PROCESS_ERROR, or CALLBACK_ERROR.

    Parameters
    ----------
    upload_id : str
    username : str
    """
    import datetime

    user = User.objects.get(username=username)

    # The upload may or may not have originated in Amphora.
    _defaults = {'created_by': user, 'state': GilesUpload.SENT}
    upload, _created = GilesUpload.objects.get_or_create(upload_id=upload_id,
                                                         defaults=_defaults)
    if not _created and upload.created_by != user:
        raise RuntimeError('Only the creator of the GilesUpload can do this')

    try:
        upload.last_checked = datetime.datetime.now()
        code, data = check_upload_status(upload_id, username)
    except Exception as E:
        upload.message = str(E)
        upload.state = GilesUpload.GILES_ERROR
        upload.save()
        return

    if code == ACCEPTED:    # Giles is still processing the upload.
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
            process_on_complete(upload.on_complete)
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
    """
    upload = GilesUpload.objects.get(upload_id=upload_id)
    resource = upload.resource
    creator = User.objects.get(username=username)

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
        container = ResourceContainer.objects.create(primary=resource,
                                                     created_by=creator.id)
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


def send_giles_upload(upload_pk, username):
    """
    Send data for a pending :class:`.GilesUpload`\.

    If successfuly, transitions state from PENDING to SENT.

    If an exception is raised, transitions state from PENDING to SEND_ERROR.

    Parameters
    ----------
    upload_pk : int
    username : str
    """
    upload = GilesUpload.objects.get(pk=upload_pk)

    # This will trigger an actual upload, and we don't want to do it twice.
    if not upload.state == GilesUpload.PENDING:
        return

    # Resource should be public unless expressly forbidden.
    if upload.resource and not upload.resource.public:
        public = False
    else:
        public = True

    try:
        result = send_to_giles(content_resource.file.name, username, public=public)
    except Exception as E:
        upload.message = str(E)
        upload.state = GilesUpload.SEND_ERROR
        upload_save()
        return

    upload.upload_id = result.get('id')
    upload.state = GilesUpload.SENT
    upload.save()
