from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404

from cookies.models import *
from cookies.filters import *
from cookies import authorization as auth

import jsonpickle
from celery.result import AsyncResult


@login_required
def jobs(request):
    queryset = UserJob.objects.filter(created_by=request.user).order_by('-created')
    filtered_objects = UserJobFilter(request.GET, queryset=queryset)
    context = {
        'filtered_objects': filtered_objects,
    }
    template = 'jobs.html'
    return render(request, template, context)


@login_required
def job_status(request, result_id):
    try:
        job = UserJob.objects.get(result_id=result_id)
        async_result = AsyncResult(result_id)
    except UserJob.DoesNotExist:
        job = {'percent': 0.}
        async_result = {'status': 'PENDING', 'id': result_id}

    context = {
        'job': job,
        'async_result': async_result,
    }
    template = 'job_status.html'

    if getattr(job, 'result', None) or getattr(async_result, 'status', None) in ['SUCCESS', 'FAILURE']:
        try:
            result = jsonpickle.decode(job.result)
        except:
            return render(request, template, context)

        return HttpResponseRedirect(reverse(result['view'], args=(result['id'], )))


    return render(request, template, context)
