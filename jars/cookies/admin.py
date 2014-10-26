from django.contrib import admin
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect
from django.conf.urls import patterns, include, url
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _


import autocomplete_light

import rdflib


from .models import *
from .forms import *

def import_schema(schema_url, schema_title):
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
#    title = str([ o for o in g.objects(titled, title) ][0])
    namespace = str(titled)
    
    # Get all of the properties.
    properties = [ _handle_rdf_property(p,g) for p in g.subjects(type, property) ]

    # Create a new Schema.
    schema = Schema(name=schema_title, uri=namespace, namespace=namespace)
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
    exclude = ('entity_type','name', 'hidden', 'public', 'namespace', 'uri',)

class StoredListFilter(admin.SimpleListFilter):
    """
    Filter :class:`.Resource`\s based on whether they are 
    :class:`.LocalResource`\s or :class:`.RemoteResource`\s.
    """
    title = _('storage location')
    parameter_name = 'stored'

    def lookups(self, request, model_admin):
        return (
            ('local', _('Local')),
            ('remote', _('Remote')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'local':
            return queryset.filter(real_type__model='localresource')
        elif self.value() == 'remote':
            return queryset.filter(real_type__model='remoteresource')

class ResourceAdminForward(admin.ModelAdmin):
    """
    
    """

    list_display = ('name','stored')
    list_filter = ( StoredListFilter, )
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


    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(
                    reverse("admin:cookies_resource_changelist"))

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
    list_display = (    'schema', 'parent', 'name', )
    list_filter = ( 'schema',   )
    exclude = ( 'entity_type', 'hidden', 'public',  )

class FieldInline(admin.TabularInline):
    fk_name = 'schema'
    model = Field
    exclude = ( 'entity_type', 'hidden', 'public', 'namespace', 'uri',
                'description',  )
    extra = 1

class SchemaAdmin(admin.ModelAdmin):
    exclude = ('entity_type', 'hidden', 'public')

    inlines = (FieldInline,)

    def add_view(self, request):
        """
        Supports an extra step, in which the user chooses whether to add a
        :class:`.Schema` manually, or from a remote RDF file.
        """
        
        if request.method == 'POST':
            # If a form was submitted, this may have been either to choose the
            #  method (manual or remote) for adding a schema, or a submission
            #  of the actual add form.
            if 'schema_method' in request.POST:
            
                # If the 'schema_method' field is present, then the user has
                #  submitted (presently, or in an earlier step) the method
                #  choice form. Now we determine which one they chose.
                if request.POST['schema_method'] == 'remote':
                
                    # If the 'schema_url' field is present, then the user has
                    #  just submitted the remote schema form.
                    if 'schema_url' not in request.POST:
                    
                        # If they have not yet submitted the remote schema form,
                        #  we set the method to GET so that add_remote_schema
                        #  (below) knows to serve a fresh form.
                        request.method = 'GET'
                        
                    # Otherwise we just pass the request through (as a POST) to
                    #  add_remote_schema for processing.
                    return self.add_remote_schema(request)
            
                elif request.POST['schema_method'] == 'manual':
                    # If the 'name' field is present, it means that the user has
                    #  submitted the manual schema add form.
                    if 'name' not in request.POST:
                        
                        # If the user hasn't submitted the manual schema add
                        #  form, set the request method to GET so that
                        #  changeform_view knows to serve a fresh form.
                        request.method = 'GET'

            # The changeform should be the default response.
            return self.changeform_view(request)

        else:
            # If no form has been submitted (i.e. a GET request), then we should
            #  serve a fresh form that prompts the user to choose a schema add
            #  method (manual or remote).
            form = ChooseSchemaMethodForm()
            return render(request, 'admin/schema_choose_method_form.html', {'form': form}  )

    def add_remote_schema(self, request):
        """
        Handles the case in which the user selects to add a :class:`.Schema`
        from a remote RDF file.
        """
        
        # The user has elected to add a schema from a remote RDF file.
        
        if request.method == 'POST':
            # If a form was submitted, then the user just submitted the remote
            #  schema add form.
            schema_url = request.POST['schema_url']
            schema_title = request.POST['schema_name']
            
            # TODO: handle exceptions (especially IntegrityError).
            import_schema(schema_url, schema_title)
            return HttpResponseRedirect(
                        reverse("admin:cookies_schema_changelist"))
        
        else:
            # If no form was submitted (i.e. a GET request), then we should give
            #  the user a fresh form asking for a schema name and the URL of the
            #  remote RDF file.
            form = RemoteSchemaForm()
            return render(request, 'admin/schema_remote_form.html',
                            {'form': form}  )

class TypeAdmin(admin.ModelAdmin):

    def get_queryset(self, request):
        """
        Should include only direct instances of :class:`.Type` and 
        :class:`.ConceptType`\.
        """
        
        qs = super(TypeAdmin, self).queryset(request)
        return qs.filter(real_type__model__in=('type', 'concepttype'))

admin.site.register(Type, TypeAdmin)
admin.site.register(Field, FieldAdmin)
admin.site.register(Schema, SchemaAdmin)

admin.site.register(Resource, ResourceAdminForward)
admin.site.register(LocalResource, ResourceAdmin)
admin.site.register(RemoteResource, ResourceAdmin)
admin.site.register(Collection, CollectionAdmin)
