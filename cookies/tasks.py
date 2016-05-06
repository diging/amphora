from __future__ import absolute_import

from celery import shared_task

from cookies import content


@shared_task
def handle_content(obj, commit=True):
    content.handle_content(obj, commit)
    return



@shared_task
def handle_bulk(file, form_data):
    content.handle_bulk(file, form_data)
    return
