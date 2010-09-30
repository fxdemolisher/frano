# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import math

from django import forms
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext

from models import User, Portfolio, Transaction, Quote
from utilities import xirr

def login_required_decorator(view_function):
  def view_function_decorated(request):
    if User.from_request(request) == None:
      return redirect('/login.html')
    else:
      return view_function(request)
    
  return view_function_decorated

def index(request):
  if User.from_request(request) != None:
    return redirect('/portfolio.html')
  
  return render_to_response('index.html', { }, context_instance = RequestContext(request))

def about(request):
  return render_to_response('about.html', { }, context_instance = RequestContext(request))

def feedback(request):
  return render_to_response('feedback.html', { }, context_instance = RequestContext(request))

def legal(request):
  return render_to_response('legal.html', { }, context_instance = RequestContext(request))

def register(request):
  return show_form_or_process(request, UsernamePasswordForm, process_registration, 'register.html')

def process_registration(request, formData, messages, context):
  if not User.username_exists(formData.username):
    user = User.register(formData.username, formData.password)
    user.to_request(request)
    return redirect("/portfolio.html")
  
  else:
    messages.append('We already have an account under that email')

def logout(request):
  User.clear_in_request(request)
  return redirect('/index.html')

def login(request):
  return show_form_or_process(request, UsernamePasswordForm, process_login, 'login.html')

def process_login(request, formData, messages, context):
  candidate = User.objects.filter(username = formData.username)
            
  if candidate.count() > 0 and candidate[0].check_password(formData.password):
    candidate[0].to_request(request)
    return redirect('/portfolio.html')
  
  else:
    messages.append('Invalid username or password')

@login_required_decorator
def settings(request):
  user = User.from_request(request)
  portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  return show_form_or_process(request, ChangeUsernamePasswordForm, process_settings, 'settings.html', { 'user': user, 'portfolios' : portfolios })

def process_settings(request, formData, messages, context):
  user = context.get('user')
  if user.check_password(formData.password):
    user.username = formData.username
    
    if formData.new_password != None and formData.new_password != '':
      user.set_password(formData.new_password)
      
    user.save()
    user.to_request(request)
    
  else :
    messages.append('Incorrect current password')

@login_required_decorator
def portfolio(request):
  user = User.from_request(request)
  portfolio_id = request.GET.get('id')
  portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  
  portfolio = None
  if portfolio_id != None:
    portfolio = Portfolio.objects.filter(id = portfolio_id)[0]
    
  elif portfolios.count() > 0:
    portfolio = portfolios[0]
    
  if portfolio == None:
    return redirect('/settings.html')
  
  transaction_infos = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
  paginator = Paginator(transaction_infos, 5)
  try: 
    page = int(request.GET.get('page', '1'))
  except ValueError:
    page = 1
  
  transactions = paginator.page(max(1, min(page, paginator.num_pages)))
  
  symbols = set([t.symbol for t in transaction_infos])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  types = dict(Transaction.TRANSACTION_TYPES)
  for transaction in transactions.object_list:
    transaction.symbol_name = quotes[transaction.symbol].name
    transaction.type_text = types[transaction.type]
  
  positions = []

  context = {
      'portfolios' : portfolios, 
      'portfolio' : portfolio,
      'transactions' : transactions,
      'positions' : positions,
    }

  if paginator.count > 0:
    lots = get_position_lots(transaction_infos)
    populate_positions(quotes, positions, lots)
    
    as_of_date = max([quotes[symbol].last_trade for symbol in quotes])
    portfolio_start = min([info.as_of_date for info in transaction_infos])
    market_value = sum([p['market_value'] for p in positions])
    cost_basis = sum([(p['cost_price'] * p['quantity']) for p in positions])
    pl = market_value - cost_basis
    pl_percent = (pl / cost_basis) * 100
    annualized_pl_percent = pl_percent / ((as_of_date.date() - portfolio_start).days / 365.0)
    xirr_percent = get_xirr_percent_for_transactions(transaction_infos, as_of_date, market_value)
    
    context['market_value'] = market_value
    context['cost_basis'] = cost_basis
    context['pl'] = pl
    context['pl_class'] = pos_neg_css_class(pl)
    context['pl_percent'] = pl_percent
    context['annualized_pl_percent'] = annualized_pl_percent
    context['xirr_percent'] = xirr_percent
    context['xirr_percent_class'] = pos_neg_css_class(xirr_percent)
    context['as_of_date'] = as_of_date
    context['portfolio_start'] = portfolio_start
    
  return render_to_response('portfolio.html', context, context_instance = RequestContext(request))

def get_position_lots(transactions):
  cash = 0.0
  lots = {}
  for transaction in reversed(transactions):
    if transaction.type == 'DEPOSIT' or transaction.type == 'ADJUST' or transaction.type == 'SELL':
      cash += float(transaction.total)
      
    elif transaction.type == 'WITHDRAW' or transaction.type == 'BUY':
      cash -= float(transaction.total)
      
    cur_lots = lots.get(transaction.symbol, [])
    lots[transaction.symbol] = cur_lots
      
    if transaction.type == 'BUY':
      cur_lots.append([ float(transaction.quantity), float(transaction.price) ])

    elif transaction.type == 'SELL':
      q = float(transaction.quantity)
      while q > 0 and len(cur_lots) > 0:
        if(q < cur_lots[0][0]):
          cur_lots[0][0] -= q
          q = 0
          
        else:
          q -= cur_lots[0][0]
          del(cur_lots[0])

  lots[Quote.CASH_SYMBOL] = [ [ cash, 1.0 ] ]
  return lots

def populate_positions(quotes, positions, lots):
  for symbol in sorted(lots):
    cost = sum([ (lot[0] * lot[1]) for lot in lots[symbol]])
    quantity = sum([ lot[0] for lot in lots[symbol]])
    opening_value = quantity * float(quotes[symbol].previous_close_price)
    current_value = quantity * float(quotes[symbol].price)
    
    day_pl = (current_value - opening_value)
    day_pl_percent = (day_pl / opening_value) * 100
    pl_percent = ((current_value - cost) / cost) * 100
    
    positions.append({
        'symbol' : symbol,
        'name' : quotes[symbol].name,
        'quantity' : quantity,
        'price' : quotes[symbol].price,
        'cost_price' : (cost / quantity),
        'market_value' : current_value,
        'day_pl' : day_pl,
        'day_pl_percent' : day_pl_percent,
        'day_pl_class' : pos_neg_css_class(day_pl),
        'pl_percent' : pl_percent,
        'pl_percent_class' : pos_neg_css_class(pl_percent),
      })
    
  market_value = sum([p['market_value'] for p in positions])
  for position in positions:
    position['allocation'] = position['market_value'] / market_value * 100

def get_xirr_percent_for_transactions(transactions, as_of_date, market_value):
  dates = []
  payments = []
  for transaction in reversed(transactions):
    if transaction.type == 'DEPOSIT' or transaction.type == 'WITHDRAW':
      dates.append(transaction.as_of_date)
      payments.append((-1 if transaction.type == 'DEPOSIT' else 1) * float(transaction.total))
      
  dates.append(as_of_date.date())
  payments.append(market_value)
  xirr_candidate = xirr(dates, payments)
  return (xirr_candidate * 100) if xirr_candidate != None else 0 

def pos_neg_css_class(value):
  return ('' if value == 0 else ('pos' if value > 0 else 'neg'))

@login_required_decorator
def create_portfolio(request):
  user = User.from_request(request)
  portfolio_count = Portfolio.objects.filter(user__id__exact = user.id).count()
  
  name = request.POST.get('name')
  if name == None or name == '':
    name = 'Default-%d' % (portfolio_count)
  
  portfolio = Portfolio()
  portfolio.user = user
  portfolio.name = name
  portfolio.save()
  
  return redirect ('/portfolio.html?portfolioId=%d' % (portfolio.id))

@login_required_decorator
def delete_portfolio(request):
  user = User.from_request(request)
  portfolio_id = request.GET.get('id')
  portfolio = Portfolio.objects.filter(id = portfolio_id, user__id__exact = user.id)[0]
  portfolio.delete()
  return redirect ('/settings.html')
  
@login_required_decorator
def update_portfolios(request):
  user = User.from_request(request)
  
  for field in request.POST:
    if field.startswith('name_'):
      portfolio_id = field[len('name_'):]
      name = request.POST.get(field)
      
      portfolio = Portfolio.objects.filter(id = portfolio_id)[0]
      if portfolio.user.id != user.id:
        return HttpResponse(status = 500)
      
      portfolio.name = name
      portfolio.save()
      
  return redirect ('/settings.html')

@login_required_decorator
def add_transaction(request):
  user = User.from_request(request)
  portfolio_id = request.POST.get('portfolio_id')
  portfolio = Portfolio.objects.filter(id = portfolio_id, user__id__exact = user.id)[0]
  
  form = TransactionForm(request.POST)
  if not form.is_valid():
    return redirect ("/portfolio.html?id=%d&invalid_transaction_input=True" % portfolio_id)
  
  formData = FormData(form)
  transaction = Transaction()
  transaction.portfolio = portfolio
  transaction.type = formData.type
  transaction.as_of_date = formData.as_of_date
  transaction.symbol = formData.symbol
  transaction.quantity = formData.quantity
  transaction.price = formData.price
  transaction.total = formData.total
  transaction.save()
  
  return redirect ("/portfolio.html?id=%s" % portfolio_id)

@login_required_decorator
def delete_transaction(request):
  user = User.from_request(request)
  transaction_id = request.GET.get('id')
  transaction = Transaction.objects.filter(id = transaction_id, portfolio__user__id__exact = user.id)[0]
  portfolio = transaction.portfolio
  transaction.delete()
  return redirect ('/portfolio.html?id=%d' % portfolio.id)

def show_form_or_process(request, formCls, process_function, template, context = {}):
  messages = []
  form = formCls()
  if request.method == 'POST':
    form = formCls(request.POST)
    formData = FormData(form)
    
    if form.is_valid():
      return_override = process_function(request, formData, messages, context)
      if return_override != None:
        return return_override
    
  context['form'] = form
  context['messages'] = messages
  return render_to_response(template, context, context_instance = RequestContext(request))

class FormData():
  def __init__(self, form):
    self.form = form
    
  def __getattr__(self, name):
    data = self.form.cleaned_data[name]
    print name
    if type(data) == 'unicode':
      data = data.encode('UTF8')
    
    return data

class UsernamePasswordForm(forms.Form):
  EMAIL_ERROR_MESSAGES = {
      'required' : 'Please enter your email address',
      'invalid' : 'Please enter a valid email address',
      'max_length' : 'Email cannot be longer than 100 characters',
    }

  PASSWORD_ERROR_MESSAGES = {
      'required' : 'Please enter your password',
      'min_length' : 'Passwords cannot be shorter than 6 characters',
      'max_length' : 'Passwords cannot be longer than 20 characters',
    }

  username = forms.EmailField(max_length = 100, error_messages = EMAIL_ERROR_MESSAGES)
  password = forms.CharField(min_length = 6, max_length = 20, error_messages = PASSWORD_ERROR_MESSAGES)


class ChangeUsernamePasswordForm(UsernamePasswordForm):
  new_password = forms.CharField(required = False, min_length = 6, max_length = 20, error_messages = UsernamePasswordForm.PASSWORD_ERROR_MESSAGES)
  
class TransactionForm(forms.Form):
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 5)
  quantity = forms.DecimalField(min_value = 0.01)
  price = forms.DecimalField(min_value = 0.01)
  total = forms.DecimalField(min_value = 0.01)
