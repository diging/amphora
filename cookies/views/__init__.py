from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.conf import settings

from cookies.models import *
from cookies.filters import *
from cookies.forms import *
from cookies import authorization as auth

from itertools import groupby

from . import resource, collection, async, conceptentity, metadata, giles


def index(request):
    return render(request, 'index.html', {})


@login_required
def logout_view(request):
    logout(request)
    return HttpResponseRedirect(request.GET.get('next', reverse('index')))


@login_required
def dashboard(request):
    qs = GilesUpload.objects.filter(created_by=request.user)
    context = {
        'uploads_pending': qs.filter(state=GilesUpload.PENDING).count(),
        'uploads_enqueued': qs.filter(state=GilesUpload.ENQUEUED).count(),
        'uploads_sent': qs.filter(state=GilesUpload.SENT).count(),
        'uploads_done': qs.filter(state=GilesUpload.DONE).count(),

    }
    return render(request, 'dashboard.html', context)


def inactive(request):
    return render(request, 'inactive.html', {'admin_email': settings.ADMIN_EMAIL})
