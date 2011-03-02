# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime

from django.shortcuts import redirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from models import Portfolio
from models import User
from models import create_user
from settings import BUILD_VERSION
from settings import BUILD_DATETIME

#-------------\
#  CONSTANTS  |
#-------------/

DEMO_USER_OPEN_ID = 'SAMPLE_USER_ONLY'

#---------------------\
#  EXPOSED FUNCTIONS  |
#---------------------/

def get_demo_user():
  candidate = User.objects.filter(open_id = DEMO_USER_OPEN_ID)
  if candidate.count() == 1:
    return candidate[0]
  else:
    return create_user(DEMO_USER_OPEN_ID, DEMO_USER_OPEN_ID)

def render_page(template_name, request, user = None, portfolio = None, portfolios = None, extra_dictionary = None):
  dictionary = extra_dictionary
  if dictionary == None:
    dictionary = { }
   
  if user == None:
    user_id = request.session.get('user_id')
    if user_id != None:
      user = User.objects.filter(id = user_id)[0]
    
  if user != None and portfolios == None:
    portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  
  dictionary['BUILD_VERSION'] = BUILD_VERSION
  dictionary['BUILD_DATETIME'] = BUILD_DATETIME
  dictionary['user'] = user
  dictionary['portfolio'] = portfolio
  dictionary['portfolios'] = portfolios
  dictionary['today'] = datetime.now()
  
  return render_to_response(template_name, dictionary, context_instance = RequestContext(request))

def redirect_to_portfolio_action(action, portfolio, query_string = None):
  return redirect("/%d/%s.html%s" % (portfolio.id, action, ('' if query_string == None else "?%s" % query_string)))

def logout_user(request):
  request.session['user_id'] = None
  del(request.session['user_id'])
  return redirect("/index.html")

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/
