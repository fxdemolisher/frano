# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import os

from django.conf.urls.defaults import *
from django.views.static import serve

from settings import SERVE_STATICS

# Main views
urlpatterns = patterns('frano.main.views',
  (r'^$', 'index'),
  (r'^index.html', 'index'),
  (r'^(?P<read_only_token>\w{10})/$', 'read_only'),
  (r'^legal.html', 'legal'),
  (r'^feedback.html', 'feedback'),
  (r'^login.html', 'login'),
  (r'^logout.html', 'logout'),
)

# Quote views
urlpatterns += patterns('frano.quotes.views',
  (r'^priceQuote.json', 'price_quote'),
)

# Account views
urlpatterns += patterns('frano.account.views',
  (r'^account.html', 'account'),
  (r'^removeAccount.html', 'remove'),
  (r'^createPortfolio.html', 'new_portfolio'),
  (r'^(?P<portfolio_id>\d+)/setName.html', 'set_portfolio_name'),
  (r'^(?P<portfolio_id>\d+)/remove.html', 'remove_portfolio'),  
)

# Transaction views
urlpatterns += patterns('frano.transactions.views',
  (r'^(?P<portfolio_id>\d+)/transactions.html', 'transactions'),
  (r'^(?P<portfolio_id>\d+)/addTransaction.html', 'add'),
  (r'^(?P<portfolio_id>\d+)/(?P<transaction_id>\d+)/remove.html', 'remove'),
  (r'^(?P<portfolio_id>\d+)/removeAllTransactions.html', 'remove_all'),
  (r'^(?P<portfolio_id>\d+)/(?P<transaction_id>\d+)/update.json', 'update'),
  (r'^(?P<portfolio_id>\d+)/exportTransactions.(?P<format>\w{3})', 'export'),
  (r'^(?P<portfolio_id>\d+)/importTransactions.html', 'import_form'),
  (r'^(?P<portfolio_id>\d+)/processImportTransactions.html', 'process_import'),
  (r'^(?P<portfolio_id>\d+)/requestImportType.html', 'request_import_type'),
)

# Position views
urlpatterns += patterns('frano.positions.views',
  (r'^(?P<portfolio_id>\d+)/positions.html', 'positions'),
  (r'^(?P<read_only_token>\w{10})/positions.html', 'read_only_positions'),
  (r'^(?P<portfolio_id>\d+)/allocation.html', 'allocation'),
  (r'^(?P<portfolio_id>\d+)/income.html', 'income'),
  (r'^(?P<read_only_token>\w{10})/income.html', 'read_only_income'),
)

if SERVE_STATICS:
  dir = os.path.realpath(os.path.dirname(__file__)) + "/static/"
  urlpatterns += patterns('django.views.static',
    (r'^css/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/css' }),
    (r'^img/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/img' }),
    (r'^js/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/js' }),
  )
