from dal import autocomplete

from django.utils import six
from django.core.exceptions import ImproperlyConfigured
from itertools import chain
from django.db.models.query import QuerySet
from django import http
from dal_select2_queryset_sequence.views import Select2QuerySetSequenceView
from queryset_sequence import QuerySetSequence
from dal import autocomplete
from .models import *
from concepts import authorities

from django.contrib.auth import get_permission_codename

import json


class EntityAutocomplete(Select2QuerySetSequenceView):
    value_models = [
        Value
        # DateTimeValue, DateValue, FloatValue, IntegerValue, StringValue
    ]

    def get_queryset(self):
        querysets = [
            Resource.objects.all(),
            ConceptEntity.objects.all(),
        ]
        qs = QuerySetSequence(*querysets)

        if self.q:
            qs = qs.filter(name__icontains=self.q)
            # In addition to filtering existing Entities, we should also
            #  consider Concepts provided by registered authority services.
            if len(self.q) > 3:  # To avoid frivolous authority calls, we only
                            #  consider Concepts once the user has entered
                            #  four characters.
                extra_choices = self._suggest_concept(self.q)

        if not self.request.user.is_authenticated():
            qs = qs.filter(private=False)

        field_id = self.request.GET.get('in_range_of', None)
        if field_id:
            qs = qs.filter(entity_type__in_range_of__in=[field_id])

        qs = self.mixup_querysets(qs)
        return qs

    def has_add_permission(self, request):
        """Return True if the user has the permission to add a model."""
        if not request.user.is_authenticated():
            return False

        opts = self.get_queryset().model._meta
        return True
        codename = get_permission_codename('add', opts)
        return request.user.has_perm("%s.%s" % (opts.app_label, codename))

    def get_model_for_value(self, value):
        for model in self.value_models:
            try:
                model.pytype(value)
                return model
            except:
                pass


    def create_object(self, text):
        """Create an object given a text."""
        model = self.get_model_for_value(text)
        if model:
            return model.objects.create(**{self.create_field: model.pytype(text)})
        return None

    def post(self, request):
        """Create an object given a text after checking permissions."""
        if not self.has_add_permission(request):
            return http.HttpResponseForbidden()

        if not self.create_field:
            raise ImproperlyConfigured('Missing "create_field"')

        text = request.POST.get('text', None)

        if text is None:
            return http.HttpResponseBadRequest()

        result = self.create_object(text)

        return http.JsonResponse({
            'id': result.pk,
            'text': six.text_type(result),
        })


    def render_to_response(self, context):
        """Return a JSON response in Select2 format."""
        create_option = []

        q = self.request.GET.get('q', None)
        if 'page_obj' in context:
            page_number = getattr(context['page_obj'], 'number', 1)
        else:
            page_number = 1

        if self.create_field and q and page_number == 1:
            create_option = [{
                'id': q,
                'text': 'Create "%s"' % q,
                'create_id': True,
            }]

        return http.HttpResponse(
            json.dumps({
                'results': self.get_results(context) + create_option,
                'pagination': {
                    'more': self.has_more(context)
                }
            }),
            content_type='application/json',
        )

    def _suggest_concept(self, query):
        """
        Loads or generates :class:`ConceptEntity` instances based on the
        autocomplete query.
        """

        # Search all available authorities for the query.
        concepts = authorities.searchall(query)

        entities = []   # Will hold ConceptEntity objects.
        # For each Concept, we need a ConceptEntity that can serve as a value
        #  for the user's input field.
        for concept in concepts:
            # An Entity with a name matching the Concept's label may already
            #  exist. If so, we check whether it is a ConceptEntity.
            qs = ConceptEntity.objects.filter(name=concept.label)

            # TODO: *** CHECK ALL ENTITIES HERE ***
            if qs.count() > 0:
                # Get the object as its "real" type.
                candidate_entity = qs[0]

                # If it is a ConceptEntity and the URI is correct, then we'll
                #  just use it.
                correct_type = type(candidate_entity) is ConceptEntity
                correct_uri = candidate_entity.uri == concept.uri
                if correct_type and correct_uri:
                    conceptentity = candidate_entity
                else:
                    # Otherwise, we will create a new ConceptEntity. Since names
                    #  must be unique, we will generate a new name using the
                    #  concept label and the concept URI.
                    #   For example: "Concept name (http://uri)".
                    conceptentity = ConceptEntity.objects.get_or_create(
                        name = '{0} ({1})'.format(concept.label, concept.uri),
                        defaults = {'concept_id': concept.id,})[0]
            # If no matching Entity exists, then we will create a new
            #  ConceptEntity with the correct name and URI.
            else:
                conceptentity, _ = ConceptEntity.objects.get_or_create(
                    name=concept.label,
                    defaults = {
                        'concept_id': concept.id,
                        'uri': concept.uri,
                    })
            entities.append(conceptentity)
        return entities
