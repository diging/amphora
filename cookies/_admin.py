from django.contrib import admin
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect
from django.conf.urls import patterns, include, url
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.template import RequestContext
from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q


from urllib2 import HTTPError

from functools import partial
from itertools import chain
from unidecode import unidecode

import rdflib

from .models import *
from .forms import *
from . import content

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('ERROR')

def import_schema(schema_url, schema_title, default_domain=None):
    """
    'http://dublincore.org/2012/06/14/dcterms.rdf'
    """

    logger.debug('load schema {0} from {1}'.format(schema_title, schema_url))

    # Load RDF from remote location.
    g = rdflib.Graph()
    try:
        g.parse(schema_url)
    except:
        g.parse(schema_url, format='xml')

    # Define some elements.
    title = rdflib.term.URIRef('http://purl.org/dc/terms/title')
    property = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#Property')
    type_element = rdflib.term.URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    class_element = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#Class')
    owl_class_element = rdflib.term.URIRef('http://www.w3.org/2002/07/owl#Class')

#    # Get the title of the schema.
#    titled = [ p for p in g.subjects(predicate=title) ][0]
#    namespace = unicode(titled)
    namespace = schema_url

    # Get all of the properties.
    properties = [ _handle_rdf_property(p,g) for p in g.subjects(type_element, property) ]

    # Get all of the Classes.
    classes = [ _handle_rdf_property(p,g) for p in g.subjects(type_element, class_element) ]
    owl_classes = [ _handle_rdf_property(p,g) for p in g.subjects(type_element, owl_class_element) ]

    logger.debug(
        '{0} properties, {1} classes, {2} OWL classes'.format(
            len(properties), len(classes), len(owl_classes)))

    # Create a new Schema.
    schema = Schema(name=schema_title, uri=namespace)#, namespace=namespace)
    schema.save()

    # Get the default domain Type, if specified.
    if default_domain is not None and default_domain != '':
        default_type = Type.objects.get(pk=int(default_domain))
    else:
        default_type = None

    # Generate new Fields from properties.
    fields = {}
    for property in properties:
        f, created = Field.objects.get_or_create(
                        uri=property['uri'],
                        defaults = {
                            'name': property['label'],
                            'description': property['description'],
                            'namespace': namespace,
                            'schema': schema,
                        })
        if created: logger.debug('created Field {0}'.format(f.uri))
        else:       logger.debug('loaded Field {0}'.format(f.uri))

        # If the User has selected a default domain (Type) for the Fields in
        #  this Schema, add that Type to the domain for this Field.
        if default_type is not None:
            f.domain.add(default_type)
            f.save()

        # Index the Field so that we can find it when handling parent-child
        #  relationships.
        fields[property['uri']] = f

    # Now go back and assign parenthood to each Field, where appropriate.
    for property in properties:

        # Not all properties have parents.
        if len(property['parents']) > 0:
            for parent in property['parents']:
                # Only consider parents that we already know about. If we can't
                #  find the parent Field, then we will simply skip it.
                try:
                    parent_field = Field.objects.get(uri=parent)
                except ObjectDoesNotExist:
                    continue

                fields[property['uri']].parent = parent_field
                fields[property['uri']].save()

                # Each Type (=> Field) can have only one parent. So we'll
                #  take the first valid parent and quit.
                break

    # Generate new Type objects from RDF and OWL Class definitions.
    types = {}
    for class_description in classes + owl_classes:
        t, created = Type.objects.get_or_create(
                        uri = class_description['uri'],
                        defaults = {
                            'name': class_description['label'],
                            'description': class_description['description'],
                            'namespace': namespace,
                            'schema': schema,
                        })
        if created: logger.debug('created Type {0}'.format(t.uri))
        else:       logger.debug('loaded Type {0}'.format(t.uri))

        types[class_description['uri']] = t

    # Now go back and assign parenthood to each Type, where appropriate.
    for class_description in classes + owl_classes:

        # Not all properties have parents.
        if len(class_description['parents']) > 0:
            for parent in class_description['parents']:
                # Only consider parents that we already know about. If we can't
                #  find the parent Field, then we will simply skip it.
                try:
                    parent_type = Type.objects.get(uri=parent)
                except ObjectDoesNotExist:
                    continue

                types[class_description['uri']].parent = parent_type
                types[class_description['uri']].save()

                # Each Type (=> Field) can have only one parent. So we'll
                #  take the first valid parent and quit.
                break

def _handle_rdf_property(p, g):
    description = rdflib.term.URIRef('http://purl.org/dc/terms/description')
    comment = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#comment')

    label = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#label')
    range = rdflib.term.URIRef('http://www.w3.org/2000/01/rdf-schema#range')
    subPropertyOf = rdflib.term.URIRef(
                        'http://www.w3.org/2000/01/rdf-schema#subPropertyOf')
    subClassOf = rdflib.term.URIRef(
                        'http://www.w3.org/2000/01/rdf-schema#subClassOf')

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

    try:
        this_label = None
        labels = [ s for s in g.objects(p, label) ]
        for label in labels:
            if label.language == 'en':
                this_label = label
        if this_label is None:
            this_label = unidecode(labels[0])

    except IndexError:
        this_label = unicode(p).split('#')[-1]

    # Grab only the attributes we'll need, and string-ify so we're not
    #  reliant on rdflib downstream.
    prop = {
        'uri': unicode(p),
        'label': this_label,
        'description': this_description,
        'range': this_range,
        'parents': [s for s in g.objects(p, subPropertyOf)] +\
                    [s for s in g.objects(p, subClassOf)],
        }

    return prop


class RelationInline(admin.TabularInline):
    model = Relation
    form = RelationForm
    fk_name = 'source'
    exclude = ('entity_type', 'name', 'hidden', 'public', 'namespace', 'uri',)

    def get_formset(self, request, obj=None, **kwargs):
        """
        Modified to include ``obj`` in the call to
        :meth:`.formfield_for_dbfield`\, so that we can apply instance-specific
        modifications to fields.
        """

        kwargs['formfield_callback'] = partial(
            self.formfield_for_dbfield, request=request, obj=obj)
        return super(RelationInline, self).get_formset(request, obj, **kwargs)

    def formfield_for_dbfield(self, db_field, **kwargs):
        """
        Modified to alter QuerySet for the Relation.predicate.
        """
        obj = kwargs.pop('obj', None)

        formfield = super(RelationInline, self).formfield_for_dbfield(
                                                            db_field, **kwargs)

        # The field for Relation.predicate is labeled 'Field'.
        if obj and hasattr(formfield, 'label'):
            if formfield.label == 'Field' and obj.entity_type is not None:

                # Limit predicate Fields to those for which this Resource is
                #  in their domain.
                query = Q(domain=obj.entity_type) | Q(domain=None)
                qs = Field.objects.filter(query)
                # ... or Fields for which a domain is not specified.

                formfield.queryset = qs

        return formfield


class StoredListFilter(admin.SimpleListFilter):
    """
    Filter :class:`.Resource`\s based on whether they are
    :class:`.LocalResource`\s or :class:`.RemoteResource`\s.
    """
    title = _('storage location')
    parameter_name = 'stored'

    def lookups(self, request, model_admin):
        """
        Defines filter options.
        """

        return (
            ('local', _('Local')),
            ('remote', _('Remote')),
        )

    def queryset(self, request, queryset):
        """
        Generates querysets based on user's filter selection.
        """

        if self.value() == 'local':
            return queryset.filter(real_type__model='localresource')
        elif self.value() == 'remote':
            return queryset.filter(real_type__model='remoteresource')


class ResourceAdminForward(admin.ModelAdmin):
    """

    """

    list_display =  (   'id', 'name','stored' )
    list_editable = (   'name', )
    list_filter = ( StoredListFilter, )
    form = ResourceForm
    inlines = (RelationInline,)

    class Media:
        js = ('admin/js/contenteditable.js',)

    def get_urls(self):
        """
        Here we override the add view to use a :class:`.ChooseResourceTypeForm`
        which, when submitted, redirects to the appropriate add view for a
        subclass of :class:`.Resource`\.
        """
        urls = super(ResourceAdminForward, self).get_urls()
        my_urls = patterns('',
            url(r'^bulk/$', self.bulk_view, name='bulk-resource')
        )
        return my_urls + urls

    def get_changelist_formset(self, request, **kwargs):
        """
        Changes the 'name' field to use a :class:`.ContenteditableInput`
        widget.
        """
        formset = super(ResourceAdminForward, self).get_changelist_formset(
                                                            request, **kwargs)

        formset.form.base_fields['name'].widget = ContenteditableInput()

        return formset

    def get_form(self, request, obj=None, **kwargs):
        form = super(ResourceAdminForward, self).get_form(request,obj,**kwargs)

        # Use different forms for Local and RemoteResources.
        if obj:
            if type(obj.cast()) is LocalResource:
                form = LocalResourceForm
            elif type(obj.cast()) is RemoteResource:
                form = RemoteResourceForm

        # Limit entity_type to direct instantiations of Type and ConceptType.
        form.base_fields['entity_type'].queryset = Type.objects.filter(
            real_type__model__in=['type', 'concepttype'])

        return form

    def change_view(self, request, obj_id, **kwargs):
        """
        Redirect to the appropriate change view based on the Resource subclass
        of the object with ``obj_id``.
        """

        obj = Resource.objects.get(pk=obj_id).cast()
        if isinstance(obj, LocalResource):
            url = reverse("admin:cookies_localresource_change", args=(obj_id,))
        elif isinstance(obj, RemoteResource):
            url = reverse("admin:cookies_remoteresource_change", args=(obj_id,))
        else:
            return super(ResourceAdminForward, self).change_view(
                                                      request, obj_id, **kwargs)
        return HttpResponseRedirect(url)

    def add_view(self, request, **kwargs):
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

            if rtype == 'bulk':
                rurl = reverse("admin:bulk-resource")
            else:
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
            return render(request, 'admin/generic_form.html', {'form': form}  )

    def bulk_view(self, request, **kwargs):
        """
        View for bulk uploads.
        """

        if request.method == 'POST':
            form = BulkResourceForm(request.POST, request.FILES)
            if form.is_valid():
                content.handle_bulk(request.FILES['file'], form)
                return HttpResponseRedirect(reverse("admin:cookies_resource_changelist"))

        else:
            form = BulkResourceForm()

            return render(request, 'admin/generic_form.html', {'form':form})


    def get_queryset(self, request):
        """
        Limit the QuerySet to :class:`.LocalResource` and
        :class:`.RemoteResource` instances.
        """
        qs = super(ResourceAdminForward, self).get_queryset(request)
        return qs.filter(real_type__model__in=['localresource','remoteresource'])


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

    def changelist_view(self, request, **kwargs):
        """
        Redirect the user to the Resource changelist (rather than displaying
        the subtype changelist).
        """
        url = reverse("admin:cookies_resource_changelist")
        return HttpResponseRedirect(url)

    def get_form(self, request, obj=None, **kwargs):
        """
        Use different forms for Local and RemoteResources.
        """

        if self.model is LocalResource:
            form = LocalResourceForm
        elif self.model is RemoteResource:
            form = RemoteResourceForm
        else:
            form = super(ResourceAdmin, self).get_form(request, obj, **kwargs)

        # Limit entity_type to direct instantiations of Type and ConceptType.
        form.base_fields['entity_type'].queryset = Type.objects.filter(
            real_type__model__in=['type', 'concepttype'])

        return form

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
    list_display = ('name',)
    exclude = ('entity_type','hidden','namespace','uri','indexable_content')

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
    fields = (  'name', 'namespace', 'uri', 'schema', 'parent', 'description',
                'domain', 'range'   )
    list_display = (    'schema', 'parent', 'name', )
    list_filter = ( 'schema',   )
    exclude = ( 'entity_type', 'hidden', 'public',  )
    filter_vertical = (   'domain', 'range'   )
    form = FieldAdminForm

    def get_form(self, request, obj=None, **kwargs):
        """
        Available values for :prop:`.domain` and :prop:`.range` should be
        limited to :class:`.Type` objects that directly instantiate the
        :class:`.Type` or :class:`.ConceptType` classes.
        """

        form = super(FieldAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['domain'].queryset = Type.objects.filter(
            real_type__model__in=['type','concepttype'])
        form.base_fields['range'].queryset = Type.objects.filter(
            real_type__model__in=['type','concepttype'])
        return form


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

                        # If no form was submitted (i.e. a GET request), then we
                        #  give the user a fresh form asking for a schema name
                        #  and the URL of the remote RDF file.
                        form = RemoteSchemaForm()
                        return render(request, 'admin/schema_remote_form.html',
                                        {'form': form}  )

                    # Instantiate the Form and validate.
                    form = RemoteSchemaForm(request.POST)
                    if form.is_valid():
                        logger.debug('form {0} is valid'.format(form))

                        # If the form is valid, add the remote schema.
                        try:
                            self.add_remote_schema(form)
                            return HttpResponseRedirect(
                                    reverse("admin:cookies_schema_changelist"))

                        # Provide an informative error message if we can't
                        #  connect to the specified URL.
                        except HTTPError:
                            if 'schema_url' not in form.errors:
                                form.errors['schema_url'] = []
                            form.errors['schema_url'] += ('Cannot access URL',)

                        # ...or if we encounter a problem parsing the RDF doc.
                        except IndexError as E:

                            if 'schema_url' not in form.errors:
                                form.errors['schema_url'] = []
                            form.errors['schema_url'] += ('Not valid RDF',)
                    else:
                        logger.debug('form {0} is not valid'.format(type(form)))
                        logger.debug('errors: {0}'.format(form.errors))


                    # Pass the invalid form back to the view.
                    return render(request, 'admin/schema_remote_form.html',
                                    {'form': form}  )
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
            return render(request,
                        'admin/schema_choose_method_form.html', {'form': form} )

    def add_remote_schema(self, form):
        """
        Handles the case in which the user selects to add a :class:`.Schema`
        from a remote RDF file.
        """

        # The user has elected to add a schema from a remote RDF file.

        # If a form was submitted, then the user just submitted the remote
        #  schema add form.
        schema_url = form.cleaned_data['schema_url']
        schema_title = form.cleaned_data['schema_name']
        default_domain = form.cleaned_data['default_domain']

        # TODO: handle exceptions (especially IntegrityError).
        import_schema(schema_url, schema_title, default_domain)


class TypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'schema')
    list_filter = ('schema',)

    def get_queryset(self, request):
        """
        Should include only direct instances of :class:`.Type` and
        :class:`.ConceptType`\.
        """

        qs = super(TypeAdmin, self).get_queryset(request)
        return qs.filter(real_type__model__in=('type', 'concepttype'))


admin.site.register(Type, TypeAdmin)
admin.site.register(Field, FieldAdmin)
admin.site.register(Schema, SchemaAdmin)

admin.site.register(Resource, ResourceAdminForward)
admin.site.register(LocalResource, ResourceAdmin)
admin.site.register(RemoteResource, ResourceAdmin)
admin.site.register(Collection, CollectionAdmin)
