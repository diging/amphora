from django.db import models, IntegrityError, transaction
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

    return '/'.join([unicode(instance.id), 'content', filename])


class Entity(models.Model):
    """
    A named object that represents some element in the data.
    """

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, blank=True, null=True)

    entity_type = models.ForeignKey('Type', blank=True, null=True,
                                    verbose_name='type', help_text=help_text(
        """
        Specifying a type helps to determine what metadata fields are
        appropriate for this resource, and can help with searching. Note that
        type-specific filtering of metadata fields will only take place after
        this resource has been saved.
        """))
    name = models.CharField(max_length=255, help_text=help_text(
        """
        Names are unique accross ALL entities in the system.
        """))

    hidden = models.BooleanField(default=False, help_text=help_text(
        """
        If a resource is hidden it will not appear in search results and will
        not be accessible directly, even for logged-in users.
        """))

    public = models.BooleanField(default=True, help_text=help_text(
        """
        If a resource is not public it will only be accessible to logged-in
        users and will not appear in public search results. If this option is
        selected, you affirm that you have the right to upload and distribute
        this resource.
        """))

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, verbose_name='URI', help_text=help_text(
       """
       You may provide your own URI, or allow the system to assign one
       automatically (recommended).
       """))


    relations_from = GenericRelation('Relation',
                                     content_type_field='source_type',
                                     object_id_field='source_instance_id')

    relations_to = GenericRelation('Relation',
                                   content_type_field='target_type',
                                   object_id_field='target_instance_id')

    events = GenericRelation('Event', content_type_field='on_type',
                             object_id_field='on_instance_id')

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
        return unicode(self.name)


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
    def local(self):
        if self.file:
            return True
        elif self.location:
            return False

    class Meta:
        permissions = (
            ('view_resource', 'View resource'),
        )
        abstract = True


class Resource(ResourceBase):
    next_page = models.OneToOneField('Resource', related_name='previous_page',
                                     blank=True, null=True)

    is_part = models.BooleanField(default=False)

    @property
    def content_location(self):
        if self.content_resource:
            if self.file:
                return self.file.url
            return self.location


class ContentRelation(models.Model):
    """
    Associates a :class:`.Resource` with its content representation(s).
    """

    for_resource = models.ForeignKey('Resource', related_name='content')
    content_resource = models.ForeignKey('Resource', related_name='parent')
    content_type = models.CharField(max_length=100, null=True, blank=True)
    content_encoding = models.CharField(max_length=100, null=True, blank=True)


class Collection(ResourceBase):
    """
    A set of :class:`.Entity` instances.
    """

    resources = models.ManyToManyField('Resource', related_name='part_of',
                                        blank=True, null=True  )

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
        # return '%s:: %s' % (getattr(self.schema, '__unicode__', lambda: '')(), self.name)


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


    class Meta:
        verbose_name = 'metadata relation'

    def save(self, *args, **kwargs):
        self.name = uuid4()
        super(Relation, self).save(*args, **kwargs)


### Actions and Events ###


class Event(models.Model):
    when = models.DateTimeField(auto_now_add=True)
    by = models.ForeignKey(User, related_name='events')
    did = models.ForeignKey('Action', related_name='events')

    on_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    on_instance_id = models.PositiveIntegerField()
    on = GenericForeignKey('on_type', 'on_instance_id')


class Action(models.Model):
    GRANT = 'GR'
    DELETE = 'DL'
    CHANGE = 'CH'
    VIEW = 'VW'
    ACTIONS = (
        (GRANT, 'GRANT'),
        (DELETE, 'DELETE'),
        (CHANGE, 'CHANGE'),
        (VIEW, 'VIEW'),
    )

    type = models.CharField(max_length=2, choices=ACTIONS, unique=True)

    def __unicode__(self):
        return unicode(self.get_type_display())

    def is_authorized(self, actor, entity):
        """
        Checks for a related :class:`.Authorization` matching the specified
        :class:`.Actor` and :class:`.Entity`\.
        """

        # Filter first for Authorizations that belong to the User actor...
        auth = self.authorizations.filter(actor__id=actor.id)

        # ...and then for those that belong on the Entity.
        auth = auth.filter(on__id=entity.id)

        # If there is a responsive Authorization, then the User actor is
        #  authorized to perform this :class:`.Action`\.
        if auth.count() == 0:
            return False
        return True

    def log(self, entity, actor, **kwargs):
        """
        Log this :class:`.Action` as an :class:`.Event`\.

        Parameters
        ----------
        entity : :class:`.Entity`
        actor : :class:`django.contrib.auth.models.User`

        Returns
        -------
        event : :class:`.Event`
        """

        # Log the action as an Event.
        event = Event(by=actor, did=self.type, on=entity)
        event.save()

        return event


class Authorization(models.Model):
    actor = models.ForeignKey(User, related_name='is_authorized_to')
    to_do = models.ForeignKey('Action', related_name='authorizations')
    on_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    on_instance_id = models.PositiveIntegerField()
    on = GenericForeignKey('on_type', 'on_instance_id')

    def __unicode__(self):
        return u'%s can %s on %s' % (self.actor, self.to_do, self.on)


class ConceptEntity(Entity):
    concept = models.ForeignKey('concepts.Concept', null=True, blank=True)


class ConceptType(Type):
    type_concept = models.ForeignKey('concepts.Type')


class UserJob(models.Model):
    """
    For tracking async jobs.
    """
    created_by = models.ForeignKey(User, related_name='jobs')
    created = models.DateTimeField(auto_now_add=True)
    result_id = models.CharField(max_length=255)
    result = models.TextField()

    def get_absolute_url(self):
        return reverse('job-status', args=(self.result_id,))


class GilesSession(models.Model):
    created_by = models.ForeignKey(User, related_name='giles_sessions')
    created = models.DateTimeField(auto_now_add=True)
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


class GilesUpload(models.Model):
    """
    Tracks files that have been uploaded via the REST API.
    """
    created_by = models.ForeignKey(User, related_name='giles_uploads')
    created = models.DateTimeField(auto_now_add=True)
