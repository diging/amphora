"""
This module provides content aggregation functionality for resources in
Amphora.

The primary use-case goes something like: a user performs a search, or
otherwise specifies a set of resources using filter parameters. The user then
wishes to download all of the content (optionally, of a specific content type)
associated with those resources.

An alternative scenario might be that the user wants to archive and store the
content on the server rather than download it directly. We may want to implement
this as part of the primary workflow in any case.

We should do this in a way that allows us to swap out the content servicing
later on, e.g. if we decide to use S3 to serve large downloads.

For performance sake, we should take full advantage of the content cache.
"""

from django.db.models import Q
from django.conf import settings
from django.core.cache import caches
from django.utils import timezone
from itertools import chain
from cookies.accession import get_remote
import smart_open, zipfile, logging, cStringIO, mimetypes
import os, urlparse, mimetypes
import unicodecsv as csv

from django.utils.text import slugify
from cookies.models import Resource, Value

cache = caches['remote_content']

logger = settings.LOGGER

METADATA_CSV_HEADER = [
    'resource_name',
    'resource_uri',
    'resource_type',
    'resource_type_uri',
    'collection_name',
    'collection_uri',
    'creator_name',
    'creator_id',
    'date_created',
    'predicate',
    'predicate_uri',
    'target',
    'target_uri',
]

CONTENT_TYPE_EXTENSIONS = {
    'text/plain'      : '.txt',
    'text/csv'        : '.csv',
    'image/tiff'      : '.tiff',
    'application/pdf' : '.pdf',
}

def get_filename(resource):
    if resource.is_external:
        if resource.name:
            filename = resource.name
        else:
            filename = urlparse.urlparse(resource.location).path.split('/')[-1]

        ext = CONTENT_TYPE_EXTENSIONS.get(resource.content_type,
                                          mimetypes.guess_extension(resource.content_type))
        return slugify(filename) + ext
    else:
        return os.path.basename(resource.file.path)

def get_content(content_resource):
    """
    Retrieve the raw content for a content resource.
    """
    logger.debug('aggregate.get_content for %i' % content_resource.id)
    if content_resource.is_external:
        content = cache.get(content_resource.location)
        if content is None:
            remote = get_remote(content_resource.external_source,
                                content_resource.created_by)
            try:
                content = remote.get(content_resource.location)
                if content is not None:
                    cache.set(content_resource.location, content, None)
            except Exception as E:
                content = E
                logger.debug('encounted exception while exporting %s: %s' % (str(content_resource), E.message))
        return content
    elif content_resource.file:
        with open(content_resource.file.path) as f:
            return f.read()
    return

def write_metadata_csv(filehandle, resource=None, write_header=False):
    writer = csv.writer(filehandle)

    if write_header:
        writer.writerow(METADATA_CSV_HEADER)

    if not resource:
        return

    for relation in resource.relations_from.all():
        row = {
            'resource_name'     : resource.name,
            'resource_uri'      : resource.uri,
            'resource_type'     : str(resource.entity_type),
            'resource_type_uri' : resource.entity_type.uri,
            'collection_name'   : resource.container.part_of.name,
            'collection_uri'    : resource.container.part_of.uri,
            'creator_name'      : resource.created_by.username,
            'creator_id'        : resource.created_by_id,
            'date_created'      : resource.created.isoformat(),
            'predicate'         : str(relation.predicate),
            'predicate_uri'     : relation.predicate.uri,
            'target'            : getattr(relation.target, "name", None),
            'target_uri'        : None
        }
        if relation.target and not isinstance(relation.target, Value):
            row['target_uri'] = relation.target.uri

        writer.writerow([row[c] for c in METADATA_CSV_HEADER])


def aggregate_content_resources_fast(container, content_type=None, part_uri='http://purl.org/dc/terms/isPartOf'):
    return Resource.objects.filter(content_resource=True, container=container).order_by('parent__for_resource__relations_from_resource__sort_order')



def aggregate_content_resources(queryset, content_type=None,
                                part_uri='http://purl.org/dc/terms/isPartOf'):
    """
    Given a queryset of :class:`cookies.models.Resource` instances, return a
    generator that yields associated :class:`cookies.models.ContentResource`
    instances.
    """
    from cookies.models import Resource
    logger.debug('aggregate_content_resources:: with content type %s' % str(content_type))
    # TODO: Ok, this was a nice little excercise with generators. But since we
    #  already have content encapsulated with their uber-parent's container,
    #  can we leverage that relation to cut down on database calls? This may not
    #  matter so long as the rate-limiting factor is content-retrieval.
    queryset = iter(queryset)
    current = None
    current_parts = None
    current_content = None
    q = Q(predicate__uri=part_uri)
    content_q = Q(content_resource=True)
    content_q |= Q(content_resource__content_resource=True)
    if content_type is not None and '__all__' not in content_type:
        if not type(content_type) is list:
            content_type = [content_type]

        content_type_q = None
        for ctype in content_type:
            if not content_type_q:
                content_type_q = Q(content_type=ctype)
            else:
                content_type_q |= Q(content_type=ctype)
            content_type_q |= Q(content_resource__content_type=ctype)

        content_q &= content_type_q

    def get_parts(resource):
        return (o for rel in resource.relations_to.filter(q).order_by('sort_order')
                    for o in chain((crel.content_resource for crel
                                    in rel.source.content.filter(content_q)),
                                   get_parts(rel.source)))

    while True:
        if current is None:
            try:
                current = queryset.next()
                for crel in current.content.filter(content_q & Q(is_deleted=False)):
                    yield crel.content_resource
                current_content = get_parts(current)

            except StopIteration:
                break
        try:
            this = current_content.next()
        except StopIteration:
            current = None
            continue
        logging.debug('aggregate.aggregate_content_resources: current %s' % str(current))
        yield this


def aggregate_content(queryset, proc=lambda content, rsrc: content, **kwargs):
    """
    Given a collection of :class:`cookies.models.Resource` instances, return a
    generator that yields raw content.

    Parameters
    ----------
    queryset : iterable
        Should yield :class:`cookies.models.Resource` instances. This could be
        a :class:`django.db.models.QuerySet`\, or something else.
    proc : callable
        If passed, will be called with the raw content of each content resource
        and the content resource itself. Whatever this function returns will be
        returned instead of the raw content.
    kwargs : kwargs
        Passed to :func:`.aggregate_content_resources`\.

    Returns
    -------
    generator
        Yields raw content (or whathever ``proc`` returns), one content resource
        at a time.
    """
    aggregator = aggregate_content_resources(queryset, **kwargs)
    return (proc(get_content(resource), resource) for resource in aggregator)

def aggregate_part_resources(queryset):
    part_uri = 'http://purl.org/dc/terms/isPartOf'
    for resource in queryset:
        yield resource
        for part_rel in resource.relations_to.filter(predicate__uri=part_uri):
            yield part_rel.source

def export(queryset, target_path, fname=get_filename, **kwargs):
    """
    Stream content to files (or something).

    See https://github.com/RaRe-Technologies/smart_open for more on smart_open.
    """
    if not target_path.endswith('/'):
        target_path += '/'

    proc = kwargs.pop('proc', lambda content, resource: content)
    export_proc = lambda content, resource: (content, resource)
    aggregator = aggregate_content(queryset, proc=export_proc, **kwargs)

    for content, resource in aggregator:
        file_path = target_path + fname(resource)
        with smart_open.smart_open(file_path, 'wb') as f:
            f.write(proc(content, resource))


def manifest(log):
    return "Bulk export from Amphora\n\n" + \
           "Process Log\n----------{}\n\n".format('\n'.join(log)) + \
           "Finished at at %s" % timezone.now().strftime('%Y-%m-%d at %H:%m:%s')


def export_zip(queryset, target_path, fname=get_filename, **kwargs):
    """
    Stream content into a zip archive at ``target_path``.
    """
    logger.debug('aggregate.export_zip: target: %s' % (target_path))
    if not target_path.endswith('.zip'):
        target_path += '.zip'

    has_metadata = kwargs.pop('has_metadata', False)
    proc = kwargs.pop('proc', lambda content, resource: content)
    export_proc = lambda content, resource: (content, resource)
    base = 'amphora/'
    log = []
    index = cStringIO.StringIO()
    metadata = cStringIO.StringIO()
    index_writer = csv.writer(index)
    index_writer.writerow(['ID', 'Name', 'PrimaryID', 'PrimaryURI', 'PrimaryName', 'Location'])

    # Write header only
    write_metadata_csv(metadata, resource=None, write_header=True)

    files_in_zip = set()
    with zipfile.ZipFile(target_path, 'w', allowZip64=True) as target:
        for queryset_resource in queryset:
            for content, resource in aggregate_content([queryset_resource], proc=export_proc, **kwargs):
                if content is None:
                    log.append('No content for resource %i (%s)' % (resource.id, resource.name))
                elif isinstance(content, Exception):
                    log.append('Encountered exception while retrieving content for %i (%s): %s' % (resource.id, resource.name, content.message))
                else:
                    filepath = fname(resource)
                    if filepath in files_in_zip:
                        filename, ext = os.path.splitext(os.path.basename(filepath))
                        filepath = os.path.join(os.path.dirname(filepath),
                                                '{}_{}{}'.format(filename,
                                                                 resource.id,
                                                                 ext))
                    files_in_zip.add(filepath)
                    target.writestr(base + filepath, content)
                    index_writer.writerow([resource.id, resource.name,
                                           resource.container.primary.id,
                                           resource.container.primary.uri,
                                           resource.container.primary.name,
                                           filepath])

            if has_metadata:
                for resource in aggregate_part_resources([queryset_resource]):
                    write_metadata_csv(metadata, resource, write_header=False)

        target.writestr(base + 'MANIFEST.txt', manifest(log))
        target.writestr(base + 'index.csv', index.getvalue())
        if has_metadata:
            target.writestr(base + 'metadata.csv', metadata.getvalue())

        metadata.close()
        index.close()
    return target_path


def export_with_collection_structure(queryset, target_path, **kwargs):
    """
    Convenience method for exporting a ZIP archive of records that preserves
    collection structure. Collection names are used to build file paths within
    the archive.
    """
    import os, urlparse
    def recursive_filename(resource):
        def get_collection_name(collection):
            if collection is None:
                return ''
            return os.path.join(get_collection_name(collection.part_of),
                                collection.name)

        return os.path.join(get_collection_name(resource.container.part_of),
                            get_filename(resource))

    return export_zip(queryset, target_path, fname=recursive_filename, **kwargs)


def export_with_resource_structure(queryset, target_path, **kwargs):
    """
    Convenience method for exporting a ZIP archive of records that preserves
    resource structure. Resource relations are used to build file paths within
    the archive.
    """

    def recursive_filename(resource):
        def get_parent_resource(collection):
            if resource is None:
                return ''
            part_of = resource.relations_from.filter(predicate__uri='http://purl.org/dc/terms/isPartOf').first()
            if part_of:
                return get_parent_resource(part_of.target) + '/' + str(resource.id)
            return str(resource.id)

        filename = get_filename(resource)

        name = get_parent_resource(resource) + '/' + filename
        if name.startswith('/'):
            name = name[1:]
        return name
    return export_zip(queryset, target_path, fname=recursive_filename, **kwargs)

def export_metadata(queryset, target_path):
    """
    Stream metadata into a zip archive at ``target_path``.
    """
    logger.debug('aggregate.export_metadata: target: %s' % (target_path))
    if not target_path.endswith('.zip'):
        target_path += '.zip'

    aggregator = aggregate_part_resources(queryset)

    base = 'amphora/'
    log = []
    metadata = cStringIO.StringIO()
    with zipfile.ZipFile(target_path, 'w', allowZip64=True) as target:
        write_metadata_csv(metadata, aggregator.next(), write_header=True)
        for resource in aggregator:
            write_metadata_csv(metadata, resource, write_header=False)
        target.writestr(base + 'metadata.csv', metadata.getvalue())
        metadata.close()
    return target_path
