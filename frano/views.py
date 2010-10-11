# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import json, math

from datetime import datetime
from urllib import urlopen

#from django import forms
#from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext

from models import User, Portfolio, Transaction, Quote
from settings import BUILD_VERSION, BUILD_DATETIME, JANRAIN_API_KEY

#--------------\
#  DECORATORS  |
#--------------/

def standard_settings_context(request):
  user_id = request.session.get('user_id')
  user = None
  if user_id != None:
    user = User.objects.filter(id = user_id)[0]
  
  return { 
      'BUILD_VERSION' : BUILD_VERSION,
      'BUILD_DATETIME' : BUILD_DATETIME,
      'user' : user,
    }

def login_required_decorator(view_function):
  def view_function_decorated(request):
    user_id = request.session.get('user_id')
    if user_id == None:
      return redirect("/index.html")
    
    else:
      user = User.objects.filter(id = user_id)[0]
      return view_function(request, user)
    
  return view_function_decorated

#---------\
#  VIEWS  |
#---------/

def index(request):
  transactions = get_sample_transactions(request)
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  positions = get_positions(symbols, quotes, transactions)
  summary = get_summary(positions, transactions)
  
  return render_to_response('index.html', { 'positions': positions, 'summary' : summary }, context_instance = RequestContext(request))

def legal(request):
  return render_to_response('legal.html', { }, context_instance = RequestContext(request))

def feedback(request):
  return render_to_response('feedback.html', { }, context_instance = RequestContext(request))

def login(request):
  token = None
  if request.method == 'POST':
    token = request.POST.get('token')
    
  else:
    token = request.GET.get('token')
    
  if token == None:
    return redirect("/index.html?loginFailed=true")
  
  u = None
  try:
    u = urlopen('https://rpxnow.com/api/v2/auth_info?apiKey=%s&token=%s' % (JANRAIN_API_KEY, token))
    auth_info = json.loads(u.read())
    status = auth_info['stat']
    if status != 'ok':
      return redirect("/index.html?loginFailed=true")
    
    profile = auth_info['profile']
    identifier = profile['identifier']
    email = profile['email'] if profile.has_key('email') else None
    candidate = User.objects.filter(open_id = identifier)
    user = None
    if candidate.count() == 0:
      user = User.create(identifier, email)
      
    else:
      user = candidate[0]
      
    request.session['user_id'] = user.id
    
  finally:
    if u != None:
      u.close()
      
  return redirect("/account.html")

def logout(request):
  request.session['user_id'] = None
  del(request.session['user_id'])
  return redirect("/index.html")

def delete_sample_position(request):
  remove_symbol = request.GET.get('symbol')
  short_infos = request.session.get('sample_transactions', DEFAULT_SAMPLE_TRANSACTIONS)
  for i in range(len(short_infos)):
    if short_infos[i][0] == remove_symbol:
      del(short_infos[i])
      break
  
  request.session['sample_transactions'] = short_infos
  return redirect("/index.html")
  
#--------\
#  FORMS |
#--------/

#-------------\
#  UTILITIES  |
#-------------/

DEFAULT_SAMPLE_TRANSACTIONS = [
    [ Quote.CASH_SYMBOL, 1000000, 1.0 ],
    [ 'SPY', 1514, 132.08 ],
    [ 'IWM', 1481, 67.48 ],
    [ 'EFA', 2879, 69.46 ],
    [ 'EEM', 2331, 42.87 ],
    [ 'GLD', 1112, 89.91 ],
    [ 'TIP', 905, 110.42 ],
  ]

def get_sample_transactions(request):
  short_infos = request.session.get('sample_transactions', DEFAULT_SAMPLE_TRANSACTIONS)
  request.session['sample_transactions'] = short_infos
  
  transactions = []
  for info in short_infos:
    transaction = Transaction()
    transaction.as_of_date = datetime.now().date()
    transaction.symbol = info[0]
    transaction.quantity = abs(info[1])
    transaction.price = info[2]
    transaction.total = transaction.quantity * transaction.price 
    
    if transaction.symbol == Quote.CASH_SYMBOL:
      transaction.type = ('DEPOSIT' if info[1] >= 0 else 'WITHDRAW')
      
    else:
      transaction.type = ('BUY' if info[1] >= 0 else 'SELL')
      
    transactions.append(transaction)
      
  return transactions
      
    
def get_positions(symbols, quotes, transactions):
  lots = get_lots(symbols, transactions)
  
  total_market_value = 0
  positions = []
  for symbol in sorted(lots):
    cost = 0
    quantity = 0
    for lot in lots[symbol]:
      cost += lot.quantity * lot.price
      quantity += lot.quantity
     
    cost_price = (cost / quantity) if quantity > 0 else 0
    position = Position(
        quotes[symbol].last_trade, 
        symbol, 
        quotes[symbol].name, 
        quantity, 
        float(quotes[symbol].price), 
        cost_price, 
        float(quotes[symbol].previous_close_price), 
        0, 
        lots[symbol]
      )
    
    total_market_value += position.market_value
    positions.append(position)

  for position in positions:
    position.allocation = ((position.market_value / total_market_value * 100) if total_market_value != 0 else 0)
    
  return positions

def get_lots(symbols, transactions):
  cash = 0.0
  first_cash_date = None
  lots = dict([(symbol, []) for symbol in symbols])
  for transaction in reversed(sorted(transactions, key = (lambda transaction: transaction.as_of_date))):
    cur_lots = lots.get(transaction.symbol)
    
    if transaction.type == 'DEPOSIT' or transaction.type == 'ADJUST' or transaction.type == 'SELL':
      cash += float(transaction.total)
      first_cash_date = (transaction.as_of_date if first_cash_date is None else first_cash_date)
      
    elif transaction.type == 'WITHDRAW' or transaction.type == 'BUY':
      cash -= float(transaction.total)
      first_cash_date = (transaction.as_of_date if first_cash_date is None else first_cash_date)
      
    if transaction.type == 'BUY':
      cur_lots.append(TaxLot(transaction.as_of_date, float(transaction.quantity), float(transaction.price)))

    elif transaction.type == 'SELL':
      q = float(transaction.quantity)
      while q > 0 and len(cur_lots) > 0:
        first_lot = cur_lots[0]
        if(q < first_lot.quantity):
          first_lot.quantity -= q
          q = 0
          
        else:
          q -= first_lot.quantity
          del(cur_lots[0])

  lots[Quote.CASH_SYMBOL] = [ TaxLot((first_cash_date if first_cash_date != None else datetime.now()), cash, 1.0) ]
  return lots

def get_summary(positions, transactions):
  as_of_date = max([position.as_of_date for position in positions])
  start_date = min([transaction.as_of_date for transaction in transactions])
    
  cost_basis = 0
  market_value = 0
  opening_market_value = 0
  for position in positions:
    cost_basis += position.cost_price * position.quantity
    market_value += position.market_value
    opening_market_value += position.opening_market_value
    
  xirr_percent = get_xirr_percent_for_transactions(transactions, as_of_date, market_value)

  return Summary(as_of_date, start_date, market_value, cost_basis, opening_market_value, xirr_percent)
  
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

def xirr(dates, payments):
  years = [ (date - dates[0]).days / 365.0 for date in dates ]
  residual = 1
  step = 0.05
  guess = 0.1
  limit = 10000
  while abs(residual) > 0.001 and limit > 0:
    residual = 0
    for i in range(len(dates)):
      residual += payments[i] / ((1 + guess)**years[i])
    
    limit -= 1
    if abs(residual) > 0.001:
      if residual > 0:
        guess += step
      else:
        guess -= step
        step /= 2.0
  
  return (guess if limit > 0 else None)

  
#-----------------\
#  VALUE OBJECTS  |
#-----------------/
  
class TaxLot:
  def __init__(self, as_of_date, quantity, price):
    self.as_of_date = as_of_date
    self.quantity = quantity
    self.price = price
    
  def __repr__(self):
    return "%.4f@.4f on %s" % (self.quantity, self.price, self.as_of_date)
    
class Position:
  def __init__(self, as_of_date, symbol, name, quantity, price, cost_price, opening_price, allocation, lots):
    self.as_of_date = as_of_date
    self.symbol = symbol
    self.name = name
    self.quantity = quantity
    self.price = price
    self.cost_price = cost_price
    self.opening_price = opening_price
    self.allocation = allocation
    self.lots = lots
    
    self.market_value = quantity * price
    self.cost_basis = quantity * cost_price
    self.opening_market_value = quantity * opening_price
    self.day_pl = (self.market_value - self.opening_market_value)
    self.day_pl_percent = (((self.day_pl / self.opening_market_value) * 100) if self.opening_market_value != 0 else 0)
    self.pl = (self.market_value - self.cost_basis)
    self.pl_percent = (((self.pl / self.cost_basis) * 100) if self.cost_basis != 0 else 0)
    
  def __repr__(self):
    return "%.4f of %s" % (self.quantity, self.symbol)

class Summary:
  def __init__(self, as_of_date, start_date, market_value, cost_basis, opening_market_value, xirr_percent):
    self.as_of_date = as_of_date
    self.start_date = start_date
    self.market_value = market_value
    self.cost_basis = cost_basis
    self.opening_market_value = opening_market_value
    self.xirr_percent = xirr_percent
    
    self.pl = market_value - cost_basis
    self.pl_percent = ((self.pl / cost_basis) * 100) if cost_basis != 0 else 0
    self.day_pl = market_value - opening_market_value
    self.day_pl_percent = ((self.day_pl / opening_market_value) * 100) if opening_market_value != 0 else 0
    self.days = (as_of_date.date() - start_date).days
    self.annualized_pl_percent = (self.pl_percent / (self.days / 365.0)) if self.days != 0 else 0

#def portfolio_by_token_decorator(view_function):
#  def view_function_decorated(request, token):
#    read_write_candidate = Portfolio.objects.filter(token__exact = token)
#    portfolio = None
#    read_only = True
#    
#    if read_write_candidate.count() == 1:
#      portfolio = read_write_candidate[0]
#      read_only = False
#      
#    else:
#      read_only_candidate = Portfolio.objects.filter(read_only_token__exact = token)
#      if read_only_candidate.count() == 1:
#        portfolio = read_only_candidate[0]
#    
#    if portfolio == None:
#      return redirect("/index.html?notFound=true")
#    
#    else:
#      return view_function(request, portfolio, read_only)
#    
#  return view_function_decorated
#


#
#
#def create_portfolio(request):
#  name = request.POST.get('name')
#  if name == None or name == '':
#    return redirect('/index.html?nameRequired=true')
#  
#  portfolio = Portfolio.create(name)
#  return redirect ('/%s/settings.html' % (portfolio.token))
#
#def recover_portfolio(request):
#  email = request.POST.get('email')
#  candidates = Portfolio.objects.filter(recovery_email = email)
#  if candidates.count() == 0:
#    return redirect('/index.html?emailNotFound=true')
#  
#  text = 'The following is a list of your portfolios in the Frano system and their links:\n\n'
#  for portfolio in candidates:
#    text += 'Portfolio: %s\n' % portfolio.name
#    text += 'Read/Write: http://%s/%s/view.html\n' % ( request.META['HTTP_HOST'], portfolio.token)
#    text += 'Read-Only: http://%s/%s/view.html\n\n' % ( request.META['HTTP_HOST'], portfolio.read_only_token)
#    
#  print text
#  send_mail('[Frano] Portfolio(s) recovery emails', text, 'gennadiy@apps.carelessmusings.com', [ email ], fail_silently = True)
#  
#  return redirect('/index.html?mailSent=true')
#
#@portfolio_by_token_decorator
#@redirect_to_view_if_read_only_decorator
#def settings(request, portfolio):
#  form = SettingsForm()
#  if request.method == 'POST':
#    form = SettingsForm(request.POST)
#    
#    if form.is_valid():
#      portfolio.name = form.cleaned_data['name'].encode('UTF8')
#      portfolio.recovery_email = form.cleaned_data['email'].encode('UTF8')
#      portfolio.save()
#  
#  return render_to_response('settings.html', { 'portfolio' : portfolio, 'form' : form }, context_instance = RequestContext(request))
#
#class SettingsForm(forms.Form):
#  NAME_ERROR_MESSAGES = {
#    'required' : 'Please enter a portfolio name',
#    'max_length' : 'Name cannot be longer than 255 characters',
#  }
#  
#  EMAIL_ERROR_MESSAGES = {
#    'required' : 'Please enter your email address',
#    'invalid' : 'Please enter a valid email address',
#    'max_length' : 'Email cannot be longer than 255 characters',
#  }
#  
#  name = forms.CharField(max_length = 255, error_messages = NAME_ERROR_MESSAGES)
#  email = forms.EmailField(max_length = 255, error_messages = EMAIL_ERROR_MESSAGES)
#
#@portfolio_by_token_decorator
#def view_portfolio(request, portfolio, read_only):
#  transaction_infos = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
#  paginator = Paginator(transaction_infos, 5)
#  try: 
#    page = int(request.GET.get('page', '1'))
#  except ValueError:
#    page = 1
#  
#  transactions = paginator.page(max(1, min(page, paginator.num_pages)))
#  
#  symbols = set([t.symbol for t in transaction_infos] + [ Quote.CASH_SYMBOL ])
#  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
#  types = dict(Transaction.TRANSACTION_TYPES)
#  for transaction in transactions.object_list:
#    transaction.symbol_name = quotes[transaction.symbol].name
#    transaction.type_text = types[transaction.type]
#  
#  positions = []
#
#  context = {
#      'portfolio' : portfolio,
#      'read_only' : read_only,
#      'transactions' : transactions,
#      'positions' : positions,
#    }
#
#  if paginator.count > 0:
#    lots = get_position_lots(transaction_infos)
#    populate_positions(quotes, positions, lots)
#    
#    as_of_date = max([quotes[symbol].last_trade for symbol in quotes])
#    portfolio_start = min([info.as_of_date for info in transaction_infos])
#    
#    cost_basis = sum([(p['cost_price'] * p['quantity']) for p in positions])
#    market_value = sum([p['market_value'] for p in positions])
#    opening_market_value = sum([p['opening_market_value'] for p in positions])
#    
#    pl = market_value - cost_basis
#    pl_percent = ((pl / cost_basis) * 100) if cost_basis != 0 else 0
#    days = (as_of_date.date() - portfolio_start).days
#    annualized_pl_percent = (pl_percent / (days / 365.0)) if days != 0 else 0
#    
#    day_pl = market_value - opening_market_value
#    day_pl_percent = ((day_pl / opening_market_value) * 100) if opening_market_value != 0 else 0
#    
#    xirr_percent = get_xirr_percent_for_transactions(transaction_infos, as_of_date, market_value)
#    
#    context['market_value'] = market_value
#    context['cost_basis'] = cost_basis
#    context['pl'] = pl
#    context['pl_class'] = pos_neg_css_class(pl)
#    context['pl_percent'] = pl_percent
#    context['day_pl'] = day_pl
#    context['day_pl_class'] = pos_neg_css_class(day_pl)
#    context['day_pl_percent'] = day_pl_percent
#    context['annualized_pl_percent'] = annualized_pl_percent
#    context['xirr_percent'] = xirr_percent
#    context['xirr_percent_class'] = pos_neg_css_class(xirr_percent)
#    context['as_of_date'] = as_of_date
#    context['portfolio_start'] = portfolio_start
#    
#  return render_to_response('portfolio.html', context, context_instance = RequestContext(request))
#
#


#@portfolio_by_token_decorator
#@redirect_to_view_if_read_only_decorator
#def remove_portfolio(request, portfolio):
#  portfolio.delete();
#  return redirect("/index.html?removed=true")
#
#@portfolio_by_token_decorator
#@redirect_to_view_if_read_only_decorator
#def add_transaction(request, portfolio):
#  form = TransactionForm(request.POST)
#  if not form.is_valid():
#    return redirect("/%s/view.html?invalidTransaction=true" % portfolio.token)
#  
#  transaction = Transaction()
#  transaction.portfolio = portfolio
#  transaction.type = form.cleaned_data.get('type').encode('UTF-8')
#  transaction.as_of_date = form.cleaned_data.get('as_of_date')
#  transaction.symbol = form.cleaned_data.get('symbol').encode('UTF-8')
#  transaction.quantity = form.cleaned_data.get('quantity')
#  transaction.price = form.cleaned_data.get('price')
#  transaction.total = form.cleaned_data.get('total')
#  transaction.save()
#  
#  return redirect("/%s/view.html" % portfolio.token)
#
#class TransactionForm(forms.Form):
#  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
#  as_of_date = forms.DateField()
#  symbol = forms.CharField(min_length = 1, max_length = 5)
#  quantity = forms.DecimalField(min_value = 0.01)
#  price = forms.DecimalField(min_value = 0.01)
#  total = forms.DecimalField(min_value = 0.01)
#
#@portfolio_by_token_decorator
#@redirect_to_view_if_read_only_decorator
#def remove_transaction(request, portfolio):
#  transaction_id = request.GET.get('id')
#  transaction = Transaction.objects.filter(id = transaction_id, portfolio__id__exact = portfolio.id)[0]
#  transaction.delete()
#  return redirect("/%s/view.html" % portfolio.token)
