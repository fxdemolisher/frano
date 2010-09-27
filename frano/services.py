import random, hashlib, datetime, csv

from decimal import *
from urllib import urlopen

from django.shortcuts import render_to_response, redirect

from frano import settings
from models import User, Quote

def get_user(request):
  return request.session.get('username')

def set_user(request, username):
  request.session['username'] = username

def login_required_decorator(view_function):
  def view_function_decorated(request):
    if get_user(request) == None:
      return redirect('/login.html')
    else:
      return view_function(request)
    
  return view_function_decorated

def does_username_exist(usenameToCheck):
  return User.objects.filter(username = usenameToCheck).count() > 0

def register_user(username, password):
  user = User()
  user.username = username
  user.salt = generate_salt(40)
  user.salted_hash = salted_hash(password, user.salt)
  user.create_date = datetime.datetime.now()
  user.save()
  
  return user

def login_user(username, password):
  if does_username_exist(username):
    user = User.objects.get(username = username)
    incoming_hash = salted_hash(password, user.salt)
    return incoming_hash == user.salted_hash
  
  return False

def update_user(username, newUsername, newPassword):
  user = User.objects.get(username = username)
  user.username = newUsername
  
  if newPassword != None and newPassword != '':
    user.salted_hash = salted_hash(newPassword, user.salt)
    
  user.save()
  return user
  
def salted_hash(password, salt):
  sha = hashlib.new('sha1')
  sha.update(password + "{" + salt + "}")
  return sha.hexdigest()

def generate_salt(length):
  out = ''
  for c in range(length):
    out += random.choice('0123456789abcdef')
  
  return out

def get_quote(symbolToFind):
  candidate = Quote.objects.filter(symbol = symbolToFind)
  quote = None
  if candidate.count() > 0:
    quote = candidate[0]
  else:
    quote = Quote(symbol = symbolToFind)
  
  if quote.quote_date == None or (datetime.datetime.now() - quote.quote_date) > settings.QUOTE_TIMEOUT_DELTA:
    update_quote(quote)
    quote.save()
  
  return quote

def update_quote(quote):
  if quote.symbol == settings.CASH_SYMBOL:
    quote.name = 'US Dollars'
    quote.price = Decimal('1.0')
    quote.previous_close_price = Decimal('1.0')
    quote.last_trade = datetime.datetime.now()
    quote.quote_date = datetime.datetime.now()
    
  else:
    update_quote_via_yahoo(quote)
    
def update_quote_via_yahoo(quote):
  try:
    u = urlopen('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=snl1pd1t1&e=.csv' % quote.symbol)
    row = csv.reader(u).next()
    if len(row) != 6:
      return
    
    quote.name = row[1]
    quote.price = Decimal(str(row[2]))
    quote.previous_close_price = Decimal(str(0.0))
    quote.last_trade = datetime.datetime.now()
    quote.quote_date = datetime.datetime.now()
    
    if row[3] != 'N/A': 
      quote.previous_close_price = row[3]
      
    if row[4] != 'N/A' and row[5] != 'N/A':
      month, day, year = [int(f) for f in row[4].split('/')]
      time = datetime.datetime.strptime(row[5], '%I:%M%p')
      last_trade = datetime.datetime(year, month, day, time.hour, time.minute, time.second)
      quote.last_trade = last_trade
      
  finally:
    u.close()