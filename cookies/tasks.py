from __future__ import absolute_import

from django.conf import settings

from celery import shared_task, task

from cookies import content, giles, authorization, operations
from cookies.models import *
from concepts import authorities
from cookies.accession import IngesterFactory
from cookies.exceptions import *
logger = settings.LOGGER

import jsonpickle, json, datetime


@shared_task
def handle_content(obj, commit=True):
    """
    Attempt to extract plain text from content files associated with a
    :class:`.Resource` instance.

    Parameters
    ----------
    obj : :class:`.Resource`
    commit : bool
    """
    return content.handle_content(obj, commit)


@task(name='jars.tasks.handle_bulk', bind=True)
def handle_bulk(self, file_path, form_data, file_name, job=None,
                ingester='cookies.accession.zotero.ZoteroIngest'):
    """
    Process resource data in a RDF document.

    Parameters
    ----------
    file_path : str
        Local path to a RDF document, or a ZIP file containing a Zotero RDF
        export (with files).
    form_data : dict
        Valid data from a :class:`cookies.forms.BulkResourceForm`\.
    file_name : str
        Name of the target file at ``file_path``\.
    job : :class:`.UserJob`
        Used to update progress.
    """
    if job:
        job.result_id = self.request.id
        job.save()

    logger.debug('handle bulk')
    creator = form_data.pop('created_by')

    # The user can either add these new records to an existing collection, or
    #  create a new one.
    collection = form_data.pop('collection', None)
    collection_name = form_data.pop('name', None)
    if not collection:
        collection = Collection.objects.create(**{
            'name': collection_name,
            'created_by': creator,
        })

    operations.add_creation_metadata(collection, creator)

    # User can indicate a default Type to assign to each new Resource.
    default_type = form_data.pop('default_type', None)
    ingester = IngesterFactory().get(ingester)(file_path)
    ingester.Resource = authorization.apply_filter(creator, 'change_resource', ingester.Resource)
    ingester.Collection = authorization.apply_filter(creator, 'change_collection', ingester.Collection)
    ingester.ConceptEntity = authorization.apply_filter(creator, 'change_conceptentity', ingester.ConceptEntity)
    ingester.set_resource_defaults(entity_type=default_type,
                                   created_by=creator, **form_data)

    N = len(ingester)
    for resource in ingester:
        collection.resources.add(resource)
        operations.add_creation_metadata(resource, creator)
        authorization.update_authorizations(Resource.DEFAULT_AUTHS, creator,
                                            resource, propagate=True)
        if job:
            job.progress += 1./N
            job.save()
    job.result = jsonpickle.encode({'view': 'collection', 'id': collection.id})
    job.save()

    return {'view': 'collection', 'id': collection.id}


@shared_task
def send_to_giles(file_name, creator, resource=None, public=True, gilesupload_id=None):
    upload = GilesUpload.objects.get(pk=gilesupload_id)

    # try:
    status_code, response_data = giles.send_to_giles(creator, file_name,
                                                     resource=resource,
                                                     public=public)
    # except:
        # logger.error("send_to_giles: failing permanently for %i" % upload.id)
        # upload.fail = True
        # upload.save()
        # return

    # session = GilesSession.objects.create(created_by_id=creator.id)

    upload.upload_id = response_data['id']
    upload.sent = datetime.datetime.now()
    upload.save()

    # try:
    #     check_giles_upload.delay(resource, creator, response_data['id'],
    #                              response_data['checkUrl'], session.id, gilesupload_id)
    # except ConnectionError:
    #     logger.error("send_to_giles: there was an error connecting to"
    #                  " the redis message passing backend.")



@shared_task
def check_giles_upload(resource, creator, upload_id, checkURL,
                       gilesupload_id):
    status, content = giles.check_upload_status(creator, checkURL)
    if status == 202:    # Accepted.
        logger.debug('Accepted, retrying in 30 seconds')
        return
        # raise check_giles_upload.retry()

    giles.process_file_upload(resource, creator, content)

    upload = GilesUpload.objects.get(pk=gilesupload_id)
    upload.response = json.dumps(content)
    upload.resolved = True
    upload.save()



@shared_task
def update_authorizations(auths, user, obj, by_user=None, propagate=True):
    authorization.update_authorizations(auths, user, obj, by_user=by_user,
                                        propagate=propagate)


@shared_task
def search_for_concept(lemma):
    authorities.searchall(lemma)


@shared_task
def check_giles_uploads():
    checkURL = lambda u: '%s/rest/files/upload/check/%s' % (settings.GILES, u.upload_id)
    query = Q(resolved=False) & ~Q(sent=None) & Q(fail=False)
    outstanding = GilesUpload.objects.filter(query)
    for upload in outstanding:
        resource = upload.content_resource.parent.first().for_resource
        status, content = giles.check_upload_status(resource.created_by, checkURL(upload))
        if status == 202:    # Accepted.
            continue
            # raise check_giles_upload.retry()

        gl = [cr for cr in resource.content.all() if cr.content_resource.external_source == Resource.GILES]
        if len(gl) > 0:
            continue
            
        giles.process_file_upload(resource, resource.created_by, content)

        upload.response = json.dumps(content)
        upload.resolved = True
        upload.save()

        # check_giles_upload(resource, , upload.id, , upload.id)


@shared_task
def send_giles_uploads():
    """
    Check for outstanding :class:`.GilesUpload`\s, and send as able.
    """
    logger.debug('Checking for outstanding GilesUploads')
    query = Q(resolved=False) & ~Q(sent=None) & Q(fail=False)
    outstanding = GilesUpload.objects.filter(query)
    pending = GilesUpload.objects.filter(resolved=False, sent=None, fail=False)

    # We limit the number of simultaneous requests to Giles.
    if outstanding.count() >= settings.MAX_GILES_UPLOADS or pending.count() == 0:
        return

    logger.debug('Found GilesUpload, processing...')

    to_upload = min(settings.MAX_GILES_UPLOADS - outstanding.count(), pending.count())
    if to_upload <= 0:
        return

    for upload in pending[:to_upload]:
        content_resource = upload.content_resource
        creator = content_resource.created_by
        resource = content_resource.parent.first().for_resource

        anonymous, _ = User.objects.get_or_create(username='AnonymousUser')
        public = authorization.check_authorization('view', anonymous, content_resource)
        result = send_to_giles(content_resource.file.name, creator,
                               resource=resource, public=public,
                               gilesupload_id=upload.id)


# session = GilesSession.objects.create(created_by_id=creator.id)
#
# stat_sucode, response_data = result
#
# try:
#     check_giles_upload.delay(resource, creator, response_data['id'],
#                              response_data['checkUrl'], session.id)
# except ConnectionError:
#     logger.error("send_to_giles: there was an error connecting to"
#                  " the redis message passing backend.")
