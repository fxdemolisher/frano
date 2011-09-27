# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import datetime, os, glob

# build info
BUILD_VERSION = '0.12'
BUILD_DATETIME = datetime.datetime(2011, 9, 27, 7, 44, 0)

# base db set up, the rest is in environment specific setting files
DATABASE_ENGINE = 'mysql'
DATABASE_OPTIONS = { "init_command" : "SET storage_engine=INNODB" }

# locale set up
TIME_ZONE = 'America/New_York'
LANGUAGE_CODE = 'en-us'
USE_I18N = False

# template set up
TEMPLATE_LOADERS = ( 'django.template.loaders.app_directories.load_template_source', )
TEMPLATE_DIRS = ( )
TEMPLATE_CONTEXT_PROCESSORS =  ( 
    'django.core.context_processors.request', 
  )

# middleware and app set up
ROOT_URLCONF = 'frano.urls'
MIDDLEWARE_CLASSES = ( 
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware', 
  )

INSTALLED_APPS = ( 
    'django.contrib.sessions',
    'frano', 
    'frano.main',
    'frano.quotes',
    'frano.transactions',
    'frano.account',
    'frano.positions',
  )

# session settings
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# load external settings
settings_dir = os.path.realpath(os.path.dirname(__file__))
settings_files = glob.glob(os.path.join(settings_dir, 'settings/*.py'))
settings_files.sort()
for f in settings_files:
  execfile(os.path.abspath(f))
