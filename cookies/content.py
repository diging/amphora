"""
DEPRECATED. This module is on the way out. What's left is here for reference
purposes only, and will be deleted in the not-so-distant future.
"""

from django.conf import settings
from django.core.files import File
from django.db.models.fields.files import FieldFile
from django.db import IntegrityError
from django.db.models import Q

from bs4 import BeautifulSoup
from uuid import uuid4
import mimetypes, jsonpickle, os, zipfile, magic, urllib

from cookies.models import *
from cookies import giles, authorization, operations
from cookies.operations import add_creation_metadata

logger = settings.LOGGER


xml_mime_types = [
    'application/xml', 'text/xml', 'text/html', 'text/x-server-parsed-html',
    'text/webviewhtml'
    ]
binary_mime_types = [
    'application/macbinary', 'application/x-binary', 'application/x-macbinary',
    'application/octet-stream', 'application/mac-binary',
    ]

pdf_mime_types = [
    'application/pdf',
    ]


def handle_content(obj, commit=True):
    """
    Attempt to extract text content that can be indexed.
    """

    for contentRelation in obj.content.all():
        if indexable(contentRelation.content_type):
            if contentRelation.content_type == 'text/plain':
                obj.indexable_content += contentRelation.content_resource.file.read()
            elif contentRelation.content_type in pdf_mime_types:
                obj.indexable_content += pdf_extract(contentRelation.content_resource.file)
            elif contentRelation.content_type in xml_mime_types:
                obj.indexable_content += soup_extract(contentRelation.content_resource.file)
            else:
                obj.indexable_content += ' '
    if commit:
        obj.processed = True
        obj.save()


def indexable(mime_type):
    if mime_type not in binary_mime_types:
        return True
    return False


# def pdf_extract(file):
#     return u'\n\n'.join([page.decode('utf-8') for page in slate.PDF(file)])


def soup_extract(file):
    return BeautifulSoup(file.read()).get_text()
