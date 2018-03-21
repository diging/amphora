from django import template
register = template.Library()

CREATOR_FIELD_URI = 'http://purl.org/dc/elements/1.1/creator'

@register.assignment_tag
def get_resource_creator(resource):
    return ','.join((r.target.name for r in resource.relations_from.filter(
        predicate__uri=CREATOR_FIELD_URI)))
