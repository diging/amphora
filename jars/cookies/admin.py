from django.contrib import admin

from models import *


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

class FieldAdmin(HiddenAdmin):
    pass

class FieldInline(admin.TabularInline):
    model = SchemaField
    extra = 0

class ValueRelationInline(admin.TabularInline):
    extra = 0
    model = ValueRelation

class EntityRelationInline(admin.TabularInline):
    extra = 0
    model = EntityRelation
    fk_name = 'source'

class ResourceAdmin(admin.ModelAdmin):
    pass
#    inlines = (ValueRelationInline, EntityRelationInline)

class SchemaAdmin(admin.ModelAdmin):
    inlines = (FieldInline,)

class CorpusAdmin(admin.ModelAdmin):
    pass

admin.site.register(RemoteResource, ResourceAdmin)
admin.site.register(LocalResource, ResourceAdmin)


admin.site.register(Authorization)
admin.site.register(Action)

admin.site.register(Schema, SchemaAdmin)
admin.site.register(Field)#, FieldAdmin)

admin.site.register(EntityRelation)
admin.site.register(ValueRelation)

admin.site.register(Corpus, CorpusAdmin)

admin.site.register(Value)

admin.site.register(LocalText)

admin.site.register(LocalConcept)

admin.site.register(Concept)