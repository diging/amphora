from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType


def resource_file_name(instance, filename):
    return '/'.join(['content', instance.name, filename])

class InheritanceCastModel(models.Model):
    real_type = models.ForeignKey(ContentType, editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.real_type = self._get_real_type()
        super(InheritanceCastModel, self).save(*args, **kwargs)

    def _get_real_type(self):
        return ContentType.objects.get_for_model(type(self))

    def cast(self):
        return self.real_type.get_object_for_this_type(pk=self.pk)

    class Meta:
        abstract = True

class NamedObject(models.Model):
    name = models.CharField(max_length=500, unique=True)

    def __unicode__(self):
        return unicode(self.name)

    class Meta:
        abstract = True

class Authority(NamedObject):
    endpoint = models.TextField()
    namespace = models.TextField()

class Entity(NamedObject, InheritanceCastModel):
    pass

class Resource(Entity):
    description = models.TextField(blank=True, null=True)

class RemoteMixin(models.Model):
    url = models.URLField(max_length=2000)
    
    class Meta:
        abstract = True

class LocalMixin(models.Model):
    file = models.FileField(upload_to=resource_file_name, blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super(LocalMixin, self).__init__(*args, **kwargs)
        setattr(self, 'url', self._url())
    
    def _url(self):
        """
        Use the file url.
        """
        
        try:
            return self.file.url
        except ValueError:
            return None

    class Meta:
        abstract = True

class RemoteResource(Resource, RemoteMixin):
    pass

class LocalResource(Resource, LocalMixin):
    pass
    
class Text(Resource):
    pass

class LocalText(Text, LocalMixin):
    pass

class RemoteText(Text, RemoteMixin):
    pass

class Corpus(Resource):
    contains = models.ManyToManyField('Resource', related_name='in_corpus')

    class Meta:
        verbose_name_plural = 'corpora'
        
class Concept(Resource):
    pass
#    
#    class Meta:
#        abstract=True
    
class LocalConcept(Concept, LocalMixin):
    pass

class RemoteConcept(Concept, RemoteMixin):
    pass

### Fields and Relations ###

class Schema(NamedObject):
    pass

class SchemaField(models.Model):
    """
    
    """

    schema = models.ForeignKey('Schema')
    field = models.ForeignKey('Field')
    verbose_name = 'field'

class FieldRelation(InheritanceCastModel):
    source = models.ForeignKey('Entity', related_name='relations_from')
    field = models.ForeignKey('Field')

class ValueRelation(FieldRelation):
    target = models.ForeignKey('Value')

class EntityRelation(FieldRelation):
    target = models.ForeignKey('Entity', related_name='relations_to')

class Value(models.Model):
    
    def type(self):
        if hasattr(self, 'integervalue'):   return 'integervalue'
        if hasattr(self, 'textvalue'):      return 'textvalue'
        if hasattr(self, 'floatvalue'):     return 'floatvalue'
        if hasattr(self, 'datetimevalue'):  return 'datetimevalue'
    
    def __unicode__(self):
        return getattr(self, self.type()).value.strftime('%Y-%m-%d')
    
class IntegerValue(Value):
    value = models.IntegerField(default=0, unique=True)

    def __unicode__(self):
        return unicode(self.value)    

class TextValue(Value):
    value = models.TextField(unique=True)

    def __unicode__(self):
        return unicode(self.value)    

class FloatValue(Value):
    value = models.FloatField(unique=True)
    
    def __unicode__(self):
        return unicode(self.value)    

class DateTimeValue(Value):
    value = models.DateTimeField(unique=True)
    
    def __unicode__(self):
        return unicode(self.datetimevalue.value)

class Field(NamedObject):
    FIELDTYPES = (
        ('Values', (
            ('IN', 'Integer'),
            ('FL', 'Float'),
            ('TX', 'Text'),
            ('DT', 'Date'),
            )
        ),
        ('Entities', (
            ('RS', 'Resource'),
            ('CP', 'Concept'),
            ('CO', 'Corpus'),
            ('TT', 'Text'),
            )
        )
    )

    VALUE_TYPES = {
        'IN': IntegerValue,
        'FL': FloatValue,
        'TX': TextValue,
        'DT': DateTimeValue
    }
    schema = models.ForeignKey('Schema', related_name='schema_fields')
    parent = models.ForeignKey('Field', related_name='children', blank=True, null=True)

    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=2, choices=FIELDTYPES)
    max_values = models.IntegerField(default=1)
    
    def full_path(self):
        obj = self
        parents = [obj]
        while obj.parent is not None:
            parents.append(obj.parent)
            obj = obj.parent
        parents.reverse()
        return parents
    
    def __unicode__(self):
        return '.'.join([ self.schema.name ] + [p.name for p in  self.full_path()])

### Actions and Events ###

class Event(models.Model):
    occurred = models.DateTimeField(auto_now_add=True)
    by = models.ForeignKey(User)
    did = models.ForeignKey('Action')
    on = models.ForeignKey('Entity')


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

    def do(self, entity, user, **kwargs):
        """
        
        Parameters
        ----------
        entity : :class:`.Entity`
        user : :class:`django.contrib.auth.models.User`
        
        Returns
        -------
        event : :class:`.Event`
        """

        # Log the action as an Event.
        event = Event(
                    by=user,
                    did=self.type,
                    on=entity
                    )
        event.save()

        return event

class Authorization(models.Model):
    actor = models.ForeignKey(User)
    to_do = models.ForeignKey('Action')
    on = models.ForeignKey('Entity')

    def __unicode__(self):
        return u'{0} can {1} {2}'.format(self.actor, self.to_do, self.on)


