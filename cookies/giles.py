from django.conf import settings

from cookies.models import *

import requests


def process_resources(request, session):
    for file_id, file_data in session.file_details.iteritems():
        files = file_data['files']
        page_field = Field.objects.get(uri='http://xmlns.com/foaf/0.1/page')
        part_type = Type.objects.get(uri='http://purl.org/net/biblio#Part')
        image_type = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Image')
        document_type = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')
        public = file_data['access'] != "PRIVATE"

        def _process_file_part(file_part, resource_type):
            # This is the page image.
            content_resource = Resource.objects.create(**{
                'name': file_part['filename'],
                'location': file_part['path'],
                'public': public,
                'content_resource': True,
                'created_by_id': request.user.id,
                'entity_type': resource_type,
                'content_type': file_part['content-type'],
            })
            session.content_resources.add(content_resource)
            # This is the page resource.
            resource = Resource.objects.create(**{
                'name': file_id,
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

        if len(files) == 1:
            resource = _process_file_part(files[0], image_type)
            session.resources.add(resource)

        elif len(files) > 1:
            master_resource = Resource.objects.create(**{
                'name': file_id,
                'public': public,
                'created_by_id': request.user.id,
                'content_resource': False,
                'entity_type': document_type
            })
            session.resources.add(master_resource)

            resources_set = {}
            for i, file_part in enumerate(files):
                resource = _process_file_part(file_part, part_type)

                # This resource is a page in the master resource.
                Relation.objects.create(**{
                    'source': master_resource,
                    'target': resource,
                    'predicate': page_field,
                })

            for i, resource in resources_set.items():
                if i < len(resources_set):
                    resource.next_page = resources_set[i + 1]
                    resource.save()



def handle_giles_callback(request, giles=settings.GILES, get=settings.GET_METHOD):
    upload_ids = request.GET.getlist('uploadids')
    if not upload_ids:
        raise ValueError('No upload ids in request')
    session = GilesSession.objects.create(created_by_id=request.user.id)

    file_details = {}
    for uid in upload_ids:
        file_details.update(get_file_details(uid, giles=giles, get=get))

    session.file_ids = upload_ids
    session.file_details = file_details
    session.save()

    process_resources(request, session)
    return session


def get_file_details(upload_id, giles=settings.GILES, get=settings.GET_METHOD):
    path = '/'.join([giles, 'rest', 'files', 'upload', upload_id])
    response = get(path)
    if response.status_code != requests.codes.ok:
        raise RuntimeError('Call to giles failed with %i: %s' % (response.status_code, response.content))

    files = {}
    for obj in response.json():
        key = obj.pop('documentId')
        files[key] = obj
        files[key]['files'] = [{
            'filename': o['filename'],
            'path': '?'.join(['/'.join([giles, 'rest', 'digilib']), o['path']]),
            'content-type': o['content-type']
        } for o in files[key]['files']]

    return files
