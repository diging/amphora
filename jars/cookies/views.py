from django.shortcuts import render, render_to_response, get_object_or_404
from django.forms.extras.widgets import SelectDateWidget
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.core.exceptions import ObjectDoesNotExist
from django.template import RequestContext
from django.db.models.query import QuerySet
import iso8601
import inspect

import autocomplete_light

from forms import *
from cookies import models



#######

def resource_change(request, id):
    fields = list(models.Field.objects.all())
    
    source = models.Resource.objects.get(pk=id)

    # Handle form submission.
    if request.method == 'POST':
        # Just pull out the form-related keys in the POST request.
        formkeys = [    key for key in request.POST.keys() 
                        if key.split('_')[0] == 'form'      ]
        print request.POST
        for key in formkeys:

            parts = key.split('_')
            field = models.Field.objects.get(pk=parts[1])
            value = request.POST[key]
            
            # Handle EntityRelations.
            if field.type in ['CP', 'RS', 'CO']:    
                if field.type == 'CP':  # Concept
                    target,created = models.LocalConcept.objects.get_or_create(
                                                                    name=value
                                                                    )
                elif field.type == 'RS':
                    target = models.Resource.objects.get(name=value)
                elif field.type == 'CO':
                    target = models.Corpus.objects.get(name=value)
                    
                relation,created = models.EntityRelation.objects.get_or_create(
                                                    source=source, 
                                                    field=field, 
                                                    target=target   
                                                    )
            # Handle ValueRelations
            elif field.type in ['IN', 'FL', 'TX', 'DT']:    
                if field.type == 'DT':
                    try:
                        value = iso8601.parse_date(value)
                    except iso8601.iso8601.ParseError:
                        print 'parserror'
                        pass    # TODO: error handling.
                
                target_class = models.Field.VALUE_TYPES[field.type]
                target,created = target_class.objects.get_or_create(value=value)
                target.save()
                
                relation,created = models.ValueRelation.objects.get_or_create(
                                                    source=source,
                                                    field=field,
                                                    target=target
                                                    )
            relation.save()
        # Done handling form submissions.
    
    # Now build the form.
    source = models.Resource.objects.get(pk=id)

    FIELDTYPES = ( (f.id, f.type) for f in fields )
    FIELDNAMES = ( (f.id, f.__unicode__()) for f in fields )
    MAX_VALUES = ( (f.id, f.max_values) for f in fields )

    data = []
    for rel in source.relations_from.all():
        print rel.field
        if rel.field.type in ['IN', 'FL', 'TX', 'DT']:
            target = rel.valuerelation.target
            value = getattr(target, target.type())
        elif rel.field.type in ['CP', 'RS', 'CO']:
            value = rel.entityrelation.target.name

        data.append( (rel.field.id, value) )
    print data
    
    resource_widget = autocomplete_light.TextWidget('ResourceAutocomplete')
    resource_rendered = resource_widget.render('resource', None)
    corpus_widget = autocomplete_light.TextWidget('CorpusAutocomplete')
    corpus_rendered = corpus_widget.render('corpus', None)
    concept_widget = autocomplete_light.TextWidget('ConceptAutocomplete')
    concept_rendered = concept_widget.render('concept', None)        
    
    addFieldForm = AddFieldForm()
    context = {
        'addFieldForm': addFieldForm,
        'fieldtypes': FIELDTYPES,
        'fieldnames': FIELDNAMES,
        'max_values': MAX_VALUES,
        'resource': resource_rendered,
        'corpus': corpus_rendered,
        'concept': concept_rendered,
        'data': data,
    }
    return render(request, 'resource_change.html', context)

### REST API ###

def serializable_resource(result):
    cast_result = result.cast()
    rtype = type(cast_result).__name__
    bases = [ c.__name__ for c in type(cast_result).__bases__ ]

    remote = hasattr(result, 'remoteresource')
    local = hasattr(result, 'localresource')

    sresult =  {
        'id': result.id,
        'name': result.name,
        'relations': [ {
                        'field': rel.predicate.__unicode__(),
                        'value': rel.cast().target.__unicode__()
                        } for rel in result.relations_from.all() ],
        'remote': 'RemoteMixin' in bases,
        'local': 'LocalMixin' in bases,
        'rtype': rtype,
        }
    return sresult

def serializable(result):
    if result is None:
        pass
    elif type(result) is QuerySet:
        resource_based = models.Resource in inspect.getmro(result.model)
        if result.model == models.Resource or resource_based:
            return [ serializable_resource(res) for res in result ]

    elif type(result) is models.Resource or models.Resource in inspect.getmro(result.model):
        return [ serializable_resource(result) ]
    return []
        
def articulate_response(user_request, result_items):
    return JsonResponse({
                'request': user_request,
                'result': {
                    'items': result_items,
                    'count': len(result_items),
                    }
                }, safe=False)

def resource(request, id):
    result = get_object_or_404(models.Resource, pk=id)
    user_request = {
        'type': 'resource',
        'id': id,
    }    
    result_items = serializable(result)

    return articulate_response(user_request, result_items)

def resources(request):
    # ``start`` is the (0-based) index of the first Resource to be returned in
    #  the results. This is NOT the id (pk) of the Resource. Responding 
    #  Resources are ordered by ID, but ``start`` refers simply to the position
    #  of the Resource objects in the QuerySet. In conjunction with ``pagesize``
    #  this is useful for paging request.
    try:
        if 'start' in request.GET: start = int(request.GET['start'])
        else: start = 0
    except ValueError:
        return HttpResponseBadRequest('invalid value for start')        
    
    # ``pagesize`` is the number of results to include in the response. This is
    #  helpful for paging. Currently there are no limits on ``pagesize``. The
    #  default value is 20.
    try:
        if 'pagesize' in request.GET: pagesize = int(request.GET['pagesize'])
        else: pagesize = 20
    except ValueError:
        return HttpResponseBadRequest('invalid value for pagesize')        
    
    # ``rtype`` specifies the Resource subclass to return. For example, 
    #  rtype=Corpus would return only Corpus objects. The default is to return
    #  all Resource objects, regardless of subclass. A non-existant ``rtype``
    #  will result in a 400 error. 
    if 'rtype' in request.GET: rtype = request.GET['rtype']
    else: rtype = 'Resource'
    if rtype not in models.__dict__:
        return HttpResponseBadRequest('invalid resource type')

    # Results are ordered by id.
    results = models.__dict__[rtype].objects.all().order_by('id')
    count = results.count()         # More efficient than len() which evaluates 
                                    #  the QuerySet.
    print count
    if count == 0:
        pass
    elif start >= count:  # Fail quietly; simply return no results.
        results = []
    else:      # Slicing evaluates the QuerySet, so we hit the database here.
        results = results[start:min(pagesize, count)]

    
    user_request = {
        'type': 'resource',
        'rtype': rtype,
        'start': start,
        'pagesize': pagesize,
    }
    
    result_items = serializable(results)

    return articulate_response(user_request, result_items)
    
