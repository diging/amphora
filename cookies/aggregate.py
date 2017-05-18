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
from itertools import chain
from cookies.accession import get_remote
import smart_open, zipfile


def get_content(content_resource):
    """
    Retrieve the raw content for a content resource.
    """
    if content_resource.is_external:
        remote = get_remote(content_resource.external_source,
                            content_resource.created_by)
        return remote.get(content_resource.location)
    elif content_resource.file:
        with open(content_resource.file.path) as f:
            return f.read()
    return 'null'


def aggregate_content_resources(queryset, content_type=None,
                                part_uri='http://purl.org/dc/terms/isPartOf'):
    """
    Given a queryset of :class:`cookies.models.Resource` instances, return a
    generator that yields associated :class:`cookies.models.ContentResource`
    instances.
    """

    # TODO: Ok, this was a nice little excercise with generators. But since we
    #  already have content encapsulated with their uber-parent's container,
    #  can we leverage that relation to cut down on database calls? This may not
    #  matter so long as the rate-limiting factor is content-retrieval.
    queryset = iter(queryset)

    current = None
    current_parts = None
    current_content = None
    q = Q(predicate__uri=part_uri)
    if content_type is not None:
        content_q = Q(content_type=content_type)
        content_q |= Q(content_resource__content_type=content_type)

    def get_parts(resource):
        return chain((rel.source for rel in resource.relations_to.filter(q)),
                     *[get_parts(rel.source) for rel in resource.relations_to.filter(q)])

    def get_content(resource):
        qs = resource.content.all()
        if content_type is not None:
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


def export_zip(queryset, target_path, fname=lambda r: '%i.txt' % r.id, **kwargs):
    """
    Stream content into a zip archive at ``target_path``.
    """
    if not target_path.endswith('.zip'):
        target_path += '.zip'

    proc = kwargs.pop('proc', lambda content, resource: content)
    export_proc = lambda content, resource: (content, resource)
    aggregator = aggregate_content(queryset, proc=export_proc, **kwargs)
    with zipfile.ZipFile(target_path, 'w') as target:
        for content, resource in aggregator:
            target.writestr(fname(resource), content)
    return target_path


def export_with_collection_structure(queryset, target_path):
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
    return aggregate.export_zip(queryset, target_path, fname=recursive_filename,
                                **kwargs)
