from django import template
from cookies.authorization import check_authorization

register = template.Library()


@register.assignment_tag
def is_authorized(perm, user, obj):
    return check_authorization(perm, user, obj)
