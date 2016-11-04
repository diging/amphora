from __future__ import absolute_import

from django.conf import settings

from celery import shared_task, task

from cookies import content, giles, authorization, operations
from cookies.models import *
from concepts import authorities
from cookies.accession import IngesterFactory
from cookies.exceptions import *
logger = settings.LOGGER

import jsonpickle


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
def send_to_giles(file_name, creator, resource=None, public=True):
    result = giles.send_to_giles(creator, file_name, resource=resource,
                                 public=public)
    session = GilesSession.objects.create(created_by_id=creator.id)

    stat_sucode, response_data = result

    try:
        check_giles_upload.delay(resource, creator, response_data['id'],
                                 response_data['checkUrl'], session.id)
    except ConnectionError:
        logger.error("send_to_giles: there was an error connecting to"
                     " the redis message passing backend.")


@shared_task(max_retries=None, default_retry_delay=10)
def check_giles_upload(resource, creator, upload_id, checkURL, session_id):
    status, content = giles.check_upload_status(creator, checkURL)
    if status == 202:    # Accepted.
        logger.debug('Accepted, retrying in 30 seconds')
        raise check_giles_upload.retry()
    giles.process_file_upload(resource, creator, content, session_id)


@shared_task
def update_authorizations(auths, user, obj, by_user=None, propagate=True):
    authorization.update_authorizations(auths, user, obj, by_user=by_user,
                                        propagate=propagate)


@shared_task
def search_for_concept(lemma):
    authorities.searchall(lemma)
