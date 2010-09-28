import math

from django import forms
from django.http import HttpResponse
from django.shortcuts import render_to_response, redirect
from django.template import RequestContext

from frano.settings import CASH_SYMBOL
from models import User, Portfolio, Transaction
from services import *

def index(request):
  if get_user(request) != None:
    return redirect('/portfolio.html')
  
  return render_to_response('index.html', { }, context_instance = RequestContext(request))

def about(request):
  return render_to_response('about.html', { }, context_instance = RequestContext(request))

def feedback(request):
  return render_to_response('feedback.html', { }, context_instance = RequestContext(request))

def legal(request):
  return render_to_response('legal.html', { }, context_instance = RequestContext(request))

def register(request):
  messages = []
  form = UsernamePasswordForm()
  if request.method == 'POST':
    form = UsernamePasswordForm(request.POST)
    
    if form.is_valid():
      username = form.cleaned_data['username'].encode('UTF8')
      password = form.cleaned_data['password'].encode('UTF8')
      
      if not does_username_exist(username):
        user = register_user(username, password)
        set_user(request, user.username)
        return redirect("/portfolio.html")
      
      else:
        messages.append('We already have an account under that email')
      
  return render_to_response('register.html', { 'form' : form, 'messages' : messages }, context_instance = RequestContext(request))

def logout(request):
  set_user(request, None)
  return redirect('/index.html')

def login(request):
  messages = []
  form = UsernamePasswordForm()
  if request.method == 'POST':
    form = UsernamePasswordForm(request.POST)
    
    if form.is_valid():
      username = form.cleaned_data['username'].encode('UTF8')
      password = form.cleaned_data['password'].encode('UTF8')
      
      if login_user(username, password):
        set_user(request, username)
        return redirect('/portfolio.html')
      
      else:
        messages.append('Invalid username or password')
    
  return render_to_response('login.html', { 'form' : form, 'messages' : messages }, context_instance = RequestContext(request))
  

@login_required_decorator
def settings(request):
  messages = []
  form = UsernamePasswordForm()
  if request.method == 'POST':
    form = ChangeUsernamePasswordForm(request.POST)
    
    if form.is_valid():
      username = form.cleaned_data['username'].encode('UTF8')
      password = form.cleaned_data['password'].encode('UTF8')
      new_password = form.cleaned_data['new_password'].encode('UTF8')
      
      if login_user(get_user(request), password):
        user = update_user(get_user(request), username, new_password)
        set_user(request, user.username)
        
      else :
        messages.append('Incorrect current password')
    
  
  portfolios = Portfolio.objects.filter(user__username__exact = get_user(request))
  
  return render_to_response('settings.html', { 'portfolios' : portfolios, 'form' : form, 'messages' : messages }, context_instance = RequestContext(request))

@login_required_decorator
def portfolio(request):
  portfolio_id = request.GET.get('id')
  portfolios = Portfolio.objects.filter(user__username__exact = get_user(request))
  
  portfolio = None
  if portfolio_id != None:
    portfolio = Portfolio.objects.filter(id = portfolio_id)[0]
    
  elif portfolios.count() > 0:
    portfolio = portfolios[0]
    
  if portfolio == None:
    return redirect('/settings.html')
  
  transaction_infos = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
  transaction_count = transaction_infos.count()
  symbols = set([t.symbol for t in transaction_infos])
  quotes = dict((symbol, get_quote(symbol)) for symbol in symbols)
  types = dict(Transaction.TRANSACTION_TYPES)
  
  last_page = int(math.ceil(transaction_count / 5.0))
  page = int(request.GET.get('page', 1))
  page = page if (page <= last_page) else last_page
  start_with = (page - 1) * 5
  end_with = min(page * 5, transaction_count)
  
  transactions = []
  positions = []

  context = {
      'portfolios' : portfolios, 
      'portfolio' : portfolio,
      'total_transactions' : transaction_count,
      'page_start' : start_with + 1,
      'page_end' : end_with,
      'page' : page,
      'previous_page' : max(page - 1, 1),
      'next_page' : min(page + 1, last_page),
      'last_page' : last_page,
      'transactions' : transactions,
      'positions' : positions,
    }

  if transaction_count > 0:
    for info in transaction_infos[start_with:end_with]:
      transactions.append(info)
      info.symbol_name = quotes[info.symbol].name
      info.type_text = types[info.type]
    
    cash = 0.0
    lots = {}
    for info in reversed(transaction_infos):
      if info.type == 'DEPOSIT' or info.type == 'WITHDRAW' or info.type == 'ADJUST':
        cash += (-1 if info.type == 'WITHDRAW' else 1) * float(info.total)
        
      elif info.symbol != CASH_SYMBOL:
        cash += (-1 if info.type == 'BUY' else 1) * float(info.total)
        cur_lots = lots.get(info.symbol, [])
        lots[info.symbol] = cur_lots
        
        if info.type == 'BUY':
	  cur_lots.append([ float(info.quantity), float(info.price) ])

        elif info.type == 'SELL':
	  q = float(info.quantity)
	  while q > 0 and len(cur_lots) > 0:
	    can_sell = min(q, cur_lots[0][0])
	    q -= can_sell
	    if can_sell == cur_lots[0][0]:
	      del(cur_lots[0])
	      
	    else:
	     cur_lots[0][0] -= can_sell

    for symbol in sorted(symbols):
      if symbol != CASH_SYMBOL:
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
	    'day_pl_class' : ('' if day_pl == 0 else ('pos' if day_pl > 0 else 'neg')),
	    'pl_percent' : pl_percent,
	    'pl_percent_class' : ('' if pl_percent == 0 else ('pos' if pl_percent > 0 else 'neg')),
	  })

    positions.append({ 'symbol' : CASH_SYMBOL, 'name' : quotes[CASH_SYMBOL].name, 'quantity' : cash, 'price' : 1.0, 
	               'cost_price' : 1.0, 'market_value' : cash, 'day_pl' : 0, 'day_pl_percent' : 0, 'pl_percent' : 0, })

    as_of_date = max([quotes[symbol].last_trade for symbol in quotes])
    portfolio_start = min([info.as_of_date for info in transaction_infos])
    market_value = sum([p['market_value'] for p in positions])
    cost_basis = sum([(p['cost_price'] * p['quantity']) for p in positions])
    pl = market_value - cost_basis
    pl_percent = (pl / cost_basis) * 100
    annualized_pl_percent = pl_percent / ((as_of_date.date() - portfolio_start).days / 365.0)
    
    for position in positions:
      position['allocation'] = position['market_value'] / market_value * 100
    
    dates = []
    payments = []
    for info in reversed(transaction_infos):
      if info.type == 'DEPOSIT' or info.type == 'WITHDRAW':
        dates.append(info.as_of_date)
        payments.append((-1 if info.type == 'DEPOSIT' else 1) * float(info.total))
        
    dates.append(as_of_date.date())
    payments.append(market_value)
    xirr_candidate = xirr(dates, payments)
    xirr_percent = (xirr_candidate * 100) if xirr_candidate != None else 0 

    context['market_value'] = market_value
    context['cost_basis'] = cost_basis
    context['pl'] = pl
    context['pl_class'] = ('' if pl == 0 else ('pos' if pl > 0 else 'neg'))
    context['pl_percent'] = pl_percent
    context['annualized_pl_percent'] = annualized_pl_percent
    context['xirr_percent'] = xirr_percent
    context['xirr_percent_class'] = ('' if xirr_percent == 0 else ('pos' if xirr_percent > 0 else 'neg'))
    context['as_of_date'] = as_of_date
    context['portfolio_start'] = portfolio_start
    
  return render_to_response('portfolio.html', context, context_instance = RequestContext(request))

@login_required_decorator
def create_portfolio(request):
  user = User.objects.filter(username = get_user(request))[0]
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
  portfolio_id = request.GET.get('id')
  portfolio = Portfolio.objects.filter(id = portfolio_id, user__username__exact = get_user(request))[0]
  portfolio.delete()
  return redirect ('/settings.html')
  
@login_required_decorator
def update_portfolios(request):
  user = User.objects.filter(username = get_user(request))[0]
  
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
  portfolio_id = request.POST.get('portfolio_id')
  portfolio = Portfolio.objects.filter(id = portfolio_id, user__username__exact = get_user(request))[0]
  
  form = TransactionForm(request.POST)
  if not form.is_valid():
    return redirect ("/portfolio.html?id=%d&invalid_transaction_input=True" % portfolio_id)
  
  cleaned_data = form.cleaned_data
  
  transaction = Transaction()
  transaction.portfolio = portfolio
  transaction.type = cleaned_data['type'].encode('UTF8')
  transaction.as_of_date = cleaned_data['as_of_date']
  transaction.symbol = cleaned_data['symbol']
  transaction.quantity = cleaned_data['quantity']
  transaction.price = cleaned_data['price']
  transaction.total = cleaned_data['total']
  transaction.save()
  
  return redirect ("/portfolio.html?id=%s" % portfolio_id)

@login_required_decorator
def delete_transaction(request):
  transaction_id = request.GET.get('id')
  transaction = Transaction.objects.filter(id = transaction_id, portfolio__user__username__exact = get_user(request))[0]
  portfolio = transaction.portfolio
  transaction.delete()
  return redirect ('/portfolio.html?id=%d' % portfolio.id)

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
