from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.conf import settings

from cookies.models import *
from cookies import giles
from cookies import content
from cookies.tasks import handle_content, send_to_giles
from cookies.exceptions import *
logger = settings.LOGGER

import mimetypes


@receiver(post_save, sender=User)
def new_users_are_inactive_by_default(sender, **kwargs):
    instance = kwargs.get('instance', None)
    if instance and kwargs.get('created', False):
        logger.debug('%s is a new user; setting inactive by default' %\
                     instance.username)
        instance.is_active = False
        instance.save()


@receiver(post_save, sender=ContentRelation)
def send_all_files_to_giles(sender, **kwargs):    # Hey, that rhymes!
    """
    Create a :class:`.GilesUpload` instance to indicate that an upload should
    be performed.
    """
    instance = kwargs.get('instance', None)
    logger.debug('received post_save for ContentRelation %i' % instance.id)

    if not instance.content_resource.file:
        return

    logger.debug('create giles upload for %i' % instance.id)
    giles.create_giles_upload(instance.for_resource.id, instance.id,
                              instance.for_resource.created_by.username,
                              delete_on_complete=settings.DELETE_LOCAL_FILES)


# @receiver(post_save, sender=ConceptEntity)
def conceptentity_post_save(sender, **kwargs):
    """
    When a :class:`.ConceptEntity` is saved, we will attempt to assign an
    appropriate :class:`.Type` based on its related :class:`.Concept`\.
    """

    instance = kwargs.get('instance', None)

    # logger.debug(
    #     'post_save signal for ConceptEntity, instance: {0}'.format(instance))

    # If this ConceptEntity already has an entity_type, there is nothing to do.
    if instance.entity_type is None:

        # Determine the concepts.Type of its associated concepts.Concept.
        type_instance = getattr(instance.concept, 'typed', None)

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
