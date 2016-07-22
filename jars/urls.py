from django.conf.urls import patterns, include, url
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
admin.autodiscover()

from cookies import views, views_rest
from cookies.autocomplete import EntityAutocomplete


router = routers.DefaultRouter()
router.register(r'resource', views_rest.ResourceViewSet)
router.register(r'collection', views_rest.CollectionViewSet)
router.register(r'relation', views_rest.RelationViewSet)
router.register(r'field', views_rest.FieldViewSet)


urlpatterns = patterns('',
    url(r'^admin/', include(admin.site.urls)),
    url(r'^autocomplete/$', EntityAutocomplete.as_view(create_field='name'), name='autocomplete'),

    url(r'^resource/([0-9]+)/$', views.resource, name="resource"),
    url(r'^resource/$', views.resource_list, name="resources"),
    url(r'^resource/create/$', views.create_resource, name="create-resource"),
    url(r'^resource/create/upload/$', views.create_resource_file, name="create-resource-file"),
    url(r'^resource/create/remote/$', views.create_resource_url, name="create-resource-url"),
    url(r'^resource/create/giles/$', views.create_resource_choose_giles, name="create-resource-choose-giles"),
    url(r'^resource/create/details/([0-9]+)/$', views.create_resource_details, name="create-resource-details"),
    url(r'^collection/([0-9]+)/$', views.collection, name="collection"),
    url(r'^collection/$', views.collection_list, name="collections"),

    url(r'^rest/', include(router.urls)),
    url(r'^rest/auth/$', include('rest_framework.urls', namespace='rest_framework')),

    url(r'^search/$', views.ResourceSearchView.as_view(), name='search'),
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    url(r'^s3/', views.sign_s3, name='sign_s3'),
    url(r'^testupload/', views.test_upload, name='test_upload'),
    url(r'^$', views.index, name="index"),
) + format_suffix_patterns((url(r'^resource_content/([0-9]+)$', views_rest.ResourceContentView.as_view(), name='resource_content'),))   + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
