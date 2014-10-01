from django import forms
import autocomplete_light

from models import *

FIELDS = ((-1,'-------'),) + tuple( (f.id, f.__unicode__()) for f in Field.objects.all() )

class AddFieldForm(forms.Form):
    field = forms.ChoiceField(widget=forms.Select, choices=FIELDS)

class ResourceRelationForm(forms.Form):
    field = forms.IntegerField()
    target = autocomplete_light.ChoiceWidget('ResourceAutocomplete')
    
class ConceptRelationForm(forms.Form):
    field = forms.IntegerField()
    target = autocomplete_light.TextWidget('ConceptAutocomplete')
    
class CorpusRelationForm(forms.Form):
    field = forms.IntegerField()
    target = autocomplete_light.ChoiceWidget('CorpusAutocomplete')
    
#class ValueRelationForm(forms.Form):
#    FIELDTYPES = {
#        'IN': forms.IntegerField,
#        'TX': forms.TextField,
#        'FL': forms.FloatField,
#        'DT': forms.DateTimeField,
#    }
#    value = forms.CharField()
#    
#    def __init__(self, type, *args, **kwargs):
#        super(ValueRelationForm, self).__init__(*args, **kwargs)
#        self.fields['value'] = self.FIELDTYPES[type]()
    
    
