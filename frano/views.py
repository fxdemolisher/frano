# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import math

from django import forms
from django.core.paginator import Paginator, InvalidPage, EmptyPage
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext

from models import Portfolio, Transaction, Quote
from settings import BUILD_VERSION, BUILD_DATETIME

def portfolio_by_token_decorator(view_function):
  def view_function_decorated(request, token):
    read_write_candidate = Portfolio.objects.filter(token__exact = token)
    portfolio = None
    read_only = True
    
    if read_write_candidate.count() == 1:
      portfolio = read_write_candidate[0]
      read_only = False
      
    else:
      read_only_candidate = Portfolio.objects.filter(read_only_token__exact = token)
      if read_only_candidate.count() == 1:
        portfolio = read_only_candidate[0]
    
    if portfolio == None:
      return redirect("/index.html?notFound=true")
    
    else:
      return view_function(request, portfolio, read_only)
    
  return view_function_decorated

def redirect_to_view_if_read_only_decorator(view_function):
  def view_function_decorated(request, portfolio, read_only):
    if read_only:
      return redirect("/%s/view.html" % portfolio.token)
    
    else:
      return view_function(request, portfolio)
    
  return view_function_decorated

def build_settings_context(context):
  return { 
      'BUILD_VERSION' : BUILD_VERSION,
      'BUILD_DATETIME' : BUILD_DATETIME,
    }

def index(request):
  return render_to_response('index.html', { }, context_instance = RequestContext(request))

def legal(request):
  return render_to_response('legal.html', { }, context_instance = RequestContext(request))

def feedback(request):
  return render_to_response('feedback.html', { }, context_instance = RequestContext(request))

def create_portfolio(request):
  name = request.POST.get('name')
  if name == None or name == '':
    return redirect('/index.html?nameRequired=true')
  
  portfolio = Portfolio.create(name)
  return redirect ('/%s/settings.html' % (portfolio.token))

def recover_portfolio(request):
  email = request.POST.get('email')
  candidates = Portfolio.objects.filter(recovery_email = email)
  if candidates.count() == 0:
    return redirect('/index.html?emailNotFound=true')
  
  text = 'The following is a list of your portfolios in the Frano system and their links:<br/><br/>\n'
  for portfolio in candidates:
    text += 'Portfolio: %s<br/>\n' % portfolio.name
    text += 'Read/Write: http://%s/%s/view.html<br/>\n' % ( request.META['HTTP_HOST'], portfolio.token)
    text += 'Read-Only: http://%s/%s/view.html<br/><br/>\n' % ( request.META['HTTP_HOST'], portfolio.read_only_token)
    
  print text
  send_mail('[Frano] Portfolio(s) recovery emails', text, 'info@frano.carelessmusings.com', [ email ], fail_silently = True)
  
  return redirect('/index.html?mailSent=true')

@portfolio_by_token_decorator
@redirect_to_view_if_read_only_decorator
def settings(request, portfolio):
  form = SettingsForm()
  if request.method == 'POST':
    form = SettingsForm(request.POST)
    
    if form.is_valid():
      portfolio.name = form.cleaned_data['name'].encode('UTF8')
      portfolio.recovery_email = form.cleaned_data['email'].encode('UTF8')
      portfolio.save()
  
  return render_to_response('settings.html', { 'portfolio' : portfolio, 'form' : form }, context_instance = RequestContext(request))

class SettingsForm(forms.Form):
  NAME_ERROR_MESSAGES = {
    'required' : 'Please enter a portfolio name',
    'max_length' : 'Name cannot be longer than 255 characters',
  }
  
  EMAIL_ERROR_MESSAGES = {
    'required' : 'Please enter your email address',
    'invalid' : 'Please enter a valid email address',
    'max_length' : 'Email cannot be longer than 255 characters',
  }
  
  name = forms.CharField(max_length = 255, error_messages = NAME_ERROR_MESSAGES)
  email = forms.EmailField(max_length = 255, error_messages = EMAIL_ERROR_MESSAGES)

@portfolio_by_token_decorator
def view_portfolio(request, portfolio, read_only):
  transaction_infos = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
  paginator = Paginator(transaction_infos, 5)
  try: 
    page = int(request.GET.get('page', '1'))
  except ValueError:
    page = 1
  
  transactions = paginator.page(max(1, min(page, paginator.num_pages)))
  
  symbols = set([t.symbol for t in transaction_infos] + [ Quote.CASH_SYMBOL ])
  quotes = dict((symbol, Quote.by_symbol(symbol)) for symbol in symbols)
  types = dict(Transaction.TRANSACTION_TYPES)
  for transaction in transactions.object_list:
    transaction.symbol_name = quotes[transaction.symbol].name
    transaction.type_text = types[transaction.type]
  
  positions = []

  context = {
      'portfolio' : portfolio,
      'read_only' : read_only,
      'transactions' : transactions,
      'positions' : positions,
    }

  if paginator.count > 0:
    lots = get_position_lots(transaction_infos)
    populate_positions(quotes, positions, lots)
    
    as_of_date = max([quotes[symbol].last_trade for symbol in quotes])
    portfolio_start = min([info.as_of_date for info in transaction_infos])
    
    cost_basis = sum([(p['cost_price'] * p['quantity']) for p in positions])
    market_value = sum([p['market_value'] for p in positions])
    opening_market_value = sum([p['opening_market_value'] for p in positions])
    
    pl = market_value - cost_basis
    pl_percent = ((pl / cost_basis) * 100) if cost_basis != 0 else 0
    annualized_pl_percent = pl_percent / ((as_of_date.date() - portfolio_start).days / 365.0)
    
    day_pl = market_value - opening_market_value
    day_pl_percent = ((day_pl / opening_market_value) * 100) if opening_market_value != 0 else 0
    
    xirr_percent = get_xirr_percent_for_transactions(transaction_infos, as_of_date, market_value)
    
    context['market_value'] = market_value
    context['cost_basis'] = cost_basis
    context['pl'] = pl
    context['pl_class'] = pos_neg_css_class(pl)
    context['pl_percent'] = pl_percent
    context['day_pl'] = day_pl
    context['day_pl_class'] = pos_neg_css_class(day_pl)
    context['day_pl_percent'] = day_pl_percent
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
    print quotes[symbol]
    cost = sum([ (lot[0] * lot[1]) for lot in lots[symbol]])
    quantity = sum([ lot[0] for lot in lots[symbol]])
    opening_value = quantity * float(quotes[symbol].previous_close_price)
    current_value = quantity * float(quotes[symbol].price)
    
    day_pl = (current_value - opening_value)
    day_pl_percent = ((day_pl / opening_value) * 100) if opening_value != 0 else 0
    pl_percent = (((current_value - cost) / cost) * 100) if cost != 0 else 0
    cost_price = (cost / quantity) if quantity > 0 else 0
    
    positions.append({
        'symbol' : symbol,
        'name' : quotes[symbol].name,
        'quantity' : quantity,
        'price' : quotes[symbol].price,
        'cost_price' : cost_price,
        'market_value' : current_value,
        'opening_market_value' : opening_value,
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

@portfolio_by_token_decorator
@redirect_to_view_if_read_only_decorator
def remove_portfolio(request, portfolio):
  portfolio.delete();
  return redirect("/index.html?removed=true")

@portfolio_by_token_decorator
@redirect_to_view_if_read_only_decorator
def add_transaction(request, portfolio):
  form = TransactionForm(request.POST)
  if not form.is_valid():
    return redirect("/%s/view.html?invalidTransaction=true" % portfolio.token)
  
  transaction = Transaction()
  transaction.portfolio = portfolio
  transaction.type = form.cleaned_data.get('type').encode('UTF-8')
  transaction.as_of_date = form.cleaned_data.get('as_of_date')
  transaction.symbol = form.cleaned_data.get('symbol').encode('UTF-8')
  transaction.quantity = form.cleaned_data.get('quantity')
  transaction.price = form.cleaned_data.get('price')
  transaction.total = form.cleaned_data.get('total')
  transaction.save()
  
  return redirect("/%s/view.html" % portfolio.token)

class TransactionForm(forms.Form):
  type = forms.ChoiceField(choices = Transaction.TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 5)
  quantity = forms.DecimalField(min_value = 0.01)
  price = forms.DecimalField(min_value = 0.01)
  total = forms.DecimalField(min_value = 0.01)

@portfolio_by_token_decorator
@redirect_to_view_if_read_only_decorator
def remove_transaction(request, portfolio):
  transaction_id = request.GET.get('id')
  transaction = Transaction.objects.filter(id = transaction_id, portfolio__id__exact = portfolio.id)[0]
  transaction.delete()
  return redirect("/%s/view.html" % portfolio.token)
