from django import template
from celery.result import AsyncResult
from django.utils.safestring import mark_safe
register = template.Library()


icons = {
    'SUCCESS': mark_safe(u'<span class="glyphicon glyphicon-ok"></span>'),
    'FAILURE': mark_safe(u'<span class="glyphicon glyphicon-exclamation-sign" style="color: red;"></span>'),
    'PENDING': mark_safe(u'<span class="glyphicon glyphicon glyphicon-hourglass" style="color: orange;"></span>'),
}


@register.filter(name='get_status')
def get_status(job):
    result = AsyncResult(job.result_id)
    return result.status


@register.filter(name='get_status_icon')
def get_status_icon(job):
    status = get_status(job)

    return icons.get(status, mark_safe('null'))
