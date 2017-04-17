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


import iso8601, json, sys, six, logging, rest_framework, jsonpickle, os
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
    full_ident = list(unicode(instance.id))

    return u'/'.join(full_ident + ['content', os.path.split(filename)[-1]])


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super(ActiveManager, self).get_queryset().filter(is_deleted=False)


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

    container = models.ForeignKey('ResourceContainer', blank=True, null=True)

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
                            null=True, max_length=2000, help_text=help_text(
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
        return reverse("resource", args=(self.id,))

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
    objects = models.Manager()
    active = ActiveManager()

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

    description = models.TextField(blank=True, null=True)

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

    OK = 'OK'
    PROCESSING = 'PR'
    ERROR = 'ER'
    @property
    def state(self):
        if self.giles_uploads.count() == 0:
            return Resource.OK
        states = self.giles_uploads.values_list('state', flat=True)
        if any(map(lambda s: s in GilesUpload.ERROR_STATES, states)):
            return Resource.ERROR
        if all(map(lambda s: s == GilesUpload.DONE, states)):
            return Resource.OK
        return Resource.PROCESSING

    def __unicode__(self):
        return self.name.encode('utf-8')


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

    objects = models.Manager()
    active = ActiveManager()

    for_resource = models.ForeignKey('Resource', related_name='content')
    content_resource = models.ForeignKey('Resource', related_name='parent')
    content_type = models.CharField(max_length=100, null=True, blank=True)
    content_encoding = models.CharField(max_length=100, null=True, blank=True)

    created_by = models.ForeignKey(User, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    container = models.ForeignKey('ResourceContainer',
                                  related_name='content_relations')
    is_deleted = models.BooleanField(default=False)


class Collection(ResourceBase):
    """
    A set of :class:`.Entity` instances.
    """
    objects = models.Manager()
    active = ActiveManager()

    part_of = models.ForeignKey('Collection', blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    def get_absolute_url(self):
        return reverse("collection", args=(self.id,))

    @property
    def size(self):
        def _count_recurse(collection):
            return ResourceContainer.objects.filter(part_of=collection).count()\
                + sum(map(_count_recurse,
                          Collection.objects.filter(part_of=collection)\
                                    .values_list('id', flat=True)))
        return _count_recurse(self)

    @property
    def resources(self):
        return Resource.objects.filter(is_primary_for__part_of_id=self.id,
                                       is_deleted=False)


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

    domain = models.ManyToManyField('Type', blank=True, help_text="The domain"
                                    " specifies the resource types to which"
                                    " this Type or Field can apply. If no"
                                    " domain is specified, then this Type or"
                                    " Field can apply to any resource.")

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

    domain = models.ManyToManyField('Type', blank=True, help_text="The domain"
                                    " specifies the resource types to which"
                                    " this Type or Field can apply. If no"
                                    " domain is specified, then this Type or"
                                    " Field can apply to any resource.")

    schema = models.ForeignKey('Schema', related_name='fields', blank=True, null=True)

    parent = models.ForeignKey('Field', related_name='children', blank=True, null=True)

    description = models.TextField(blank=True, null=True)

    range = models.ManyToManyField('Type', related_name='in_range_of',
                                   blank=True, help_text="The field's range"
                                   " specifies the resource types that are"
                                   " valid values for this field. If no range"
                                   " is specified, then this field will accept"
                                   " any value.")

    def __unicode__(self):
        return '%s (%s)' % (self.name, getattr(self.schema, '__unicode__', lambda: '')())


### Values ###



class Value(models.Model):
    """
    Generic container for freeform data.

    Uses jsonpickle to support Python data types, as well as ``date`` and
    ``datetime`` objects.
    """

    _value = models.TextField()
    _type = models.CharField(max_length=255, blank=True, null=True)

    def _get_value(self):
        return jsonpickle.decode(self._value)

    def _set_value(self, value):
        self._type = type(value).__name__
        self._value = jsonpickle.encode(value)

    name = property(_get_value, _set_value)

    container = models.ForeignKey('ResourceContainer', blank=True, null=True)

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

    data_source = models.CharField(max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name = 'metadata relation'
        permissions = (
            ('view_relation', 'View relation'),
            ('change_authorizations', 'Change authorizations'),
            ('view_authorizations', 'View authorizations'),
        )

        # Unless otherwise specified, relations will be displayed in order of
        #  their creation (oldest first).
        ordering = ['id',]

    def save(self, *args, **kwargs):
        self.name = uuid4()
        super(Relation, self).save(*args, **kwargs)



### Actions and Events ###


class ConceptEntity(Entity):
    objects = models.Manager()
    active = ActiveManager()

    concept = models.ManyToManyField('concepts.Concept', blank=True)

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
    upload_id = models.CharField(max_length=255, blank=True, null=True)
    resource = models.ForeignKey('Resource', related_name='giles_uploads',
                                 blank=True, null=True)
    """
    If the upload originated from Amphora, it should be associated with a
    :class:`.Resource` instance.
    """

    created_by = models.ForeignKey(User, related_name='giles_uploads')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    last_checked = models.DateTimeField(blank=True, null=True)

    PENDING = 'PD'
    ENQUEUED = 'EQ'
    SENT = 'ST'
    DONE = 'DO'
    SEND_ERROR = 'SE'
    GILES_ERROR = 'GE'
    PROCESS_ERROR = 'PE'
    CALLBACK_ERROR = 'CE'
    ASSIGNED = 'AS'     # A worker is polling this task.
    ERROR_STATES = (SEND_ERROR, GILES_ERROR, PROCESS_ERROR, CALLBACK_ERROR)
    STATES = (
        (PENDING, 'Pending'),      # Upload is ready to be dispatched.
        (ENQUEUED, 'Enqueued'),    # Dispatcher has created an upload task.
        (SENT, 'Sent'),            # File was sent successfully to Giles.
        (DONE, 'Done'),            # File was processed by Giles and Amphora.
        (SEND_ERROR, 'Send error'),    # Problem sending the file to Giles.
        (GILES_ERROR, 'Giles error'),  # Giles responded oddly after upload.
        (PROCESS_ERROR, 'Process error'),    # We screwed up post-processing.
        (CALLBACK_ERROR, 'Callback error'),  # Something went wrong afterwards.
        (ASSIGNED, 'Assigned')
    )
    state  = models.CharField(max_length=2, choices=STATES)

    message = models.TextField()
    """Error messages, etc."""

    on_complete = models.TextField()
    """Serialized callback instructions."""

    file_path = models.CharField(max_length=1000, blank=True, null=True)
    """Relative to MEDIA_ROOT."""


class GilesToken(models.Model):
    """
    A short-lived auth token for sending content to Giles on behalf of a user.

    See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
    """

    for_user = models.OneToOneField(User, related_name='giles_token')
    created = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=255)


class ResourceContainer(models.Model):
    """
    Encapsulates a set of linked objects.
    """
    objects = models.Manager()
    active = ActiveManager()

    created_by = models.ForeignKey(User, related_name='containers', blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    primary = models.ForeignKey('Resource', related_name='is_primary_for',
                                blank=True, null=True)

    part_of = models.ForeignKey('Collection', blank=True, null=True)
    is_deleted = models.BooleanField(default=False)


class CollectionAuthorization(models.Model):
    granted_by = models.ForeignKey(User, related_name='created_resource_auths')
    granted_to = models.ForeignKey(User, related_name='resource_resource_auths', blank=True, null=True)
    for_resource = models.ForeignKey('Collection', related_name='authorizations')
    heritable = models.BooleanField(default=True,
                                    help_text="Policy applies to all resources"
                                    " in this collection.")
    """
    If ``True``, this policy also applies to the :class:`.ResourceContainer`\s
    in the :class:`.Collection`\.
    """

    VIEW = 'VW'    # User can view the collection (list its contents).
    EDIT = 'ED'    # User can edit collection details.
    ADD = 'AD'     # User can add resources.
    REMOVE = 'RM'    # User can remove resources.
    SHARE = 'SH'     # User can share the collection with others.
    AUTH_ACTIONS = (
        (VIEW, 'View'),
        (EDIT, 'Edit'),
        (ADD, 'Add'),
        (REMOVE, 'Remove'),
        (SHARE, 'Share'),
    )
    action = models.CharField(choices=AUTH_ACTIONS, max_length=2)

    ALLOW = 'AL'
    DENY = 'DY'
    POLICIES = (
        (ALLOW, 'Allow'),
        (DENY, 'Deny'),
    )
    policy = models.CharField(choices=POLICIES, max_length=2)



class ResourceAuthorization(models.Model):
    granted_by = models.ForeignKey(User, related_name='created_collection_auths')
    granted_to = models.ForeignKey(User, related_name='resource_collection_auths', blank=True, null=True)
    for_resource = models.ForeignKey('ResourceContainer',
                                     related_name='authorizations')

    VIEW = 'VW'
    EDIT = 'ED'
    SHARE = 'SH'
    DELETE = 'DL'
    AUTH_ACTIONS = (
        (VIEW, 'View'),
        (EDIT, 'Edit'),
        (SHARE, 'Share'),
    )
    action = models.CharField(choices=AUTH_ACTIONS, max_length=2)

    ALLOW = 'AL'
    DENY = 'DY'
    POLICIES = (
        (ALLOW, 'Allow'),
        (DENY, 'Deny'),
    )
    policy = models.CharField(choices=POLICIES, max_length=2)
