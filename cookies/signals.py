from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from cookies.models import *
from cookies import content
from tasks import handle_content, send_to_giles, update_authorizations

import logging
logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel('DEBUG')


@receiver(post_save, sender=Collection)
@receiver(post_save, sender=Resource)
@receiver(post_save, sender=Relation)
@receiver(post_save, sender=ConceptEntity)
def set_default_auths_for_collection(sender, **kwargs):
    instance = kwargs.get('instance', None)
    created = kwargs.get('created', False)
    if created and instance.created_by:
        update_authorizations.delay(sender.DEFAULT_AUTHS, instance.created_by,
                                    instance, by_user=instance.created_by)


@receiver(post_save, sender=User)
def new_users_are_inactive_by_default(sender, **kwargs):
    instance = kwargs.get('instance', None)
    if instance and kwargs.get('created', False):
        logger.debug('%s is a new user; setting inactive by default' % instance.username)
        # instance.is_active = False
        # instance.save()


# TODO: enable this when Giles is ready for asynchronous uploads.
#@receiver(post_save, sender=ContentRelation)
def send_pdfs_and_images_to_giles(sender, **kwargs):
    instance = kwargs.get('instance', None)
    print 'received post_Save for ContentRelation %i' % instance.id

    if instance and kwargs.get('created', False) and instance.content_resource.file.name is not None:
        # PDFs and images should be stored in Digilib via Giles.
        if instance.content_resource.content_type in ['image/png', 'image/tiff', 'image/jpeg', 'application/pdf']:
            logger.debug('%s has a ContentResource; sending to Giles' % instance.content_resource.name)
            send_to_giles.delay(instance.content_resource.file.name,
                                instance.for_resource.created_by, resource=instance.for_resource,
                                public=instance.for_resource.public)#delay


@receiver(post_save, sender=ConceptEntity)
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


# @receiver(post_save, sender=Resource)
def resource_post_save(sender, **kwargs):
    """
    When a :class:`.Resource` is saved, we will attempt to extract any
    indexable content from its associated file (if there is one).
    """

    instance = kwargs.get('instance', None)
    # logger.debug(
    #     'post_save signal for Resource, instance: {0}'.format(instance))

    if instance.processed:
        return

    # Only attempt to extract content if the instance has a file associated
    #  with it, and indexable_content has not been set.
    if instance.file._committed and not instance.indexable_content:
        handle_content.delay(instance)

# TODO: list for RemoteResource post_save and try to get text via request and
# BeautifulSoup.text


# class ResourceSignalProcessor(signals.RealtimeSignalProcessor):
#     def handle_save(self, sender, instance, **kwargs):
#         """
#         Given an individual model instance, determine which backends the
#         update should be sent to & update the object on those backends.
#         """
#         if hasattr(instance, 'content_resource'):
#             if instance.content_resource:
#                 return
#
#         using_backends = self.connection_router.for_write(instance=instance)
#
#         for using in using_backends:
#             try:
#                 index = self.connections[using].get_unified_index().get_index(sender)
#                 index.update_object(instance, using=using)
#             except NotHandled:
#                 # TODO: Maybe log it or let the exception bubble?
#                 pass
