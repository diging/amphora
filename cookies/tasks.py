from __future__ import absolute_import

from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone
from django.utils.text import slugify

from cookies import aggregate
from cookies.filters import ResourceContainerFilter


from celery import shared_task, task

from cookies import content, giles, authorization, operations
from cookies.models import *
from concepts import authorities
from cookies.accession import IngesterFactory
from cookies.exceptions import *


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)

import jsonpickle, json, os
from datetime import timedelta, datetime

# Celery priorities need to be 0-9, 9 being the highest and 0 being the lowest.
CELERY_PRIORITY_HIGH = 8
CELERY_PRIORITY_MEDIUM = 5
CELERY_PRIORITY_LOW = 2

GILESUPLOAD_CELERY_PRIORITY_MAP = {
    GilesUpload.PRIORITY_HIGH: CELERY_PRIORITY_HIGH,
    GilesUpload.PRIORITY_MEDIUM: CELERY_PRIORITY_MEDIUM,
    GilesUpload.PRIORITY_LOW: CELERY_PRIORITY_LOW,
}

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
        operations.add_creation_metadata(collection, creator)
        if form_data.get('public'):
            #  Create an authoirzation for AnonymousUser.
            CollectionAuthorization.objects.create(granted_by=creator,
                                                   granted_to=None,
                                                   for_resource=collection,
                                                   policy=CollectionAuthorization.ALLOW,
                                                   action=CollectionAuthorization.VIEW)
            public_policy = True


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
    ingester.set_collection(collection)

    N = len(ingester)
    resource_auths = []
    for resource in ingester:
        resource.container.part_of = collection
        if form_data.get('public') and not public_policy:
            resource_auths.append(
                ResourceAuthorization(granted_by=creator,
                                      granted_to=None,
                                      for_resource=resource.container,
                                      policy=ResourceAuthorization.ALLOW,
                                      action=ResourceAuthorization.VIEW)
            )
        resource.container.save()
        # collection.resources.add(resource)
        operations.add_creation_metadata(resource, creator)

        if job:
            job.progress += 1./N
            job.save()
    ResourceAuthorization.objects.bulk_create(resource_auths)
    job.result = jsonpickle.encode({'view': 'collection', 'id': collection.id})
    job.save()

    return {'view': 'collection', 'id': collection.id}


@shared_task(rate_limit="15/m")
def send_to_giles(upload_pk, created_by):
    logger.debug('send upload %i for user %s' % (upload_pk, created_by))
    try:
        giles.send_giles_upload(upload_pk, created_by)
    except Exception as e:
        GilesUpload.objects.filter(pk=upload_pk).update(state=GilesUpload.SEND_ERROR, message=str(e))


@shared_task(rate_limit="2/s")
def check_giles_upload(upload_id, username):
    logger.debug('check_giles_upload %s for user %s' % (upload_id, username))
    try:
        return giles.process_upload(upload_id, username)
    except Exception as e:
        GilesUpload.objects.filter(upload_id=upload_id).update(state=GilesUpload.GILES_ERROR, message=str(e))


@shared_task
def search_for_concept(lemma):
    authorities.searchall(lemma)


@shared_task
def check_giles_uploads():
    """
    Periodic task that reviews currently outstanding Giles uploads, and checks
    their status.
    """

    # for upload_id, username in qs.order_by('updated').values_list('upload_id', 'created_by__username')[:500]:
    qs = GilesUpload.objects.filter(state=GilesUpload.SENT)
    _u = 0
    for upload in qs.order_by('updated')[:100]:
        upload.state = GilesUpload.ASSIGNED
        upload.save()
        check_giles_upload.delay(upload.upload_id, upload.created_by.username)
        _u += 1
    logger.debug('assigned %i uploads to check' % _u)

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
    for upload in pending.order_by('priority')[:remaining]:
        priority = GILESUPLOAD_CELERY_PRIORITY_MAP.get(upload.priority, CELERY_PRIORITY_LOW)
        # FIXME: Celery's support for 'priority' on Redis backend isn't clear.
        # Revisit after https://github.com/celery/celery/issues/4028 is
        # resolved and Amphora's celery version is updated.
        send_to_giles.apply_async(args=(upload.id, upload.created_by),
                                  kwargs={},
                                  priority=priority)
        upload.state = GilesUpload.ENQUEUED
        upload.save()
        _e += 1
    logger.debug('enqueued %i uploads to send' % _e)


    q = Q(last_checked__gte=timezone.now() - timedelta(seconds=300)) | Q(last_checked=None)#.filter(q)


@task(name='jars.tasks.create_snapshot_async', bind=True)
def create_snapshot_async(self, dataset_id, snapshot_id, export_structure, job=None):
    if job:
        job.result_id = self.request.id
        job.save()

    logging.debug('tasks.create_snapshot_async with dataset %i and snapshot %i' % (dataset_id, snapshot_id))
    dataset = Dataset.objects.get(pk=dataset_id)
    snapshot = DatasetSnapshot.objects.get(pk=snapshot_id)

    if dataset.dataset_type == Dataset.EXPLICIT:
        queryset = dataset.resources.all()
    else:
        params = QueryDict(dataset.filter_parameters)

        queryset = authorization.apply_filter(ResourceAuthorization.VIEW,
                                     dataset.created_by,
                                     ResourceContainer.active.all())
        queryset = ResourceContainerFilter(params, queryset=queryset).qs

    # Only include records that the __current__ user has permission to view.
    queryset = authorization.apply_filter(ResourceAuthorization.VIEW,
                                          snapshot.created_by, queryset)

    snapshot.state = DatasetSnapshot.IN_PROGRESS
    snapshot.save()

    methods = {
        'flat': aggregate.export_zip,
        'collection': aggregate.export_with_collection_structure,
        'parts': aggregate.export_with_resource_structure,
    }

    with transaction.atomic():
        now = timezone.now().strftime('%Y-%m-%d-%H-%m-%s')
        fname = 'dataset-%s-%s.zip' % (slugify(dataset.name), now)
        target_path = os.path.join(settings.MEDIA_ROOT, 'upload', fname)
        methods[export_structure]((obj.primary for obj in queryset if obj.primary), target_path, content_type=snapshot.content_type.split(','))

        container = ResourceContainer.objects.create(created_by=snapshot.created_by)
        resource = Resource.objects.create(
            name = 'Snapshot for dataset %s, %s' % (dataset.name, now),
            created_by = snapshot.created_by,
            container = container,
            entity_type = Type.objects.get_or_create(uri='http://dbpedia.org/ontology/File')[0],
        )
        container.primary = resource
        container.save()
        content = Resource.objects.create(
            name = 'Snapshot for dataset %s, %s' % (dataset.name, now),
            content_resource = True,
            entity_type = Type.objects.get_or_create(uri='http://dbpedia.org/ontology/File')[0],
            created_by = snapshot.created_by,
            container = container,
            content_type = 'application/zip'
        )
        ContentRelation.objects.create(
            for_resource = resource,
            content_resource = content,
            content_type = 'application/zip',
            created_by = snapshot.created_by,
            container = container
        )
        logging.debug('tasks.create_snapshot_async: export to %s' % (target_path))
        with open(target_path, 'r') as f:
            archive = File(f)
            content.file = archive
            content.save()
        logging.debug('tasks.create_snapshot_async: export complete')
        snapshot.resource = resource
        snapshot.state = DatasetSnapshot.DONE
        snapshot.save()
    job.result = jsonpickle.encode({'view': 'resource', 'id': resource.id})
    job.save()
