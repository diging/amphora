from django.contrib import admin
import autocomplete_light

from .models import *
from .forms import *

class RelationInline(admin.TabularInline):
    model = Relation
    form = RelationForm
    fk_name = 'source'
    exclude = ('entity_type','name')


class ResourceAdmin(admin.ModelAdmin):
    inlines = (RelationInline,)
    model = Resource

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



admin.site.register(Entity)
admin.site.register(Resource, ResourceAdmin)
admin.site.register(Type)
admin.site.register(Field)
admin.site.register(Schema)
admin.site.register(Relation)
admin.site.register(LocalResource, ResourceAdmin)
admin.site.register(IntegerValue)
