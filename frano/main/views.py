# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import json
import random

from StringIO import StringIO
from urllib import urlopen

from django.shortcuts import redirect

from demo import get_demo_transactions
from models import Portfolio
from models import User
from models import create_portfolio
from models import create_user
from transactions.models import clone_transaction
from settings import JANRAIN_API_KEY
from view_utils import get_demo_user
from view_utils import logout_user
from view_utils import redirect_to_portfolio_action
from view_utils import render_page

#-------------\
#  CONSTANTS  |
#-------------/

#---------\
#  VIEWS  |
#---------/

def index(request):
  user_id = request.session.get('user_id')
  portfolio = None
  if user_id != None and request.GET.get('demo') == None:
    portfolio = Portfolio.objects.filter(user__id__exact = user_id)[0]
  else:
    portfolio_id = request.session.get('sample_portfolio_id')
    portfolio = _get_demo_portfolio(portfolio_id)
    request.session['sample_portfolio_id'] = portfolio.id
    
  return redirect("/%s/positions.html" % portfolio.id)

def read_only(request, read_only_token):
  return redirect("/%s/positions.html" % read_only_token)

def legal(request):
  return render_page('legal.html', request)
  
def feedback(request):
  return render_page('feedback.html', request)

def login(request):
  token = None
  if request.method == 'POST':
    token = request.POST.get('token')
    
  else:
    token = request.GET.get('token')
    
  if token == None:
    return redirect("/demo.html?loginFailed=true")
  
  u = None
  try:
    u = urlopen('https://rpxnow.com/api/v2/auth_info?apiKey=%s&token=%s' % (JANRAIN_API_KEY, token))
    auth_info = json.loads(u.read())
    status = auth_info['stat']
    if status != 'ok':
      return redirect("/demo.html?loginFailed=true")
    
    profile = auth_info['profile']
    identifier = profile['identifier']
    email = profile['email'] if profile.has_key('email') else None
    candidate = User.objects.filter(open_id = identifier)
    user = None
    portfolio = None
    target = 'transactions'
    if candidate.count() == 0:
      user = create_user(identifier, email)
      portfolio = create_portfolio(user, 'Default')
      
    else:
      user = candidate[0]
      portfolio = Portfolio.objects.filter(user__id__exact = user.id)[0]
      target = 'positions'
      
    request.session['user_id'] = user.id
    return redirect_to_portfolio_action(target, portfolio)
    
  finally:
    if u != None:
      u.close()
  
def logout(request):
  return logout_user(request)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _get_demo_portfolio(portfolio_id):
  if portfolio_id != None:
    candidate = Portfolio.objects.filter(id = portfolio_id)
    if candidate.count() == 1:
      return candidate[0]
  
  else:
    portfolio = create_portfolio(get_demo_user(), ('SAMPLE #%d' % random.randint(100000000, 999999999)))
    for sample_transaction in get_demo_transactions():
      transaction = clone_transaction(sample_transaction, portfolio);
      transaction.save()

    return portfolio
