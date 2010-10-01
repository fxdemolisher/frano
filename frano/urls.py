# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.conf.urls.defaults import *
from django.views.static import serve
from settings import DEBUG

import os

urlpatterns = patterns('frano.views',
  (r'^$', 'index'),
  (r'^index.html', 'index'),
  (r'^legal.html', 'legal'),
  (r'^feedback.html', 'feedback'),
  (r'^createPortfolio.html', 'create_portfolio'),
  (r'^(?P<token>\w{20})/settings.html', 'settings'),
  (r'^(?P<token>\w{20})/view.html', 'view_portfolio'),
  (r'^(?P<token>\w{20})/remove.html', 'remove_portfolio'),
  (r'^(?P<token>\w{20})/addTransaction.html', 'add_transaction'),
  (r'^(?P<token>\w{20})/removeTransaction.html', 'remove_transaction'),
)

if DEBUG:
  dir = os.path.realpath('./../static')
  urlpatterns += patterns('django.views.static',
    (r'^css/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/css' }),
    (r'^img/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/img' }),
    (r'^js/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/js' }),
  )
