from __future__ import absolute_import

from celery import shared_task

from cookies import content, giles
from cookies.models import *


@shared_task
def handle_content(obj, commit=True):
    return content.handle_content(obj, commit)


@shared_task
def handle_bulk(file_path, form_data, file_name):
    return content.handle_bulk(file_path, form_data, file_name)


@shared_task
def send_to_giles(file_obj, creator, resource=None, public=True):
    return giles.send_to_giles(file_obj, creator, resource=resource,
                               public=public)
