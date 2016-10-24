import importlib
from cookies.models import *


class IngesterFactory(object):
    def get(self, path):
        path_parts = path.split('.')
        class_name = path_parts[-1]
        import_source = '.'.join(path_parts[:-1])

        # TODO: use importlib instead.
        module = __import__(import_source, fromlist=[class_name])
        return IngestWrapper(getattr(module, class_name))


class IngestManager(object):
    def __init__(self, wraps):
        self.wraps = wraps

    def create_resource(self, resource_data):
        return Resource.objects.create(**resource_data)

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

    def create_relation(self, relation_data):
        source_model, source_data = relation_data.get('source', None)
        predicate = self.get_or_create_predicate(relation_data.get('predicate'))
        target_model, target_data = relation_data.get('target', None)

    def next(self):
        resource_data, relations = self.wraps.next()
        resource = self.create_resource(resource_data)

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
