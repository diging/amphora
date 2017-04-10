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


def dashboard(request):
    print request.user.is_authenticated(), request.user.is_active, request.user
    return HttpResponse('Hello!')


def inactive(request):
    return render(request, 'inactive.html', {'admin_email': settings.ADMIN_EMAIL})
