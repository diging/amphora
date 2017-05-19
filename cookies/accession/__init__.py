from django.conf import settings
from django.core.files import File
from  django.core.exceptions import ObjectDoesNotExist
from django.db.models import QuerySet
from django.db import transaction
from django.utils import timezone

import importlib, mimetypes, copy, os, logging, requests
from cookies.models import *
from uuid import uuid4
from cookies import metadata
from datetime import datetime, timedelta


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(settings.LOGLEVEL)

from itertools import repeat, imap


__part__ = Field.objects.get_or_create(uri='http://purl.org/dc/terms/isPartOf')[0]
__text__ = Type.objects.get_or_create(uri='http://purl.org/dc/dcmitype/Text')[0]
__image__ = Type.objects.get_or_create(uri='http://purl.org/dc/dcmitype/Image')[0]
__document__ = Type.objects.get_or_create(uri='http://xmlns.com/foaf/0.1/Document')[0]


from functools import partial


def provider_token_generator(user, provider):
    try:
        return user.social_auth.get(provider=provider).extra_data.get('access_token')
    except ObjectDoesNotExist:
        raise RuntimeError('User %s has no token for provider %s' % (user.username, provider))


def access_token_generator(user, fallback):
    """
    Get the current auth token for a :class:`.User`\. If the user has no auth
    token, retrieves one and stores it.

    Parameters
    ----------
    user : :class:`django.contrib.auth.User`
    fallback : function
        Method for retrieving a new access token from the remote service.
        Returns an authorization token (str).

    Returns
    -------
    str
        Authorization token for ``user``.
    """

    try:
        ex = timezone.now() - timedelta(minutes=settings.GILES_TOKEN_EXPIRATION)
        if user.giles_token.created > ex:
            return user.giles_token.token
    except (AttributeError, ObjectDoesNotExist):    # RelatedObjectDoesNotExist.
        pass    # Will proceed to retrieve token.


    try:    # Delete the old token first.
        user.giles_token.delete()
    except (AssertionError, ObjectDoesNotExist):
        pass

    token = fallback()
    user.giles_token = GilesToken.objects.create(for_user=user, token=token)
    user.save()
    return user.giles_token.token


class WebRemote(object):
    def get(self, uri, raw=False):
        response = requests.get(uri)
        if raw:
            return response
        return content


def get_remote(external_source, user):
    if external_source == Resource.HATHITRUST:
        from cookies.accession.hathitrust import HathiTrustRemote
        return HathiTrustRemote(settings.HATHITRUST_CLIENT_KEY,
                                settings.HATHITRUST_CLIENT_SECRET,
                                settings.HATHITRUST_CONTENT_BASE,
                                settings.HATHITRUST_METADATA_BASE)
    elif external_source == Resource.GILES:
        from cookies.accession.giles import GilesRemote

        return GilesRemote(settings.GILES_APP_TOKEN, settings.GILES,
                           settings.GILES_DEFAULT_PROVIDER,
                           partial(provider_token_generator, user),
                           partial(access_token_generator, user))

    return WebRemote()


class IngesterFactory(object):
    """
    Used to load a wrapped ingest class to accession new resource data.
    """
    def get(self, path):
        """
        Load an ingest class at ``path``, and wrap it with
        :class:`.IngestWrapper`\.

        Parameters
        ----------
        path : str
            Should be a full (dotted) import path for the ingest class or
            other callable that returns an iterable object that yields
            resource data.

        Returns
        -------
        :class:`.IngestWrapper`
            When called with kwargs, instantiates the ingest class at ``path``
            with those kwargs, and returns an instance of
            :class:`.IngestManager` wrapping the ingest class instance. During
            iteration, the resulting object will draw parsed resource data from
            the wrapped ingest class instance, and return new
            :class:`.Resource` instances created from those data.

        """
        path_parts = path.split('.')
        class_name = path_parts[-1]
        import_source = '.'.join(path_parts[:-1])

        # TODO: use importlib instead.
        module = __import__(import_source, fromlist=[class_name])
        return IngestWrapper(getattr(module, class_name))


class IngestManager(object):
    """
    Wraps ingest class instances to accession parsed data to database models.

    Parameters
    ----------
    wraps : object
        Any iterable that yields resource data. Each datum should be a
        dict-like object. Keys in :prop:`.model_fields` are used to populate
        the :class:`.Resource` instance, and any URI-like keys are treated as
        relations. Remote and local content resource data are expected in
        ``link`` and/or ``url``.
    """
    model_fields = [
        'entity_type',
        'created_by',
        'name',
        'uri',
        'part_of',
        'external_source',
        'location',
        'content_type'
    ]

    def __init__(self, wraps):
        self.resource_data = {}
        self.wraps = wraps

        # To limit the search space for matching entities by URI, the caller
        #  should override or filter these QuerySets directly.
        self.Resource = Resource.objects.all()
        self.Collection = Collection.objects.all()
        self.ConceptEntity = ConceptEntity.objects.all()

        self.collection = None

    def set_collection(self, collection):
        self.collection = collection

    def set_resource_defaults(self, **resource_data):
        """
        Provide default field data for model fields. These will be used when
        creating :class:`.Resource`\, :class:`.Relation`\, and
        :class:`.ContentRelation` instances.

        Parameters
        ----------
        resource_data : kwargs
            Keys should be model field names. E.g. ``created_by``\.
        """
        self.resource_data = {k: v for k, v in resource_data.iteritems()
                              if k in self.model_fields}

    def _handle_uri_ref(self, predicate, data):
        """
        TODO: refactor this.
        """
        if type(data) not in [str, unicode] or predicate == 'uri':
            return data
        if not data.startswith('http'):
            return data
        if predicate == 'entity_type':
            if type(data) is list:
                data = data[0]
            return metadata.field_or_type_from_uri(data, Type)

    def _get_or_create_entity(self, uri, entity_type=None, **defaults):
        """
        Look for a :class:`.Resource`\, :class:`.Collection`\, or
        :class:`.ConceptEntity` with ``uri`` and ``entity_type`` (if provided).
        If not found, create a new :class:`.Concept` with ``defaults``.

        This method uses pre-instantiated QuerySet instances (see
        :meth:`.__init__`\), which allows the search scope to be explicitly
        limited. The caller should filter those QuerySets directly.

        Parameters
        ----------
        uri : str
        entity_type : :class:`.Type`
        defaults : kwargs
            Field data for :class:`.ConceptEntity`\.

        Returns
        -------
        :class:`.Resource`\, :class:`.Collection`\, or :class:`.ConceptEntity`
        """
        instance = None

        for queryset in [self.Resource, self.Collection, self.ConceptEntity]:
            try:
                instance = queryset.get(uri=uri)
                if entity_type and instance.entity_type \
                    and instance.entity_type != entity_type:
                    continue
            except queryset.model.DoesNotExist:
                continue
        if instance is None:
            instance = ConceptEntity.objects.create(uri=uri, **defaults)
            if entity_type:
                instance.entity_type = entity_type
                instance.save()
        return instance

    def create_relations(self, predicate, values, resource):
        """
        Create :class:`.Relation` instances using the ``predicate`` and one or
        more ``values``.

        Parameters
        ----------
        predicate : str
            Should be an URI; will be used to get or create a :class:`.Field`\.
        values : object
            If a list, each item will be treated as a separate relation target.

        """
        if type(predicate) is list:
            predicate = predicate[0]
        predicate = metadata.field_or_type_from_uri(predicate)
        values = [values] if not isinstance(values, list) else values
        n = len(values)
        map(self.create_relation, repeat(predicate, n),
            values, repeat(resource, n))

    def create_relation(self, predicate, value, resource):
        """
        Create a new :class:`.Relation` instance between ``resource`` (source),
        ``predicate``, and ``value`` (target).

        Parameters
        ----------
        predicate : :class:`.Field`
        value : object
            If a dict, will be treated as composite entity data and handled
            accordingly. If a str containing an URI, will attempt to find a
            matching Resource, Collection, or ConceptEntity, or (if not found)
            create a new ConceptEntity. Otherwise, serialized as a Value
            instance.
        resource : model instance
            Usually a :class:`.Resource`\, but this can be an instance of any
            model.

        """
        defaults = copy.copy(self.resource_data)
        defaults.update({'container': resource.container})
        if type(value) is dict:   # This is an entity with relations of its own.
            uri = value.pop('uri', None)
            entity_type = value.pop('entity_type', defaults.get('entity_type', None))


            name = value.pop('name', None)

            if entity_type:
                if type(entity_type) is list:
                    entity_type = entity_type[0]
                entity_type = metadata.field_or_type_from_uri(entity_type, Type)
                defaults.update({'entity_type': entity_type})

            if not name:
                name = 'Unnamed %s: %s' % (entity_type.name, unicode(uuid4()))
            defaults.update({'name': name})

            extra = {k: v for k, v in defaults.iteritems() if k != 'entity_type'}
            if 'container' not in extra:
                extra['container'] = resource.container
            if uri:
                instance = self._get_or_create_entity(value, entity_type, **extra)
            else:
                instance = ConceptEntity.objects.create(**defaults)

            if len(value) > 0:
                n = len(value)
                map(self.create_relations, value.keys(), value.values(),
                    repeat(instance, n))

        elif type(value) in [str, unicode] and value.startswith('http'):
            instance = self._get_or_create_entity(value, container=resource.container)
        else:
            instance = Value.objects.create()
            instance.container = resource.container
            instance.name = value
            instance.save()

        relation = Relation.objects.create(**{
            'source': resource,
            'predicate': predicate,
            'target': instance,
            'container': resource.container,
            'created_by': resource.created_by
        })

    def create_resource(self, resource_data, relation_data, container=None):
        """
        Create a new :class:`.Resource`\.

        If ``link`` is provided in ``resource_data``, a new :class:`.File` will
        be created and associated with the created :class:`.Resource` instance.

        Parameters
        ----------
        resource_data : dict
            All of the keys should be valid field names for :class:`.Resource`\,
            plus (optionally) ``link`` and/or ``url``.
        relation_data : dict
            Keys should be URIs, used to find or create :clas:`.Field`
            instances. Values should be lists of relation targets.

        Returns
        -------
        :class:`.Resource`
        """
        data = copy.copy(self.resource_data)
        data.update(resource_data)
        file_path = data.pop('link', None)
        location = data.pop('url', None)
        uri = data.get('uri')

        part_data = relation_data.pop('parts', None)

        collection = data.pop('collection', None)
        resource = None

        if resource is None:
            try:
                resource = Resource.objects.create(**data)
            except Exception as E:
                print data
                print E
                raise E
        if container is None:
            container = ResourceContainer.objects.create(primary=resource,
                                                         created_by=resource.created_by,
                                                         part_of=self.collection)
        resource.container = container
        resource.save()

        if file_path:
            try:
                _, fname = os.path.split(file_path)
                with open(file_path, 'r') as f:
                    resource.file.save(fname, File(f), True)
            except IOError:
                logger.debug('Could not find file at %s; skipping.' % file_path)
                pass
        if location:
            resource.location = location
            resource.save()

        if part_data is not None:
            for datum in part_data:
                self.create_part(datum, resource)

        map(self.create_relations, relation_data.keys(), relation_data.values(),
            repeat(resource, len(relation_data)))
        return resource

    def create_part(self, datum, resource):
        resource_data, relation_data, file_data = self.separate_field_and_relation_data(datum)
        sort_order = relation_data.pop('sort_order', 0)
        part = self.process(resource_data, relation_data, file_data, container=resource.container)

        __part__ = Field.objects.get_or_create(uri='http://purl.org/dc/terms/isPartOf')[0]
        Relation.objects.create(source=part,
                                predicate=__part__,
                                target=resource,
                                created_by=resource.created_by,
                                container=resource.container,
                                sort_order=sort_order)


    def create_content_relation(self, content_resource, resource,
                                content_type=None):
        """
        Create a new :class:`.ContentRelation` between ``resource`` and
        ``content_resource``.

        Parameters
        ----------
        content_resource : :class:`.Resource`
        resource : :class:`.Resource`
        content_type : str
            Optionally, provide a valid mime-type. If not provided, and
            ``content_resource`` has a ``file``, will attempt to guess the
            type based on file name.

        Returns
        -------
        :class:`.ContentRelation`
        """
        data = copy.copy(self.resource_data)
        data.update({
            'for_resource': resource,
            'content_resource': content_resource,
            'container': resource.container,
        })
        if content_type:    # May have been explicitly provided.
            data.update({'content_type': content_type})
        elif content_resource.is_local:
            # Attempt to guess the content type from the file name. We could
            #  probably be more precise if we looked at the contents of the
            #  file, but that could get costly for large ingests.
            ctype = mimetypes.guess_type(content_resource.file.name)
            if ctype:
                data.update({
                    'content_type': ctype[0],
                    'content_encoding': ctype[1],
                    'container': resource.container
                })
        data.pop('entity_type', None)    # ContentRelation is not an Entity.
        return ContentRelation.objects.create(**data)

    def create_content_resource(self, content_data, resource):
        """
        Create a new :class:`.Resource` with content for ``resource`` using
        ``content_data``.

        Parameters
        ----------
        content_data : dict
            Can contain both model field-data and relation data.
        resource : :class:`.Resource`
            The "master" resource for which the content resource is being
            created.

        """
        content_type = content_data.pop('content_type', None)

        resource_data = {}
        relation_data = {}
        for key, value in content_data.items():
            if key in self.model_fields + ['link', 'url']:
                if key in ['url', 'location']:
                    if value and type(value) is list:
                        value = value[0]
                    if value.startswith('http'):
                        resource_data['is_external'] = True
                    resource_data['location'] = value
                elif key in ['external_source', 'content_type']:
                    resource_data[key] = value
                    if key == 'content_type':
                        content_type = value
                else:
                    self._handle_uri_ref(key, value)
            else:
                relation_data[key] = value
        resource_data.update({
            'content_resource': True,
            'container': resource.container,
        })
        if content_type:
            resource_data['content_type'] = content_type
            relation_data['content_type'] = content_type
        content_resource = self.create_resource(resource_data, relation_data, resource.container)
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

    def __len__(self):
        return len(self.wraps)

    def __iter__(self):
        return self


    def separate_field_and_relation_data(self, raw_data):
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
        return resource_data, relation_data, file_data

    def process(self, resource_data, relation_data, file_data, container=None):
        resource = self.create_resource(resource_data, relation_data, container=container)

        if file_data:
            n = len(file_data)
            map(self.create_content_resource, file_data, repeat(resource, n))
        return resource

    def next(self):
        """
        Yield a :class:`.Resource`\.

        Draw data from the wrapped ingest class via its ``next()`` method.
        """
        raw_data = self.wraps.next()

        with transaction.atomic():
            resource_data, relation_data, file_data = self.separate_field_and_relation_data(raw_data)
            resource = self.process(resource_data, relation_data, file_data)

        return resource


class IngestWrapper(object):
    """
    Wraps ingest classes with :class:`.IngestManager` to support consistent
    accessioning of parsed resource data.

    Child classes can specify an alternate to :class:`.IngestManager` by
    overriding the ``wrapper`` attribute. When called, ``wrapper`` should
    accept a single argument (an ingest class instance), and return an iterable
    that yields :class:`.Resource` instances.

    Parameters
    ----------
    wraps : class
        Ingest class that, when instantiated, behaves as described in
        :class:`.IngestManager`\. Instantiated by :meth:`.__call__`\; to the
        caller this should look just like instantiating ``wraps`` directly.

    """
    wrapper = IngestManager

    def __init__(self, wraps):
        self.wraps = wraps

    def __call__(self, *args, **kwargs):
        """
        Instantiate
        """
        return self.wrapper(self.wraps(*args, **kwargs))


class Import(object):
    def __init__(self, obj):
        self.obj = stream

    def next(self):
        """
        Yield data for a single Resource.
        """
        raise NotImplemented('Subclass should implement next()')
