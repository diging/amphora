"""
This module provides methods for interacting with Giles.
"""


from django.conf import settings
from django.core.files import File
from  django.core.exceptions import ObjectDoesNotExist

from cookies.models import *
from cookies import models    # TODO: wtf.
from cookies.exceptions import *

import requests, os, jsonpickle, urllib, urlparse
from datetime import datetime, timedelta
from django.utils import timezone
from collections import defaultdict
from jars.settings import GILES_RESPONSE_CREATOR_MAP

import django.db.utils

GET = requests.get
POST = requests.post
ACCEPTED = 202

logger = settings.LOGGER


class StatusException(Exception):
    def __init__(self, response):
        self.message = 'Encountered status %i: %s' % (response.status_code, response.content)
        self.response = response
        self.status_code = response.status_code

    def __str__(self):
        return repr(self.message)


class UserHasNoProviderToken(Exception):
    pass


def handle_status_exception(func):
    """
    Decorator for functions that call Giles. Provides automatic token refresh,
    and raises a :class:`.StatusException` for non-200-series HTTP status codes.
    """
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)

        if type(user) in [str, unicode]:    # May be a username, rather than a User.
            user = User.objects.get(username=user)

        if response.status_code == 401:    # Auth token expired.
            try:
                user.giles_token.delete()
            except (AssertionError, ObjectDoesNotExist):
                pass
            except Exception as E:
                raise

            get_user_auth_token(user, fresh=True, **kwargs)
            user.refresh_from_db()
            response  = func(user, *args, **kwargs)
            logger.debug('response %s: %s' % (response.status_code, response.content))
            return response
        elif response.status_code != requests.codes.ok and response.status_code != 202:
            logger.error('Giles responded with status %i: content: %s' % \
                         (response.status_code, response.content))
            raise StatusException(response)
        return response
    return wrapper


def api_request(func):
    """
    Convenience decorator for functions that call Giles. Automatically pulls
    out the status code and JSON data from the response.
    """
    def wrapper(user, *args, **kwargs):
        response = func(user, *args, **kwargs)
        return response.status_code, response.json()
    return wrapper


def _create_auth_header(user, **kwargs):
    """
    Convenience function for generating the authorization header for Giles
    requests.
    """
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    return {'Authorization': 'token %s' % get_user_auth_token(user)}


def get_user_auth_token(user, **kwargs):
    """
    Get the current auth token for a :class:`.User`\. If the user has no auth
    token, retrieves one and stores it.

    Parameters
    ----------
    user : :class:`django.contrib.auth.User`
    kwargs : kwargs

    Returns
    -------
    str
        Giles authorization token for ``user``.
    """
    fresh = kwargs.pop('fresh', False)
    logger.debug('get_user_auth_token:: for %s' % user.username)

    try:
        _expiry = timezone.now() - timedelta(minutes=settings.GILES_TOKEN_EXPIRATION)
        if not fresh and user.giles_token.created > _expiry:
            return user.giles_token.token
    except (AttributeError, ObjectDoesNotExist):    # RelatedObjectDoesNotExist.
        pass    # Will proceed to retrieve token.

    data = None
    try:
        try:    # Delete the old token first.
            user.giles_token.delete()
        except (AssertionError, ObjectDoesNotExist):
            pass

        status_code, data = get_auth_token(user, **kwargs)
        user.giles_token = GilesToken.objects.create(for_user=user, token=data["token"])
        user.save()
        return user.giles_token.token
    except Exception as E:
        logger.error("Failed to retrieve access token for %s: %s" % \
                     (user.username, str(E)))
        import json
        logger.error(json.dumps(data))
        if kwargs.get('raise_exception', False):
            raise E


@api_request
def get_auth_token(user, **kwargs):
    """
    Obtain and store a short-lived authorization token from Giles.

    See https://diging.atlassian.net/wiki/display/GIL/REST+Authentication.
    """
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', POST)
    provider = kwargs.get('provider', settings.GILES_DEFAULT_PROVIDER)
    app_token = kwargs.get('app_token', settings.GILES_APP_TOKEN)

    path = '/'.join([giles, 'rest', 'token'])
    try:
        provider_token = user.social_auth.get(provider=provider)\
                                         .extra_data.get('access_token')
    except ObjectDoesNotExist:
        raise UserHasNoProviderToken('User %s has no token for provider %s' % \
                                     (user.username, provider))

    return post(path, data={'providerToken': provider_token},
                headers={'Authorization': 'token %s' % app_token})


@api_request
@handle_status_exception
def send_to_giles(username, file_name, public=False, **kwargs):
    """
    Send a file to Giles.

    Parameters
    ----------
    username : str
        The owner of the file. This will be used to select the authorization
        token, and the resource will permanently belong to this user in Giles.
    file_name : str
        File path relative to MEDIA_ROOT.
    public : bool
        Whether or not the file should be publically accessible on Giles. The
        current approach is to set all files to private, and then provide
        paths with short-lived Giles tokens to individual users on a
        case-by-case basis.

    Returns
    -------
    :class:`requests.Response`

    """
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    post = kwargs.get('post', POST)

    path = '/'.join([giles, 'rest', 'files', 'upload'])
    headers = _create_auth_header(user, **kwargs)
    # headers.update({ 'Content-Type': 'multipart/form-data', })

    data = {'access': 'PUBLIC' if public else 'PRIVATE',}
    _full_path = os.path.join(settings.MEDIA_ROOT, file_name.encode('utf-8'))
    # POST payload.
    files = {
        'files': ( file_name, File(open(_full_path, 'rb')), 'application/pdf')
    }

    # Giles should respond with a token for each upload, which we should
    #  check periodically for completion (OCR takes longer than the Apache
    #  timeout).
    # import httplib as http_client
    # http_client.HTTPConnection.debuglevel = 1
    # requests_log = logging.getLogger("requests.packages.urllib3")
    # requests_log.setLevel(logging.DEBUG)
    # requests_log.propagate = True
    return post(path, headers=headers, files=files, data=data)


def create_giles_upload(resource_id, content_relation_id, username,
                        delete_on_complete=True):
    """
    Create a new pending :class:`.GilesUpload` for a :class:`.Resource`\.

    No files will have been sent at this point -- a worker will add this upload
    to the queue.

    Parameters
    ----------
    resource_id : int
        This :class:`.Resource` will be associated with the upload.
    content_relation_id : int
    username : str
    delete_on_complete : bool
        If True, the local file will be removed once Giles has fully processed
        the upload; the content resource will be flagged as deleted.

    Returns
    -------
    int
        The ID of the :class:`.GilesUpload`\.
    """
    resource = Resource.objects.get(pk=resource_id)
    content_relation = ContentRelation.objects.get(pk=content_relation_id)
    content_resource = content_relation.content_resource
    user = User.objects.get(username=username)

    if resource.created_through == Resource.INTERFACE_WEB:
        priority = GilesUpload.PRIORITY_MEDIUM
    elif resource.created_through == Resource.INTERFACE_API:
        priority = GilesUpload.PRIORITY_LOW
    else:
        priority = GilesUpload.PRIORITY_MEDIUM

    data = {
        'resource':resource,
        'file_path': content_resource.file.name,
        'state': GilesUpload.PENDING,
        'created_by': user,
        'priority': priority,
    }

    if delete_on_complete:
        data.update({
            'on_complete': jsonpickle.encode([
                ('Resource', content_resource.id, 'delete'),
                ('ContentRelation', content_relation_id, 'delete'),
            ])
        })

    return GilesUpload.objects.create(**data).id



def send_giles_upload(upload_pk, username):
    """
    Send data for a pending :class:`.GilesUpload`\.

    If successfuly, transitions state from PENDING to SENT. If an exception is
    raised, transitions state from PENDING to SEND_ERROR.

    Parameters
    ----------
    upload_pk : int
    username : str
    """
    upload = GilesUpload.objects.get(pk=upload_pk)

    # This will trigger an actual upload, and we don't want to do it twice.
    if not upload.state in [GilesUpload.PENDING, GilesUpload.ENQUEUED]:
        return

    try:
        code, result = send_to_giles(username, upload.file_path, public=False)
        if code != 200:
            raise RuntimeError('Giles returned HTTP {}'.format(code))
        upload.upload_id = result['id']
        upload.state = GilesUpload.SENT
    except AttributeError as E:
        message = str(result)
        logger.error("Giles returned an uninterpretable message when sending"
                     " upload %i: %s" % (upload.id, message))
        upload.message = message
        upload.state = GilesUpload.SEND_ERROR
    except Exception as E:    # TODO: be more specific.
        logger.error('Encountered exception when sending upload %i: %s' % \
                     (upload.id, str(E)))
        upload.message = str(E)
        upload.state = GilesUpload.SEND_ERROR
    upload.save()


@api_request
@handle_status_exception
def check_upload_status(username, upload_id , **kwargs):
    """
    Poll Giles for the status of a POSTed upload.

    Parameters
    ----------
    username : str
        This must be the same user on whose behalf we uploaded the file.
    upload_id : str
        The "poll id" that Giles returned upon upload.
    kwargs : kwargs
        Can inject ``giles`` (base path for Giles instance) and ``get``
        (callable that accepts an URL and ``headers`` kwarg).

    Returns
    -------
    :class:`requests.Response`
    """
    user = User.objects.get(username=username)
    giles = kwargs.get('giles', settings.GILES)
    get = kwargs.get('get', GET)
    checkURL = giles + '/rest/files/upload/check/%s' % upload_id
    return get(checkURL, headers=_create_auth_header(user, **kwargs))


def process_on_complete(on_complete):
    """
    Perform post-processing actions.

    These are set when a :class:`.GilesUpload` is created. Currently only
    supports ``'delete'`` action, which sets ``is_deleted`` and permanently
    deletes any attached files in the filesystem.

    Parameters
    ----------
    on_complete : list
        Should be a list of 3-tuples: ``(model, pk, action)``.
    """

    def _delete(obj):
        if getattr(obj, 'file', None):
            path = os.path.join(settings.MEDIA_ROOT, obj.file.name)
            if os.path.isfile(path):
                os.remove(path)
        obj.file = None
        obj.is_deleted = True
        obj.save()

    _actions = {'delete': _delete}
    for model, pk, action in on_complete:
        obj = getattr(models, model).objects.get(pk=pk)
        _actions.get(action, (lambda o: o))(obj)


def process_upload(upload_id, username, reprocess=False):
    """
    Given a Giles upload id, attempt to retrieve file details and create local
    data structures (if ready).

    Transitions state from SENT to DONE, or (if there are exceptions) one of
    the error states.

    Parameters
    ----------
    upload_id : str
        The "poll id" returned by Giles when the file was uploaded.
    username : str
        This must be the same user on whose behalf we uploaded the file.
    reprocess : bool
        If True, reprocess the Giles response even if the upload was processed
        before. Default behavior (reprocess=False) is to do nothing if the
        upload is in one of the error states or Done.
    """
    import datetime, jsonpickle
    from django.utils import timezone

    user = User.objects.get(username=username)

    # The upload may or may not have originated in Amphora.
    _defaults = {'created_by': user, 'state': GilesUpload.SENT}
    upload, _created = GilesUpload.objects.get_or_create(upload_id=upload_id,
                                                         defaults=_defaults)

    if not _created and upload.created_by != user:
        raise RuntimeError('Upload was made on behalf of a different user')

    upload.last_checked = timezone.now()    # TODO: this is probably redundant.
    try:
        code, data = check_upload_status(username, upload_id)
    except Exception as E:
        upload.message = str(E)
        upload.state = GilesUpload.GILES_ERROR
        upload.save()
        return

    if code == ACCEPTED:    # Giles is still processing the upload.
        upload.state = GilesUpload.SENT
        upload.save()
        return

    if code >= 400:
        upload.message = str(data)
        upload.state = GilesUpload.GILES_ERROR
        upload.save()
        return

    with transaction.atomic():
        is_processed = ((upload.state in GilesUpload.ERROR_STATES) or (upload.state == GilesUpload.DONE))
        if is_processed and not reprocess:
            # Resource already processed. Do nothing.
            return

        try:
            # If Giles is done processing the upload, details about the resulting
            # files are returned.
            resource = process_details(data, upload_id, username)
            if not upload.resource:
                upload.resource = resource
                upload.save()
        except django.db.utils.Error as E:
            # Being in a transaction, can't update `upload` object on Database
            # errors.
            logger.exception('Database error processing Giles response')
            raise
        except Exception as E:    # We f***ed something up.
            logger.exception('Error processing Giles response')
            upload.message = str(E)
            upload.state = GilesUpload.PROCESS_ERROR
            upload.save()
            return

        # Depending on configuration, we may want to do things like delete local
        #  copies of files.
        if upload.on_complete:
            try:
                process_on_complete(jsonpickle.decode(upload.on_complete))
            except Exception as E:
                logger.exception('Error executing callback')
                upload.message = str(E)
                upload.state = GilesUpload.CALLBACK_ERROR
                upload.save()
                return

        # Woohoo!
        upload.state = GilesUpload.DONE
        upload.message = jsonpickle.encode(data)
        upload.save()


class _GilesDetailsProcessor(object):

    def __init__(self, upload, resource, user, data):
        self.__creator__ = Field.objects.get(uri='http://purl.org/dc/elements/1.1/creator')
        self.__text__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Text')
        self.__image__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Image')
        self.__document__ = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')
        self.__dataset__ = Type.objects.get(uri='http://purl.org/dc/dcmitype/Dataset')
        self.__part__ = Field.objects.get(uri='http://purl.org/dc/terms/isPartOf')

        self.CONTENT_RESOURCE_TYPE_MAP = {
            'text/plain': self.__text__,
            'text/csv': self.__dataset__,
            'application/pdf': self.__text__,
        }

        self._upload = upload
        self._resource = resource
        self._user = user
        self._data = data
        content_filter = dict(is_deleted=False, content_resource__is_external=True,
            content_resource__external_source=Resource.GILES)
        self._existing_giles_resources = {
            crel.content_resource.location: (crel, crel.content_resource)
                for crel in resource.content.filter(**content_filter)
        }
        self._pages = {
            int(rel.sort_order): rel.source
                for rel in self._resource.parts.order_by('sort_order')
        }
        for page in self._pages.values():
            for crel in page.content.filter(**content_filter):
                self._existing_giles_resources[crel.content_resource.location] = (crel, crel.content_resource)

    def _process_uploaded_file(self):
        upload_data = self._data.get('uploadedFile')
        giles_url = upload_data.get('url')
        resource_uri = giles_url

        content_type = upload_data.get('content-type')
        resource_type = self.CONTENT_RESOURCE_TYPE_MAP.get(content_type,
                                                           self.__image__)
        self._save_content_resource(self._resource, resource_type, resource_uri,
                                    giles_url, content_type=content_type,
                                    name='%s (uploaded)' % (self._resource.name),
                                    file_id=upload_data['id'])

    def _process_extracted_text(self):
        text_data = self._data.get('extractedText', None)
        if text_data is None:
            return
        text_content_type = text_data.get('content-type')
        text_uri = text_data.get('url')
        content_resource = self._save_content_resource(
            self._resource, self.__text__, text_uri, text_uri,
            content_type=text_content_type,
            name='%s (extracted)' % (self._resource.name),
            file_id=text_data['id'],
        )
        self._save_resource_creator(content_resource,
                                    self.__creator__,
                                    GILES_RESPONSE_CREATOR_MAP['extractedText'])

    def _process_pages(self):
        # Keep track of page resources so that we can populate ``next_page``.
        pages = defaultdict(dict)
        document_id = self._data.get('documentId')

        # Each page is represented by a Resource.
        for page_data in self._data.get('pages', []):
            page_nr = int(page_data.get('nr'))
            page_uri = '%s/documents/%s/%i' % (settings.GILES, document_id, page_nr)
            page_resource = self._save_page_resource(self._resource, page_nr, self.__document__,
                                                     page_uri, page_data.get('url'),
                                                     public=False)
            pages[page_nr]['resource'] = page_resource

            # Each page resource can have several content resources.
            for fmt in ['image', 'text', 'ocr',]:
                # We may not have both formats for each page.
                fmt_data = page_data.get(fmt, None)
                if fmt_data is None:
                    continue

                page_fmt_uri = '%s/files/%s' % (settings.GILES, fmt_data.get('id'))
                content_resource = self._save_content_resource(
                    page_resource, self.__image__ if fmt == 'image' else self.__text__,
                    page_fmt_uri, fmt_data.get('url'),
                    public=False, content_type=fmt_data.get('content-type'),
                    file_id=fmt_data['id'],
                    name='%s (%s)' % (page_resource.name, fmt)
                )

                try:
                    self._save_resource_creator(content_resource,
                                                self.__creator__,
                                                GILES_RESPONSE_CREATOR_MAP[fmt])
                except KeyError:
                    # Creator not defined for `fmt` in GILES_RESPONSE_CREATOR_MAP
                    pass

                pages[page_nr][fmt] = content_resource

            name_fn = lambda d: '%s - %s (%s)' % (page_resource.name, d.get('id'),
                                                  d.get('content-type'))
            # Content resource for each additional file, if available.
            self._process_additional_files(page_data.get('additionalFiles', []),
                                           page_resource,
                                           name_fn=name_fn)

            # Populate the ``next_page`` field for pages, and for their content
            #  resources.
            for i in sorted(pages.keys())[:-1]:
                for fmt in ['resource', 'image', 'text', 'ocr',]:
                    if fmt not in pages[i]:
                        continue
                    pages[i][fmt].next_page = pages[i + 1][fmt]
                    pages[i][fmt].save()

    def _process_additional_files(self, additional_files, parent_resource,
                                  name_fn=lambda x:x['url']):
        """
        Helper function for creating content resources for 'additionalFiles' in
        processed Giles upload response.

        Parameters
        ----------
        additional_files : list
            List of dicts containing details of each additional file.
        parent_resource : :class:`.Resource` instance
            Represents the document/object of which the content resource (to be
            created) is a digital surrogate.
        creator : :class:`.User`
            The person responsible for adding the content to Giles.
        name_fn : callable
            A function accepting dict and returning name for each additional file
            content resource. Must return a str.
        """

        def _get_resource_type(data):
            content_type = data.get('content-type')
            try:
                return self.CONTENT_RESOURCE_TYPE_MAP[content_type]
            except KeyError:
                if 'image' in content_type:
                    return self.__image__
            return self.__document__

        for additional_file in additional_files:
            content_type = additional_file.get('content-type')
            uri = additional_file.get('url')
            resource_type = _get_resource_type(additional_file)

            content_resource = self._save_content_resource(
                parent_resource,
                resource_type,
                uri, uri,
                content_type=content_type,
                file_id=additional_file['id'],
                name=name_fn(additional_file),
            )

            if additional_file.get('processor'):
                self._save_resource_creator(
                    content_resource,
                    self.__creator__,
                    additional_file.get('processor'),
                )

    def process(self):
        # Content resource for uploaded file.
        self._process_uploaded_file()

        # Content resource for extracted text, if available.
        self._process_extracted_text()

        name_fn = lambda d: '%s - %s (%s)' % (self._resource.name, d.get('id'),
                                              d.get('content-type'))
        # Content resource for each additional file, if available.
        self._process_additional_files(self._data.get('additionalFiles', []),
                                       self._resource,
                                       name_fn=name_fn)

        self._process_pages()

        return self._resource

    def _save_content_resource(self, parent_resource, resource_type, uri, url,
                               public=False, **meta):
        """
        Helper function for creating appropriate resources and relations after
        Giles successfully processes an upload.

        Parameters
        ----------
        parent_resource : :class:`.Resource` instance
            Represents the document/object of which the content resource (to be
            created) is a digital surrogate.
        resource_type : :class:`.Type` instance
        uri : str
            Identifier for the content resource. Should usually be
            ``{giles}/files/{file_id}``.
        url : str
            Location of the content.
        meta : kwargs
            Can provide any of the following:
            - ``name`` : Human-readable name (for display).
            - ``file_id`` : Giles identifier.
            - ``path`` : Digilib-style image path.
            - ``size`` : (int) Dimensionless.
            - ``content_type`` : Should be a valid MIME-type (but not enforced).
            - ``public`` : bool
                  Whether or not this record should be public in JARS. This should match
                  the setting for this resource in Giles, otherwise things might get
                  weird.

        Returns
        -------
        :class:`.Resource`
            The content resource.
        """
        try:
            content_rel, content_resource = self._existing_giles_resources[url]
            content_resource.entity_type = resource_type
            for key, value in meta.items():
                try:
                    setattr(content_resource, key, value)
                except AttributeError, e:
                    logger.warning(e)

            content_resource.save()

            if 'content_type' in meta.keys():
                content_rel.content_type = meta.get('content_type')
                content_rel.save()

        except KeyError:
            kwargs = {
                'name': meta.get('name', url),
                'public': meta.get('public', False),
                'content_resource': True,
                'created_by_id': self._user.id,
                'created_through': parent_resource.created_through,
                'entity_type': resource_type,
                'content_type': meta.get('content_type', None),
                'is_external': True,
                'external_source': Resource.GILES,
                'uri': uri,
                'container': parent_resource.container,
            }
            try:
                kwargs['location_id'] = meta['file_id']
            except KeyError:
                kwargs['location'] = url

            content_resource = Resource.objects.create(**kwargs)
            content_rel = ContentRelation.objects.create(**{
                'for_resource': parent_resource,
                'content_resource': content_resource,
                'content_type': meta.get('content_type', None),
                'container': parent_resource.container,
            })
            self._existing_giles_resources[url] = (content_rel,
                                                   content_resource)

        return content_resource

    def _save_page_resource(self, parent_resource, page_nr, resource_type, uri,
                            url, public=False, **meta):
        """
        Helper function for creating appropriate resources and relations after
        Giles successfully processes an upload.

        Parameters
        ----------
        parent_resource : :class:`.Resource` instance
        page_nr : int
        resource_type : :class:`.Type` instance
        uri : str
            Identifier for the content resource. Should usually be
            ``{giles}/files/{file_id}``.
        url : str
            Location of the content.
        public : bool
            Whether or not this record should be public in JARS. This should match
            the setting for this resource in Giles, otherwise things might get
            weird.
        meta : kwargs
        """
        try:
            return self._pages[page_nr]
        except KeyError:
            pass

        resource = Resource.objects.create(**{
            'name': '%s, page %i' % (parent_resource.name, page_nr),
            'created_by_id': self._user.id,
            'created_through': parent_resource.created_through,
            'entity_type': resource_type,
            'public': public,
            'content_resource': False,
            'is_part': True,
            'is_external': True,
            'external_source': Resource.GILES,
            'container': parent_resource.container,
        })

        Relation.objects.create(**{
            'source': resource,
            'target': parent_resource,
            'predicate': self.__part__,
            'container': parent_resource.container,
            'sort_order': int(page_nr),
        })
        self._pages[page_nr] = resource
        return resource

    def _save_resource_creator(self, resource, predicate, value):
        existing_relations = resource.relations_from.filter(predicate=predicate)
        rel_count = existing_relations.count()
        if rel_count == 0:
            Relation.objects.create(
                source=resource,
                predicate=predicate,
                target=Value.objects.create(name=value),
                container=resource.container,
            )
        elif rel_count == 1:
            target = existing_relations[0].target
            target.name = value
            target.save()
        else:
            logger.warning('Multiple creator relations for Resource {}'.format(resource))


def process_details(data, upload_id, username):
    """
    Process document data from Giles.

    Paramters
    ---------
    data : dict
    upload_id : str
        The original poll ID returned by Giles upon upload.
    username : str

    Returns
    -------
    :class:`.Resource`
    """

    if isinstance(data, list):
        if len(data) == 0:
            raise ValueError('data is empty')
        data = data[0]

    upload = GilesUpload.objects.get(upload_id=upload_id)
    resource = upload.resource    # This is the master resource.
    creator = User.objects.get(username=username)

    giles = settings.GILES

    document_id = data.get('documentId')

    # We may already have a master Resource, e.g. if we POSTed a file from a
    #  Zotero batch-ingest and have been awaiting processing by Giles.
    if resource is None:
        __document__ = Type.objects.get(uri='http://xmlns.com/foaf/0.1/Document')
        resource, created = Resource.objects.get_or_create(
            name = document_id,
            defaults = {
                'created_by_id': creator.id,
                'entity_type': __document__,
                'uri': '%s/documents/%s' % (giles, document_id),
                'content_resource': False,
                'is_external': True,
                'external_source': Resource.GILES,
            })
        container = ResourceContainer.objects.create(primary=resource,
                                                     created_by=creator)
        resource.container = container
        resource.save()

    return _GilesDetailsProcessor(upload, resource, creator, data).process()


def format_giles_url(url, username, dw=300):
    """
    Adds ``accessToken`` and ``dw`` parameters to ``url``.

    Parameters
    ----------
    url : str
        This should be an URL for content in Giles.
    username : str
        Name of the user who owns (or has Giles-level rights) to the resource.
        Will be used to select the Giles access token.
    dw : int
        Display width (for images); for Digilib.

    Returns
    -------
    str
        URL with auth token and display width GET parameters.
    """

    user = User.objects.get(username=username)
    parts = list(tuple(urlparse.urlparse(url)))
    q = {k: v[0] for k, v in urlparse.parse_qs(parts[4]).iteritems()}
    q.update({'accessToken': get_user_auth_token(user), 'dw': dw})
    parts[4] = urllib.urlencode(q)
    return urlparse.urlunparse(tuple(parts))
