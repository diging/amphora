from django.shortcuts import render

from cookies.models import *
from cookies import authorization as auth


from cookies import metadata


def list_metadata(request):
    """
    Users should be able to search/filter for metadata entries by subject,
    predicate, and/or object.
    """
    source = request.GET.get('source', None)
    predicate = request.GET.get('predicate', None)
    target = request.GET.get('target', None)
    offset = int(request.GET.get('offset', 0))
    size = int(request.GET.get('size', 20))
    qs = metadata.filter_relations(source=source if source else None,
                                   predicate=predicate if predicate else None,
                                   target=target if target else None,
                                   user=request.user)
    max_results = qs.count()
    current_path = request.get_full_path().split('?')[0]
    params = request.GET.copy()
    if 'offset' in params:
        del params['offset']
    base_path = current_path + '?' + params.urlencode()
    previous_offset = offset - size if offset - size >= 0 else -1
    next_offset = offset + size if offset + size < max_results else None

    qs[offset:offset+size]
    context = {
        'relations': qs[offset:offset+size],
        'source': source,
        'predicate': predicate,
        'target': target,
        'offset': offset,
        'first_result': offset + 1,
        'last_result': min(offset + size, max_results),
        'next_url': base_path + '&offset=%i' % next_offset if next_offset else None,
        'previous_url': base_path + '&offset=%i' % previous_offset if previous_offset >= 0 else None,
        'size': size,
        'max_results': max_results,
    }
    template = 'list_metadata.html'
    return render(request, template, context)
