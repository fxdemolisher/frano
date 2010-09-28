from django.conf.urls.defaults import *
from django.views.static import serve
from settings import DEBUG

import os

urlpatterns = patterns('frano.views',
  (r'^$', 'index'),
  (r'^index.html', 'index'),
  (r'^about.html', 'about'),
  (r'^feedback.html', 'feedback'),
  (r'^legal.html', 'legal'),
  (r'^login.html', 'login'),
  (r'^register.html', 'register'),
  (r'^logout.html', 'logout'),
  (r'^settings.html', 'settings'),
  (r'^portfolio.html', 'portfolio'),
  (r'^createPortfolio.html', 'create_portfolio'),
  (r'^deletePortfolio.html', 'delete_portfolio'),
  (r'^updatePortfolios.html', 'update_portfolios'),
  (r'^addTransaction.html', 'add_transaction'),
  (r'^deleteTransaction.html', 'delete_transaction'),
)

if DEBUG:
  dir = os.path.realpath('./../static')
  urlpatterns += patterns('django.views.static',
    (r'^css/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/css' }),
    (r'^img/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/img' }),
    (r'^js/(?P<path>.*)$', 'serve', { 'document_root' : dir + '/js' }),
  )
