from django import template
from cookies.authorization import check_authorization

register = template.Library()


@register.tag
def authorized(perm, user, obj):
    return check_authorization(perm, user, obj)
