from django.conf import settings

from cookies.models import *

import requests


def process_resources(request, session, giles=settings.GILES):
    """
    Once details have been retrieved concerning images uploaded to Giles, we
    need to create the appropriate metadata records (Resources). This function
    processes all of the file data associated with a :class:`.GilesSession`\,
    creating :class:`.Resource` instances and attendant :class:`.Relation`\s
    as needed.

    Parameters
    ----------
    request
    session : :class:`.GilesSession`

    Returns
    -------
    None
    """

    for document_id, file_data in session.file_details.iteritems():
        document_uri = '/'.join([giles, 'rest', 'files', document_id, 'content'])

        if Resource.objects.filter(uri=document_uri).count() > 0:
            continue

        files = file_data['files']
        page_field = Field.objects.get(uri='http://xmlns.com/foaf/0.1/page')
        part_type = Type.objects.get(uri='http://purl.org/net/biblio#Part')
        image_type = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Image')
        document_type = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')
        public = file_data['access'] != "PRIVATE"

        def _process_file_part(file_part, resource_type):
            """
            Creates appropriate :class:`.Resource`\s and
            :class:`.ContentRelation` for a single image file.

            A :class:`.Resource` with ``content_resource == True`` is created
            for the (remote) image file itself, and a "master"
            :class:`.Resource` for the document that the image represents (e.g.
            a page, photograph, etc) is also created. It is the "master"
            resource that is returned.

            Parameters
            ----------
            file_part : dict
            resource_type : :class:`.Type`

            Returns
            -------
            :class:`.Resource`
            """

            uri = '/'.join([giles, 'rest', 'files', file_part['id'], 'content'])

            # This is the page image.
            content_resource = Resource.objects.create(**{
                'name': file_part['filename'],
                'location': file_part['path'],
                'public': public,
                'content_resource': True,
                'created_by_id': request.user.id,
                'entity_type': resource_type,
                'content_type': file_part['content-type'],
                'uri': uri
            })
            session.content_resources.add(content_resource)

            # This is the page resource.
            resource = Resource.objects.create(**{
                'name': document_id,
                'created_by_id': request.user.id,
                'entity_type': resource_type,
                'public': public,
                'content_resource': False,
            })
            # The page image is the content for the page resource.
            ContentRelation.objects.create(**{
                'for_resource': resource,
                'content_resource': content_resource,
                'content_type': file_part['content-type'],
            })
            return resource

        # There is only one image in this document.
        if len(files) == 1:
            resource = _process_file_part(files[0], image_type)
            session.resources.add(resource)

        # There are several pages in this document.
        elif len(files) > 1:
            # This ``master_resource`` represents the document itself.
            master_resource = Resource.objects.create(**{
                'name': document_id,
                'public': public,
                'created_by_id': request.user.id,
                'content_resource': False,
                'entity_type': document_type
            })
            session.resources.add(master_resource)

            content_resource = Resource.objects.create(**{
                'name': document_id + ' content',
                'public': public,
                'created_by_id': request.user.id,
                'content_resource': True,
                'entity_type': document_type,
                'uri': document_uri,
            })

            ContentRelation.objects.create(**{
                'for_resource': master_resource,
                'content_resource': content_resource,
                'content_type': 'multipart/mixed',
            })

            resources_set = {}
            for i, file_part in enumerate(files):
                # This resource is a page in the master resource.
                resource = _process_file_part(file_part, part_type)

                Relation.objects.create(**{
                    'source': master_resource,
                    'target': resource,
                    'predicate': page_field,
                })

            # Interlink page resources using the ``next_page`` (and
            #  ``previous_page``) relations.
            for i, resource in resources_set.items():
                if i < len(resources_set):
                    resource.next_page = resources_set[i + 1]
                    resource.save()


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
        file_details.update(get_file_details(request, uid, giles=giles, get=get))

    session.file_ids = upload_ids
    session.file_details = file_details
    session.save()

    process_resources(request, session)
    return session


def get_file_details(request, upload_id, giles=settings.GILES, get=settings.GET):
    """
    Calls Giles back with ``uploadIds`` observed in
    :func:`.handle_giles_callback`\, and retrieves details about images that
    the user has uploaded to Giles.

    Parameters
    ----------
    request
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
    social = request.user.social_auth.get(provider='github')
    path = '/'.join([giles, 'rest', 'files', 'upload', upload_id])
    path += '?accessToken=' + social.extra_data['access_token']
    response = get(path)
    if response.status_code != requests.codes.ok:
        raise RuntimeError('Call to giles failed with %i: %s' % \
                           (response.status_code, response.content))

    files = {}
    for obj in response.json():
        key = obj.pop('documentId')

        files[key] = obj
        files[key]['files'] = [{
            'filename': o['filename'],
            'path': o['path'],
            'content-type': o['content-type'],
            'id': o['id'],
        } for o in files[key]['files']]

    return files
