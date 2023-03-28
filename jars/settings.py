import os, socket, sys, requests, dj_database_url
from urlparse import urlparse, urljoin
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
HOSTNAME = socket.gethostname()

TEST = 'test' in sys.argv or eval(os.environ.get('TEST', 'False'))
DEVELOP = 'runserver' in sys.argv or eval(os.environ.get('DEVELOP', 'False'))
DEBUG = eval(os.environ.get('DEBUG', 'False')) or TEST or DEVELOP
SECRET_KEY = os.environ.get('SECRET_KEY', 'fake')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': (
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
            ) + ((
                "django.template.context_processors.request",
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                #    "audit_log.middleware.UserLoggingMiddleware",
            ) if not TEST else ()),
        },
    },
]

ALLOWED_HOSTS = ['*']

# TODO: clean out dependencies that are no longer used.
INSTALLED_APPS = (
    'dal',
    'dal_select2',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dj_pagination',
    'django_extensions',
    'djcelery',
    'cookies',
    'concepts',
    'oauth2_provider',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
    'social_django',
    'django.contrib.humanize',
    'pg_fts',
)

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'jars.auth.GithubTokenBackendMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'dj_pagination.middleware.PaginationMiddleware',
)

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
        'rest_framework.renderers.JSONRenderer',
        # 'rest_framework_xml.renderers.XMLRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'oauth2_provider.contrib.rest_framework.OAuth2Authentication',
        'jars.auth.GithubTokenBackend',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',)

}
CORS_ORIGIN_ALLOW_ALL = True

ROOT_URLCONF = 'jars.urls'

WSGI_APPLICATION = 'jars.wsgi.application'

# Database.
if DEVELOP or TEST:
    if os.environ.get('BACKEND', 'sqlite') == 'postgres':
        DATABASES = {
            'default': dj_database_url.config()
        }
        DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql_psycopg2'
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
            }
        }
else:
    DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.environ.get('DB_NAME', '/'),
        'USER': os.environ.get('DB_USER', '/'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '/'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
BASE_URL = os.environ.get('BASE_URL', '/')
STATIC_URL = BASE_URL + 'static/'
STATIC_ROOT = os.environ.get('STATIC_ROOT', '')
MEDIA_ROOT = os.environ.get('MEDIA_ROOT', '')
MEDIA_URL = BASE_URL + 'media/'

EXPORT_ROOT = os.environ.get('EXPORT_ROOT', os.path.join(MEDIA_ROOT, 'export'))


# Celery: async tasks.
CELERY_IMPORTS = ('cookies.tasks',)
CELERY_DEFAULT_RATE_LIMIT = "100/m"
CELERYBEAT_SCHEDULE = {
    'check_giles_uploads': {
        'task': 'cookies.tasks.check_giles_uploads',
        'schedule': timedelta(seconds=30)
    }
}

# File handling.
FILE_UPLOAD_HANDLERS = ["cookies.uploadhandler.PersistentTemporaryFileUploadHandler",]
FILE_UPLOAD_TEMP_DIR = os.path.join(MEDIA_ROOT, 'upload')

# Authentication.
AUTHENTICATION_BACKENDS = (
    'jars.backends.AllowAllUsersModelBackend', # default
    'guardian.backends.ObjectPermissionBackend',
    'social_core.backends.github.GithubOAuth2',
    'jars.auth.GithubAuthenticationBackend',
    'jars.auth.AmphoraTokenAuthBackend',
)
ANONYMOUS_USER_ID = -1

SOCIAL_AUTH_GITHUB_KEY = os.environ.get('SOCIAL_AUTH_GITHUB_KEY', None)
SOCIAL_AUTH_GITHUB_SECRET = os.environ.get('SOCIAL_AUTH_GITHUB_SECRET', None)
SOCIAL_AUTH_LOGIN_REDIRECT_URL = BASE_URL
SOCIAL_AUTH_GITHUB_SCOPE = ['user']
SOCIAL_AUTH_INACTIVE_USER_URL = BASE_URL + 'inactive/'

if not TEST and not DEVELOP:    # MySQL has a hard time with life.
    SOCIAL_AUTH_UID_LENGTH = 122
    SOCIAL_AUTH_NONCE_SERVER_URL_LENGTH = 100
    SOCIAL_AUTH_ASSOCIATION_SERVER_URL_LENGTH = 135
    SOCIAL_AUTH_ASSOCIATION_HANDLE_LENGTH = 125

LOGIN_URL = BASE_URL
LOGIN_REDIRECT_URL = BASE_URL + 'dashboard/'

# Giles and HTTP.
GILES = os.environ.get('GILES', 'https://diging.asu.edu/geco-giles-staging')
if GILES.endswith('/'):
    GILES = GILES[:-1]
IMAGE_AFFIXES = ['png', 'jpg', 'jpeg', 'tiff', 'tif']
GILES_APP_TOKEN = os.environ.get('GILES_APP_TOKEN', 'nope')
GILES_DEFAULT_PROVIDER = os.environ.get('GILES_DEFAULT_PROVIDER', 'github')
GILES_TOKEN_EXPIRATION = os.environ.get('GILES_TOKEN_EXPIRATION', 120)    # min.
GILES_CONTENT_FORMAT_STRING = GILES + '/rest/files/{giles_file_id}/content'
MAX_GILES_UPLOADS = 200

# Defines creators for each type of document keys in Giles response.
#  - Keys in this map are the keys that may be present in
#    Giles JSON response for a processed document.
#  - Values in this map specify what Amphora should use as a "target" while
#    defining creator metadata for each document resource in Giles JSON
#    response.
GILES_RESPONSE_CREATOR_MAP = {
    'ocr' : 'Tesseract',
    'text': 'PDF Extract',
    'extractedText': 'PDF Extract',
}

# Metadata globals.
RDFNS = 'http://www.w3.org/2000/01/rdf-schema#'
LITERAL = 'http://www.w3.org/2000/01/rdf-schema#Literal'
PROVENANCE = 'http://purl.org/dc/terms/provenance'
IS_PART_OF = 'http://purl.org/dc/terms/isPartOf'

URI_NAMESPACE = os.environ.get('NAMESPACE', 'http://diging.asu.edu/amphora')


LOGFORMAT = '%(asctime)s:%(levelname)s:%(pathname)s:%(lineno)d:: %(message)s'
LOGLEVEL = os.environ.get('LOGLEVEL', 'ERROR')
# LOGLEVEL = 'ERROR'
import logging
logging.basicConfig(format=LOGFORMAT)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOGLEVEL)


CELERYD_TASK_TIME_LIMIT = 300000


GOAT = os.environ.get('GOAT', 'http://black-goat.herokuapp.com')
GOAT_APP_TOKEN = os.environ.get('GOAT_APP_TOKEN')

ADMIN_EMAIL = u'erick.peirson@asu.edu'
REPOSITORY_NAME = u'Amphora'

SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# If True, files will be deleted as soon as they are successfully added to
#  Giles.
DELETE_LOCAL_FILES = True
APPEND_SLASH = True    # Rewrite URLs that lack a slash.
USE_THOUSAND_SEPARATOR = False


HATHITRUST_CLIENT_KEY = os.environ.get('HATHITRUST_CLIENT_KEY')
HATHITRUST_CLIENT_SECRET = os.environ.get('HATHITRUST_CLIENT_SECRET')
HATHITRUST_CONTENT_BASE = 'https://babel.hathitrust.org/cgi/htd'
HATHITRUST_METADATA_BASE = 'https://catalog.hathitrust.org/api/volumes/brief/htid'




CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'content_cache',
    },
    'remote_content': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'content_cache',
    },
    'rest_cache': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'rest_cache',
    }
}


SESSION_COOKIE_NAME = 'amphora'
