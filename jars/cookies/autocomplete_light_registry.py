import autocomplete_light
from models import *

class EntityAutocomplete(autocomplete_light.AutocompleteModelBase):
    search_fields=['id', 'name']
    autocomplete_js_attributes={'placeholder': 'Entity name ?',}
    
    def choices_for_request(self):
        """
        Will filter autocomplete suggestions based on whether an Entity
        has a Type within the range of a Field (given by field_id).
        """
        
        # TODO: modify to filter based on VIEW privileges.
        if not self.request.user.is_staff:
            self.choices = self.choices.filter(private=False)

        q = self.request.GET.get('q', '')
        field_id = self.request.GET.get('in_range_of', None)
        print field_id
        choices = self.choices.all()
        if q:
            choices = choices.filter(name__icontains=q)
        if field_id:
            choices = choices.filter(entity_type__in_range_of__in=[field_id])

        return self.order_choices(choices)[0:self.limit_choices]


autocomplete_light.register(Entity, EntityAutocomplete)
