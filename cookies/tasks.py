from __future__ import absolute_import

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from celery import shared_task, task

from cookies import content, giles, authorization, operations
from cookies.models import *
from concepts import authorities
from cookies.accession import IngesterFactory
from cookies.exceptions import *



logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)

import jsonpickle, json
from datetime import timedelta


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
    public_policy = False
    if not collection:
        collection = Collection.objects.create(**{
            'name': collection_name,
            'created_by': creator,
        })
        if form_data.get('public'):
            #  Create an authoirzation for AnonymousUser.
            CollectionAuthorization.objects.create(granted_by=creator,
                                                   granted_to=None,
                                                   for_resource=collection,
                                                   policy=CollectionAuthorization.ALLOW,
                                                   action=CollectionAuthorization.VIEW)
            public_policy = True

    operations.add_creation_metadata(collection, creator)

    # User can indicate a default Type to assign to each new Resource.
    default_type = form_data.pop('default_type', None)
    upload_resource = Resource.objects.create(
        created_by=creator,
        name=file_name,
    )
    with open(file_path, 'r') as f:
        upload_resource.file.save(file_name, File(f), True)

    ingester = IngesterFactory().get(ingester)(upload_resource.file.path)
    ingester.Resource = authorization.apply_filter(ResourceAuthorization.EDIT, creator, ingester.Resource)
    ingester.Collection = authorization.apply_filter(ResourceAuthorization.EDIT, creator, ingester.Collection)
    ingester.ConceptEntity = authorization.apply_filter(ResourceAuthorization.EDIT, creator, ingester.ConceptEntity)
    ingester.set_resource_defaults(entity_type=default_type,
                                   collection=collection,
                                   created_by=creator, **form_data)

    N = len(ingester)
    for resource in ingester:
        resource.container.part_of = collection
        if form_data.get('public') and not public_policy:
            ResourceAuthorization.objects.create(granted_by=creator,
                                                 granted_to=None,
                                                 for_resource=resource.container,
                                                 policy=ResourceAuthorization.ALLOW,
                                                 action=ResourceAuthorization.VIEW)
        resource.container.save()
        # collection.resources.add(resource)
        operations.add_creation_metadata(resource, creator)

        if job:
            job.progress += 1./N
            job.save()
    job.result = jsonpickle.encode({'view': 'collection', 'id': collection.id})
    job.save()

    return {'view': 'collection', 'id': collection.id}


@shared_task(rate_limit="6/m")
def send_to_giles(upload_pk, created_by):
    logger.debug('send upload %i for user %s' % (upload_pk, username))
    giles.send_giles_upload(upload_pk, created_by)


@shared_task(rate_limit="1/s")
def check_giles_upload(upload_id, username):
    logger.debug('check_giles_upload %s for user %s' % (upload_id, username))
    return giles.process_upload(upload_id, username)


@shared_task
def search_for_concept(lemma):
    authorities.searchall(lemma)


@shared_task
def check_giles_uploads():
    """
    Periodic task that reviews currently outstanding Giles uploads, and checks
    their status.
    """

    outstanding = GilesUpload.objects.filter(state__in=GilesUpload.OUTSTANDING)
    pending = GilesUpload.objects.filter(state=GilesUpload.PENDING)

    # We limit the number of simultaneous requests to Giles.
    remaining = settings.MAX_GILES_UPLOADS - outstanding.count()
    logger.debug("there are %i GilesUploads pending and %i outstanding, with %i"
                 " remaining to be enqueued" %\
                 (pending.count(), outstanding.count(), remaining))
    if remaining <= 0 or pending.count() == 0:
        return

    _e = 0
    for upload in pending[:remaining]:
        send_to_giles.delay(upload.id, upload.created_by)
        upload.state = GilesUpload.ENQUEUED
        upload.save()
        _e += 1
    logger.debug('enqueued %i uploads to send' % _e)

    q = Q(last_checked__gte=timezone.now() - timedelta(seconds=300)) | Q(last_checked=None)#.filter(q)

    # for upload_id, username in qs.order_by('updated').values_list('upload_id', 'created_by__username')[:500]:
    qs = GilesUpload.objects.filter(state=GilesUpload.SENT)
    _u = 0
    for upload in qs.order_by('updated')[:100]:
        upload.state = GilesUpload.ASSIGNED
        upload.save()
        check_giles_upload.delay(upload.upload_id, upload.created_by.username)
        _u += 1
    logger.debug('assigned %i uploads to check' % _u)
