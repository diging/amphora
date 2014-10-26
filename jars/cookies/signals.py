from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist

from .models import ConceptType, ConceptEntity

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

@receiver(post_save, sender=ConceptEntity)
def conceptentity_post_save(sender, **kwargs):
    instance = kwargs.get('instance', None)
    if instance.entity_type is None:
        print instance.concept
        type_instance = instance.concept.typed
        if type_instance is not None:

            ctype_instance = ConceptType.objects.get_or_create(
                type_concept_id=type_instance.id,
                defaults={
                    'uri': type_instance.uri,
                    'name': type_instance.label,
                })[0]
            instance.entity_type = ctype_instance
            instance.save()
