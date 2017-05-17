import os, socket, sys, requests, dj_database_url
from urlparse import urlparse
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
HOSTNAME = socket.gethostname()

TEST = 'test' in sys.argv or eval(os.environ.get('TEST', 'False'))
DEVELOP = 'runserver' in sys.argv or eval(os.environ.get('DEVELOP', 'False'))
DEBUG = eval(os.environ.get('DEBUG', 'False')) or TEST or DEVELOP
SECRET_KEY = os.environ.get('SECRET_KEY', 'fake')

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
)

if not TEST:    # These are removed for test performance.
    TEMPLATE_CONTEXT_PROCESSORS += (
        "django.core.context_processors.request",
        'social_django.context_processors.backends',
        'social_django.context_processors.login_redirect',
        #    "audit_log.middleware.UserLoggingMiddleware",
    )

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
    'pagination',
    'django_extensions',
    'djcelery',
    'cookies',
    'concepts',
    'oauth2_provider',
    'corsheaders',
    'rest_framework',
    'rest_framework.authtoken',
     'social_django',
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
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'oauth2_provider.ext.rest_framework.OAuth2Authentication',
        'jars.auth.GithubTokenBackend',
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
        'default': dj_database_url.config()
    }
    DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql_psycopg2'

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
GILES = os.environ.get('GILES', 'https://diging-dev.asu.edu/giles-review')
if GILES.endswith('/'):
    GILES = GILES[:-1]
IMAGE_AFFIXES = ['png', 'jpg', 'jpeg', 'tiff', 'tif']
GILES_APP_TOKEN = os.environ.get('GILES_APP_TOKEN', 'nope')
GILES_DEFAULT_PROVIDER = os.environ.get('GILES_DEFAULT_PROVIDER', 'github')
GILES_TOKEN_EXPIRATION = os.environ.get('GILES_TOKEN_EXPIRATION', 120)    # min.
MAX_GILES_UPLOADS = 50

# Metadata globals.
RDFNS = 'http://www.w3.org/2000/01/rdf-schema#'
LITERAL = 'http://www.w3.org/2000/01/rdf-schema#Literal'
PROVENANCE = 'http://purl.org/dc/terms/provenance'
IS_PART_OF = 'http://purl.org/dc/terms/isPartOf'

URI_NAMESPACE = os.environ.get('NAMESPACE', 'http://diging.asu.edu/amphora')


LOGLEVEL = os.environ.get('LOGLEVEL', 'ERROR')
# LOGLEVEL = 'ERROR'
import logging
logging.basicConfig()
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
