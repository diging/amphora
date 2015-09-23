from django.utils.datastructures import SortedDict
from rest_framework import renderers

from rest_framework_cj.renderers import CollectionJsonRenderer
from rest_framework.negotiation import BaseContentNegotiation, DefaultContentNegotiation
import magic

from .models import *

