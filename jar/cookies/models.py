from django.db import models
from django.contrib.auth.models import User

def resource_file_name(instance, filename):
    return '/'.join(['content', instance.name, filename])

class NamedObject(models.Model):
    name = models.CharField(max_length=500)

    def __unicode__(self):
        return unicode(self.name)

    class Meta:
        abstract = True

class Authority(NamedObject):
    endpoint = models.TextField()
    namespace = models.TextField()

class Entity(NamedObject):
    pass

class Resource(Entity):
    description = models.TextField(blank=True, null=True)

class RemoteMixin(models.Model):
    url = models.URLField(max_length=2000)
    
    class Meta:
        abstract = True

class LocalMixin(models.Model):
    file = models.FileField(upload_to=resource_file_name, blank=True, null=True)

    class Meta:
        abstract = True

class RemoteResource(Resource, RemoteMixin):
    pass

class LocalResource(Resource, LocalMixin):
    pass

class Corpus(Resource):
    contains = models.ManyToManyField('Resource', related_name='in_corpus')

    class Meta:
        verbose_name_plural = 'corpora'

### Fields and Relations ###

class Schema(NamedObject):
    pass

class SchemaField(models.Model):
    """
    
    """

    schema = models.ForeignKey('Schema')
    field = models.ForeignKey('Field')
    verbose_name = 'field'

class Field(NamedObject):
    FIELDTYPES = (
        ('Values', (
            ('IN', 'Integer'),
            ('FL', 'Floating point number'),
            ('TX', 'Text'),
            ('DT', 'Date and time'),
            )
        ),
        ('Entities', (
            ('RS', 'Resource'),
            )
        )
    )

    description = models.TextField(null=True, blank=True)
    type = models.CharField(max_length=2, choices=FIELDTYPES)

class FieldRelation(models.Model):
    source = models.ForeignKey('Entity', related_name='relations_from')
    field = models.ForeignKey('Field')

class ValueRelation(FieldRelation):
    value = models.ForeignKey('Value')

class EntityRelation(FieldRelation):
    target = models.ForeignKey('Entity', related_name='relations_to')

class Value(models.Model):
    name = models.CharField(max_length=100)

class IntegerValue(Value):
    value = models.IntegerField(default=0)

class TextValue(Value):
    value = models.TextField()

class FloatValue(Value):
    value = models.FloatField()

class DateTimeValue(Value):
    value = models.DateTimeField()

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
    ACTIONS = (
        (GRANT, 'GRANT'),
        (DELETE, 'DELETE'),
        (CHANGE, 'CHANGE'),
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


