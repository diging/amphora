from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType


def resource_file_name(instance, filename):
    return '/'.join(['content', instance.name, filename])

class HeritableObject(models.Model):
    real_type = models.ForeignKey(ContentType, editable=False)

    def save(self, *args, **kwargs):
        if not self.id:
            self.real_type = self._get_real_type()
        super(HeritableObject, self).save(*args, **kwargs)

    def _get_real_type(self):
        return ContentType.objects.get_for_model(type(self))

    def cast(self):
        return self.real_type.get_object_for_this_type(pk=self.pk)

    def __unicode__(self):
        return self.cast().__unicode__()

    class Meta:
        abstract = True

class Entity(HeritableObject):
    entity_type = models.ForeignKey('Type', blank=True, null=True)
    name = models.CharField(max_length=500, unique=True)
    
    class Meta:
        verbose_name_plural = 'entities'

    def __unicode__(self):
        return unicode(self.name)

class Resource(Entity):
    pass

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

class Collection(Entity):
    resources = models.ManyToManyField( 'Entity', related_name='part_of',
                                        blank=True, null=True  )

### Types and Fields ###

class Schema(Entity):
    pass

class Type(Entity):
    """
    If :attr:`.domain` is null, can be applied to any :class:`.Entity` 
    regardless of its :attr:`.Entity.entity_type`\.
    """

    domain = models.ManyToManyField(    'Type', related_name='in_domain_of',
                                        blank=True, null=True   )

    schema = models.ForeignKey(    'Schema', related_name='types',
                                    blank=True, null=True   )
                                    
    parent = models.ForeignKey(     'Type', related_name='children',
                                    blank=True, null=True   )

#    def full_path(self):
#        obj = self
#        parents = [obj]
#        while obj.parent is not None:
#            parents.append(obj.parent)
#            obj = obj.parent
#        parents.reverse()
#        
#        if self.schema.name is not None:
#            parents = [ self.schema ] + parents
#        return parents

#    def __unicode__(self):
#        return '.'.join([s.name for s in self.full_path()])

class Field(Type):
    """
    A :class:`.Field` is a :class:`.Type` for :class:`.Relation`\s.
    
    If range is null, can be applied to any Entity regardless of Type.
    """

    range = models.ManyToManyField(    'Type', related_name='in_range_of',
                                        blank=True, null=True   )


### Values ###

class Value(Entity):
    pass
    
class IntegerValue(Value):
    value = models.IntegerField(default=0, unique=True)

    def __unicode__(self):
        return unicode(self.value)    

class StringValue(Value):
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

### Relations ###

class Relation(Entity):
    source = models.ForeignKey( 'Entity', related_name='relations_from' )
    predicate = models.ForeignKey(  'Field', related_name='instances'   )
    target = models.ForeignKey( 'Entity', related_name='relations_to'   )

### Actions and Events ###

class Event(HeritableObject):
    when = models.DateTimeField(auto_now_add=True)
    by = models.ForeignKey(User, related_name='events')
    did = models.ForeignKey('Action', related_name='events')
    on = models.ForeignKey('Entity', related_name='events')

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
        
        auth = self.authorizations.filter(actor__id=actor.id).filter(on__id=entity.id)
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


