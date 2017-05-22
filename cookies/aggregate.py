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
import smart_open, zipfile, logging, cStringIO
import unicodecsv as csv

cache = caches['remote_content']

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)



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


def aggregate_content_resources(queryset, content_type=None,
                                part_uri='http://purl.org/dc/terms/isPartOf'):
    """
    Given a queryset of :class:`cookies.models.Resource` instances, return a
    generator that yields associated :class:`cookies.models.ContentResource`
    instances.
    """
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
    if content_type is not None and '__all__' not in content_type:
        if not type(content_type) is list:
            content_type = [content_type]

        content_q = Q(content_type=content_type[0])
        content_q |= Q(content_resource__content_type=content_type[0])
        if len(content_type) > 1:
            for ctype in content_type[1:]:
                content_q |= Q(content_type=ctype)
                content_q |= Q(content_resource__content_type=ctype)

    def get_parts(resource):
        return chain((rel.source for rel in resource.relations_to.filter(q)),
                     *[get_parts(rel.source) for rel in resource.relations_to.filter(q)])

    def get_content(resource):
        qs = resource.content.all()
        if content_type is not None and '__all__' not in content_type:
            qs = qs.filter(content_q)
        return (rel.content_resource for rel in qs)

    while True:
        if current is None:
            try:
                current = queryset.next()
                current_parts = chain([current], get_parts(current))
                current_content = chain(*[get_content(part) for part in current_parts])
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


def export(queryset, target_path, fname=lambda r: '%i.txt' % r.id, **kwargs):
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


def export_zip(queryset, target_path, fname=lambda r: '%i.txt' % r.id, **kwargs):
    """
    Stream content into a zip archive at ``target_path``.
    """
    logger.debug('aggregate.export_zip: target: %s' % (target_path))
    if not target_path.endswith('.zip'):
        target_path += '.zip'

    proc = kwargs.pop('proc', lambda content, resource: content)
    export_proc = lambda content, resource: (content, resource)
    aggregator = aggregate_content(queryset, proc=export_proc, **kwargs)
    base = 'amphora/'
    log = []
    index = cStringIO.StringIO()
    index_writer = csv.writer(index)
    index_writer.writerow(['ID', 'Name', 'PrimaryID', 'PrimaryURI', 'PrimaryName', 'Location'])
    with zipfile.ZipFile(target_path, 'w') as target:
        for content, resource in aggregator:
            if content is None:
                log.append('No content for resource %i (%s)' % (resource.id, resource.name))
            elif isinstance(content, Exception):
                log.append('Encountered exception while retrieving content for %i (%s): %s' % (resource.id, resource.name, content.message))
            else:
                filename = fname(resource)
                index_writer.writerow([resource.id, resource.name, resource.container.primary.id, resource.container.primary.uri, resource.container.primary.name, filename])
                target.writestr(base + filename, content)
        target.writestr(base + 'MANIFEST.txt', manifest(log))
        target.writestr(base + 'index.csv', index.getvalue())
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
            return get_collection_name(collection.part_of) + '/' + collection.name
        if resource.is_external:
            filename = urlparse.urlparse(resource.location).path.split('/')[-1]
        else:
            filename = os.path.split(resource.file.path)[-1]
        name = get_collection_name(resource.container.part_of) + '/' + filename
        if name.startswith('/'):
            name = name[1:]
        return name
    return export_zip(queryset, target_path, fname=recursive_filename, **kwargs)


def export_with_resource_structure(queryset, target_path, **kwargs):
    """
    Convenience method for exporting a ZIP archive of records that preserves
    resource structure. Resource relations are used to build file paths within
    the archive.
    """
    import os, urlparse, mimetypes
    def recursive_filename(resource):
        def get_parent_resource(collection):
            if resource is None:
                return ''
            part_of = resource.relations_from.filter(predicate__uri='http://purl.org/dc/terms/isPartOf').first()
            if part_of:
                return get_parent_resource(part_of.target) + '/' + str(resource.id)
            return str(resource.id)

        if resource.is_external:
            if resource.name:
                filename = resource.name
            else:
                filename = urlparse.urlparse(resource.location).path.split('/')[-1]
        else:
            filename = os.path.split(resource.file.path)[-1]

        # Try to append a file extension, one is not already present.
        filename, ext = os.path.splitext(filename)
        if not ext:
            ext = mimetypes.guess_extension(resource.content_type)
            if ext:
                filename += '.' + ext
        name = get_parent_resource(resource) + '/' + filename
        if name.startswith('/'):
            name = name[1:]
        return name
    return export_zip(queryset, target_path, fname=recursive_filename, **kwargs)
