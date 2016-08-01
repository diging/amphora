from cookies.models import *

import jsonpickle, datetime


def add_creation_metadata(resource, user):
    PROVENANCE = Field.objects.get(uri='http://purl.org/dc/terms/provenance')
    now = str(datetime.datetime.now())
    creation_message = u'Added by %s on %s' % (user.username, now)
    Relation.objects.create(**{
        'source': resource,
        'predicate': PROVENANCE,
        'target': Value.objects.create(**{
            '_value': jsonpickle.encode(creation_message),
        })
    })
