"""
Django settings for jars project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os
import socket
import sys
from urlparse import urlparse
import requests
BASE_DIR = os.path.dirname(os.path.dirname(__file__))

LOCAL_PATH = '/'


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.6/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = eval(os.environ.get('DEBUG', 'False'))
TEMPLATE_DIRS = [os.path.join(BASE_DIR, 'templates')]
TEMPLATE_DEBUG = True
TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.core.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
    "django.core.context_processors.request",
    'social.apps.django_app.context_processors.backends',
    'social.apps.django_app.context_processors.login_redirect',
#    "audit_log.middleware.UserLoggingMiddleware",
)

ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = (
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'pagination',
    'django_extensions',
    'djcelery',
    'cookies',
    'concepts',
    'oauth2_provider',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'guardian',
     'social.apps.django_app.default',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'pagination.middleware.PaginationMiddleware',
)


AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend', # default
    'guardian.backends.ObjectPermissionBackend',
    'social.backends.github.GithubOAuth2',
)
ANONYMOUS_USER_ID = -1

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    # 'DEFAULT_PERMISSION_CLASSES': [
    #     'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly'
    # ],
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework_xml.parsers.XMLParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework_xml.renderers.XMLRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'oauth2_provider.ext.rest_framework.OAuth2Authentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 10,
}


ROOT_URLCONF = 'jars.urls'

WSGI_APPLICATION = 'jars.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2', # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
#         'NAME': 'jars_tests',                      # Or path to database file if using sqlite3.
#         # The following settings are not used with sqlite3:
#         'USER': 'jars_tests',
#         'PASSWORD': 'test_password',
#         'HOST': 'localhost',                      # Empty for localhost through domain sockets or           '127.0.0.1' for localhost through TCP.
#         'PORT': '',                      # Set to empty string for default.
#     }
# }
# else:
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'OPTIONS': {
#             'read_default_file': '/diging/applications/jars/mysql.cnf',
#         },
#     }
# }


# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

BASE_URL = os.environ.get('BASE_URL', '/amphora/')
STATIC_URL = BASE_URL + 'static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT')

MEDIA_ROOT = os.environ.get('MEDIA_ROOT')
MEDIA_URL = BASE_URL + 'media/'

URI_NAMESPACE = 'http://diging.asu.edu/amphora'

RDFNS = 'http://www.w3.org/2000/01/rdf-schema#'
LITERAL = 'http://www.w3.org/2000/01/rdf-schema#Literal'

HOSTNAME = socket.gethostname()

# STATICFILES_STORAGE = 'whitenoise.django.GzipManifestStaticFilesStorage'
#
# DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'

# AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY')
# AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_KEY')
# AWS_STORAGE_BUCKET_NAME = os.environ.get('S3_BUCKET')
#
# AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
# MEDIAFILES_LOCATION = 'media'
# MEDIA_URL = "https://%s/%s/" % (AWS_S3_CUSTOM_DOMAIN, MEDIAFILES_LOCATION)
# DEFAULT_FILE_STORAGE = 'jars.custom_storages.MediaStorage'

CORS_ORIGIN_ALLOW_ALL = True
CELERY_IMPORTS = ('cookies.tasks',)
CELERY_DEFAULT_RATE_LIMIT = "100/m"


FILE_UPLOAD_HANDLERS = ["cookies.uploadhandler.PersistentTemporaryFileUploadHandler",]
FILE_UPLOAD_TEMP_DIR = os.path.join(MEDIA_ROOT, 'uploads')


SOCIAL_AUTH_GITHUB_KEY = os.environ.get('SOCIAL_AUTH_GITHUB_KEY', None)
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get('SOCIAL_AUTH_GITHUB_SECRET', None)
SOCIAL_AUTH_LOGIN_REDIRECT_URL = BASE_URL
SOCIAL_AUTH_GITHUB_SCOPE = ['user']

LOGIN_URL = LOCAL_PATH + 'login/github/'
LOGIN_REDIRECT_URL = 'index'


GILES = 'https://diging.asu.edu/giles-review'
GET = requests.get
POST = requests.post
IMAGE_AFFIXES = ['png', 'jpg', 'jpeg', 'tiff', 'tif']

import json
# def GET_METHOD(path, params={}, headers={}):
#     class MockResponse(object):
#         def __init__(self, status_code, content):
#             self.status_code = status_code
#             self.content = content
#
#         def json(self):
#             return json.loads(self.content)
#
#     if path.startswith('/'.join([GILES, 'rest', 'files', 'upload'])):
#         with open('cookies/tests/data/giles_file_response.json', 'r') as f:
#             return MockResponse(200, f.read())
