from django.db import models, IntegrityError, transaction
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
import rest_framework

import iso8601
import sys
import six
from uuid import uuid4

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('ERROR')


from jars import settings
import concepts


def resource_file_name(instance, filename):
    """
    Generates a file name for Files added to a :class:`.LocalResource`\.
    """

    return '/'.join(['content', filename])


class HeritableObject(models.Model):
    """
    An object that is aware of its "real" type, i.e. the subclass that it
    instantiates.
    """

    real_type = models.ForeignKey(ContentType, editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.real_type = self._get_real_type()
        super(HeritableObject, self).save(*args, **kwargs)

    def _get_real_type(self):
        return ContentType.objects.get_for_model(type(self))

    def cast(self):
        """
        Re-cast this object using its "real" subclass.
        """

        return self.real_type.get_object_for_this_type(pk=self.pk)

    class Meta:
        abstract = True


class Entity(HeritableObject):
    """
    A named object that represents some element in the data.
    """

    entity_type = models.ForeignKey(
        'Type', blank=True, null=True, verbose_name='type',
        help_text='Specifying a type helps to determine what metadata fields'+\
        ' are appropriate for this resource, and can help with searching.'   +\
        ' Note that type-specific filtering of metadata fields will only take'+\
        ' place after this resource has been saved.')
    name = models.CharField(max_length=255,
        help_text='Names are unique accross ALL entities in the system.')

    hidden = models.BooleanField(default=False,
        help_text='If a resource is hidden it will not appear in search' +\
        ' results and will not be accessible directly, even for logged-in' +\
        ' users.')
    public = models.BooleanField(default=True,
        help_text='If a resource is not public it will only be accessible'+\
        ' to logged-in users and will not appear in public search results.')

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
        verbose_name='URI',
        help_text='You may provide your own URI, or allow the system to'+\
        ' assign one automatically (recommended).')

    class Meta:
        verbose_name_plural = 'entities'

    def save(self, *args, **kwargs):
        # Enforce unique name.
        if self.name is not None:
            logger.debug('save Entity with name {0}'.format(self.name))
            with_name = Entity.objects.filter(name=self.name)

            # No Entity exists with that name.
            if with_name.count() == 0:
                pass
            # One Entity exists with that name, and it is the current Entity.
            elif with_name.count() == 1 and with_name[0].id == self.id:
                pass
            else:
                logger.debug('id: {0}, with_name: {1}'.format(self.id, [ (e.name, e.id) for e in with_name ]))
                raise IntegrityError(
                            'An Entity with that name already exists.')

        # Enforce unique URI.
        if self.uri is not None:
            with_uri = Entity.objects.filter(uri=self.uri)
            if with_uri.count() == 0: pass
            elif with_uri.count() == 1 and with_uri[0].id == self.id: pass
            else: raise IntegrityError(
                            'An Entity with that URI already exists.')

        # Parent class save operation.
        super(Entity, self).save(*args, **kwargs)

        # Generate a URI if one has not already been assigned.
        #  TODO: this should call a method to generate a URI, to allow for more
        #        flexibility (e.g. calling a Handle server).
        if not self.uri:
            self.uri = '/'.join([   settings.URI_NAMESPACE,
                                    str(self.real_type.model),
                                    str(self.id) ])
        super(Entity, self).save()

    def __unicode__(self):
        return unicode(self.name)


class Resource(Entity):
    """
    An :class:`.Entity` that contains potentially useful information.

    Should be instantiated as one of its subclasses, :class:`.LocalResource` or
    :class:`.RemoteResource`\.
    """

    indexable_content = models.TextField(blank=True, null=True)
    content_type = models.CharField(max_length=255, blank=True, null=True)

    @property
    def text_available(self):
        return len(self.indexable_content) > 2

    @property
    def stored(self):
        if hasattr(self, 'remoteresource'): return 'Remote'
        if hasattr(self, 'localresource'): return 'Local'

    def get_absolute_url(self):
        return reverse("cookies.views.resource", args=(self.id,))


    @property
    def content_location(self):
        return self.cast().url

    class Meta:
        permissions = (
            ('view_resource', 'View resource'),
        )


class RemoteMixin(models.Model):
    """
    A Remote object has a URL.
    """

    location = models.URLField(max_length=255, verbose_name='URL')

    @property
    def url(self):
        return self.location

    class Meta:
        abstract = True


class LocalMixin(models.Model):
    """
    A Local object can (optionally) have a File attached to it.
    """

    file = models.FileField(upload_to=resource_file_name, blank=True, null=True,
        help_text='Drop a file onto this field, or click "Choose File" to'+\
        ' select a file on your computer.')

    def __init__(self, *args, **kwargs):
        super(LocalMixin, self).__init__(*args, **kwargs)
        setattr(self, 'url', self._url())

    def _url(self):
        """
        Location where one can GET or PUT the LocalResource.file.
        """

        if not self.id:
            return None
        return rest_framework.reverse.reverse('resource_content', args=[self.id])

    class Meta:
        abstract = True


class RemoteResource(Resource, RemoteMixin):
    """
    An :class:`.Entity` that contains some potentially useful information,
    stored remotely (e.g. a Wikipedia article).
    """

    pass


class LocalResource(Resource, LocalMixin):
    """
    An :class:`.Entity` that contains some potentially useful information,
    stored locally, maybe in a File (e.g. a stored Text document, or a
    concept of a person.
    """

    pass


class Collection(Resource):
    """
    A set of :class:`.Entity` instances.
    """

    resources = models.ManyToManyField( 'Resource', related_name='part_of',
                                        blank=True, null=True  )

    def get_absolute_url(self):
        return reverse("cookies.views.collection", args=(self.id,))

### Types and Fields ###

class Schema(HeritableObject):
    name = models.CharField(max_length=255)

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
        verbose_name='URI')

    active = models.BooleanField(default=True)

    def __unicode__(self):
        return unicode(self.name)

class Type(HeritableObject):
    """
    If :attr:`.domain` is null, can be applied to any :class:`.Entity`
    regardless of its :attr:`.Entity.entity_type`\.
    """

    name = models.CharField(max_length=255)

    namespace = models.CharField(max_length=255, blank=True, null=True)
    uri = models.CharField(max_length=255, blank=True, null=True,
        verbose_name='URI')

    domain = models.ManyToManyField(
        'Type', related_name='in_domain_of', blank=True, null=True,
        help_text='The domain specifies the resource types to which this Type'+\
        ' or Field can apply. If no domain is specified, then this Type or'   +\
        ' Field can apply to any resource.')

    schema = models.ForeignKey(
        'Schema', related_name='types', blank=True, null=True   )

    parent = models.ForeignKey(
        'Type', related_name='children', blank=True, null=True   )

    description = models.TextField(blank=True, null=True)

    def __unicode__(self):
        return unicode(self.name)


class Field(Type):
    """
    A :class:`.Field` is a :class:`.Type` for :class:`.Relation`\s.

    If range is null, can be applied to any Entity regardless of Type.
    """

    range = models.ManyToManyField(
        'Type', related_name='in_range_of', blank=True, null=True,
        help_text='The field\'s range specifies the resource types that are' +\
        ' valid values for this field. If no range is specified, then this'  +\
        ' field will accept any value.')

### Values ###

class ValueQueryset(models.QuerySet):
    def get_or_create(self, defaults=None, **kwargs):
        """
        Get a :class:`.Value` based on the parameters in **kwargs. If a matching
        :class:`.Value` can't be found, create a new one.

        This is customized so that queries against the ``name`` field get recast
        as the appropriate type, depending on which :class:`.Value` subclass
        is using this :class:`.ValueQueryset`\.

        """
        lookup, params = self._extract_model_params(defaults, **kwargs)

        # The value of the lookup for ``name`` may not be the right datatype
        #  for this subclass of Value. E.g. if the request was generated from
        #  user data entered through a :class:`.TargetField` (which just passes
        #  the raw input along).
        if 'name' in lookup:

            # The _convert method will recast the value for the ``name`` lookup.
            name = self.model()._convert(lookup['name'])

            # Update lookup, kwargs, and params just for good measure.
            lookup['name'] = name
            kwargs['name'] = name
            params['name'] = name

        # The rest of this is straight from the original Django sourcecode.
        self._for_write = True
        try:
            return self.get(**lookup), False
        except self.model.DoesNotExist:
            return self._create_object_from_params(lookup, params)

    def _create_object_from_params(self, lookup, params):
        """
        Tries to create an object using passed params.

        Used by get_or_create and update_or_create.

        This is identical to the method in the Github sourcecode, it's just nice
        to have access to it for debugging.
        """
        try:
            with transaction.atomic(using=self.db):
                obj = self.create(**params)
            return obj, True
        except IntegrityError:
            exc_info = sys.exc_info()
            try:
                return self.get(**lookup), False
            except self.model.DoesNotExist:
                pass
            six.reraise(*exc_info)

    def create(self, **kwargs):
        """
        Creates a new object with the given kwargs, saving it to the database
        and returning the created object.

        This is identical to the original method, except that we are explicitly
        setting the :attr:`.name` attribute. For some reason passing ``name``
        in kwargs doesn't always work on some models.
        """

        obj = self.model(**kwargs)

        # Here we set ``name`` explicitly based on kwargs.
        if 'name' in kwargs:
            obj.name = kwargs['name']

        # Everything else is the same as the original method.
        self._for_write = True
        obj.save(force_insert=True, using=self.db)
        return obj

class ValueManager(models.Manager):
    """
    Allows us to use a custom :class:`.QuerySet`\, the :class:`.ValueQueryset`\.
    """

    def get_queryset(self):
        return ValueQueryset(self.model, using=self._db, hints=self._hints)

class Value(Entity):
    """
    Value should never be instantiated directly.

    TODO: We may want to make this abstract.
    """

    stop_recursion = False

    def __setattr__(self, key, value):
        if key == 'name' and not self.stop_recursion:
            self._value = value
            self.stop_recursion = True
            self.name = str(value)[:255]
            self.stop_recursion = False
        else:
            super(Value, self).__setattr__(key, value)

    def __getattr__(self, key):
        if key == 'name':
            return self._value
        super(Value, self).__getattr__(key)

    def save(self, *args, **kwargs):
        # There are a few housekeeping tasks when a Value is created.
        if not self.id and self.entity_type is None:

            # First, we need to establish its 'real_type', so that we can
            #  down-cast it, below. This is handled by the HeritableObject
            #  save method.
            super(Value, self).save(force_insert=False)

            # Next, we ensure that the value for name is of the correct type.
            self.name = self._convert(self.name)

            # All instances of Value subclasses should have a Type in the
            #  "System" Schema. In case this hasn't been created yet, we use
            #  the Schema Manager's get_or_create method.
            schema = Schema.objects.get_or_create(name='System')[0]
            schema.save()

            # We're looking for the Type that is identical to the name of the
            #  'real_type' of this Value object. E.g. if this is an
            #  IntegerValue, then it should have the Type "IntegerValue".
            try:
                rdf_schema = Entity.objects.get(name ='RDF').cast()
            except ObjectDoesNotExist:
                rdf_schema = Schema(name ='RDF')
                rdf_schema.save()

            try:
                literal = Type.objects.get(name='Literal')
            except ObjectDoesNotExist:
                literal = Type(
                            uri = settings.LITERAL,
                            schema = rdf_schema,
                            namespace = settings.RDFNS,
                            name = 'Literal',
                            )
                literal.save()

            cast_name = type(self.cast()).__name__
            try:
                e_type = Type.objects.get(name=cast_name)
            except ObjectDoesNotExist:
                e_type = Type(
                            name = cast_name,
                            schema = schema,
                            parent = literal,
                            )
                e_type.save()
            self.entity_type = e_type

            # Since we just assigned a value to entity_type, we'll save again.
            super(Value, self).save(force_insert=False)

    def _convert(self, value):
        """
        Re-casts a string or unicode input as the datatype expected by a
        :class:`.Value` subclass.
        """

        # Each Value subclass should have a staticmethod called pytype that
        #  will return the correct Python object for a given str or unicode
        #  value.
        try:
            return globals()[type(self).__name__].pytype(str(value))
        except ValueError:
            raise ValidationError('Invalid input type')

class IntegerValue(Value):
    objects = ValueManager()
    _value = models.IntegerField(default=0, unique=True)
    pytype = staticmethod(int)

class StringValue(Value):
    objects = ValueManager()
    _value = models.TextField()
    pytype = staticmethod(str)

class FloatValue(Value):
    objects = ValueManager()
    _value = models.FloatField(unique=True)
    pytype = staticmethod(float)

class DateTimeValue(Value):
    objects = ValueManager()
    _value = models.DateTimeField(unique=True, null=True, blank=True)
    pytype = staticmethod(iso8601.parse_date)

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

    source = models.ForeignKey(     'Entity', related_name='relations_from' )
    predicate = models.ForeignKey(
        'Field', related_name='instances', verbose_name='field')
    target = models.ForeignKey(
        'Entity', related_name='relations_to', verbose_name='value')

    class Meta:
        verbose_name = 'metadata relation'

    def save(self, *args, **kwargs):
        self.name = uuid4()
        super(Relation, self).save(*args, **kwargs)

### Actions and Events ###

class Event(HeritableObject):
    when = models.DateTimeField(auto_now_add=True)
    by = models.ForeignKey(User, related_name='events')
    did = models.ForeignKey(    'Action', related_name='events' )
    on = models.ForeignKey(     'Entity', related_name='events' )

class Action(HeritableObject):
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
        event = Event(
                    by=actor,
                    did=self.type,
                    on=entity
                    )
        event.save()

        return event

class Authorization(HeritableObject):
    actor = models.ForeignKey(User, related_name='is_authorized_to')
    to_do = models.ForeignKey('Action', related_name='authorizations')
    on = models.ForeignKey('Entity')

    def __unicode__(self):
        return u'{0} can {1} {2}'.format(self.actor, self.to_do, self.on)


class ConceptEntity(Entity):
    concept = models.ForeignKey('concepts.Concept')

class ConceptType(Type):
    type_concept = models.ForeignKey('concepts.Type')
