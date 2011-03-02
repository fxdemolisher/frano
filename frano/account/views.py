# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django import forms
from django.shortcuts import redirect

from main.decorators import login_required_decorator
from main.decorators import portfolio_manipulation_decorator
from main.models import Portfolio
from main.models import create_portfolio
from main.view_utils import logout_user 
from main.view_utils import redirect_to_portfolio_action
from main.view_utils import render_page

#-------------\
#  CONSTANTS  |
#-------------/

#---------\
#  VIEWS  |
#---------/

@login_required_decorator
def account(request, user):
  return render_page('account.html', request)

@login_required_decorator
def remove(request, user):
  user.delete()
  return logout_user(request)

@login_required_decorator
def new_portfolio(request, user):
  form = PortfolioNameForm(request.POST)
  if not form.is_valid():
    return redirect("/account.html")
  
  name = _get_effective_portfolio_name(user, form.cleaned_data.get('portfolioName').encode('UTF-8'))
  portfolio = create_portfolio(user, name)
  
  return redirect_to_portfolio_action('importTransactions', portfolio)

@login_required_decorator
@portfolio_manipulation_decorator
def set_portfolio_name(request, user, portfolio, is_sample, read_only):
  form = PortfolioNameForm(request.POST)
  if form.is_valid():
    portfolio.name = _get_effective_portfolio_name(user, form.cleaned_data.get('portfolioName').encode('UTF-8'))
    portfolio.save()
    
  return redirect("/account.html")

@login_required_decorator
@portfolio_manipulation_decorator
def remove_portfolio(request, user, portfolio, is_sample, read_only):
  portfolio.delete()
  return redirect("/account.html")

#---------\
#  FORMS  |
#---------/

class PortfolioNameForm(forms.Form):
  portfolioName = forms.CharField(min_length = 3, max_length = 30)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _get_effective_portfolio_name(user, name):
  portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  names = set([ p.name for p in portfolios])
    
  index = 0
  new_name = name
  while new_name in names:
    index = index + 1
    new_name = "%s-%d" % (name, index)
    
  return new_name
