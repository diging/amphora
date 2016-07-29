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
    collection = forms.ModelChoiceField(**{
        'queryset': Collection.objects.all(),
        'empty_label': u'Create a new collection',
        'required': False,
    })

    name = forms.CharField(**{
        'max_length': 255,
        'help_text': u'Enter a name for your new collection.',
        'required': False,
    })


    public = forms.BooleanField(**{
        'help_text': u'By checking this box, you affirm that you have the' \
                   + u' right to upload and distribute this content.',
        'required': False,
    })

    upload_file = forms.FileField(**{
        'help_text': u'Drop or select a ZIP archive. A new LocalResource will' \
                   + u' be generated for each file in the archive.'
    })

    default_type = forms.ModelChoiceField(**{
        'queryset': Type.objects.all(),
        'required': False,
        'help_text': u'All resources in this upload will be assigned the' \
                   + u' specified type, unless a metadata file is included' \
                   + u' (not yet implemented).'
    })
    ignore_duplicates = forms.BooleanField(**{
        'required': False,
        'help_text': u'If selected, if a file in this upload shares a name' \
                   + u' with an existing resource it will simply be ignored.'\
                   + u' Otherwise, its name will be modified slightly so that'\
                   + u' it is unique.'
    })

    def clean(self):
        cleaned_data = super(BulkResourceForm, self).clean()
        collection = cleaned_data.get('collection', None)
        name = cleaned_data.get('name', None)
        if not collection and not name:
            raise forms.ValidationError("Please enter a name for your new collection")


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
        exclude = ['entity_type', ]


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        exclude = ['content_resource', 'content_type', 'processed', 'hidden',
                    'indexable_content']

    def __init__(self, *args, **kwargs):
        super(ResourceForm, self).__init__(*args, **kwargs)


class UserResourceForm(forms.Form):
    name = forms.CharField(help_text='Give your resource a unique name')
    resource_type = forms.ModelChoiceField(**{
        'queryset': Type.objects.all().order_by('name'),
        'help_text': 'Types help JARS determine what metadata fields are' \
                   + ' appropriate for your resource.',
    })
    public = forms.BooleanField(**{
        'help_text': u'If checked, this resource will be available to the' \
                   + u' public. By checking this box you affirm that you have' \
                   + u' the right to upload and distribute this resource.'
    })
    uri = forms.CharField(**{
        'required': False,
        'help_text': u'You may (optionally) specifiy an URI for your resource.'\
                   + u' If you\'re unsure, leave this blank and let JARS' \
                   + u' generate a URI for you.',
        'label': 'URI',
    })
    namespace = forms.CharField(**{
        'help_text': u'Use this field if you wish to explicitly specify a' \
                   + u' namespace for this resource.',
        'required': False,
    })
    collection = forms.ModelChoiceField(**{
        'queryset': Collection.objects.all().order_by('name'),
        'required': False
    })


class UserEditResourceForm(forms.Form):
    name = forms.CharField(help_text='Give your resource a unique name')
    resource_type = forms.ModelChoiceField(**{
        'queryset': Type.objects.all().order_by('name'),
        'help_text': 'Types help JARS determine what metadata fields are' \
                   + ' appropriate for your resource.',
    })
    public = forms.BooleanField(**{
        'required': False,
        'help_text': u'If checked, this resource will be available to the' \
                   + u' public. By checking this box you affirm that you have' \
                   + u' the right to upload and distribute this resource.'
    })
    uri = forms.CharField(**{
        'required': False,
        'help_text': u'You may (optionally) specifiy an URI for your resource.'\
                   + u' If you\'re unsure, leave this blank and let JARS' \
                   + u' generate a URI for you.',
        'label': 'URI',
    })
    namespace = forms.CharField(**{
        'help_text': u'Use this field if you wish to explicitly specify a' \
                   + u' namespace for this resource.',
        'required': False,
    })


class UserResourceFileForm(forms.Form):
    upload_file = forms.FileField()


class UserResourceURLForm(forms.Form):
    url = forms.URLField(**{
        'label': 'Enter an URL',
        'help_text': u'If your resource is already online, specify the full' \
                   + u' path to the resource here.'
    })


class ChooseCollectionForm(forms.Form):
    collection = forms.ModelChoiceField(**{
        'queryset': Collection.objects.all()
    })


class MetadatumForm(forms.Form):
    field = forms.ModelChoiceField(queryset=Field.objects.all().order_by('-name'))
    value = forms.CharField()#widget=forms.HiddenInput()
    value_id = forms.CharField(widget=forms.HiddenInput(), required=False)#
