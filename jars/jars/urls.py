from django.conf.urls import patterns, include, url
from rest_framework import routers
from django.conf import settings
from django.conf.urls.static import static

import autocomplete_light
autocomplete_light.autodiscover()

from django.contrib import admin
admin.autodiscover()

from cookies import views, views_rest

router = routers.DefaultRouter()
#router.register(r'entity', views_rest.EntityViewSet)
router.register(r'resource', views_rest.ResourceViewSet)
router.register(r'field', views_rest.FieldViewSet)
router.register(r'relation', views_rest.RelationViewSet)

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'jar.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    
    url(r'^admin/', include(admin.site.urls)),
    url(r'^autocomplete/', include('autocomplete_light.urls')),

    url(r'^resource/([0-9]+)/$', views.resource, name="resource"),
    url(r'^resource/$', views.resource_list, name="resources"),
    url(r'^collection/([0-9]+)/$', views.collection, name="collection"),
    url(r'^collection/$', views.collection_list, name="collections"),

    url(r'^rest/', include(router.urls)),
    url(r'^rest/auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    url(r'^search/', include('haystack.urls'), name='search'),
    
    url(r'^$', views.index, name="index"),
)    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

