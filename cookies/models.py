from django.db import models, IntegrityError, transaction
from django.db.models.query import Q
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.conf import settings


import iso8601, json, sys, six, logging, rest_framework, jsonpickle
from uuid import uuid4

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('ERROR')

from django.conf import settings
import concepts


def help_text(text):
    return u' '.join([chunk.strip() for chunk in text.split('\n')])



def _resource_file_name(instance, filename):
    """
    Generates a file name for Files added to a :class:`.LocalResource`\.
    """

    return '/'.join([str(instance.id), 'content', filename])


class Entity(models.Model):
    """
    A named object that represents some element in the data.
    """

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, blank=True, null=True)
    updated = models.DateTimeField(auto_now=True)

    entity_type = models.ForeignKey('Type', blank=True, null=True,
                                    verbose_name='type',
                                    help_text="Specifying a type helps to"
                                    " determine what metadata fields are"
                                    " appropriate for this resource, and can"
                                    " help with searching. Note that type-"
                                    "specific filtering of metadata fields"
                                    " will only take place after this resource"
                                    " has been saved.")

    name = models.CharField(max_length=255)

    hidden = models.BooleanField(default=False)
    """
    If a resource is hidden it will not appear in search results and will
    not be accessible directly, even for logged-in users.
    """

    public = models.BooleanField(default=False, help_text="If a resource is not"
                                 " public it will only be accessible to"
                                 " logged-in users and will not appear in"
                                 " public search results. If this option is"
                                 " selected, you affirm that you have the right"
                                 " to upload and distribute this resource.")

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, verbose_name='URI',
                           help_text="You may provide your own URI, or allow"
                           " the system to assign one automatically"
                           " (recommended).")


    relations_from = GenericRelation('Relation',
                                     content_type_field='source_type',
                                     object_id_field='source_instance_id')

    relations_to = GenericRelation('Relation',
                                   content_type_field='target_type',
                                   object_id_field='target_instance_id')

    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'entities'
        abstract = True

    def save(self, *args, **kwargs):
        super(Entity, self).save()
        # Generate a URI if one has not already been assigned.
        #  TODO: this should call a method to generate a URI, to allow for more
        #        flexibility (e.g. calling a Handle server).
        if not self.uri:
            self.uri = u'/'.join([settings.URI_NAMESPACE,
                                  self.__class__.__name__.lower(),
                                  unicode(self.id)])
        super(Entity, self).save()

    def __unicode__(self):
        return unicode(self.id)


class ResourceBase(Entity):
    """
    """

    indexable_content = models.TextField(blank=True, null=True)
    processed = models.BooleanField(default=False)
    content_type = models.CharField(max_length=255, blank=True, null=True)
    content_resource = models.BooleanField(default=False)

    file = models.FileField(upload_to=_resource_file_name, blank=True,
                            null=True, help_text=help_text(
        """
        Drop a file onto this field, or click "Choose File" to select a file on
        your computer.
        """))

    location = models.URLField(max_length=255, verbose_name='URL', blank=True,
                               null=True)

    @property
    def text_available(self):
        if self.indexable_content:
            return len(self.indexable_content) > 2
        return False

    def get_absolute_url(self):
        return reverse("cookies.views.resource", args=(self.id,))

    @property
    def is_local(self):
        if self.file:
            return True
        elif self.location:
            return False

    @property
    def parts(self):
        page_field, _ = Field.objects.get_or_create(uri='http://purl.org/dc/terms/isPartOf')
        return self.relations_to.filter(predicate=page_field)

    class Meta:
        permissions = (
            ('view_resource', 'View resource'),
            ('change_authorizations', 'Change authorizations'),
            ('view_authorizations', 'View authorizations'),
        )
        abstract = True


class Resource(ResourceBase):
    DEFAULT_AUTHS = ['change_resource', 'view_resource',
                     'delete_resource', 'change_authorizations',
                     'view_authorizations']

    belongs_to = models.ForeignKey('Collection',
                                   related_name='native_resources',
                                   blank=True, null=True)
    """
    As of 0.4, a :class:`.Resource` instance belongs to one and only one
    :class:`.Collection` instance.
    """

    next_page = models.OneToOneField('Resource', related_name='previous_page',
                                     blank=True, null=True)

    is_part = models.BooleanField(default=False)
    is_external = models.BooleanField(default=False)

    GILES = 'GL'
    WEB = 'WB'
    SOURCES = (
        (GILES, 'Giles'),
        (WEB, 'Web'),
    )
    external_source = models.CharField(max_length=2, choices=SOURCES,
                                       blank=True, null=True)

    @property
    def content_location(self):
        if self.content_resource:
            if self.file:
                return self.file.url
            return self.location

    @property
    def content_types(self):
        if self.content_resource:
            return self.content_type

        direct = [(cr.content_type, cr.content_resource.content_type)
                    for cr in self.content.all()
                   if cr.content_resource.content_type or cr.content_type]
        if direct:
            d0, d1 = map(list, zip(*direct))
            direct = d0 + d1
        parts = []
        for r in self.relations_to.all():
             if r.source.content_type:
                parts += r.source.content_types
        return set([ct for ct in direct + parts if ct is not None])

    @property
    def content_view(self):
        return reverse('resource-content', args=(self.id,))

    @property
    def is_remote(self):
        return not self.is_local and not self.is_external

    @property
    def has_giles_content(self):
        return self.content.filter(content_resource__external_source=Resource.GILES).count() > 0

    @property
    def has_local_content(self):
        return self.content.filter(~Q(content_resource__file='')).count() > 0

    def __unicode__(self):
        return unicode(self.id)


class Tag(models.Model):
    """
    """
    created_by = models.ForeignKey(User, related_name='tags')
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=255)


class ResourceTag(models.Model):
    """
    """
    created_by = models.ForeignKey(User, related_name='resource_tags')
    created = models.DateTimeField(auto_now_add=True)
    tag = models.ForeignKey('Tag', related_name='resource_tags')
    resource = models.ForeignKey('Resource', related_name='tags')


class ContentRelation(models.Model):
    """
    Associates a :class:`.Resource` with its content representation(s).
    """

    for_resource = models.ForeignKey('Resource', related_name='content')
    content_resource = models.ForeignKey('Resource', related_name='parent')
    content_type = models.CharField(max_length=100, null=True, blank=True)
    content_encoding = models.CharField(max_length=100, null=True, blank=True)

    created_by = models.ForeignKey(User, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)


class Collection(ResourceBase):
    """
    A set of :class:`.Entity` instances.
    """
    DEFAULT_AUTHS = ['change_collection', 'view_resource',
                     'delete_collection', 'change_authorizations',
                     'view_authorizations']

    resources = models.ManyToManyField('Resource', related_name='part_of',
                                        blank=True, null=True  )

    part_of = models.ForeignKey('Collection', blank=True, null=True)

    def get_absolute_url(self):
        return reverse("cookies.views.collection", args=(self.id,))

    @property
    def size(self):
        return self.resources.count()


### Types and Fields ###


class Schema(models.Model):
    name = models.CharField(max_length=255)

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
                           verbose_name='URI')

    active = models.BooleanField(default=True)
    prefix = models.CharField(max_length=10, blank=True, null=True)

    def __unicode__(self):
        return unicode(self.name)


class Type(models.Model):
    name = models.CharField(max_length=255)

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
        verbose_name='URI')

    domain = models.ManyToManyField('Type', blank=True, null=True,
                                    help_text=help_text(
        """
        The domain specifies the resource types to which this Type or Field can
        apply. If no domain is specified, then this Type or Field can apply to
        any resource.
        """))

    schema = models.ForeignKey('Schema', related_name='types', blank=True, null=True)
    parent = models.ForeignKey('Type', related_name='children', blank=True, null=True)
    description = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return '%s (%s)' % (self.name, getattr(self.schema, '__unicode__', lambda: '')())


class Field(models.Model):
    """
    A :class:`.Field` is a type for :class:`.Relation`\s.

    If range is null, can be applied to any Entity regardless of Type.
    """

    name = models.CharField(max_length=255)

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
        verbose_name='URI')

    domain = models.ManyToManyField(
        'Type', blank=True, null=True,
        help_text='The domain specifies the resource types to which this Type'+\
        ' or Field can apply. If no domain is specified, then this Type or'   +\
        ' Field can apply to any resource.')

    schema = models.ForeignKey('Schema', related_name='fields', blank=True, null=True)

    parent = models.ForeignKey('Field', related_name='children', blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    range = models.ManyToManyField(
        'Type', related_name='in_range_of', blank=True, null=True,
        help_text=help_text(
        """
        The field's range specifies the resource types that are valid values
        for this field. If no range is specified, then this field will accept
        any value.
        """))

    def __unicode__(self):
        return '%s (%s)' % (self.name, getattr(self.schema, '__unicode__', lambda: '')())


### Values ###



class Value(models.Model):
    """
    Generic container for freeform data.

    Uses jsonpickle to support Python data types, as well as ``date`` and
    ``datetime`` objects.
    """

    DEFAULT_AUTHS = ['view', 'change', 'add', 'delete']
    _value = models.TextField()
    _type = models.CharField(max_length=255, blank=True, null=True)

    def _get_value(self):
        return jsonpickle.decode(self._value)

    def _set_value(self, value):
        self._type = type(value).__name__
        self._value = jsonpickle.encode(value)

    name = property(_get_value, _set_value)

    def __unicode__(self):
        return unicode(self.name)

    @property
    def uri(self):
        return u'Literal: ' + self.__unicode__()

    relations_from = GenericRelation('Relation',
                                     content_type_field='source_type',
                                     object_id_field='source_instance_id')

    relations_to = GenericRelation('Relation',
                                   content_type_field='target_type',
                                   object_id_field='target_instance_id')


### Relations ###


class Relation(Entity):
    """
    Defines a relationship beteween two :class:`Entity` instances.

    The :class:`.Entity` indicated by :attr:`.target` should fall within
    the range of the :class:`.Field` indicated by :attr:`.predicate`\. In other
    words, the :class:`.Type` of the target Entity should be listed in the
    predicate's :attr:`.Field.range` (unless the ``range`` is empty, in which
    case anything goes).
    """
    DEFAULT_AUTHS = ['change_relation', 'view_relation',
                     'delete_relation', 'change_authorizations',
                     'view_authorizations']

    source_type = models.ForeignKey(ContentType, related_name='relations_from',
                                    on_delete=models.CASCADE)
    source_instance_id = models.PositiveIntegerField()
    source = GenericForeignKey('source_type', 'source_instance_id')

    predicate = models.ForeignKey('Field', related_name='instances',
                                  verbose_name='field')

    target_type = models.ForeignKey(ContentType, related_name='relations_to',
                                    on_delete=models.CASCADE, blank=True, null=True)
    target_instance_id = models.PositiveIntegerField(blank=True, null=True)
    target = GenericForeignKey('target_type', 'target_instance_id')

    belongs_to = models.ForeignKey('Collection',
                                   related_name='native_relations',
                                   blank=True, null=True)


    class Meta:
        verbose_name = 'metadata relation'
        permissions = (
            ('view_relation', 'View relation'),
            ('change_authorizations', 'Change authorizations'),
            ('view_authorizations', 'View authorizations'),
        )

    def save(self, *args, **kwargs):
        self.name = uuid4()
        super(Relation, self).save(*args, **kwargs)



### Actions and Events ###


class ConceptEntity(Entity):
    DEFAULT_AUTHS = ['change_conceptentity', 'view_entity',
                     'delete_conceptentity', 'change_authorizations',
                     'view_authorizations']

    concept = models.ForeignKey('concepts.Concept', null=True, blank=True)

    belongs_to = models.ForeignKey('Collection',
                                   related_name='native_conceptentities',
                                   blank=True, null=True)

    def get_absolute_url(self):
        return reverse('entity-details', args=(self.id,))

    class Meta:
        permissions = (
            ('view_entity', 'View entity'),
            ('change_authorizations', 'Change authorizations'),
            ('view_authorizations', 'View authorizations'),
        )


class Identity(models.Model):
    created_by = models.ForeignKey(User)
    created = models.DateTimeField(auto_now_add=True)
    representative = models.ForeignKey('ConceptEntity', related_name='represents')
    entities = models.ManyToManyField('ConceptEntity', related_name='identities')


class ConceptType(Type):
    type_concept = models.ForeignKey('concepts.Type')


class UserJob(models.Model):
    """
    For tracking async jobs.
    """
    created_by = models.ForeignKey(User, related_name='jobs')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    result_id = models.CharField(max_length=255, null=True, blank=True)
    result = models.TextField()
    progress = models.FloatField(default=0.0)

    @property
    def percent(self):
        return self.progress * 100.

    def get_absolute_url(self):
        if self.result_id:
            return reverse('job-status', args=(self.result_id,))
        return reverse('jobs')


class GilesUpload(models.Model):
    """
    Represents a single upload.
    """

    created = models.DateTimeField(auto_now_add=True)
    sent = models.DateTimeField(null=True, blank=True)
    """The datetime when the file was uploaded."""

    upload_id = models.CharField(max_length=255, blank=True, null=True)
    """Returned by Giles upon upload."""

    content_resource = models.ForeignKey('Resource', null=True, blank=True,
                                         related_name='giles_upload')
    """This is the resource that directly 'owns' the uploaded file."""

    response = models.TextField(blank=True, null=True)
    """This should be raw JSON."""

    resolved = models.BooleanField(default=False)
    """When a successful response is received, this should be set ``True``."""

    fail = models.BooleanField(default=False)
    """If ``True``, should not be retried."""

    @property
    def pending(self):
        return not self.resolved


class GilesSession(models.Model):
    created_by = models.ForeignKey(User, related_name='giles_sessions')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    _file_ids = models.TextField()
    _file_details = models.TextField()


    content_resources = models.ManyToManyField('Resource', related_name='content_in_giles_sessions')
    resources = models.ManyToManyField('Resource', related_name='giles_sessions')
    collection = models.ForeignKey('Collection', null=True, blank=True)

    def _get_file_ids(self):
        return json.loads(self._file_ids)

    def _set_file_ids(self, value):
        self._file_ids = json.dumps(value)

    def _get_file_details(self):
        return json.loads(self._file_details)

    def _set_file_details(self, value):
        self._file_details = json.dumps(value)

    file_ids = property(_get_file_ids, _set_file_ids)
    file_details = property(_get_file_details, _set_file_details)



class GilesToken(models.Model):
    """
    A short-lived auth token for sending content to Giles on behalf of a user.

    See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
    """

    for_user = models.OneToOneField(User, related_name='giles_token')
    created = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=255)
