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
import inspect, jsonpickle
from cookies.models import *
from cookies import authorization


class CustomModelChoiceField(forms.ModelChoiceField):
    """
    Overriding label_from_instance function in ModelChoiceField
    """

    def label_from_instance(self, obj):
         return obj.name


class TypeModelChoiceField(forms.ModelChoiceField):
    """
    Overriding label_from_instance function in ModelChoiceField
    """

    def label_from_instance(self, obj):
        if obj.schema is not None:
            return u'%s: %s' % (obj.schema.name, obj.name)
        else:
            return obj.name


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
    collection = CustomModelChoiceField(**{
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

    default_type = CustomModelChoiceField(**{
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


class ResourceForm(forms.ModelForm):
    class Meta:
        model = Resource
        exclude = ['content_resource', 'content_type', 'processed', 'hidden',
                    'indexable_content']

    def __init__(self, *args, **kwargs):
        super(ResourceForm, self).__init__(*args, **kwargs)


class UserResourceForm(forms.Form):
    name = forms.CharField(help_text='Give your resource a unique name')
    resource_type = TypeModelChoiceField(**{
        'queryset': Type.objects.all().order_by('name'),
        'help_text': 'Types help JARS determine what metadata fields are' \
                   + ' appropriate for your resource.',
    })
    public = forms.BooleanField(**{
        'help_text': u'If checked, this resource will be available to the' \
                   + u' public. By checking this box you affirm that you have' \
                   + u' the right to upload and distribute this resource.',
        'required': False,
    })
    uri = forms.CharField(**{
        'required': False,
        'help_text': u'You may (optionally) specifiy an URI for your resource.'\
                   + u' If you\'re unsure, leave this blank and let JARS' \
                   + u' generate a URI for you.',
        'label': 'URI',
    })
    # namespace = forms.CharField(**{
    #     'help_text': u'Use this field if you wish to explicitly specify a' \
    #                + u' namespace for this resource.',
    #     'required': False,
    # })
    collection = CustomModelChoiceField(**{
        'queryset': Collection.objects.all().order_by('name'),
        'required': False
    })

    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)


class UserEditResourceForm(forms.Form):
    """
    Form to edit a resource
    """

    name = forms.CharField(help_text='Give your resource a unique name')
    resource_type = CustomModelChoiceField(**{
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

class ResourceGilesPriorityForm(forms.Form):
    CHOICES_CONFIRM_CHANGE = (GilesUpload.PRIORITY_HIGH, GilesUpload.PRIORITY_LOW,)
    priority = forms.ChoiceField(choices=GilesUpload.PRIORITIES, required=False)

class UserDefineContentRegionForm(forms.Form):
    """
    Form to define an content region from a resource
    """
    def __init__(self, *args, **kwargs):
        self.resource_choices = kwargs.pop('resource_choices', None)
        super(UserDefineContentRegionForm, self).__init__(*args, **kwargs)

        self.groups = [
            {
                'name': 'start',
                'fields': {},
            },
            {
                'name': 'end',
                'fields': {},
            }
        ]
        self.fields['name'] = forms.CharField(**{
            'label': 'Name',
            'help_text': 'Give the content region a unique name'
        })

        self.fields['content_region_start_resource'] = forms.ChoiceField(**{
            'label': 'Start Resource',
            'help_text': 'Specify content region\'s starting resource',
            'choices': self.resource_choices,
        })
        self.groups[0]['fields']['resource'] = self['content_region_start_resource']

        self.fields['content_region_start_position'] = forms.IntegerField(**{
            'label': 'Start Position',
            'help_text': 'Specify content region\'s starting position',
            'min_value': 0,
        })
        self.groups[0]['fields']['position'] = self['content_region_start_position']

        self.fields['content_region_end_resource'] = forms.ChoiceField(**{
            'label': 'End Resource',
            'help_text': 'Specify content region\'s ending resource',
            'choices': self.resource_choices,
        })
        self.groups[1]['fields']['resource'] = self['content_region_end_resource']

        self.fields['content_region_end_position'] = forms.IntegerField(**{
            'label': 'End Position',
            'help_text': 'Specify content region\'s ending position',
            'min_value': 0,
        })
        self.groups[1]['fields']['position'] = self['content_region_end_position']

class ChooseCollectionForm(forms.Form):
    collection = CustomModelChoiceField(**{
        'queryset': Collection.objects.all(),
        'empty_label': u'Create a new collection',
        'required': False,
    })

    name = forms.CharField(**{
        'max_length': 255,
        'help_text': u'Enter a name for your new collection.',
        'required': False,
    })


class MetadatumValueTextAreaForm(forms.Form):
    value = forms.CharField(widget=forms.Textarea)
    # form_class = forms.TextInput(widget=forms.HiddenInput())

class MetadatumValueIntegerForm(forms.Form):
    value = forms.IntegerField()

class MetadatumValueFloatForm(forms.Form):
    value = forms.FloatField()

class MetadatumValueDateTimeForm(forms.Form):
    value = forms.DateTimeField()
    target_class = forms.CharField(widget=forms.HiddenInput(), required=False)

class MetadatumValueDateForm(forms.Form):
    value = forms.DateField()

class MetadatumConceptEntityForm(forms.Form):
    value = CustomModelChoiceField(queryset=ConceptEntity.objects.all().order_by('-name'))

class MetadatumResourceForm(forms.Form):
    value = CustomModelChoiceField(queryset=Resource.objects.all().order_by('-name'))

class MetadatumTypeForm(forms.Form):
    value = CustomModelChoiceField(queryset=Type.objects.all().order_by('-name'))


class MetadatumForm(forms.Form):
    predicate = CustomModelChoiceField(queryset=Field.objects.all().order_by('-name'))
    value_type = forms.ChoiceField(choices=(
        ('Int', 'Integer'),
        ('Float', 'Float'),
        ('Datetime', 'Date & Time'),
        ('Date', 'Date'),
        ('Text', 'Text'),
        ('ConceptEntity', 'Concept'),
        ('Resource', 'Resource'),
        ('Type', 'Type'),
    ))


class ConceptEntityForm(forms.ModelForm):
    class Meta:
        model = ConceptEntity
        fields = ('name', 'entity_type')


class ConceptEntityLinkForm(forms.Form):
    """
    Form for searching URIs based on the input and for linking a URI with an
    Entity instance.
    """

    q = forms.CharField(max_length=255, label='Search', required=False)


class CollectionForm(forms.ModelForm):

    """
    Form for allowing Curator to create a collection from
    the collection list view.
    """

    uri = forms.CharField(**{
        'required': False,
        'help_text': "Optional. Use this field if the collection represents an"
                     " existing set of resources located somewhere else in the"
                     " world."
    })
    part_of = CustomModelChoiceField(queryset=Collection.objects.all().order_by('name'),
                                     required=False,
                                     help_text="Make this collection a"
                                               " subcollection of an existing"
                                               " collection.")

    class Meta:
        model = Collection
        fields = ['name', 'public', 'uri', 'description']

    def __init__(self, *args, **kwargs):
        super(CollectionForm, self).__init__(*args, **kwargs)


class HiddenModelMultipleChoiceField(forms.ModelMultipleChoiceField):
    """
    Overriding functions in ModelMultipleChoiceField
    """

    def clean(self, value):
        value = eval(value)
        return super(HiddenModelMultipleChoiceField, self).clean(value)

    def to_python(self, value):
        if not value:
            return []
        value = eval(value)
        return super(HiddenModelMultipleChoiceField, self).to_python(value)

    def validate(self, value):
        # print 'validate', value
        pass


class AddTagForm(forms.Form):
    """
    Form for creating tags for resources
    """

    tag = CustomModelChoiceField(queryset=Tag.objects.all(),
                                 empty_label=u'Create a new tag',
                                 required=False)
    tag_name = forms.CharField(max_length=255, required=False)

    resources = HiddenModelMultipleChoiceField(queryset=Resource.objects.all(),
                                               widget=forms.widgets.HiddenInput(),
                                               required=False)

    def clean(self):
        cleaned_data = super(AddTagForm, self).clean()
        tag = cleaned_data.get('tag', None)
        name = cleaned_data.get('tag_name', None)
        if not tag and not name:
            raise forms.ValidationError("Please enter a name for your new tag")


VALUE_FORMS = dict([
    ('Int', MetadatumValueIntegerForm),
    ('Float', MetadatumValueFloatForm),
    ('Datetime', MetadatumValueDateTimeForm),
    ('Date', MetadatumValueDateForm),
    ('Text', MetadatumValueTextAreaForm),
    ('ConceptEntity', MetadatumConceptEntityForm),
    ('Resource', MetadatumResourceForm),
    ('Type', MetadatumTypeForm),
])



class DatasetForm(forms.ModelForm):
    filter_parameters = forms.CharField(widget=forms.HiddenInput())

    description = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}),
                                  help_text="Please describe the purpose and"
                                            " content of the dataset"
                                            " (optional).")

    dataset_type = forms.ChoiceField(choices=Dataset.TYPES,
        help_text="An explicit dataset stores references to the resources"
                  " that are currently selected. A dynamic dataset only stores"
                  " a reference to the parameters that you used to select the"
                  " resources. So if resources that respond to those parameters"
                  " are added or removed in the future, the content of the"
                  " dataset will change.")

    class Meta:
        model = Dataset
        fields = ('name', 'description', 'dataset_type', 'filter_parameters')


class SnapshotForm(forms.Form):
    content_type = forms.MultipleChoiceField(choices=[], required=False)
    include_metadata = forms.BooleanField(label="Metadata", required=False, initial=True)
    include_content = forms.BooleanField(label="Content", required=False, initial=True)
    export_structure = forms.ChoiceField(choices=[
        ('flat', 'Flat'),
        ('collection', 'Preserve collection structure'),
        ('parts', 'Preserve resource hierarchy')
    ], required=False, label="Content export structure")

    def __init__(self, *args, **kwargs):
        super(SnapshotForm, self).__init__(*args, **kwargs)

        # FIXME: The following statement results in a very expensive Postgres query.
        # As a temporary workaround, use a static list for choices.
        # content_types = Resource.objects.values_list('content_type', flat=True).distinct('content_type')
        content_type_choices = [
            'application/java-archive',
            'application/javascript',
            'application/json',
            'application/msword',
            'application/octet-stream',
            'application/pdf',
            'application/rtf',
            'application/vnd.apple.pages',
            'application/vnd.ms-excel',
            'application/vnd.oasis.opendocument.text',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/x-bibtex-text-file',
            'application/xhtml+xml',
            'application/x-java-archive',
            'application/xml',
            'application/x-msdownload',
            'application/x-msdownload; format=pe32',
            'application/x-sh',
            'application/x-sqlite3',
            'application/x-tika-msoffice',
            'application/zip',
            'image/gif',
            'image/png',
            'image/tiff',
            'image/vnd.microsoft.icon',
            'message/news',
            'multipart/appledouble',
            'text/css',
            'text/csv',
            'text/html',
            'text/html; charset=utf-8',
            'text/plain',
            'text/tab-separated-values',
            'text/x-matlab',
            'text/xml',
            'text/x-python',
            'video/quicktime',
        ]
        self.fields['content_type'].choices = [('__all__', 'All')] + zip(content_type_choices, content_type_choices)

    def clean(self):
        cleaned_data = super(SnapshotForm, self).clean()
        if not (cleaned_data.get('include_metadata') or cleaned_data.get('include_content')):
            raise forms.ValidationError('At least one of "include_content", "include_metadata" is required')

        if (cleaned_data.get('include_content')
                and not (cleaned_data.get('content_type')
                         and cleaned_data.get('export_structure'))):
            raise forms.ValidationError('Content type and export structure required')
        return cleaned_data

class GilesLogForm(forms.Form):
    APPLY_ALL = 'all'
    APPLY_SELECTED = 'selected'

    def __init__(self, *args, **kwargs):
        queryset = kwargs.pop('queryset', [])
        super(GilesLogForm, self).__init__(*args, **kwargs)
        upload_type = forms.ChoiceField(choices=[
            (self.APPLY_SELECTED, 'Apply Selected'),
            (self.APPLY_ALL, 'Apply All'),
        ], required=True)
        self.fields['apply_type'] = upload_type

        resources = forms.ModelMultipleChoiceField(
            queryset=queryset,
            required=False,
        )
        self.fields['resources'] = resources

        choices = [('', '--------')]
        choices.extend(GilesUpload.PRIORITIES)
        desired_priority = forms.ChoiceField(initial='',
                                             choices=choices,
                                             label='Priority',
                                             required=False)
        self.fields['desired_priority'] = desired_priority

        choices = [(state, text) if state != GilesUpload.PENDING else (state, text + ' (reupload)') for (state, text) in GilesUpload.STATES]
        choices.insert(0, ('','--------'))

        desired_state = forms.ChoiceField(initial='',
                                          choices=choices,
                                          label='State',
                                          required=False)
        self.fields['desired_state'] = desired_state

    def clean(self):
        cleaned_data = super(GilesLogForm, self).clean()
        if not (cleaned_data.get('desired_state') or cleaned_data.get('desired_priority')):
            raise forms.ValidationError('One of State, Priority is required.')
        return cleaned_data


class GilesLogItemForm(GilesLogForm):
    def __init__(self, *args, **kwargs):
        super(GilesLogItemForm, self).__init__(*args, **kwargs)
        self.fields.pop('apply_type')
        self.fields.pop('resources')
