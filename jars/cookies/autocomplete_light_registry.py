import autocomplete_light
from models import *

class ResourceAutocomplete(autocomplete_light.AutocompleteModelBase):
    search_fields=['^name']
    autocomplete_js_attributes={'placeholder': 'Resource name ?',}
    
    def choices_for_request(self):
        # TODO: modify to filter based on VIEW privileges.
        if not self.request.user.is_staff:
            self.choices = self.choices.filter(private=False)
        return super(ResourceAutocomplete, self).choices_for_request()


class EntityAutocomplete(autocomplete_light.AutocompleteModelBase):
    search_fields=['id', 'name']
    autocomplete_js_attributes={'placeholder': 'Entity name ?',}
    
    def choices_for_request(self):
        # TODO: modify to filter based on VIEW privileges.
        if not self.request.user.is_staff:
            self.choices = self.choices.filter(private=False)

        q = self.request.GET.get('q', '')
        field_id = self.request.GET.get('in_range_of', None)

        choices = self.choices.all()
        if q:
            choices = choices.filter(name__icontains=q)
        if field_id:
            choices = choices.filter(entity_type__in_range_of__in=field_id)

        return self.order_choices(choices)[0:self.limit_choices]


autocomplete_light.register(Resource, ResourceAutocomplete)
autocomplete_light.register(Entity, EntityAutocomplete)
