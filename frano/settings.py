# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import datetime

import os, glob

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
TEMPLATE_CONTEXT_PROCESSORS = ( 'django.core.context_processors.request', )

# middleware and app set up
MIDDLEWARE_CLASSES = ( 'django.middleware.common.CommonMiddleware', )
ROOT_URLCONF = 'frano.urls'
INSTALLED_APPS = ( 'frano' )

# load external settings
settings_dir = os.path.realpath('./settings')
settings_files = glob.glob(os.path.join(settings_dir, '*.py'))
settings_files.sort()
for f in settings_files:
  execfile(os.path.abspath(f))
