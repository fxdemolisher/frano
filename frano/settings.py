# Django settings for tracker project.

import datetime

DEBUG = True
TEMPLATE_DEBUG = True

DATABASE_ENGINE = 'mysql'
DATABASE_NAME = 'frano'
DATABASE_USER = 'tracker'
DATABASE_PASSWORD = 'trackmystocks'
DATABASE_HOST = 'localhost'
DATABASE_PORT = '3306'
DATABASE_OPTIONS = { "init_command" : "SET storage_engine=INNODB" }

TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
USE_I18N = False

SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SECRET_KEY = '&1*y2=g+h57qxa&qct#z6+408l5$i5p7&cjp6)@@nfqwtrxn3&'

TEMPLATE_LOADERS = (
  'django.template.loaders.app_directories.load_template_source',
)

TEMPLATE_DIRS = ( )

TEMPLATE_CONTEXT_PROCESSORS = (
  'django.core.context_processors.request',
)

MIDDLEWARE_CLASSES = (
  'django.middleware.common.CommonMiddleware',
  'django.contrib.sessions.middleware.SessionMiddleware',
)

ROOT_URLCONF = 'frano.urls'

INSTALLED_APPS = (
  'django.contrib.sessions',
  'frano'
)

QUOTE_TIMEOUT_DELTA = datetime.timedelta(0, 0, 0, 0, 15)
CASH_SYMBOL = '*CASH'
