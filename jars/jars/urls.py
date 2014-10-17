from django.conf.urls import patterns, include, url
from rest_framework import routers

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

    url(r'^localresource/([0-9]+)/$', views.localresource),
    url(r'^remoteresource/([0-9]+)/$', views.remoteresource),
    url(r'^relation/([0-9]+)/$', views.relation),
    url(r'^collection/([0-9]+)/$', views.collection),

    url(r'^rest/', include(router.urls)),
    url(r'^rest/auth/', include('rest_framework.urls', namespace='rest_framework'))
)
