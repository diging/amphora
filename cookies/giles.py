from django.conf import settings
from django.core.files import File

from cookies.models import *

import requests, os
from collections import defaultdict

_fix_url = lambda url: url.replace('http://', 'https://') if url is not None else None


def _get_file_data(raw_data):
    files = {}
    for obj in raw_data:
        key = obj.get('documentId')

        files[key] = obj
    return files


def check_upload_status(creator, checkURL, giles=settings.GILES, get=settings.GET):
    response = get(checkURL + '?accessToken=' + creator.social_auth.get(provider='github').extra_data['access_token'])
    return response.status_code, response.json()


def process_file_upload(resource, creator, raw_data, session_id, giles=settings.GILES):
    session = GilesSession.objects.get(pk=session_id)

    file_details = _get_file_data(raw_data)
    session.file_ids = [o['uploadId'] for o in raw_data]
    session.file_details = file_details
    session.save()

    for document_id, file_data in session.file_details.iteritems():
        _process_document_data(session, file_data, creator, resource=resource, giles=giles)


def send_to_giles(file_name, creator, resource=None, public=True,
                  giles=settings.GILES, post=settings.POST):
    """

    Parameters
    ----------
    creator : :class:`.User`
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
    social = creator.social_auth.get(provider='github')

    path = '/'.join([giles, 'rest', 'files', 'upload']) + '?accessToken=' + social.extra_data['access_token']
    headers = {
        'content-type': 'multipart/form-data',
    }

    data = {    # Maybe someday we will send several files at once.
        'accessToken': social.extra_data['access_token'],
        'access': 'PUBLIC' if public else 'PRIVATE',
    }


    # TODO: Giles should respond with a token for each upload, which we should
    #  check periodically for completion (OCR takes longer than the Apache
    #  timeout).
    # return


    session = GilesSession.objects.create(created_by_id=creator.id)

    # POST request.
    files = {'files': (file_name, File(open(os.path.join(settings.MEDIA_ROOT, file_name), 'rb')), 'application/pdf')}
    response = post(path, files=files, data=data)

    if response.status_code != requests.codes.ok:
        raise RuntimeError('Call to giles failed with %i: %s' % \
                           (response.status_code, response.content))
    return response.status_code, response.json(), session


def _create_content_resource(parent_resource, resource_type, creator, uri, url, public=True, **meta):
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
    })

    Relation.objects.create(**{
        'source': resource,
        'target': parent_resource,
        'predicate': __part__,
    })
    return resource


def _process_document_data(session, data, creator, resource=None, giles=settings.GILES):

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
            })

    session.resources.add(resource)

    # Content resource for uploaded file.
    upload_data = data.get('uploadedFile')
    content_type = upload_data.get('content-type')
    resource_type = __text__ if content_type == 'application/pdf' else __image__
    resource_uri = '%s/files/%s' % (giles, upload_data.get('id'))
    session.content_resources.add(
        _create_content_resource(resource, resource_type, creator, resource_uri,
                                 _fix_url(upload_data.get('url')), public=public,
                                 content_type=content_type)
    )

    # Content resoruce for extracted text, if available.
    text_data = data.get('extractedText', None)
    if text_data is not None:
        text_content_type = text_data.get('content-type')
        text_uri = '%s/files/%s' % (giles, text_data.get('id'))
        session.content_resources.add(
            _create_content_resource(resource, __text__, creator, text_uri,
                                     _fix_url(text_data.get('url')), public=public,
                                     content_type=text_content_type)
        )

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
                                     creator, page_fmt_uri, _fix_url(fmt_data.get('url')),
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


def process_resources(user, session, giles=settings.GILES):
    """
    Once details have been retrieved concerning images uploaded to Giles, we
    need to create the appropriate metadata records (Resources). This function
    processes all of the file data associated with a :class:`.GilesSession`\,
    creating :class:`.Resource` instances and attendant :class:`.Relation`\s
    as needed.

    Parameters
    ----------
    user : :class:`.User`
    session : :class:`.GilesSession`

    Returns
    -------
    None
    """

    for document_id, file_data in session.file_details.iteritems():
        _process_document_data(session, file_data, user, giles=giles)


def handle_giles_callback(request, giles=settings.GILES, get=settings.GET):
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

    Returns
    -------
    :class:`.GilesSession`
        This is used to track the provenance of Giles images.
    """
    upload_ids = request.GET.getlist('uploadids') + request.GET.getlist('uploadIds')
    if not upload_ids:
        raise ValueError('No upload ids in request')


    session = GilesSession.objects.create(created_by_id=request.user.id)

    file_details = {}
    for uid in upload_ids:
        file_details.update(get_file_details(request.user, uid, giles=giles, get=get))

    session.file_ids = upload_ids
    session.file_details = file_details
    session.save()

    process_resources(request.user, session)
    return session


def get_file_details(user, upload_id, giles=settings.GILES, get=settings.GET):
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
    giles : str
        Location of the Giles REST endpoint.
    get : callable
        Function for executing an HTTP GET request. Must return an object with
        properties ``status_code`` and ``content``, and method ``json()``.

    Returns
    -------
    dict
        Giles image file details. Keys are ``documentId``s (generated by Giles),
        values are lists of dicts, each containing details about an image
        file in that document.
    """
    social = user.social_auth.get(provider='github')
    path = '/'.join([giles, 'rest', 'files', 'upload', upload_id])
    path += '?accessToken=' + social.extra_data['access_token']
    print path
    response = get(path)
    if response.status_code != requests.codes.ok:
        raise RuntimeError('Call to giles failed with %i: %s' % \
                           (response.status_code, response.content))

    return _get_file_data(response.json())
