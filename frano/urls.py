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
  (r'^login.html', 'login'),
  (r'^logout.html', 'logout'),
  (r'^createPortfolio.html', 'create_portfolio'),
  (r'^(?P<portfolio_id>\d+)/addTransaction.html', 'add_transaction'),
  (r'^(?P<portfolio_id>\d+)/(?P<transaction_id>\d+)/remove.html', 'remove_transaction'),
  (r'^(?P<portfolio_id>\d+)/settings.html', 'portfolio_settings'),
  (r'^(?P<portfolio_id>\d+)/update.html', 'portfolio_update'),
  (r'^(?P<portfolio_id>\d+)/remove.html', 'portfolio_remove'),
  (r'^(?P<portfolio_id>\d+)/positions.html', 'portfolio_positions'),
  (r'^(?P<portfolio_id>\d+)/transactions.html', 'portfolio_transactions'),
  (r'^(?P<read_only_token>\w+)/view.html', 'portfolio_read_only'),
)

if DEBUG:
  dir = os.path.realpath(os.path.dirname(__file__)) + "/static/"
  urlpatterns += patterns('django.views.static',
    (r'^css/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/css' }),
    (r'^img/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/img' }),
    (r'^js/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/js' }),
  )
