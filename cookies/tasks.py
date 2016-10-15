from __future__ import absolute_import

from django.conf import settings

from celery import shared_task

from cookies import content, giles, authorization
from cookies.models import *
from concepts import authorities
from cookies.exceptions import *
logger = settings.LOGGER


@shared_task
def handle_content(obj, commit=True):
    """
    Attempt to extract plain text from content files associated with a
    :class:`.Resource` instance.

    Parameters
    ----------
    obj : :class:`.Resource`
    commit : bool
    """
    return content.handle_content(obj, commit)


@shared_task
def handle_bulk(file_path, form_data, file_name):
    """
    Process resource data in a RDF document.

    Parameters
    ----------
    file_path : str
        Local path to a RDF document, or a ZIP file containing a Zotero RDF
        export (with files).
    form_data : dict
        Valid data from a :class:`cookies.forms.BulkResourceForm`\.
    file_name : str
        Name of the target file at ``file_path``\.
    """
    return content.handle_bulk(file_path, form_data, file_name)


@shared_task
def send_to_giles(file_name, creator, resource=None, public=True):
    result = giles.send_to_giles(file_name, creator,
                                 resource=resource,
                                 public=public)
    status_code, response_data, session = result

    try:
        check_giles_upload.delay(resource, creator, response_data['id'],
                                 response_data['checkUrl'], session.id)
    except ConnectionError:
        logger.error("send_to_giles: there was an error connecting to"
                     " the redis message passing backend.")


@shared_task(max_retries=None, default_retry_delay=10)
def check_giles_upload(resource, creator, upload_id, checkURL, session_id):

    status, content = giles.check_upload_status(creator, checkURL)
    if status == 202:    # Accepted.
        logger.debug('Accepted, retrying in 30 seconds')
        raise check_giles_upload.retry()
    giles.process_file_upload(resource, creator, content, session_id)


@shared_task
def update_authorizations(auths, user, obj, by_user=None):
    authorization.update_authorizations(auths, user, obj, by_user=by_user)


@shared_task
def search_for_concept(lemma):
    authorities.searchall(lemma)
