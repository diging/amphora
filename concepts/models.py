from django.contrib.auth.models import User
from django.db import models
from django.contrib.contenttypes.models import ContentType

optional = { 'blank': True, 'null': True }


class HeritableObject(models.Model):
    """
    An object that is aware of its "real" type, i.e. the subclass that it
    instantiates.
    """

    real_type = models.ForeignKey(ContentType, editable=False)
    label = models.CharField(max_length=255, **optional)

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

    def __unicode__(self):
        return unicode(self.label)

    class Meta:
        abstract = True


class ExternalConcept(models.Model):
    uri = models.CharField(max_length=255)
    VIAF = 'VIAF'
    SOURCES = [
        (VIAF, 'VIAF'),
    ]
    source = models.CharField(max_length=4, choices=SOURCES)
    label = models.CharField(max_length=255)
    description = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='external_concepts')


class IdentityRelation(models.Model):
    concept = models.ForeignKey('Concept', related_name='external_identities')
    external = models.ForeignKey('Concept', related_name='internal_concepts')
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, related_name='identity_relations')


class Concept(HeritableObject):
    uri = models.CharField(max_length=255)
    resolved = models.BooleanField(default=False)
    typed = models.ForeignKey('Type', related_name='instances', **optional )
    description = models.TextField(**optional)
    authority = models.CharField(max_length=255)


class Type(Concept):
    pass
