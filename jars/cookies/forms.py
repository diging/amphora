from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _

import autocomplete_light
import inspect

from . import models

class TargetField(forms.models.ModelChoiceField):
    """
    Supports the target field in the :class:`.RelationForm`\.
    """
    def to_python(self, value):
        """
        Just pass the value (str/unicode) on through, so that we can evaluate
        it later.
        """
        
        return value

    def prepare_value(self, value):
        """
        If value is an int, it is a primary key for Entity. Otherwise (e.g.
        where there was a ValidationError) it is a value for ``name`` and should
        be displayed directly.
        """
        
        if value is not None:
            if type(value) is int:
                entity = models.Entity.objects.get(pk=value)
                return entity.name
            else:
                return value
        return None


class RelationForm(forms.ModelForm):
    """
    Supports the :class:`.RelationInline` by handling heterogeneous input and
    resolving them into Entities.
    
    TODO: Handle cases where the range of a Field includes non-Value types.
    """
    
    model = models.Relation
    
    def __init__(self, *args, **kwargs):
        super(RelationForm, self).__init__(*args, **kwargs)
        self.fields['target'] = TargetField(queryset=models.Entity.objects.all())
        self.fields['target'].widget = autocomplete_light.TextWidget('EntityAutocomplete')
        self.fields['predicate'].widget.widget.attrs.update(
            {
                'class': 'autocomplete_filter',
                'target': 'target',
            })
    
    def clean_target(self):
        return self.cleaned_data['target']

    def clean(self):
        cleaned_data = super(RelationForm, self).clean()
        predicate = cleaned_data.get('predicate')

        # Handle target field.
        target_data = cleaned_data.get('target')
        
        # First, attempt to get an Entity by name.
        try:
            target_obj = models.Entity.objects.get(name=target_data)
            target_obj = target_obj.cast()
        
        # If that fails, try to cast the data based on any System fields in the
        #  predicate Field's range.
        except ObjectDoesNotExist:
        
            # Try to get a model for each System type in the predicate's range.
            cast = False
            for ftype in predicate.range.all():
                if ftype.schema.name == 'System':
                
                    # It is unlikely, but if there is no model corresponding to
                    #  the System type (ftype), then we should move on.
                    try:
                        candidate_model = models.__dict__[ftype.name]
                    except:
                        continue
                    
                    # If the model is retrieved successfully, we instantiate it
                    #  and assign the data to its name attribute.
                    try:
                        target_obj, created = candidate_model.objects.get_or_create(name=target_data)
                        target_obj = target_obj.cast()
                        # If the data is successfully cast as the selected
                        #  model, then we will stop here and proceed with saving
                        #  the Relation.
                        cast = True     # Evaluated below.
                        break
                        
                    # Otherwise, move on to the next type in the predicate's
                    #  range.
                    except (ValidationError, ValueError):
                        continue

            # If the data cannot be cast as one of the model classes indicated
            #  by the System Types in the Field's range, there is no further
            #  recourse; the data is invalid for this Field.
            if not cast:
                self._errors['target'] = self.error_class(
                                            ['Invalid value for this Field']
                                            )
                del cleaned_data['target']
                return cleaned_data     # We're completely done here.

        # If we made it this far, then we have succesfully created or retrieved
        #  an Entity that is a candidate for the Relation's target.

        # The target must be in the Relation's Field's range. If the range is
        #  empty, then any Entity will do.
        if predicate.range.count() > 0:
            range = predicate.range.all()   # This is the database hit.
            
            # This should be an informative error message.
            range_msg = 'Value must be one of: {0}'.format(
                            ', '.join([str(r) for r in range])  )
            
            # Cast will re-cast the Entity as its 'real' model class.
            cast_entity = target_obj.cast()
            if hasattr(cast_entity, 'entity_type'):
            
                # Here we check wheter the Entity's type is in range.
                if not cast_entity.entity_type in range:
                    self._errors['target'] = self.error_class([range_msg])
                    del cleaned_data['target']
            
            # If the predicate has a range and the down-cast Entity has no type,
            #  there is no way for the Entity to be in range.
            else:
                self._errors['target'] = self.error_class([range_msg])
                del cleaned_data['target']

        # Success!
        cleaned_data['target'] = target_obj
        return cleaned_data

