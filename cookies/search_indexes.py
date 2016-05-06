import datetime
from haystack import indexes
from .models import Resource


class ResourceIndex(indexes.SearchIndex, indexes.Indexable):
    text = indexes.NgramField(document=True)
    name = indexes.NgramField(stored=True, indexed=True, model_attr='name')

    def get_model(self):
        return Resource

    def index_queryset(self, using=None):
        "Used when the entire index for model is updated."
        return self.get_model().objects.filter(content_resource=False)

    def prepare_text(self, instance):
        if instance.name:
            name = instance.name
        else:
            name = ''

        if instance.indexable_content:
            indexable = instance.indexable_content
        else:
            indexable = ''

        return u'\n\n'.join([name, indexable])
