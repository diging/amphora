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

class CorpusAutocomplete(autocomplete_light.AutocompleteModelBase):
    search_fields=['^name']
    autocomplete_js_attributes={'placeholder': 'Corpus name ?',}
    
    def choices_for_request(self):
        # TODO: modify to filter based on VIEW privileges.
        if not self.request.user.is_staff:
            self.choices = self.choices.filter(private=False)
        return super(CorpusAutocomplete, self).choices_for_request()
        
class ConceptAutocomplete(autocomplete_light.AutocompleteModelBase):
    search_fields=['^name']
    autocomplete_js_attributes={'placeholder': 'Concept name ?',}
    
    def choices_for_request(self):
        # TODO: modify to filter based on VIEW privileges.
        if not self.request.user.is_staff:
            self.choices = self.choices.filter(private=False)
        return super(ConceptAutocomplete, self).choices_for_request()        

autocomplete_light.register(Resource, ResourceAutocomplete)
autocomplete_light.register(Corpus, CorpusAutocomplete)
autocomplete_light.register(Concept, ConceptAutocomplete)