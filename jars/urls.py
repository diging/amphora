from django.conf.urls import patterns, include, url
from rest_framework import routers
from rest_framework.urlpatterns import format_suffix_patterns
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
admin.autodiscover()

from cookies import views, views_rest, views_oaipmh
from cookies.autocomplete import EntityAutocomplete


router = routers.DefaultRouter()
router.register(r'resource', views_rest.ResourceViewSet)
router.register(r'collection', views_rest.CollectionViewSet)
router.register(r'relation', views_rest.RelationViewSet)
router.register(r'field', views_rest.FieldViewSet)
router.register(r'concept', views_rest.ConceptViewSet)


urlpatterns = patterns('',
    url('', include('social_django.urls', namespace='social')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^autocomplete/$', EntityAutocomplete.as_view(create_field='name'), name='autocomplete'),
    url(r'^logout/$', views.logout_view, name='logout'),

    url(r'^resource/([0-9]+)/$', views.resource.resource, name="resource"),
    url(r'^resource/([0-9]+)/content/$', views.resource.resource_content, name="resource-content"),
    url(r'^resource/get/$', views.resource.resource_by_uri, name="resource_by_uri"),
    url(r'^resource/$', views.resource.resource_list, name="resources"),
    url(r'^resource/create/$', views.resource.create_resource, name="create-resource"),
    url(r'^resource/create/upload/$', views.resource.create_resource_file, name="create-resource-file"),
    url(r'^resource/create/remote/$', views.resource.create_resource_url, name="create-resource-url"),
    url(r'^resource/create/giles/$', views.resource.create_resource_choose_giles, name="create-resource-choose-giles"),
    url(r'^resource/create/giles/callback/$', views.resource.handle_giles_upload, name="create-handle-giles"),
    url(r'^resource/merge/$', views.resource.resource_merge, name="resource-merge"),
    url(r'^resource/bulk/$', views.resource.bulk_action_resource, name="bulk-action-resource"),
    url(r'^resource/bulk/addtag/$', views.resource.bulk_add_tag_to_resource, name="bulk-add-tag-to-resource"),
    url(r'^resource/([0-9]+)/edit/$', views.resource.edit_resource_details, name="edit-resource-details"),
    url(r'^resource/([0-9]+)/giles/([0-9]+)$', views.resource.trigger_giles_submission, name="trigger-giles-submission"),
    url(r'^resource/([0-9]+)/prune/$', views.resource.resource_prune, name="resource-prune"),
    url(r'^resource/([0-9]+)/edit/([0-9]+)/$', views.resource.edit_resource_metadatum, name="edit-resource-metadatum"),
    url(r'^resource/([0-9]+)/edit/([0-9]+)/delete/$', views.resource.delete_resource_metadatum, name="delete-resource-metadatum"),
    url(r'^resource/([0-9]+)/edit/add/$', views.resource.create_resource_metadatum, name='create-resource-metadatum'),
    url(r'^resource/create/giles/process/([0-9]+)/$', views.resource.process_giles_upload, name="create-process-giles"),
    url(r'^resource/create/details/([0-9]+)/$', views.resource.create_resource_details, name="create-resource-details"),
    url(r'^resource/create/bulk/$', views.resource.create_resource_bulk, name="create-resource-bulk"),
    url(r'^collection/([0-9]+)/$', views.collection.collection, name="collection"),
    url(r'^collection/([0-9]+)/edit/$', views.collection.collection_edit, name="collection-edit"),
    url(r'^collection/([0-9]+)/authorizations/$', views.collection.collection_authorizations, name="collection-authorizations"),
    url(r'^collection/([0-9]+)/authorizations/create/$', views.collection.collection_authorization_create, name="collection-authorization-create"),
    url(r'^collection/([0-9]+)/authorizations/remove/([0-9]+)/$', views.collection.collection_authorization_remove, name="collection-authorization-remove"),


    url(r'^collection/$', views.collection.collection_list, name="collections"),
    url(r'^collection/create/$', views.collection.create_collection, name="create-collection"),
    url(r'^collection/export/([0-9]+)/$',views.collection.export_coauthor_data, name="export-coauthor-data"),

    url(r'^metadata/$', views.metadata.list_metadata, name='list-metadata'),

    url(r'^entity/$', views.conceptentity.entity_list, name='entity-list'),
    url(r'^entity/merge/$', views.conceptentity.entity_merge, name='entity-merge'),
    url(r'^entity/([0-9]+)/$', views.conceptentity.entity_details, name='entity-details'),
    url(r'^entity/([0-9]+)/change/$', views.conceptentity.entity_change, name='entity-change'),
    url(r'^entity/([0-9]+)/change/concept/$', views.conceptentity.entity_change_concept, name='entity-change-concept'),
    url(r'^entity/([0-9]+)/prune/$', views.conceptentity.entity_prune, name="entity-prune"),


    url(r'^task/$', views.async.jobs, name='jobs'),
    url(r'^task/([0-9a-z\-]+)/$', views.async.job_status, name='job-status'),

    url(r'^rest/', include(router.urls)),
    url(r'^rest/auth/', include('rest_framework.urls', namespace='rest_framework')),

    url(r'^oaipmh/', views_oaipmh.oaipmh, name='oaipmh'),

    # url(r'^search/$', views.ResourceSearchView.as_view(), name='search'),
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    url(r'^s3/', views.resource.sign_s3, name='sign_s3'),
    url(r'^testupload/', views.resource.test_upload, name='test_upload'),
    url(r'^$', views.index, name="index"),
) + format_suffix_patterns((url(r'^resource_content/([0-9]+)$', views_rest.ResourceContentView.as_view(), name='resource_content'),))   + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
