from django.contrib import admin
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect
from django.conf.urls import patterns, include, url
from django.shortcuts import render
from django.core.urlresolvers import reverse


import autocomplete_light

import rdflib


from .models import *
from .forms import *

def import_schema(schema_url, domain=None):
    """
    'http://dublincore.org/2012/06/14/dcterms.rdf'
    """

    # Load RDF from remote location.
    g = rdflib.Graph()
    g.parse(schema_url)

    # Define some elements.
    title = rdflib.term.URIRef('http://purl.org/dc/terms/title')
    property = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#Property')
    type = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')



    # Get the title of the schema.
    titled = [ p for p in g.subjects(predicate=title) ][0]
    title = str([ o for o in g.objects(titled, title) ][0])
    namespace = str(titled)
    
    # Get all of the properties.
    properties = [ _handle_rdf_property(p,g) for p in g.subjects(type, property) ]

    # Create a new Schema.
    schema = Schema(name=title, uri=namespace, namespace=namespace)
    schema.save()

    # Generate new Fields from properties.
    fields = {}
    for property in properties:
        f = Field(
                name=property['label'],
                uri=property['uri'],
                description=property['description'],
                namespace=namespace,
                schema=schema
                )
        f.save()
        fields[property['uri']] = f

    # Now go back and assign parenthood to each Field, where appropriate.
    for property in properties:
        if len(property['parents']) > 0:    # Not all properties have parents.

            for parent in property['parents']:
            
                # Only consider parents that we know about in this schema.
                if parent in fields:
                    parent_field = fields[parent]
                    fields[property['uri']].parent = parent_field
                    fields[property['uri']].save()

                    # Each Type (=> Field) can have only one parent. So we'll
                    #  take the first valid parent and quit.
                    break

def _handle_rdf_property(p, g):
    description = rdflib.term.URIRef('http://purl.org/dc/terms/description')
    comment = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#comment')
    
    label = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#label')
    range = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#range')
    subPropertyOf = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#subPropertyOf')

    # Get the description for this Field. First try for the DC description,
    #  then try for the RDF comment. If neither is available, give up.
    try:
        this_description = [ s for s in g.objects(p, description)][0]
    except IndexError:
        try:
            this_description = [ s for s in g.objects(p, comment)][0]
        except IndexError:
            this_description = ''

    # Get the range, if available. We'll interpret this later.
    try:
        this_range = [ s for s in g.objects(p, range)][0]
    except IndexError:
        this_range = []

    # Grab only the attributes we'll need, and string-ify so we're not
    #  reliant on rdflib downstream.
    prop = {
        'uri': str(p),
        'label': str([ s for s in g.objects(p, label) ][0]),
        'description': this_description,
        'range': this_range,
        'parents': [ str(s) for s in g.objects(p, subPropertyOf) ],
        }

    return prop

class RelationInline(admin.TabularInline):
    model = Relation
    form = RelationForm
    fk_name = 'source'
    exclude = ('entity_type','name')

class ResourceAdminForward(admin.ModelAdmin):
    """
    
    """

    list_display = ('name','stored')
    
    form = ResourceForm
    inlines = (RelationInline,)
    
    def get_urls(self):
        """
        Here we override the add view to use a :class:`.ChooseResourceTypeForm`
        which, when submitted, redirects to the appropriate add view for a
        subclass of :class:`.Resource`\.
        """
        urls = super(ResourceAdminForward, self).get_urls()
        my_urls = patterns('',
            (r'^add/$', self.add_redirect)
        )
        return my_urls + urls

    def add_redirect(self, request):
        """
        Since we don't want the user to instantiate :class:`.Resource` directly,
        we will ask them to select a resource type and then direct them to the
        appropriate add view.
        
        Presents a :class:`.ChooseResourceTypeForm`\. When the form is submitted
        will redirect the user to an add view for the chosen subclass of
        :class:`.Resource`\.
        """
        
        # When the user submits their choice, we should figure out which
        #  subclass is appropriate, and redirect them to its add view.
        if request.method == 'POST':
            rtype = request.POST['resource_type']
            
            # Get the url for the add view based on the selected resource type.
            rurl = reverse("admin:cookies_{0}_add".format(rtype))
            
            # Since this view may be loaded in a popup (e.g. to add a Resource
            #  to a Collection) we should pass along any GET parameters to the
            #  ultimate add view.
            rurl += '?' + '&'.join([ '='.join([param,value])
                                        for param, value
                                        in request.GET.items()  ])

            return HttpResponseRedirect(rurl)
        
        # Load and render the ChooseResourceTypeForm.
        else:
            # The ChooseResourceTypeForm asks the user to select a resource
            #  type, which corresponds to a subclass of Resource (e.g.
            #  LocalResource).
            form = ChooseResourceTypeForm()
            
            # The admin/generic_form.html template is nothing special;
            #  it just embeds the form in the admin base_site template.
            return render(request, 'admin/generic_form.html',
                            {'form': form}  )

    def stored(self, obj, **kwargs):
        if type(obj.cast()) is LocalResource:
            return 'Local'
        elif type(obj.cast()) is RemoteResource:
            return 'Remote'
        return None

class ResourceAdmin(admin.ModelAdmin):
    """
    Admin interface for managing :class:`.Resource`\s.
    
    The main objective is to support adding/changing :class:`.Relation`\s for
    these :class:`.Resource`\s. This should be used by subclasses of
    :class:`.Resource` and NOT :class:`.Resource` itself.
    """
    
    inlines = (RelationInline,)
    form = ResourceForm
    model = Resource


class CollectionAdmin(admin.ModelAdmin):
    """
    Admin interface for managing :class:`.Collection`\s.
    """

    filter_horizontal = ('resources',)
    model = Collection

class HiddenAdmin(admin.ModelAdmin):
    """
    Subclasses of the :class:`.HiddenAdmin` will not be visible in the list of
    admin changelist views, but individual objects will be accessible directly.
    """
    
    def get_model_perms(self, request):
        """
        Return empty perms dict thus hiding the model from admin index.
        
        Parameters
        ----------
        request : :class:`django.http.HttpRequest`
        
        Returns
        -------
        perms : dict
            An empty dict.
        """
        
        return {}

class FieldAdmin(admin.ModelAdmin):
    list_display = ('schema', 'parent', 'name')

class SchemaAdmin(admin.ModelAdmin):
    def add_view(self, request):
        if request.method == 'POST':
            if 'schema_method' in request.POST:
                request.method = 'GET'
                if request.POST['schema_method'] == 'remote':
                    return self.add_remote_schema(request)
            return self.changeform_view(request)
        else:
            form = ChooseSchemaMethodForm()
            return render(request, 'admin/generic_form.html',
                            {'form': form}  )

    def add_remote_schema(self, request):
        if request.method == 'POST':
            pass
        else:
            form = RemoteSchemaForm()
            return render(request, 'admin/filter_form.html',
                            {'form': form}  )



admin.site.register(Type)
admin.site.register(Field, FieldAdmin)
admin.site.register(Schema, SchemaAdmin)

admin.site.register(Resource, ResourceAdminForward)
admin.site.register(LocalResource, ResourceAdmin)
admin.site.register(RemoteResource, ResourceAdmin)
admin.site.register(Collection, CollectionAdmin)

admin.site.register(Relation)
admin.site.register(Value)
admin.site.register(IntegerValue)
