# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.shortcuts import redirect

from models import Portfolio
from models import User

#-------------\
#  CONSTANTS  |
#-------------/

#---------------------\
#  EXPOSED FUNCTIONS  |
#---------------------/

def portfolio_manipulation_decorator(view_function):
  def view_function_decorated(request, portfolio_id, read_only = False, **args):
    portfolio = Portfolio.objects.filter(id = int(portfolio_id))[0]
    sample_portfolio_id = request.session.get('sample_portfolio_id')
    user_id = request.session.get('user_id')
    is_sample = (portfolio.id == sample_portfolio_id)
    
    if is_sample or portfolio.user.id == user_id or read_only:
      return view_function(request, portfolio = portfolio, is_sample = is_sample, read_only = read_only, **args)
      
    return redirect("/index.html")
    
  return view_function_decorated

def login_required_decorator(view_function):
  def view_function_decorated(request, **args):
    user_id = request.session.get('user_id')
    if user_id == None:
      return redirect("/index.html")
    
    else:
      user = User.objects.filter(id = user_id)[0]
      args['user'] = user
      return view_function(request, **args)
    
  return view_function_decorated

def read_only_decorator(view_function):
  def view_function_decorated(request, read_only_token, **args):
    portfolio = Portfolio.objects.filter(read_only_token__exact = read_only_token)[0]
    return view_function(request, portfolio = portfolio, **args)
    
  return view_function_decorated

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

