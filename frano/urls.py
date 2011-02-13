# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.conf.urls.defaults import *
from django.views.static import serve
from settings import SERVE_STATICS

import os

urlpatterns = patterns('frano.views',
  (r'^$', 'index'),
  (r'^index.html', 'index'),
  (r'^legal.html', 'legal'),
  (r'^feedback.html', 'feedback'),
  (r'^login.html', 'login'),
  (r'^logout.html', 'logout'),
  (r'^account.html', 'my_account'),
  (r'^removeAccount.html', 'remove_account'),
  (r'^createPortfolio.html', 'create_portfolio'),
  (r'^(?P<portfolio_id>\d+)/setName.html', 'portfolio_set_name'),
  (r'^(?P<portfolio_id>\d+)/remove.html', 'portfolio_remove'),
  (r'^(?P<portfolio_id>\d+)/addTransaction.html', 'add_transaction'),
  (r'^(?P<portfolio_id>\d+)/(?P<transaction_id>\d+)/remove.html', 'remove_transaction'),
  (r'^(?P<portfolio_id>\d+)/removeAllTransactions.html', 'remove_all_transactions'),
  (r'^(?P<portfolio_id>\d+)/(?P<transaction_id>\d+)/update.json', 'update_transaction'),
  (r'^(?P<portfolio_id>\d+)/positions.html', 'portfolio_positions'),
  (r'^(?P<portfolio_id>\d+)/transactions.html', 'portfolio_transactions'),
  (r'^(?P<portfolio_id>\d+)/exportTransactions.(?P<format>\w{3})', 'export_transactions'),
  (r'^(?P<portfolio_id>\d+)/importTransactions.html', 'import_transactions'),
  (r'^(?P<portfolio_id>\d+)/processImportTransactions.html', 'process_import_transactions'),
  (r'^(?P<portfolio_id>\d+)/requestImportType.html', 'request_import_type'),
  (r'^(?P<portfolio_id>\d+)/allocation.html', 'portfolio_allocation'),
  (r'^(?P<portfolio_id>\d+)/income.html', 'portfolio_income'),
  (r'^(?P<read_only_token>\w{10})/positions.html', 'portfolio_read_only_positions'),
  (r'^(?P<read_only_token>\w{10})/income.html', 'portfolio_read_only_income'),
  (r'^(?P<read_only_token>\w{10})/', 'portfolio_read_only'),
  (r'^priceQuote.json', 'price_quote'),
)

if SERVE_STATICS:
  dir = os.path.realpath(os.path.dirname(__file__)) + "/static/"
  urlpatterns += patterns('django.views.static',
    (r'^css/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/css' }),
    (r'^img/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/img' }),
    (r'^js/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/js' }),
  )
