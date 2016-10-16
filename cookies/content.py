from django.conf import settings
from django.core.files import File
from django.db.models.fields.files import FieldFile
from django.db import IntegrityError
from django.db.models import Q

from bs4 import BeautifulSoup
from uuid import uuid4
import mimetypes, jsonpickle, os, zipfile, magic, urllib

from cookies.models import *
from cookies.ingest import read
from cookies import giles, authorization
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
    if type(v) is unicode:    # TODO: what is this for?
        tname = v.split('/')[-1].split('#')[-1]
    else:
        tname = v

    qs = Resource.objects.filter(Q(name=tname) | Q(name=v) | Q(uri=v))
    if qs.count() > 0:
        return qs.first()
    else:
        value = jsonpickle.encode(v)
        qs = Value.objects.filter(_value=value)
        if qs.count() > 0:
            return qs.first()
        return Value.objects.create(_value=value)


def _process_people(field, data, entity_type, creator):
    entities = []
    for surname, forename in data:
        if surname.startswith('http'):
            entity = _find_entity(field, surname)
            if not entity:
                entity = ConceptEntity.objects.create(name=surname, uri=surname, entity_type=entity_type, created_by=creator)
        else:
            entity = ConceptEntity.objects.create(name=u', '.join([surname, forename]), entity_type=entity_type, created_by=creator)
        entities.append(entity)
    return entities


def _process_ispartof(field, data, creator):
    IDENTIFIER = Field.objects.get(uri='http://purl.org/dc/elements/1.1/identifier')
    TITLE = Field.objects.get(uri='http://purl.org/dc/elements/1.1/title')
    TYPE = Field.objects.get(uri='http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    entity = None
    name = None
    uri = None
    entity_type = None
    field_data = []

    if type(data) is list and len(data) > 1 and type(data[0]) is not tuple:
        data = data[1]
    for k, v in data:
        field = _find_field(k)
        if field == IDENTIFIER:
            entity = _find_entity(k, v)
            uri = v
        elif field == TITLE:
            name = v
        elif field == TYPE:
            entity_type = _find_type(v)
        else:
            field_data.append((field, v))

    if entity is None:
        uu = str(uuid4())
        entity = ConceptEntity.objects.create(
            name=name if name else uu,
            uri=uri if uri else uu,
            entity_type=entity_type,
            created_by=creator,
        )

    for field, value in field_data:
        target = _find_entity(field, value)
        if target is None:
            target = Value.objects.create(_value=jsonpickle.encode(value))
        Relation.objects.create(source=entity, predicate=field, target=target, created_by=creator)

    return entity


def _find_entity(key, value):
    search_models = [
        (Type, 'uri'),
        (ConceptEntity, 'uri'),
        (Resource, 'uri'),
        (Resource, 'name'),
    ]
    for model, field in search_models:
        try:
            return model.objects.get(**{field: value})
        except model.DoesNotExist:
            continue


def _find_field(key):
    try:
        return Field.objects.get(uri=key)
    except Field.DoesNotExist:
        return key


def _find_type(key):
    try:
        return Type.objects.get(uri=key)
    except Type.DoesNotExist:
        return key


def _cast_value(value):
    if type(value) not in [str, unicode]:
        return value

    for coercion in [iso8601.parse_date, int, float]:
        try:
            return coercion(value)
        except:
            continue
    return value


def _process_metadata(metadata, resource, creator):
    """
    Translate key/value data in ``resource`` into JARS model.
    """
    CREATOR = Field.objects.get(uri='http://purl.org/dc/terms/creator')
    AUTHOR,_ = Field.objects.get_or_create(uri='http://purl.org/net/biblio#authors', defaults={'name': 'authors'})
    ISPARTOF = Field.objects.get(uri='http://purl.org/dc/terms/isPartOf')
    PERSON = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Person')
    TITLE = Field.objects.get(uri='http://purl.org/dc/elements/1.1/title')
    IDENTIFIER = Field.objects.get(uri='http://purl.org/dc/elements/1.1/identifier')
    TYPE = Field.objects.get(uri='http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    ZTYPE, _ = Field.objects.get_or_create(uri='http://www.zotero.org/namespaces/export#itemType')


    entity_type = None


    def _process_keypair(key, value, creator):
        value = _cast_value(value)

        # If we are on an inner recursion step, ``key`` will already be
        #  resolved to a Field instance.
        if type(key) is not Field:
            if key in ['name', 'entity_type', 'file']:
                return
            if key in ['uri', 'url']:
                metadata.append((key, value))
                return

            key = _find_field(key)
            if type(key) is not Field:  # Could not find a field; create one!
                key_name = key.split('/')[-1].split('#')[-1]
                if key_name in ['link', 'type']:
                    metadata.append((key_name, value))
                    return

                if '#' in key:
                    schema_uri = key.split('#')[0] + '#'
                else:
                    schema_uri = u'/'.join(key.split('/')[:-1]) + u'#'

                # This is kind of hacky, but we need a prefix.
                prefix = ''.join([c for c in schema_uri.replace('http://', '').replace('www.', '').split('.')[0] if c not in 'aeiouy'])
                schema, _ = Schema.objects.get_or_create(uri=schema_uri, defaults={'prefix': prefix, 'name': schema_uri})
                key = Field.objects.create(name=key_name.title(), uri=key, schema=schema, namespace=schema_uri)


        if key in [CREATOR, AUTHOR]:
            for creator in _process_people(key, value, PERSON, creator):
                metadata.append((CREATOR, creator))
        elif key == ISPARTOF:
            value = _process_ispartof(key, value, creator)
            metadata.append((key, value))
        elif key in [TYPE, ZTYPE]:
            entity_type = _find_type(value)
            if type(entity_type) is not Type:
                entity_type = Type.objects.create(**{
                    'name': value.split('/')[-1].split('#')[-1],
                    'uri': value
                })
            metadata.append((TYPE, entity_type))

        elif type(value) in [str, unicode] and key not in [TITLE]:
            found = _find_entity(key, value)
            if found:
                value = found
            else:
                if value.startswith('http'):
                    value = Resource.objects.create(name=value, uri=value, created_by=creator)
                else:
                    value = Value.objects.create(_value=jsonpickle.encode(value))
            metadata.append((key, value))
        elif type(value) is list:
            for elem in value:      # Recurse.
                _process_keypair(key, elem, creator)
        else:
            value = Value.objects.create(_value=jsonpickle.encode(value))
            metadata.append((key, value))

    for key, value in resource:
        _process_keypair(key, value, creator)

    return metadata


def _create_content_resource(localresource, form_data, content_resource_data,
                             loc, fpath, fname):
    creator = form_data.get('created_by')
    contentResource = Resource.objects.create(
        name=fname,
        content_resource=True,
        processed=True,
        public=form_data.get('public'),
        created_by=creator,
    )

    cr_data = {
        'for_resource': localresource,
        'content_resource': contentResource,
        'created_by': creator,
    }
    if loc == 'local':
        try:
            with open(fpath, 'r') as f:
                contentResource.file.save(fname, File(f), True)
                content_type, content_encoding = mimetypes.guess_type(contentResource.file.name)
            cr_data.update({
                'content_type': content_type,
                'content_encoding': content_encoding,
            })
        except:
            pass
    elif loc == 'remote':
        contentResource.location = fpath

    contentRelation = ContentRelation.objects.create(**cr_data)
    for field, target in content_resource_data:
        if type(field) is not Field:
            continue
        Relation.objects.create(**{
            'source': contentResource,
            'predicate': field,
            'target': target,
            'public': form_data.get('public'),
            'created_by': creator,
        })
    add_creation_metadata(contentResource, creator)
    contentResource.save()
    return contentResource


def _create_resource_for_upload(file_name, public, creator):
    """
    """
    upload_resource_data = {
        'name': file_name,
        'public': public,
        'created_by': creator,
        'content_resource': True,
    }
    if file_name.endswith('.zip'):
        upload_resource_data.update({'content_type': 'application/zip'})
    elif file_name.endswith('.rdf'):
        upload_resource_data.update({'content_type': 'application/rdf+xml'})
    return Resource.objects.create(**upload_resource_data)


def _get_or_create_collection(form_data, public, creator):
    collection = form_data.get('collection', None)
    collection_name = form_data.get('name', None)
    if not collection:
        collection = Collection.objects.create(**{
            'name': collection_name,
            'created_by': creator,
            'public': public
        })
        add_creation_metadata(collection, creator)
    return collection


def _get_content_resources(resource, creator):
    file_data = getattr(resource, 'file', [])
    content_resources = []
    if len(file_data) > 0:
        if type(file_data[0]) is list:
            for fdata in file_data:
                content_metadata = []
                content_resources.append(_process_metadata(content_metadata, fdata, creator))
        else:
            content_metadata = []
            content_resources.append(_process_metadata(content_metadata, file_data, creator))
    return content_resources


def handle_bulk(file_path, form_data, file_name):
    TYPE = Field.objects.get(uri='http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    SOURCE = Field.objects.get(uri='http://purl.org/dc/terms/source')

    public = form_data.get('public')
    creator = form_data.get('created_by')

    # The uploaded file itself should be stored.
    upload = _create_resource_for_upload(file_name, public, creator)

    resources = read(file_path)
    if not resources:
        resources = _resources_from_zip(file_path, default_type_instance)

    # User can indicate that files that share names with existing resources
    #  should be ignored.
    bail_on_duplicate = form_data.get('ignore_duplicates', False)

    # The user can either add these new records to an existing collection, or
    #  create a new one.
    collection = _get_or_create_collection(form_data, public, creator)

    # We want to be able to recall that this bulk upload was a/the source for
    #  this collection.
    Relation.objects.create(source=collection, predicate=SOURCE, target=upload, created_by=creator)

    # Each file will result in a new Resource.
    for resource in resources:
        name = resource.__dict__.get('name', unicode(uuid4()))

        # These will be used to populate the Resource model itself.
        resource_data = {
            'name': name,
            'public': public,
            'created_by': creator,
        }

        # These are the metadata that will be used to create Relations later on,
        #  as opposed to the field values on the Resource model itself.
        resource_metadata = _process_metadata([], resource.__dict__.items(), creator)

        # These may be remote (i.e. just URLs), local (i.e. with a file), or
        #  both.
        content_resources = _get_content_resources(resource, creator)

        # User can indicate a default Type to assign to each new Resource.
        default_type = form_data.get('default_type', None)

        entity_type = None
        for key, value in resource_metadata:
            if key == TYPE:
                entity_type = value
                break
        if entity_type:
            resource_data.update({'entity_type': entity_type})
        elif default_type:
            # If the user has selected a default type for these resources,
            #  load and assign it.
            resource_data.update({'entity_type': default_type})

        uri = resource.__dict__.get('uri', None)
        if uri:
            resource_data.update({'uri': uri})

        # Here we create the new Resource instance from the current Zotero
        #  record.
        localresource = Resource.objects.create(**resource_data)
        add_creation_metadata(localresource, creator)

        # Handle content.
        for content_resource_data in content_resources:
            try:
                fpaths = filter(lambda e: e[0] == 'link', content_resource_data)
                fpaths = [fpath[1] for fpath in fpaths]
                fnames = [os.path.split(fpath)[1] for fpath in fpaths]

            except IndexError:
                fpaths = []

            try:
                urls = filter(lambda e: e[0] == 'url', content_resource_data)
                urls = [url[1] for url in urls]
                ufnames = [url.split('/')[-1].split('?')[0] for url in urls]
            except IndexError:
                urls = []

            if len(fpaths) == 0 and len(urls) == 0:
                continue    # No content is available for this Resource.

            for fpath, fname in zip(fpaths, fnames):
                # Zotero escapes local file paths as if they were URLs.
                fpath = urllib.unquote(fpath)
                try:
                    fname_has_extension = fname[-4] == '.' or fname[-5] == '.'
                except IndexError:
                    fname_has_extension = False
                if (fpath[-4] == '.' or fpath[-5] == '.') and not (fname_has_extension):
                    fname += '.' + fpath.split('.')[-1]
                _create_content_resource(localresource, form_data, content_resource_data, 'local', fpath, fname)
            for url, fname in zip(urls, ufnames):
                fname = fname if fname else url
                _create_content_resource(localresource, form_data, content_resource_data, 'remote', url, fname)

        collection.resources.add(localresource)

        created_by = form_data.get('created_by')
        for field, target in resource_metadata:
            if type(field) is not Field:
                continue

            Relation.objects.create(source=localresource,
                                    predicate=field,
                                    target=target,
                                    public=form_data.get('public'),
                                    created_by=created_by,)
        authorization.update_authorizations(Collection.DEFAULT_AUTHS, created_by, collection, propagate=True)

    return {'view': 'collection', 'id': collection.id}
