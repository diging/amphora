from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist

from .models import ConceptType, ConceptEntity, LocalResource
from . import content

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')

@receiver(post_save, sender=ConceptEntity)
def conceptentity_post_save(sender, **kwargs):
    """
    When a :class:`.ConceptEntity` is saved, we will attempt to assign an 
    appropriate :class:`.Type` based on its related :class:`.Concept`\.
    """

    instance = kwargs.get('instance', None)

    logger.debug(
        'post_save signal for ConceptEntity, instance: {0}'.format(instance))
    
    # If this ConceptEntity already has an entity_type, there is nothing to do.
    if instance.entity_type is None:

        # Determine the concepts.Type of its associated concepts.Concept.
        type_instance = instance.concept.typed
        
        if type_instance is not None:
            # Since Entity.entity_type must point to a cookies.Type rather than
            #  a concepts.Type, we use an instance of cookies.ConceptType which
            #  is a subclass of cookies.Type.
            ctype_instance = ConceptType.objects.get_or_create(
                uri = type_instance.uri,
                defaults={
                    'name': type_instance.label,
                    'type_concept': type_instance,
                })[0]
            # We associate this cookies.ConceptType with its corresponding
            #  concepts.Type instance to make it easier to find later on.
            instance.entity_type = ctype_instance
            instance.save()

@receiver(post_save, sender=LocalResource)
def localresource_post_save(sender, **kwargs):
    """
    When a :class:`.LocalResource` is saved, we will attempt to extract any
    indexable content from its associated file (if there is one).
    """

    instance = kwargs.get('instance', None)
    logger.debug(
        'post_save signal for LocalResource, instance: {0}'.format(instance))
    
    # Only attempt to extract content if the instance has a file associated
    #  with it, and indexable_content has not been set.
    if hasattr(instance.file, 'url') and not instance.indexable_content:
        # TODO: Celery-ify.
        content.handle_content(instance)

# TODO: list for RemoteResource post_save and try to get text via request and
# BeautifulSoup.text
