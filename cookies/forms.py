from django import forms
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.forms.utils import flatatt
from django.utils.translation import ugettext as _
from django.db.models import Q
from django.utils.encoding import force_text
from django.utils.html import conditional_escape, format_html
from django.db.utils import OperationalError

from dal import autocomplete
from dal_queryset_sequence.fields import QuerySetSequenceModelField
from dal_select2_queryset_sequence.widgets import QuerySetSequenceSelect2
from queryset_sequence import QuerySetSequence
import inspect

from .models import *
from . import models as md


class ContenteditableInput(forms.TextInput):
    """
    A contenteditable widget to include in your form
    """

    def render(self, name, value, attrs):
        attributes = attrs
        attributes['type'] = 'hidden'

        res = super(ContenteditableInput, self).render(name, value, attrs = attributes)
        res += '<div id="{0}" contenteditable="true">{1}</div>'.format(name, value)
        return res


class FieldAdminForm(forms.ModelForm):
    model = Field


class ChooseSchemaMethodForm(forms.Form):
    METHODS = (
        ('manual', 'Manual'),
        ('remote', 'Remote (RDF)'),
    )

    description = 'You can either create a schema manually or generate one' + \
                  ' from a RDF document.'
    schema_method = forms.ChoiceField(choices=METHODS)


class RemoteSchemaForm(forms.Form):
    description = 'Enter the location of a remote RDF schema.'

    schema_name = forms.CharField(required=True)
    schema_url = forms.URLField(required=True)
    choices = [('','--------')]

    default_domain = forms.ChoiceField(
        choices=choices,
        required=False,
        help_text='The domain specifies the resource types to which this Type'+\
        ' or Field can apply. If no domain is specified, then this Type or'   +\
        ' Field can apply to any resource. This resource type will be used'   +\
        ' as the domain for all fields in this schema, unless the schema'     +\
        ' explicitly specifies domains for its fields.')

    class Media:
        css = {'all': ('/static/admin/css/widgets.css',),}
        js = ('/admin/jsi18n/',)

	def __init__(self, *args, **kwargs):
		try:
			self.choices += [
				(t.id,t.name) for t in Type.objects.filter(
					~Q(real_type__model='field'))
			]
		except OperationalError:
			pass    # Exception is raised when database is initialized.
		super(RemoteSchemaForm, self).__init__(*args, **kwargs)


class BulkResourceForm(forms.Form):
    name = forms.CharField(max_length=255, help_text='A new Collection will be created from this bulk ingest.')

    file = forms.FileField(
        help_text='Drop or select a ZIP archive. A new LocalResource will be'+\
        ' generated for each file in the archive.')

    default_type = forms.ModelChoiceField(
        queryset=Type.objects.all(),
        required=False,
        help_text='All resources in this upload will be assigned the' + \
        ' specified type, unless a metadata file is included (not yet' + \
        ' implemented).')
    ignore_duplicates = forms.BooleanField(
        required=False,
        help_text='If selected, if a file in this upload shares a name with' +\
        ' an existing resource it will simply be ignored. Otherwise, its name'+\
        ' will be modified slightly so that it is unique.')


class RelationForm(autocomplete.FutureModelForm):
    """
    Supports the :class:`.RelationInline` by handling heterogeneous input and
    resolving them into Entities.

    TODO: Handle cases where the range of a Field includes non-Value types.
    """

    target = QuerySetSequenceModelField(
        queryset=QuerySetSequence(*[
            Resource.objects.all(),
            IntegerValue.objects.all(),
            StringValue.objects.all(),
            FloatValue.objects.all(),
            DateTimeValue.objects.all(),
            DateValue.objects.all(),
            ConceptEntity.objects.all(),
        ]),
        required=False,
        widget=QuerySetSequenceSelect2(
            url='autocomplete',
            attrs={
                'data-placeholder': 'Autocomplete ...',
                'data-minimum-input-length': 3,
            }
        )
    )

    def __init__(self, *args, **kwargs):
        super(RelationForm, self).__init__(*args, **kwargs)

        self.fields['predicate'].widget.widget.attrs.update({
                'class': 'autocomplete_filter',
                'target': 'target',
            })

        # Sort predicate Fields alphabetically, by name.
        qs = self.fields['predicate'].queryset.order_by('name')
        self.fields['predicate'].queryset = qs

    class Meta:
        model = Relation
        exclude = ['entity_type',]


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        exclude = []

    def __init__(self, *args, **kwargs):
        super(ResourceForm, self).__init__(*args, **kwargs)
