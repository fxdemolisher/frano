# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv

from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from urllib import urlopen
from utilities import generate_salt, salted_hash 

class User(models.Model):
  """A registered user in the system"""
  
  username = models.CharField(max_length = 255, unique = True)
  salt = models.CharField(max_length = 40)
  salted_hash = models.CharField(max_length = 40)
  create_date = models.DateTimeField()
  
  def __unicode__(self):
    return self.username
  
  def to_request(self, request):
    request.frano_user = self
    request.session['username'] = self.username
    
  def check_password(self, candidatePassword):
    incoming_hash = salted_hash(candidatePassword, self.salt)
    return incoming_hash == self.salted_hash
  
  def set_password(self, new_password):
    self.salted_hash = salted_hash(new_password, self.salt)
    
  @classmethod
  def clear_in_request(cls, request):
    request.frano_user = None
    request.session['username'] = None
  
  @classmethod
  def from_request(cls, request):
    if hasattr(request, 'frano_user') and request.frano_user != None:
      return request.frano_user
    
    name = request.session.get('username')
    if name != None:
      user = User.objects.filter(username = name)[0]
      user.to_request(request)
      return user
    
    return None
  
  @classmethod
  def username_exists(cls, usernameToCheck):
    return User.objects.filter(username = usernameToCheck).count() > 0
  
  @classmethod
  def register(cls, username, password):
    user = User()
    user.username = username
    user.salt = generate_salt(40)
    user.salted_hash = salted_hash(password, user.salt)
    user.create_date = datetime.now()
    user.save()
  
    return user
  
class Portfolio(models.Model):
  """A user's portfolio"""
  
  user = models.ForeignKey(User)
  name = models.CharField(max_length = 30)
  
  def __unicode__(self):
    return self.name
  
class Transaction(models.Model):
  """A recorded transaction in a portfolio"""
  
  TRANSACTION_TYPES = (
    ('BUY', 'Buy'),
    ('SELL', 'Sell'),
    ('DEPOSIT', 'Deposit'),
    ('WITHDRAW', 'Withdraw'),
    ('ADJUST', 'Adjust'),
  )
  
  portfolio = models.ForeignKey(Portfolio)
  type = models.CharField(max_length = 10, choices = TRANSACTION_TYPES)
  as_of_date = models.DateField()
  symbol = models.CharField(max_length = 5)
  quantity = models.DecimalField(max_digits = 20, decimal_places = 10)
  price = models.DecimalField(max_digits = 20, decimal_places = 10)
  total = models.DecimalField(max_digits = 20, decimal_places = 10)
  
  class Meta:
    ordering = [ '-as_of_date', 'symbol' ]
  
  def __unicode__(self):
    return self.symbol
  
class Quote(models.Model):
  """Price quote of a instrument"""
  
  TIMEOUT_DELTA = timedelta(0, 0, 0, 0, 15)
  CASH_SYMBOL = '*CASH'
  
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.DecimalField(max_digits = 20, decimal_places = 10)
  previous_close_price = models.DecimalField(max_digits = 20, decimal_places = 10)
  last_trade = models.DateTimeField()
  quote_date = models.DateTimeField()
  
  def __unicode__(self):
    return self.symbol
  
  def refresh(self):
    self.last_trade = datetime.now()
    self.quote_date = datetime.now()
      
    if self.symbol == Quote.CASH_SYMBOL:
      self.name = 'US Dollars'
      self.price = Decimal('1.0')
      self.previous_close_price = Decimal('1.0')
            
    else:
      u = None
      try:
        u = urlopen('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=snl1pd1t1&e=.csv' % self.symbol)
        row = csv.reader(u).next()
        if len(row) != 6:
          return
        
        self.name = row[1]
        self.price = Decimal(str(row[2]))
        self.previous_close_price = Decimal(str(0.0))
        
        if row[3] != 'N/A': 
          self.previous_close_price = row[3]
          
        if row[4] != 'N/A' and row[5] != 'N/A':
          month, day, year = [int(f) for f in row[4].split('/')]
          time = datetime.strptime(row[5], '%I:%M%p')
          last_trade = datetime(year, month, day, time.hour, time.minute, time.second)
          self.last_trade = last_trade
          
      finally:
        if u != None:
          u.close()
        
    self.save()
    return self
  
  @classmethod
  def by_symbol(cls, symbolToFind):
    candidate = Quote.objects.filter(symbol = symbolToFind)
    quote = None
    if candidate.count() > 0:
      quote = candidate[0]
    else:
      quote = Quote(symbol = symbolToFind)
    
    if quote.quote_date == None or (datetime.now() - quote.quote_date) > Quote.TIMEOUT_DELTA:
      quote.refresh()
          
    return quote
