"""
Interactions with external concept services.
"""

from concepts.models import *

from django.conf import settings
import goat
import os

os.environ.setdefault('GOAT_WAIT_INTERVAL', '0.001')
goat.GOAT_APP_TOKEN = settings.GOAT_APP_TOKEN
goat.GOAT = settings.GOAT


def get_or_create(uri):
    """
    Get or create a :class:`.Concept` instance.

    We use the non-shortcut pattern to avoid waiting for remote data if the
    :class:`.Concept` instance already exists locally.

    Parameters
    ----------
    uri : str
    """
    try:
        return Concept.objects.get(uri=uri), False
    except Concept.DoesNotExist:
        pass

    data = goat.Concept.retrieve(uri)
    defaults = {
        'label': data.data['name'],
        'description': data.data['description'],
        'authority': data.data['authority']['name']
    }

    # TODO: hmmm, that looks redundant.
    return Concept.objects.get_or_create(uri=uri, defaults=defaults)



def concept_search(query):
    """
    BlackGoat API is used to search for the URIs and the sources by querying
    with the text entered.

    Parameters
    ----------
    query : str
        This is the search text that will be used by BlackGoat API to query for
        the URIs.

    Returns
    -------
    concepts : list
        This is a list of all :class:`.GoatConcept` objects obtained from the
        search result of the BlackGoat API.
    """
    #If no query text is entered, the result from search is None.
    if not query:
        return []

    #The BlackGoat API for search is used to get a list of all URIs associated
    # with the text entered.
    concepts = goat.Concept.search(q=query)
    if not concepts:
        return []

    #All the concepts from the search API are iterated to get a dictionary of
    # lists containing the name, source and uri
    concept_data = []
    for concept in concepts:
        concept_data.append({
            'name': concept.data['name'],
            'source': concept.data['authority']['name'],
            'uri': concept.data['identifier'],
            'description': concept.data['description']
        })
    return concept_data
