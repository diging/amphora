# TODO: Celery-ify.

from django.core.files import File
from django.db.models.fields.files import FieldFile
from django.db import IntegrityError

import slate
import magic
from bs4 import BeautifulSoup
import zipfile
from uuid import uuid4


from .models import *

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
    mime_type = magic.from_file(obj.file.path, mime=True)

    if indexable(mime_type):
        with open(obj.file.path, 'r') as f:
            if mime_type == 'text/plain':
                obj.indexable_content = f.read()
            elif mime_type in pdf_mime_types:
                obj.indexable_content = pdf_extract(f)
            elif mime_type in xml_mime_types:
                obj.indexable_content = soup_extract(f)
            else:
                obj.indexable_content = ' '

        if commit:
            obj.save()

def indexable(mime_type):
    if mime_type not in binary_mime_types:
        return True
    return False

def pdf_extract(file):
    return slate.PDF(file)

def soup_extract(file):
    return BeautifulSoup(file.read()).get_text()


def handle_bulk(file, form):
    # The user has uploaded a zip file.
    # TODO: handle exceptions (e.g. not a zip file).
    z = zipfile.ZipFile(file)
    
    # User can indicate a default Type to assign to each new Resource.
    default_type = form.cleaned_data['default_type']

    # User can indicate that files that share names with existing resources
    #  should be ignored.
    bail_on_duplicate = form.cleaned_data['ignore_duplicates']

    # Each file will result in a new LocalResource.
    for name in z.namelist():
    
        # Some archives have odd extra files, so we'll skip those.
        if not name.startswith('._'):
        
            # We need a filepointer to attach the file to the new LocalResource.
            fpath = z.extract(name, '/tmp/')
            fname = fpath.split('/')[-1]
            with open(fpath, 'r') as f:
                
                # This partial random UUID will help us to create a new unique
                #  name if we encounter a duplicate.
                _uuid = str(uuid4())[-5:]
                
                # First, try to create a LocalResource using the filename alone.
                try:
                    resource = LocalResource(name=name)
                    resource.save()
                
                # If that doesn't work, add the partial random UUID to the end
                #  of the filename.
                except IntegrityError:
                
                    # ...unless the user has chosen to ignore duplicates.
                    if bail_on_duplicate:
                        continue
                    
                    resource = LocalResource(name=name + _uuid)
                    resource.save()
                    
                # Now we associate the file, and save the LocalResource again.
                resource.file.save(fname, File(f), True)
                
                # If the user has selected a default type for these resources,
                #  load and assign it.
                if default_type:
                    resource.entity_type = Type.objects.get(pk=default_type)
                    resource.save()

