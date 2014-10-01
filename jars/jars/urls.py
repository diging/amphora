from django.conf.urls import patterns, include, url

import autocomplete_light
autocomplete_light.autodiscover()

from django.contrib import admin
admin.autodiscover()

from cookies import views



urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'jar.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^autocomplete/', include('autocomplete_light.urls')),
    url(r'^resource/([0-9]+)/edit/$', views.resource_change),
    url(r'^rest/resource/([0-9]+)/$', views.resource),
    url(r'^rest/resource/$', views.resources),    
)
