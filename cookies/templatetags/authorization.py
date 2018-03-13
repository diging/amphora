from django import template
from cookies.authorization import check_authorization, AUTHORIZATIONS_MAP

register = template.Library()


@register.assignment_tag
def is_authorized(perm, user, obj):
    action = AUTHORIZATIONS_MAP.get(perm, perm)
    return check_authorization(action, user, obj)
