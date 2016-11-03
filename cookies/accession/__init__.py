import importlib, mimetypes, copy, os
from cookies.models import *
from uuid import uuid4
from cookies import metadata
from django.conf import settings
logger = settings.LOGGER

from itertools import repeat, imap



class IngesterFactory(object):
    def get(self, path):
        path_parts = path.split('.')
        class_name = path_parts[-1]
        import_source = '.'.join(path_parts[:-1])

        # TODO: use importlib instead.
        module = __import__(import_source, fromlist=[class_name])
        return IngestWrapper(getattr(module, class_name))


class IngestManager(object):
    model_fields = [
        'entity_type',
        'created_by',
        'name',
        'uri',
        'part_of',
    ]
    def __init__(self, wraps):
        self.resource_data = {}
        self.wraps = wraps

    def set_resource_defaults(self, **resource_data):
        self.resource_data = resource_data

    def _handle_uri_ref(self, predicate, data):
        if type(data) not in [str, unicode] or predicate == 'uri':
            return data
        if not data.startswith('http'):
            return data
        if predicate == 'entity_type':
            return metadata.field_or_type_from_uri(data, Type)

    def _get_or_create_entity(self, uri, entity_type=None, **defaults):
        instance = None
        for model in [Resource, Collection, ConceptEntity]:
            try:
                instance = model.objects.get(uri=value)
                if entity_type and instance.entity_type and instance.entity_type != entity_type:
                    continue
            except model.DoesNotExist:
                continue
        if instance is None:
            instance = ConceptEntity.objects.create(uri=uri, **defaults)
            if entity_type:
                instance.entity_type = entity_type
                instance.save()
        return instance

    def create_relations(self, predicate, values, resource):
        predicate = metadata.field_or_type_from_uri(predicate)
        values = [values] if not isinstance(values, list) else values
        n = len(values)
        map(self.create_relation, repeat(predicate, n),
            values, repeat(resource, n))

    def create_relation(self, predicate, value, resource):
        defaults = copy.copy(self.resource_data)
        if type(value) is dict:   # This is an entity with relations of its own.
            uri = value.pop('uri', None)
            entity_type = value.pop('entity_type', None)
            name = value.pop('name', None)
            if entity_type:
                entity_type = metadata.field_or_type_from_uri(entity_type, Type)
            if not name:
                name = 'Unnamed %s: %s' % (entity_type.name, unicode(uuid4()))
            defaults.update({'name': name})

            if uri:
                instance = self._get_or_create_entity(value, entity_type,
                                                      **defaults)
            else:
                instance = ConceptEntity.objects.create(entity_type=entity_type,
                                                        **defaults)
            if len(value) > 0:
                n = len(value)
                map(self.create_relations, value.keys(), value.values(),
                    repeat(instance, n))

        elif type(value) in [str, unicode] and value.startswith('http'):
            instance = self._get_or_create_entity(value)
        else:
            instance = Value.objects.create()
            instance.name = value
            instance.save()
        relation = Relation.objects.create(**{
            'source': resource,
            'predicate': predicate,
            'target': instance,
        })

    def create_resource(self, resource_data, relation_data):
        data = copy.copy(self.resource_data)
        data.update(resource_data)
        file_path = data.pop('link', None)
        location = data.pop('url', None)
        resource = Resource.objects.create(**data)

        if file_path:
            try:
                _, fname = os.path.split(file_path)
                with open(file_path, 'r') as f:
                    resource.file.save(fname, File(f), True)
            except IOError:
                logger.debug('Could not find file at %s; skipping.' % file_path)
                pass
        if location:
            print 'location!!', location
            resource.location = location
            resource.save()
        map(self.create_relations, relation_data.keys(), relation_data.values(),
            repeat(resource, len(relation_data)))
        return resource

    def create_content_relation(self, content_resource, resource, content_type=None):
        data = copy.copy(self.resource_data)
        data.update({
            'for_resource': resource,
            'content_resource': content_resource,
        })
        if content_type:
            data.update({'content_type': content_type})
        elif content_resource.is_local:
            content_type, content_encoding = mimetypes.guess_type(content_resource.file.name)
            data.update({
                'content_type': content_type,
                'content_encoding': content_encoding,
            })
        print 'content relation', content_resource, ' | ', resource
        return ContentRelation.objects.create(**data)

    def create_content_resource(self, content_data, resource):
        content_type = content_data.pop('content_type', None)

        resource_data = {}
        relation_data = {}
        for key, value in content_data.items():
            if key in self.model_fields + ['link', 'url']:
                resource_data[key] = value if key == 'url' else self._handle_uri_ref(key, value)
            else:
                relation_data[key] = value

        resource_data.update({'content_resource': True})
        print resource_data

        content_resource = self.create_resource(resource_data, relation_data)
        self.create_content_relation(content_resource, resource, content_type)

    def get_or_create_predicate(self, pred_data):
        """

        Parameters
        ----------
        pred_data : dict

        Returns
        -------
        :class:`.Field`
        """
        uri = predicate_data.pop('uri', None)
        if uri is None:
            field = Field.objects.create(**pred_data)
        else:
            field, _ = Field.objects.get_or_create(uri=uri, defaults=pred_data)
        return field

    def __iter__(self):
        return self

    def next(self):
        raw_data = self.wraps.next()
        resource_data = {}
        relation_data = {}
        file_data = None
        for key, value in raw_data.iteritems():
            if key in self.model_fields:
                # We have to assume here that there is only one value for
                #  each of these fields.
                resource_data[key] = self._handle_uri_ref(key, value[0])
            elif key == 'file':
                file_data = value
            else:
                relation_data[key] = value

        resource = self.create_resource(resource_data, relation_data)

        if file_data:
            n = len(file_data)
            map(self.create_content_resource, file_data, repeat(resource, n))

        return resource


class IngestWrapper(object):
    wrapper = IngestManager

    def __init__(self, wraps):
        self.wraps = wraps

    def __call__(self, *args, **kwargs):
        return self.wrapper(self.wraps(*args, **kwargs))


class Import(object):
    def __init__(self, obj):
        self.obj = stream

    def next(self):
        """
        Yield data for a single Resource.
        """
        raise NotImplemented('Subclass should implement next()')
