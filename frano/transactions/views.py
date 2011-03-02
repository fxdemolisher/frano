# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime
from exceptions import Exception

from django import forms
from django.core.mail import EmailMessage
from django.forms.formsets import formset_factory
from django.http import HttpResponse
from django.template.loader import render_to_string

from main.decorators import portfolio_manipulation_decorator
from main.view_utils import redirect_to_portfolio_action
from main.view_utils import render_page
from models import TRANSACTION_TYPES
from models import Transaction
from models import detect_transaction_file_type
from models import parse_transactions
from models import transactions_as_csv
from positions.models import refresh_positions
from quotes.models import CASH_SYMBOL
from quotes.models import quote_by_symbol

#-------------\
#  CONSTANTS  |
#-------------/

TRANSACTIONS_BEFORE_SEE_ALL = 20

#---------\
#  VIEWS  |
#---------/

@portfolio_manipulation_decorator
def transactions(request, portfolio, is_sample, read_only):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  symbols = set([t.symbol for t in transactions])
  
  symbol_filter = request.GET.get('filter')
  if symbol_filter != None and symbol_filter != '':
    transactions = transactions.filter(symbol = symbol_filter)
  
  context = {
      'symbols' : symbols.difference([CASH_SYMBOL]),
      'transaction_sets' : [ transactions[0:TRANSACTIONS_BEFORE_SEE_ALL], transactions[TRANSACTIONS_BEFORE_SEE_ALL:transactions.count()] ],
      'current_tab' : 'transactions',
      'symbol_filter' : symbol_filter,  
    }
  
  return render_page('transactions.html', request, portfolio = portfolio, extra_dictionary = context)
  
@portfolio_manipulation_decorator
def add(request, portfolio, is_sample, read_only):
  form = TransactionForm(request.POST)
  if form.is_valid():
    commission = form.cleaned_data.get('commission')
    if commission == None:
      commission = 0.0
    
    type = form.cleaned_data.get('type').encode('UTF-8')
    
    symbol = form.cleaned_data.get('symbol').encode('UTF-8').upper()
    linked_symbol = None
    if type == 'ADJUST':
      linked_symbol = symbol
      
    if type in ['DEPOSIT', 'WITHDRAW', 'ADJUST']:
      symbol = CASH_SYMBOL
    
    if symbol != None and len(symbol) > 0:
      transaction = Transaction()
      transaction.portfolio = portfolio
      transaction.type = type
      transaction.as_of_date = form.cleaned_data.get('as_of_date')
      transaction.symbol = symbol
      transaction.quantity = form.cleaned_data.get('quantity')
      transaction.price = form.cleaned_data.get('price')
      transaction.total = (transaction.quantity * transaction.price) + commission
      transaction.linked_symbol = linked_symbol
      transaction.save()
    
      refresh_positions(portfolio, force = True)
  
  return redirect_to_portfolio_action('transactions', portfolio)

@portfolio_manipulation_decorator
def remove(request, portfolio, is_sample, read_only, transaction_id):
  transaction = Transaction.objects.filter(id = transaction_id)[0]
  if transaction.portfolio.id == portfolio.id:
    transaction.delete()
    refresh_positions(portfolio, force = True)
    
  return redirect_to_portfolio_action('transactions', portfolio) 

@portfolio_manipulation_decorator
def remove_all(request, portfolio, is_sample, read_only):
  Transaction.objects.filter(portfolio__id__exact = portfolio.id).delete()
  refresh_positions(portfolio, force = True)
    
  return redirect_to_portfolio_action('importTransactions', portfolio)

@portfolio_manipulation_decorator
def update(request, portfolio, is_sample, read_only, transaction_id):
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
        if transaction.symbol == CASH_SYMBOL:
          transaction.quantity = transaction.total
      
      linked_symbol = form.get_if_present('linkedsymbol')
      if linked_symbol != None:
        transaction.linked_symbol = (linked_symbol.encode('UTF-8').upper() if linked_symbol.strip() != '' else None)
      
      transaction.save()
      refresh_positions(portfolio, force = True)
      success = True
    
  return HttpResponse("{ \"success\": \"%s\" }" % success)

@portfolio_manipulation_decorator
def export(request, portfolio, is_sample, read_only, format):
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
      
    quotes = [ quote_by_symbol(symbol) for symbol in set([t.symbol for t in transactions]).difference([CASH_SYMBOL]) ]
    
    response.write(render_to_string('transactions.ofx', {
        'portfolio' : portfolio,
        'transactions': transactions,
        'start_date' : min([t.as_of_date for t in transactions]),
        'end_date' : max([t.as_of_date for t in transactions]),
        'quotes' : quotes, 
      }))
    
  return response

@portfolio_manipulation_decorator
def import_form(request, portfolio, is_sample, read_only):
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
          if len(transaction.symbol) < 1 or len(transaction.symbol) > 10:
            raise Exception("Invalid symbol: %s" % transaction.symbol)
          
          is_duplicate = False
          possibles = by_date_map.get(transaction.as_of_date)
          if possibles != None:
            for possible in possibles:
              if possible.type == transaction.type and possible.symbol == transaction.symbol and abs(possible.quantity - transaction.quantity) < 0.01 and abs(possible.price - transaction.price) < 0.01:
                is_duplicate = True
            
          transaction.is_duplicate = is_duplicate
    
  context = { 
      'transactions' : transactions, 
      'current_tab' : 'transactions', 
      'auto_detect_error' : auto_detect_error 
    }
  
  return render_page('importTransactions.html', request, portfolio = portfolio, extra_dictionary = context)  

@portfolio_manipulation_decorator
def process_import(request, portfolio, is_sample, read_only):
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
    
  refresh_positions(portfolio, force = True)
  return redirect_to_portfolio_action('transactions', portfolio)

@portfolio_manipulation_decorator
def request_import_type(request, portfolio, is_sample, read_only):
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
  
  return redirect_to_portfolio_action('importTransactions', portfolio, 'requestSent=true')

#---------\
#  FORMS  |
#---------/

class TransactionForm(forms.Form):
  type = forms.ChoiceField(choices = TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 10, required = False)
  quantity = forms.FloatField()
  price = forms.FloatField(min_value = 0.01)
  commission = forms.FloatField(min_value = 0.01, required = False)

class UpdateTransactionForm(forms.Form):
  type = forms.ChoiceField(choices = TRANSACTION_TYPES, required = False)
  date = forms.DateField(required = False)
  symbol = forms.CharField(required = False, min_length = 1, max_length = 10)
  quantity = forms.FloatField(required = False)
  price = forms.FloatField(required = False, min_value = 0.01)
  total = forms.FloatField(required = False)
  linkedsymbol = forms.CharField(required = False, max_length = 10) # underscore removed due to JS split issue
  
  def __init__(self, data):
    forms.Form.__init__(self, data)
    self.original_data = data
    
  def get_if_present(self, name):
    return (self.cleaned_data.get(name) if name in self.original_data else None)

class ImportForm(forms.Form):
  TYPE_CHOICES = [
      ('AUTO', u'AUTO'),
      ('FRANO', u'FRANO'), 
      ('CHARLES', u'CHARLES'),
      ('GOOGLE', u'GOOGLE'),
      ('SCOTTRADE', u'SCOTTRADE'),
      ('AMERITRADE', u'AMERITRADE'),
      ('ZECCO', u'ZECCO'),
      ('FIDELITY', u'FIDELITY'),
      ('MERCER_401', u'MERCER_401'),
    ]
  
  type = forms.ChoiceField(choices = TYPE_CHOICES)
  file = forms.FileField()
  
class RequestImportForm(forms.Form):
  type = forms.CharField(max_length = 255)
  file = forms.FileField()
  
class ImportTransactionForm(forms.Form):
  type = forms.ChoiceField(choices = TRANSACTION_TYPES)
  as_of_date = forms.DateField()
  symbol = forms.CharField(min_length = 1, max_length = 10)
  quantity = forms.FloatField()
  price = forms.FloatField(min_value = 0.01)
  total = forms.FloatField()
  linked_symbol = forms.CharField(max_length = 10, required = False)
  exclude = forms.BooleanField(required = False)

ImportTransactionFormSet = formset_factory(ImportTransactionForm)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/
