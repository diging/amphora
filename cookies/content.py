from django.core.files import File
from django.db.models.fields.files import FieldFile
from django.db import IntegrityError
from django.db.models import Q

import slate
import magic
from bs4 import BeautifulSoup
import zipfile
from uuid import uuid4
import mimetypes
import os

from cookies.models import *
from cookies.ingest import read

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


def pdf_extract(file):
    return u'\n\n'.join([page.decode('utf-8') for page in slate.PDF(file)])


def soup_extract(file):
    return BeautifulSoup(file.read()).get_text()


def _handle_resource(resource):
    pass


def _resources_from_zip(file, type_instance):
    # The user has uploaded a zip file.
    # TODO: handle exceptions (e.g. not a zip file).
    z = zipfile.ZipFile(file)

    resources = []

    # Each file will result in a new Resource.
    for name in z.namelist():

        # Some archives have odd extra files, so we'll skip those.
        if name.startswith('._'):
            continue

        # We need a filepointer to attach the file to the new Resource.
        fpath = z.extract(name, '/tmp/')
        fname = fpath.split('/')[-1]

        # Skip directories.
        if os.path.isdir(fpath):
            continue

        resources.append({
            'file': fpath,
            'name': fname,
            'uuid': unicode(uuid4()),
            'type': type_instance,
        })
    return resources


def _get_target(v):
    valueTypes = {
        'int': IntegerValue,
        'str': StringValue,
        'unicode': StringValue,
        'float': FloatValue,
        'datetime': DateTimeValue,
    }
    if type(v) is unicode:
        tname = v.split('/')[-1].split('#')[-1]
    else:
        tname = v

    qs = Resource.objects.filter(Q(name=tname) | Q(name=v) | Q(uri=v))
    if qs.count() > 0:
        return qs.first()
    else:
        type_name = type(v).__name__
        if type_name in valueTypes:
            qs = valueTypes[type_name].objects.filter(name=v)
            if qs.count() > 0:
                return qs.first()
            return valueTypes[type_name].objects.create(name=v)


def handle_bulk(file, form_data):

    # User can indicate a default Type to assign to each new Resource.
    default_type = form_data.get('default_type', None)

    resources = read(file)

    if not resources:
        resources = _resources_from_zip(file, default_type_instance)

    # User can indicate that files that share names with existing resources
    #  should be ignored.
    bail_on_duplicate = form_data.get('ignore_duplicates', False)

    collection_name = form_data['name']
    collection = Collection.objects.create(name=collection_name)

    # Each file will result in a new Resource.
    for resource in resources:
        name = resource.__dict__.get('name', unicode(uuid4()))
        # First, try to create a Resource using the filename alone.
        try:
            localresource = Resource(name=name)
            localresource.save()

        # If that doesn't work, add the partial random UUID to the end
        #  of the filename.
        except IntegrityError:
            # ...unless the user has chosen to ignore duplicates.
            if bail_on_duplicate:
                continue

            localresource = Resource(name=name + u' - ' + unicode(uuid4()))
            localresource.save()

        fpaths = resource.__dict__.get('file', None)
        if fpaths:
            if type(fpaths) is not list:
                fpaths = [fpaths]
            for fpath in fpaths:
                _, fname = os.path.split(fpath)

                with open(fpath, 'r') as f:
                    # Now we associate the file, and save the Resource again.
                    contentResource = Resource.objects.create(
                        name=fname,
                        content_resource=True,
                        processed=True
                    )
                    contentResource.file.save(fname, File(f), True)
                    content_type, content_encoding = mimetypes.guess_type(contentResource.file.name)
                    contentRelation = ContentRelation.objects.create(
                        for_resource=localresource,
                        content_resource=contentResource,
                        content_type=content_type,
                        content_encoding=content_encoding,
                    )

        # If the user has selected a default type for these resources,
        #  load and assign it.
        if default_type:
            localresource.type = default_type
        localresource.save()

        collection.resources.add(localresource)

        for k, v in resource.__dict__.iteritems():
            if k in ['file', 'name']:
                continue
            name = k.split('/')[-1].split('#')[-1]
            predicate, _ = Field.objects.get_or_create(uri=k,
                                                       defaults={'name': name})

            if type(v) is list:
                for subv in v:
                    if type(subv) is tuple:
                        pass
                    else:
                        name = subv.split('/')[-1].split('#')[-1]
                        predicate, _ = Field.objects.get_or_create(uri=subv, defaults={'name': name})
                        target = _get_target(subv)
                        Relation.objects.create(source=localresource,
                                                predicate=predicate,
                                                target=target)

            else:
                target = _get_target(v)
                if not target:
                    continue

                relation = Relation.objects.create(source=localresource,
                                                   predicate=predicate,
                                                   target=target)
