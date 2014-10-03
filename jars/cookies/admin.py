from django.contrib import admin
from django.forms.models import inlineformset_factory
from django.http import HttpResponseRedirect
from django.conf.urls import patterns, include, url
from django.shortcuts import render
from django.core.urlresolvers import reverse


import autocomplete_light


from .models import *
from .forms import *

class RelationInline(admin.TabularInline):
    model = Relation
    form = RelationForm
    fk_name = 'source'
    exclude = ('entity_type','name')

class ResourceAdminForward(admin.ModelAdmin):
    """
    Since we don't want the user to instantiate :class:`.Resource` directly,
    we will ask them to select a resource type and then direct them to the
    appropriate add view.
    """

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
            
            # The admin/resource_choosetype.html template is nothing special;
            #  it just embeds the form in the admin base_site template.
            return render(request, 'admin/resource_choosetype.html',
                            {'form': form}  )

class ResourceAdmin(admin.ModelAdmin):
    """
    Admin interface for managing :class:`.Resource`\s.
    
    The main objective is to support adding/changing :class:`.Relation`\s for
    these :class:`.Resource`\s. This should be used by subclasses of
    :class:`.Resource` and NOT :class:`.Resource` itself.
    """
    
    inlines = (RelationInline,)
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

class DateTimeValueAdmin(admin.ModelAdmin):
    model = DateTimeValue



admin.site.register(Type)
admin.site.register(Field)
admin.site.register(Schema)

admin.site.register(Resource, ResourceAdminForward)
admin.site.register(LocalResource, ResourceAdmin)
admin.site.register(RemoteResource, ResourceAdmin)
admin.site.register(Collection, CollectionAdmin)
