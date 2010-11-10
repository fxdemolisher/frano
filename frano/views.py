# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import json, math, random

from datetime import date, datetime, timedelta
from urllib import urlopen

from django import forms
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.forms.formsets import formset_factory
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.contrib.sessions.models import Session

from import_export import transactions_as_csv, parse_transactions
from models import User, Portfolio, Transaction, Quote
from settings import BUILD_VERSION, BUILD_DATETIME, JANRAIN_API_KEY

#-------------\
#  CONSTANTS  |
#-------------/

SAMPLE_USER_OPEN_ID = 'SAMPLE_USER_ONLY'
TRANSACTIONS_BEFORE_SEE_ALL = 20

#--------------\
#  DECORATORS  |
#--------------/

def standard_settings_context(request):
  user_id = request.session.get('user_id')
  user = None
  portfolios = None
  if user_id != None:
    user = User.objects.filter(id = user_id)[0]
    portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  
  return { 
      'BUILD_VERSION' : BUILD_VERSION,
      'BUILD_DATETIME' : BUILD_DATETIME,
      'user' : user,
      'portfolios' : portfolios,
      'today' : datetime.now(),
    }

def portfolio_manipilation_decorator(view_function):
  def view_function_decorated(request, portfolio_id, **args):
    portfolio_id = int(portfolio_id)
    sample_portfolio_id = request.session.get('sample_portfolio_id')
    user_id = request.session.get('user_id')
    
    if portfolio_id == sample_portfolio_id:
      portfolio = Portfolio.objects.filter(id = portfolio_id)[0]
      return view_function(request, portfolio, True, **args)
      
    elif user_id != None:
      portfolio = Portfolio.objects.filter(id = portfolio_id)[0]
      if portfolio.user.id == user_id:
        return view_function(request, portfolio = portfolio, is_sample = False, **args)
      
    return HttpResponseServerError("bad porfolio")
    
  return view_function_decorated

def login_required_decorator(view_function):
  def view_function_decorated(request, **args):
    user_id = request.session.get('user_id')
    if user_id == None:
      return redirect("/index.html")
    
    else:
      user = User.objects.filter(id = user_id)[0]
      return view_function(request, user = user, **args)
    
  return view_function_decorated

#---------\
#  VIEWS  |
#---------/

def index(request):
  user_id = request.session.get('user_id')
  if user_id != None:
    portfolio = Portfolio.objects.filter(user__id__exact = user_id)[0]
    return redirect("/%s/positions.html" % portfolio.id)
  
  else:
    return redirect("/demo.html")

def demo(request):
  portfolio = get_sample_portfolio(request)
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  positions = get_positions(symbols, quotes, transactions)
  summary = get_summary(positions, transactions)
  
  context = {
      'symbols' : symbols.difference([Quote.CASH_SYMBOL]),
      'portfolio' : portfolio, 
      'positions': positions, 
      'transaction_sets' : [ transactions[0:TRANSACTIONS_BEFORE_SEE_ALL], transactions[TRANSACTIONS_BEFORE_SEE_ALL:transactions.count()] ], 
      'summary' : summary
    }
  
  return render_to_response('demo.html', context, context_instance = RequestContext(request))

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
      user = User.create(identifier, email)
      portfolio = Portfolio.create(user, 'Default')
      
    else:
      user = candidate[0]
      portfolio = Portfolio.objects.filter(user__id__exact = user.id)[0]
      target = 'positions'
      
    request.session['user_id'] = user.id
    return redirect("/%d/%s.html" % (portfolio.id, target))
    
  finally:
    if u != None:
      u.close()
  
def logout(request):
  request.session['user_id'] = None
  del(request.session['user_id'])
  return redirect("/index.html")

@login_required_decorator
def create_portfolio(request, user):
  portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  new_name = 'Default-%d' % (len(portfolios) + 1)
  portfolio = Portfolio.create(user, new_name)
  return redirect('/%d/transactions.html' % portfolio.id)
  
@portfolio_manipilation_decorator
def add_transaction(request, portfolio, is_sample):
  form = TransactionForm(request.POST)
  if form.is_valid():
    commission = form.cleaned_data.get('commission')
    if commission == None:
      commission = 0.0
    
    type = form.cleaned_data.get('type').encode('UTF-8')
    
    transaction = Transaction()
    transaction.portfolio = portfolio
    transaction.type = type
    transaction.as_of_date = form.cleaned_data.get('as_of_date')
    transaction.symbol = form.cleaned_data.get('symbol').encode('UTF-8')
    transaction.quantity = form.cleaned_data.get('quantity')
    transaction.price = form.cleaned_data.get('price')
    transaction.total = (transaction.quantity * transaction.price) + commission
    transaction.save()
  
  return redirect_to_portfolio('transactions', portfolio, is_sample)

@portfolio_manipilation_decorator
def remove_transaction(request, portfolio, is_sample, transaction_id):
  transaction = Transaction.objects.filter(id = transaction_id)[0]
  if transaction.portfolio.id == portfolio.id:
    transaction.delete()
    
  return redirect_to_portfolio('transactions', portfolio, is_sample) 

@portfolio_manipilation_decorator
def update_transaction(request, portfolio, is_sample, transaction_id):
  transaction = Transaction.objects.filter(id = transaction_id)[0]
  success = False
  if transaction.portfolio.id == portfolio.id:
    form = UpdateTransactionForm(request.POST)
    if form.is_valid():
      current_commission = transaction.total - (transaction.price * transaction.quantity)
      
      as_of_date = form.cleaned_data.get('date')
      if as_of_date != None:
        transaction.as_of_date = as_of_date
        
      symbol = form.cleaned_data.get('symbol')
      if symbol != None and symbol != '':
        transaction.symbol = symbol.encode('UTF-8')
        
      quantity = form.cleaned_data.get('quantity')
      if quantity != None:
        transaction.quantity = quantity
        transaction.total = (transaction.price * transaction.quantity) + current_commission
      
      price = form.cleaned_data.get('price')
      if price != None:
        transaction.price = price
        transaction.total = (transaction.price * transaction.quantity) + current_commission
      
      total = form.cleaned_data.get('total')
      if total != None:
        transaction.total = total
        if transaction.symbol == Quote.CASH_SYMBOL:
          transaction.quantity = transaction.total
      
      transaction.save()
      success = True
    
  return HttpResponse("{ \"success\": \"%s\" }" % success)

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_positions(request, user, portfolio, is_sample):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  positions = get_positions(symbols, quotes, transactions)
  summary = get_summary(positions, transactions)
  
  return render_to_response('positions.html', { 'portfolio' : portfolio, 'positions': positions, 'summary' : summary, 'current_tab' : 'positions' }, context_instance = RequestContext(request))

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_set_name(request, user, portfolio, is_sample):
  form = PortfolioForm(request.POST)
  success = False
  if form.is_valid():
    portfolio.name = form.cleaned_data.get('name')
    portfolio.save()
    success = True
  
  return HttpResponse("{ \"success\": \"%s\" }" % success)  

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_remove(request, user, portfolio, is_sample):
  portfolio.delete()
  
  portfolios = Portfolio.objects.filter(user__id__exact = user.id)
  return redirect_to_portfolio('positions', portfolios[0], False)

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_transactions(request, user, portfolio, is_sample):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  symbols = set([t.symbol for t in transactions])
  
  context = {
      'symbols' : symbols.difference([Quote.CASH_SYMBOL]),
      'portfolio' : portfolio, 
      'transaction_sets' : [ transactions[0:TRANSACTIONS_BEFORE_SEE_ALL], transactions[TRANSACTIONS_BEFORE_SEE_ALL:transactions.count()] ],
      'current_tab' : 'transactions', 
    }
  
  return render_to_response('transactions.html', context, context_instance = RequestContext(request))

def portfolio_read_only(request, read_only_token):
  portfolio = Portfolio.objects.filter(read_only_token__exact = read_only_token)[0]
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  positions = get_positions(symbols, quotes, transactions)
  summary = get_summary(positions, transactions)
  
  return render_to_response('read_only.html', { 'supress_navigation' : True, 'portfolio' : portfolio, 'positions': positions, 'summary' : summary }, context_instance = RequestContext(request))

def price_quote(request):
  as_of_date = date(int(request.GET.get('year')), int(request.GET.get('month')), int(request.GET.get('day')))
  quote = Quote.by_symbol(request.GET.get('symbol'))
  return HttpResponse("{ \"price\": %f }" % quote.price_as_of(as_of_date), mimetype="application/json")

@login_required_decorator
@portfolio_manipilation_decorator
def export_transactions(request, user, portfolio, is_sample):
  response = HttpResponse(mimetype = 'text/csv')
  response['Content-Disposition'] = 'attachment; filename=transactions-%s-%s.csv' % (portfolio.name, datetime.now().strftime('%Y%m%d'))

  transactions_as_csv(response, portfolio)
  return response

@portfolio_manipilation_decorator
def import_transactions(request, portfolio, is_sample):
  transactions = None
  if request.method == 'POST':
    form = ImportForm(request.POST, request.FILES)
    if form.is_valid():
      type = request.POST.get('type')
      transactions = parse_transactions(type, request.FILES['file'])
    
  return render_to_response('importTransactions.html', { 'portfolio' : portfolio, 'transactions' : transactions, 'current_tab' : 'import'}, context_instance = RequestContext(request))  

@portfolio_manipilation_decorator
def process_import_transactions(request, portfolio, is_sample):
  formset = ImportTransactionFormSet(request.POST)
  if not formset.is_valid():
    raise Exception('Invalid import set');
  
  for form in formset.forms:
    cd = form.cleaned_data
    
    if not cd.get('exclude'):
      transaction = Transaction()
      transaction.portfolio = portfolio
      transaction.type = cd.get('type').encode('UTF-8')
      transaction.as_of_date = cd.get('as_of_date')
      transaction.symbol = cd.get('symbol').encode('UTF-8')
      transaction.quantity = cd.get('quantity')
      transaction.price = cd.get('price')
      transaction.total = cd.get('total')
      transaction.save()
    
  return redirect_to_portfolio('transactions', portfolio, is_sample)

#--------\
#  FORMS |
#--------/

class TransactionForm(forms.Form):
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 5)
  quantity = forms.FloatField()
  price = forms.FloatField(min_value = 0.01)
  commission = forms.FloatField(min_value = 0.01, required = False)

class UpdateTransactionForm(forms.Form):
  date = forms.DateField(required = False)
  symbol = forms.CharField(required = False, min_length = 1, max_length = 5)
  quantity = forms.FloatField(required = False)
  price = forms.FloatField(required = False, min_value = 0.01)
  total = forms.FloatField(required = False)

class PortfolioForm(forms.Form):
  name = forms.CharField(min_length = 3, max_length = 50)
  
class ImportForm(forms.Form):
  TYPE_CHOICES = [
      ('FRANO', u'FRANO'), 
      ('CHARLES', u'CHARLES'),
      ('GOOGLE', u'GOOGLE'),
      ('SCOTTRADE', u'SCOTTRADE'),
      ('AMERITRADE', u'AMERITRADE'),
      ('ZECCO', u'ZECCO'),
    ]
  
  type = forms.ChoiceField(choices = TYPE_CHOICES)
  file = forms.FileField()
  
class ImportTransactionForm(forms.Form):
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 5)
  quantity = forms.FloatField()
  price = forms.FloatField(min_value = 0.01)
  total = forms.FloatField()
  exclude = forms.BooleanField(required = False)

ImportTransactionFormSet = formset_factory(ImportTransactionForm)

#-------------\
#  UTILITIES  |
#-------------/

DEFAULT_SAMPLE_TRANSACTIONS = [
    { 'symbol' : Quote.CASH_SYMBOL, 'as_of_date' : date(2010, 5, 1),   'type' : 'DEPOSIT',  'quantity' : 100000, 'price' : 1.0 },
    { 'symbol' : 'SPY',             'as_of_date' : date(2010, 5, 3),   'type' : 'BUY',      'quantity' : 125,    'price' : 119.14 },
    { 'symbol' : 'EFA',             'as_of_date' : date(2010, 6, 29),  'type' : 'BUY',      'quantity' : 427,    'price' : 46.83 },
    { 'symbol' : 'AGG',             'as_of_date' : date(2010, 8, 5),   'type' : 'BUY',      'quantity' : 368,    'price' : 106.86 },
    { 'symbol' : 'SPY',             'as_of_date' : date(2010, 8, 17),  'type' : 'BUY',      'quantity' : 137,    'price' : 109.01 },
    { 'symbol' : Quote.CASH_SYMBOL, 'as_of_date' : date(2010, 10, 1),  'type' : 'WITHDRAW', 'quantity' : 10000,  'price' : 1.0 },
  ]

def get_sample_portfolio(request):
  portfolio_id = request.session.get('sample_portfolio_id')
  if portfolio_id != None:
    return Portfolio.objects.filter(id = portfolio_id)[0]
  
  user = get_sample_user()
  portfolio = Portfolio()
  portfolio.user = user
  portfolio.name = 'SAMPLE #%d' % random.randint(100000000, 999999999)
  portfolio.read_only_token = portfolio.name
  portfolio.create_date = datetime.now()
  portfolio.save()
  
  # poor man's cleanup processes, every 100 new portfolios created on the front page
  if portfolio.id % 100 == 0:
    Session.objects.filter(expire_date__lte = datetime.now()).delete()
    cutoff_date = datetime.now() - timedelta(weeks = 2)
    Portfolio.objects.filter(user__id__exact = user.id, create_date__lte = cutoff_date).delete()
  
  for sample_transaction in DEFAULT_SAMPLE_TRANSACTIONS:
    transaction = Transaction()
    transaction.portfolio = portfolio
    transaction.type = sample_transaction['type']
    transaction.as_of_date = sample_transaction['as_of_date']
    transaction.symbol = sample_transaction['symbol']
    transaction.quantity = sample_transaction['quantity']
    transaction.price = sample_transaction['price']
    transaction.total = transaction.quantity * transaction.price
    transaction.save()
  
  request.session['sample_portfolio_id'] = portfolio.id
  return portfolio
  
def get_sample_user():
  candidate = User.objects.filter(open_id = SAMPLE_USER_OPEN_ID)
  if candidate.count() == 1:
    return candidate[0]
  
  else:
    user = User()
    user.open_id = SAMPLE_USER_OPEN_ID
    user.email = SAMPLE_USER_OPEN_ID
    user.create_date = datetime.now()
    user.save()
    return user
    
def get_positions(symbols, quotes, transactions):
  transactions = sorted(transactions, key = (lambda transaction: transaction.id)) 
  transactions = sorted(transactions, key = (lambda transaction: transaction.as_of_date))
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
    previous_price = (1.0 if symbol == Quote.CASH_SYMBOL else quotes[symbol].previous_close_price())
    
    position = Position(
        quotes[symbol].last_trade, 
        symbol, 
        quotes[symbol].name, 
        quantity, 
        float(quotes[symbol].price), 
        cost_price, 
        float(previous_price), 
        0, 
        lots[symbol]
      )
    
    total_market_value += position.market_value
    
    if position.symbol == Quote.CASH_SYMBOL or position.market_value <> 0.0:
      positions.append(position)

  for position in positions:
    position.allocation = ((position.market_value / total_market_value * 100) if total_market_value != 0 else 0)
    
  return positions

def get_lots(symbols, transactions):
  cash = 0.0
  first_cash_date = None
  lots = dict([(symbol, []) for symbol in symbols])
  for transaction in transactions:
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
  as_of_date = max([position.as_of_date for position in positions]) if len(positions) > 0 else datetime.now().date()
  start_date = min([transaction.as_of_date for transaction in transactions]) if len(transactions) > 0 else datetime.now().date()
    
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

def redirect_to_portfolio(action, portfolio, is_sample):
  if is_sample:
    return redirect("/demo.html")
  
  else:
    return redirect("/%d/%s.html" % (portfolio.id, action))
  
#-----------------\
#  VALUE OBJECTS  |
#-----------------/
  
class TaxLot:
  def __init__(self, as_of_date, quantity, price):
    self.as_of_date = as_of_date
    self.quantity = quantity
    self.price = price
    
  def __repr__(self):
    #return "%.4f@.4f on %s" % (self.quantity, self.price, self.as_of_date.strftime('%m/%d/%Y'))
    return "%.4f at %.4f on %s" % (self.quantity, self.price, self.as_of_date.strftime('%m/%d/%Y'))
    
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
