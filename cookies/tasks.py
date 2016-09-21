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
def send_to_giles(file_name, creator, resource=None, public=True):
    status_code, response_data, session = giles.send_to_giles(file_name, creator,
                                                              resource=resource,
                                                              public=public)
    check_giles_upload.delay(resource, creator, response_data['id'], response_data['checkUrl'], session.id)


@shared_task(max_retries=None, default_retry_delay=10)
def check_giles_upload(resource, creator, upload_id, checkURL, session_id):

    status, content = giles.check_upload_status(creator, checkURL)
    if status == 202:    # Accepted.
        print 'Accepted, retrying in 30 seconds'
        raise check_giles_upload.retry()
    print content
    giles.process_file_upload(resource, creator, content, session_id)
