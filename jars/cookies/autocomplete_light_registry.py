import autocomplete_light
from itertools import chain
from django.db.models.query import QuerySet
from .models import *
from concepts import authorities



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

        choices = self.choices.all()
        extra_choices = []
        if q:
            choices = choices.filter(name__icontains=q)
            
            # In addition to filtering existing Entities, we should also
            #  consider Concepts provided by registered authority services.
            if len(q) > 3:  # To avoid frivolous authority calls, we only
                            #  consider Concepts once the user has entered
                            #  four characters.
                extra_choices = self.suggest_concept(q)
        if field_id:
            choices = choices.filter(entity_type__in_range_of__in=[field_id])

        # Sort and combine autofill suggestions. Internal suggestions should
        #  go first, followed by external suggestions (e.g. Concepts).
        sorted_choices = list(chain(
                            self.order_choices(choices)[0:self.limit_choices],
                            extra_choices
                            ))

        return sorted_choices

    def suggest_concept(self, query):
        """
        Loads or generates :class:`ConceptEntity` instances based on the
        autocomplete query.
        """
        
        # Search all available authorities for the query.
        concepts = authorities.searchall(query)

        entities = []   # Will hold ConceptEntity objects.
        # For each Concept, we need a ConceptEntity that can serve as a value
        #  for the user's input field.
        for concept in concepts:
            # An Entity with a name matching the Concept's label may already
            #  exist. If so, we check whether it is a ConceptEntity.
            qs = Entity.objects.filter(name=concept.label)
            
            # TODO: *** CHECK ALL ENTITIES HERE ***
            if qs.count() > 0:
                # Get the object as its "real" type.
                candidate_entity = qs[0].cast()
                
                # If it is a ConceptEntity and the URI is correct, then we'll
                #  just use it.
                correct_type = type(candidate_entity) is ConceptEntity
                correct_uri = candidate_entity.uri == concept.uri
                if correct_type and correct_uri:
                    conceptentity = candidate_entity
                else:
                    # Otherwise, we will create a new ConceptEntity. Since names
                    #  must be unique, we will generate a new name using the
                    #  concept label and the concept URI.
                    #   For example: "Concept name (http://uri)".
                    conceptentity = ConceptEntity.objects.get_or_create(
                        name = '{0} ({1})'.format(concept.label, concept.uri),
                        defaults = {
                            'concept_id': concept.id,
                            })[0]
            # If no matching Entity exists, then we will create a new
            #  ConceptEntity with the correct name and URI.
            else:
                conceptentity = ConceptEntity.objects.get_or_create(
                    name=concept.label,
                    defaults = {
                        'concept_id': concept.id,
                        'uri': concept.uri,
                        })[0]
            entities.append(conceptentity)
        return entities


autocomplete_light.register(Entity, EntityAutocomplete)
