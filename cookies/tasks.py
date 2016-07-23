from __future__ import absolute_import

from celery import shared_task

from cookies import content


@shared_task
def handle_content(obj, commit=True):
    return content.handle_content(obj, commit)


@shared_task
def handle_bulk(file, form_data):
    return content.handle_bulk(file, form_data)
