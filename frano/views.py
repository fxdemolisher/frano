# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import json, math, random

from datetime import date, datetime, timedelta
from urllib import urlopen

from django import forms
from django.core.mail import EmailMessage
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.db import connection, transaction
from django.forms.formsets import formset_factory
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext
from django.template.loader import render_to_string
from django.contrib.sessions.models import Session

from import_export import transactions_as_csv, parse_transactions, detect_transaction_file_type
from models import User, Portfolio, Transaction, Position, TaxLot, Quote
from settings import BUILD_VERSION, BUILD_DATETIME, JANRAIN_API_KEY

#-------------\
#  CONSTANTS  |
#-------------/

SAMPLE_USER_OPEN_ID = 'SAMPLE_USER_ONLY'
TRANSACTIONS_BEFORE_SEE_ALL = 20
DAYS_IN_PERFORMANCE_HISTORY = 90
PERFORMANCE_BENCHMARK_SYMBOL = 'ACWI'

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
  Position.refresh_if_needed(portfolio, transactions)
    
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  positions = Position.get_latest(portfolio)
  decorate_positions_for_display(positions, symbols, request.GET.get("showClosedPositions", False))
  decorate_positions_with_lots(positions)
  summary = get_summary(positions, transactions)
  performance_history = get_performance_history(portfolio, DAYS_IN_PERFORMANCE_HISTORY)
  
  symbol_filter = request.GET.get('filter')
  if symbol_filter != None and symbol_filter != '':
    transactions = transactions.filter(symbol = symbol_filter)
  
  context = {
      'symbols' : symbols.difference([Quote.CASH_SYMBOL]),
      'portfolio' : portfolio, 
      'positions': positions, 
      'transaction_sets' : [ transactions[0:TRANSACTIONS_BEFORE_SEE_ALL], transactions[TRANSACTIONS_BEFORE_SEE_ALL:transactions.count()] ],
      'symbol_filter' : symbol_filter, 
      'summary' : summary,
      'performance_history' : performance_history,
      'benchmark_symbol' : PERFORMANCE_BENCHMARK_SYMBOL,
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
  names = set([ p.name for p in portfolios])
  
  index = 1
  new_name = 'Default-%d' % index
  while new_name in names:
    new_name = 'Default-%d' % index
    index += 1
    
  portfolio = Portfolio.create(user, new_name)
  return redirect('/%d/importTransactions.html' % portfolio.id)
  
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
    transaction.symbol = form.cleaned_data.get('symbol').encode('UTF-8').upper()
    transaction.quantity = form.cleaned_data.get('quantity')
    transaction.price = form.cleaned_data.get('price')
    transaction.total = (transaction.quantity * transaction.price) + commission
    transaction.save()
    
    Position.refresh_if_needed(portfolio, force = True)
  
  return redirect_to_portfolio('transactions', portfolio, is_sample)

@portfolio_manipilation_decorator
def remove_transaction(request, portfolio, is_sample, transaction_id):
  transaction = Transaction.objects.filter(id = transaction_id)[0]
  if transaction.portfolio.id == portfolio.id:
    transaction.delete()
    Position.refresh_if_needed(portfolio, force = True)
    
  return redirect_to_portfolio('transactions', portfolio, is_sample) 

@portfolio_manipilation_decorator
def remove_all_transactions(request, portfolio, is_sample):
  Transaction.objects.filter(portfolio__id__exact = portfolio.id).delete()
  Position.refresh_if_needed(portfolio, force = True)
    
  return redirect_to_portfolio('transactions', portfolio, is_sample)

@portfolio_manipilation_decorator
def update_transaction(request, portfolio, is_sample, transaction_id):
  transaction = Transaction.objects.filter(id = transaction_id)[0]
  success = False
  if transaction.portfolio.id == portfolio.id:
    form = UpdateTransactionForm(request.POST)
    if form.is_valid():
      current_commission = transaction.total - (transaction.price * transaction.quantity)
      
      type = form.get_if_present('type')
      if type != None and type != '':
        transaction.type = type.encode('UTF-8')
      
      as_of_date = form.get_if_present('date')
      if as_of_date != None:
        transaction.as_of_date = as_of_date
        
      symbol = form.get_if_present('symbol')
      if symbol != None and symbol != '':
        transaction.symbol = symbol.encode('UTF-8').upper()
        
      quantity = form.get_if_present('quantity')
      if quantity != None:
        transaction.quantity = quantity
        transaction.total = (transaction.price * transaction.quantity) + current_commission
      
      price = form.get_if_present('price')
      if price != None:
        transaction.price = price
        transaction.total = (transaction.price * transaction.quantity) + current_commission
      
      total = form.get_if_present('total')
      if total != None:
        transaction.total = total
        if transaction.symbol == Quote.CASH_SYMBOL:
          transaction.quantity = transaction.total
      
      linked_symbol = form.get_if_present('linkedsymbol')
      if linked_symbol != None:
        transaction.linked_symbol = (linked_symbol.encode('UTF-8').upper() if linked_symbol.strip() != '' else None)
      
      transaction.save()
      Position.refresh_if_needed(portfolio, force = True)
      success = True
    
  return HttpResponse("{ \"success\": \"%s\" }" % success)

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_positions(request, user, portfolio, is_sample):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  Position.refresh_if_needed(portfolio, transactions)
  
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  positions = Position.get_latest(portfolio)
  decorate_positions_for_display(positions, symbols, request.GET.get("showClosedPositions", False))
  decorate_positions_with_lots(positions)
  summary = get_summary(positions, transactions)
  performance_history = get_performance_history(portfolio, DAYS_IN_PERFORMANCE_HISTORY)
  
  return render_to_response('positions.html', { 
      'portfolio' : portfolio, 
      'positions': positions, 
      'summary' : summary, 
      'current_tab' : 'positions',
      'performance_history' : performance_history, 
      'benchmark_symbol' : PERFORMANCE_BENCHMARK_SYMBOL,
    }, context_instance = RequestContext(request))

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
  
  symbol_filter = request.GET.get('filter')
  if symbol_filter != None and symbol_filter != '':
    transactions = transactions.filter(symbol = symbol_filter)
  
  context = {
      'symbols' : symbols.difference([Quote.CASH_SYMBOL]),
      'portfolio' : portfolio, 
      'transaction_sets' : [ transactions[0:TRANSACTIONS_BEFORE_SEE_ALL], transactions[TRANSACTIONS_BEFORE_SEE_ALL:transactions.count()] ],
      'current_tab' : 'transactions',
      'symbol_filter' : symbol_filter,  
    }
  
  return render_to_response('transactions.html', context, context_instance = RequestContext(request))

def portfolio_read_only(request, read_only_token):
  portfolio = Portfolio.objects.filter(read_only_token__exact = read_only_token)[0]
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  Position.refresh_if_needed(portfolio, transactions)
  
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  positions = Position.get_latest(portfolio)
  decorate_positions_for_display(positions, symbols, request.GET.get("showClosedPositions", False))
  decorate_positions_with_lots(positions)
  summary = get_summary(positions, transactions)
  performance_history = get_performance_history(portfolio, DAYS_IN_PERFORMANCE_HISTORY)
  
  return render_to_response('positions.html', { 
      'supress_navigation' : True, 
      'portfolio' : portfolio, 
      'positions': positions, 
      'summary' : summary,
      'performance_history' : performance_history, 
      'benchmark_symbol' : PERFORMANCE_BENCHMARK_SYMBOL,
    }, context_instance = RequestContext(request))

def price_quote(request):
  today = datetime.now().date()
  as_of_date = date(int(request.GET.get('year', today.year)), int(request.GET.get('month', today.month)), int(request.GET.get('day', today.day)))
  quote = Quote.by_symbol(request.GET.get('symbol'))
  return HttpResponse("{ \"price\": %f }" % quote.price_as_of(as_of_date), mimetype="application/json")

@portfolio_manipilation_decorator
def export_transactions(request, portfolio, is_sample, format):
  format = format.lower()
  name = ('DEMO' if is_sample else portfolio.name)
  
  response = HttpResponse(mimetype = ('text/%s' % format))
  response['Content-Disposition'] = 'attachment; filename=transactions-%s-%s.%s' % (name, datetime.now().strftime('%Y%m%d'), format)
  
  if format == 'csv':
    transactions_as_csv(response, portfolio)
  elif format == 'ofx':
    transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
    for transaction in transactions:
      transaction.commission = abs(transaction.total - (transaction.price * transaction.quantity))
      transaction.quantity = ((-transaction.quantity) if transaction.type == 'SELL' else transaction.quantity)
      transaction.total = ((-transaction.total) if transaction.type == 'BUY' or transaction.type == 'WITHDRAW' else transaction.total)
      
    quotes = [ Quote.by_symbol(symbol) for symbol in set([t.symbol for t in transactions]).difference([Quote.CASH_SYMBOL]) ]
    
    response.write(render_to_string('transactions.ofx', {
        'portfolio' : portfolio,
        'transactions': transactions,
        'start_date' : min([t.as_of_date for t in transactions]),
        'end_date' : max([t.as_of_date for t in transactions]),
        'quotes' : quotes, 
      }))
    
  return response

@portfolio_manipilation_decorator
def import_transactions(request, portfolio, is_sample):
  transactions = None
  auto_detect_error = False
  if request.method == 'POST':
    form = ImportForm(request.POST, request.FILES)
    if form.is_valid():
      type = request.POST.get('type')
      if type == 'AUTO':
        type = detect_transaction_file_type(request.FILES['file'])
      
      auto_detect_error = (True if type == None else False);
      if not auto_detect_error:
        transactions = parse_transactions(type, request.FILES['file'])
        
        existing_transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
        by_date_map = dict([ (as_of_date, []) for as_of_date in set([ transaction.as_of_date for transaction in existing_transactions]) ])
        for transaction in existing_transactions:
          by_date_map.get(transaction.as_of_date).append(transaction)
        
        for transaction in transactions:
                    
          is_duplicate = False
          possibles = by_date_map.get(transaction.as_of_date)
          if possibles != None:
            for possible in possibles:
              if possible.type == transaction.type and possible.symbol == transaction.symbol and abs(possible.quantity - transaction.quantity) < 0.01 and abs(possible.price - transaction.price) < 0.01:
                is_duplicate = True
            
          transaction.is_duplicate = is_duplicate
    
  return render_to_response('importTransactions.html', 
      { 'portfolio' : portfolio, 'transactions' : transactions, 'current_tab' : 'transactions', 'auto_detect_error' : auto_detect_error }, 
      context_instance = RequestContext(request)
    )  

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
      transaction.symbol = cd.get('symbol').encode('UTF-8').upper()
      transaction.quantity = cd.get('quantity')
      transaction.price = cd.get('price')
      transaction.total = cd.get('total')
      
      linked_symbol = cd.get('linked_symbol').encode('UTF-8')
      if linked_symbol != None and linked_symbol != '':
        transaction.linked_symbol = linked_symbol
        
      transaction.save()
    
  Position.refresh_if_needed(portfolio, force = True)
  return redirect_to_portfolio('transactions', portfolio, is_sample)

@portfolio_manipilation_decorator
def request_import_type(request, portfolio, is_sample):
  form = RequestImportForm(request.POST, request.FILES)
  if not form.is_valid():
    raise Exception('Bad file for request');
    
  type = request.POST.get('type')
  uploaded_file = request.FILES['file']
  body = "Request for import for type: %s\nRequest for portfolio: %s (%d)\nRequest made from:%s" % (
      type, 
      ('Demo' if is_sample else portfolio.name), 
      portfolio.id, 
      ('Demo user' if is_sample else portfolio.user.email)
    )
      
  email = EmailMessage("Import type requested",
      body,
      "no-reply@frano.carelessmusings.com",
      [ "gennadiy@apps.carelessmusings.com" ],
      [ ])
  
  email.attach(uploaded_file.name, uploaded_file.read(), uploaded_file.content_type)
  email.send(fail_silently = False)
  
  return redirect("/%d/importTransactions.html?requestSent=true" % portfolio.id)

@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_allocation(request, user, portfolio, is_sample):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  Position.refresh_if_needed(portfolio, transactions)
  
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  positions = Position.get_latest(portfolio)
  decorate_positions_for_display(positions, symbols, False)
  
  return render_to_response('allocation.html', { 
      'portfolio' : portfolio, 
      'positions': positions, 
      'current_tab' : 'allocation',
    }, context_instance = RequestContext(request))
  
@login_required_decorator
@portfolio_manipilation_decorator
def portfolio_income(request, user, portfolio, is_sample):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  Position.refresh_if_needed(portfolio, transactions)
  
  symbols = set([t.symbol for t in transactions] + [ Quote.CASH_SYMBOL ])
  positions = Position.get_latest(portfolio)
  decorate_positions_for_display(positions, symbols, request.GET.get("showClosedPositions", False))
  
  summary_map = {}
  for position in positions:
    summary_map[position.symbol] = IncomeSummary(position.symbol, position.market_value, position.cost_basis, position.pl, position.pl_percent, position.show)
  
  total_summary = IncomeSummary('*TOTAL*', 0.0, 0.0, 0.0, 0.0, True)
  for transaction in transactions:
    if transaction.type != 'ADJUST':
      continue
    
    symbol = transaction.linked_symbol
    if symbol == None or symbol == '':
      symbol = transaction.symbol
      
    summary = summary_map.get(symbol)
    summary.add_income(transaction.as_of_date, transaction.total)
    
    if summary.show:
      total_summary.add_income(transaction.as_of_date, transaction.total)
    
  summaries = sorted(summary_map.values(), key = (lambda summary: summary.symbol))
  
  return render_to_response('income.html', { 
      'portfolio' : portfolio, 
      'summaries': summaries,
      'total_summary' : total_summary,
      'current_tab' : 'income',
    }, context_instance = RequestContext(request))

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
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES, required = False)
  date = forms.DateField(required = False)
  symbol = forms.CharField(required = False, min_length = 1, max_length = 5)
  quantity = forms.FloatField(required = False)
  price = forms.FloatField(required = False, min_value = 0.01)
  total = forms.FloatField(required = False)
  linkedsymbol = forms.CharField(required = False, max_length = 5) # underscore removed due to JS split issue
  
  def __init__(self, data):
    forms.Form.__init__(self, data)
    self.original_data = data
    
  def get_if_present(self, name):
    return (self.cleaned_data.get(name) if name in self.original_data else None)
    
class PortfolioForm(forms.Form):
  name = forms.CharField(min_length = 3, max_length = 50)
  
class ImportForm(forms.Form):
  TYPE_CHOICES = [
      ('AUTO', u'AUTO'),
      ('FRANO', u'FRANO'), 
      ('CHARLES', u'CHARLES'),
      ('GOOGLE', u'GOOGLE'),
      ('SCOTTRADE', u'SCOTTRADE'),
      ('AMERITRADE', u'AMERITRADE'),
      ('ZECCO', u'ZECCO'),
    ]
  
  type = forms.ChoiceField(choices = TYPE_CHOICES)
  file = forms.FileField()
  
class RequestImportForm(forms.Form):
  type = forms.CharField(max_length = 255)
  file = forms.FileField()
  
class ImportTransactionForm(forms.Form):
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 5)
  quantity = forms.FloatField()
  price = forms.FloatField(min_value = 0.01)
  total = forms.FloatField()
  linked_symbol = forms.CharField(max_length = 5, required = False)
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
    { 'symbol' : 'SPY',             'as_of_date' : date(2010, 9, 20),  'type' : 'SELL',     'quantity' : 130,    'price' : 114.21 },
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

def decorate_positions_for_display(positions, symbols, showClosedPositions):
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  as_of_date = min([quote.last_trade.date() for symbol, quote in quotes.items()])
  
  total_market_value = 0
  for position in positions:
    price = (1.0 if position.symbol == Quote.CASH_SYMBOL else quotes[position.symbol].price)
    previous_price = (1.0 if position.symbol == Quote.CASH_SYMBOL else quotes[position.symbol].previous_close_price())
    
    position.decorate_with_prices(price, previous_price)
    position.show = (showClosedPositions or abs(position.quantity) > 0.01)
    
    total_market_value += position.market_value
    
  for position in positions:
    position.allocation = ((position.market_value / total_market_value * 100) if total_market_value != 0 else 0)
    position.effective_as_of_date = as_of_date
    
def decorate_positions_with_lots(positions):
  for position in positions:
    lots = []
    for lot in position.taxlot_set.order_by('-as_of_date'):
      lot.unrealized_pl = (lot.quantity - lot.sold_quantity) * (position.price - lot.cost_price)
      lot.unrealized_pl_percent = ((((position.price / lot.cost_price) - 1) * 100) if lot.cost_price <> 0 and abs(lot.unrealized_pl) > 0.01 else 0)
      lot.realized_pl = lot.sold_quantity * (lot.sold_price - lot.cost_price)
      
      days_open = (datetime.now().date() - lot.as_of_date).days
      if abs(lot.quantity - lot.sold_quantity) < 0.0001:
        lot.status = 'Closed'
        
      elif days_open <= 365:
        lot.status = 'Short'
        
      else:
        lot.status = 'Long'
    
      lots.append(lot)
    
    position.lots = lots
  
def get_summary(positions, transactions):
  as_of_date = max([position.effective_as_of_date for position in positions]) if len(positions) > 0 else datetime.now().date()
  start_date = min([transaction.as_of_date for transaction in transactions]) if len(transactions) > 0 else datetime.now().date()
  
  market_value = 0  
  cost_basis = 0
  realized_pl = 0
  previous_market_value = 0
  for position in positions:
    market_value += position.market_value
    cost_basis += position.cost_price * position.quantity
    realized_pl += position.realized_pl
    previous_market_value += position.previous_market_value
  
  print market_value
  print previous_market_value  
  xirr_percent = get_xirr_percent_for_transactions(transactions, as_of_date, market_value)

  return Summary(as_of_date, start_date, market_value, cost_basis, realized_pl, previous_market_value, xirr_percent)
  
def get_xirr_percent_for_transactions(transactions, as_of_date, market_value):
  transactions = sorted(transactions, key = (lambda transaction: transaction.id)) 
  transactions = sorted(transactions, key = (lambda transaction: transaction.as_of_date))

  dates = []
  payments = []
  for transaction in transactions:
    if transaction.type == 'DEPOSIT' or transaction.type == 'WITHDRAW':
      dates.append(transaction.as_of_date)
      payments.append((-1 if transaction.type == 'DEPOSIT' else 1) * transaction.total)
      
  dates.append(as_of_date)
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

def redirect_to_portfolio(action, portfolio, is_sample, query_string = None):
  if is_sample:
    return redirect("/demo.html%s" % ('' if query_string == None else "?%s" % query_string))
  
  else:
    return redirect("/%d/%s.html%s" % (portfolio.id, action, ('' if query_string == None else "?%s" % query_string)))

def get_performance_history(portfolio, days):
  query = """
      SELECT D.portfolio_date,
             D.deposit,
             D.withdrawal,
             SUM(P.quantity * ((CASE WHEN P.symbol = '*CASH' THEN 1.0 ELSE H.price END))) as market_value
        FROM position P
             JOIN
             (
                 SELECT D.portfolio_id,
                        D.portfolio_date,
                        D.position_date,
                        SUM(CASE WHEN T.type = 'DEPOSIT' THEN T.total ELSE 0 END) as deposit,
                        SUM(CASE WHEN T.type = 'WITHDRAW' THEN T.total ELSE 0 END) as withdrawal
                   FROM (
                            SELECT P.portfolio_id,
                                   D.portfolio_date,
                                   MAX(P.as_of_date) as position_date
                              FROM (
                                     SELECT DISTINCT
                                            D.portfolio_id,
                                            DATE(H.as_of_date) as portfolio_date
                                       FROM (
                                              SELECT DISTINCT
                                                     P.portfolio_id,
                                                     P.symbol
                                                FROM position P
                                               WHERE P.symbol != '*CASH'
                                            ) S
                                            JOIN quote Q ON (Q.symbol = S.symbol)
                                            JOIN price_history H ON (H.quote_id = Q.id)
                                            JOIN
                                            (
                                                SELECT P.portfolio_id,
                                                       MIN(as_of_date) as start_date
                                                  FROM position P
                                              GROUP BY P.portfolio_id
                                            ) D ON (D.portfolio_id = S.portfolio_id AND H.as_of_date >= D.start_date)
                                      WHERE DATEDIFF(NOW(), H.as_of_date) < %s
                                   ) D
                                   JOIN 
                                   (
                                     SELECT DISTINCT 
                                            P.portfolio_id,
                                            P.as_of_date
                                       FROM position P
                                   )  P ON (P.portfolio_id = D.portfolio_id AND P.as_of_date <= D.portfolio_date)
                          GROUP BY D.portfolio_id,
                                   D.portfolio_date
                        ) D
                        LEFT JOIN
                        (
                          SELECT T.portfolio_id,
                                 T.as_of_date,
                                 T.type,
                                 T.total
                            FROM transaction T
                           WHERE T.type IN ('DEPOSIT', 'WITHDRAW')
                        ) T ON (T.portfolio_id = D.portfolio_id AND T.as_of_date = D.portfolio_date)
               GROUP BY D.portfolio_id,
                        D.portfolio_date
             ) D ON (P.portfolio_id = D.portfolio_id AND P.as_of_date = D.position_date)
             LEFT JOIN quote Q ON (Q.symbol = P.symbol)
             LEFT JOIN price_history H ON (H.quote_id = Q.id AND H.as_of_date = D.portfolio_date)
       WHERE P.quantity <> 0
         AND P.portfolio_id = %s
    GROUP BY D.portfolio_date
    ORDER BY D.portfolio_date"""
  
  cursor = connection.cursor()
  cursor.execute(query, [days, portfolio.id])
  
  benchmark_quote = Quote.by_symbol(PERFORMANCE_BENCHMARK_SYMBOL)
  cutoff_date = datetime.now().date() - timedelta(days = DAYS_IN_PERFORMANCE_HISTORY)
  benchmark_price = {}
  for history in benchmark_quote.pricehistory_set.filter(as_of_date__gte = cutoff_date).order_by('as_of_date'):
    benchmark_price[history.as_of_date.date()] = history.price
    
  shares = None
  last_price = None
  first_benchmark = None
  out = []
  for row in cursor.fetchall():
    as_of_date = row[0]
    deposit = float(row[1])
    withdraw = float(row[2])
    market_value = float(row[3])
    
    benchmark = benchmark_price.get(as_of_date, 0.0)
    if first_benchmark == None:
      first_benchmark = benchmark
    
    performance = 0
    if shares == None:
      shares = market_value
      
    else:
      net_inflow = deposit - withdraw
      shares += net_inflow / last_price
      performance = (((market_value / shares) - 1) if shares <> 0 else 0) 
    
    last_price = ((market_value / shares) if shares <> 0 else 1.0)
    benchmark_performance = (((benchmark / first_benchmark) - 1) if first_benchmark <> 0 else 0)
    out.append(PerformanceHistory(as_of_date, performance, benchmark_performance))
    
  cursor.close()
  return out
  
#-----------------\
#  VALUE OBJECTS  |
#-----------------/

class Summary:
  def __init__(self, as_of_date, start_date, market_value, cost_basis, realized_pl, previous_market_value, xirr_percent):
    self.as_of_date = as_of_date
    self.start_date = start_date
    self.market_value = market_value
    self.cost_basis = cost_basis
    self.realized_pl = realized_pl
    self.previous_market_value = previous_market_value
    self.xirr_percent = xirr_percent
    
    self.pl = market_value - cost_basis
    self.pl_percent = ((self.pl / cost_basis) * 100) if cost_basis != 0 else 0
    self.day_pl = market_value - previous_market_value
    self.day_pl_percent = ((self.day_pl / previous_market_value) * 100) if previous_market_value != 0 else 0
    self.days = (as_of_date - start_date).days
    self.annualized_pl_percent = (self.pl_percent / (self.days / 365.0)) if self.days != 0 else 0
    self.total_pl = self.pl + self.realized_pl

class PerformanceHistory:
  def __init__(self, as_of_date, percent, benchmark_percent):
    self.as_of_date = as_of_date
    self.percent = percent
    self.benchmark_percent = benchmark_percent
    
class IncomeSummary:
  def __init__(self, symbol, market_value, cost_basis, unrealized_pl, unrealized_pl_percent, show):
    self.symbol = symbol
    self.market_value = market_value
    self.cost_basis = cost_basis
    self.unrealized_pl = unrealized_pl
    self.unrealized_pl_percent = unrealized_pl_percent
    self.show = show
     
    self.income_one_month = 0.0
    self.income_three_months = 0.0
    self.income_six_months = 0.0
    self.income_one_year = 0.0
    self.total_income = 0.0
    
  def add_income(self, as_of_date, amount):
    current = datetime.now().date()
    self.total_income += amount
    if (current - as_of_date).days < 365:
      self.income_one_year += amount
      
    if (current - as_of_date).days < 180:
      self.income_six_months += amount
      
    if (current - as_of_date).days < 90:
      self.income_three_months += amount
      
    if (current - as_of_date).days < 30:
      self.income_one_month += amount
        