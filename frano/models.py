# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv
import string
import random

from datetime import datetime, timedelta
from decimal import Decimal
from django.db import models
from exceptions import StopIteration
from urllib import urlopen

class User(models.Model):
  open_id = models.CharField(max_length = 255, unique = True)
  email = models.CharField(max_length = 255, unique = True, null = True)
  create_date = models.DateTimeField()
  
  class Meta:
    db_table = 'user'
  
  def __unicode__(self):
    return "%s - %s" % (self.email, self.open_id)
  
  @classmethod
  def create(cls, open_id, email):
    user = User()
    user.open_id = open_id
    user.email = email
    user.create_date = datetime.now()
    user.save()
    
    return user
  
class Portfolio(models.Model):
  TOKEN_LETTERS = string.digits + string.uppercase + string.lowercase
  
  user = models.ForeignKey(User)
  name = models.CharField(max_length = 30)
  read_only_token = models.CharField(max_length = 20, unique = True)
  create_date = models.DateTimeField()
  
  class Meta:
    db_table = 'portfolio'
  
  def __unicode__(self):
    return "%s" % (self.name)
  
  @classmethod
  def create(cls, user, name):
    read_only_token = ''
    for i in range(20):
      read_only_token += random.choice(Portfolio.TOKEN_LETTERS)
      
    portfolio = Portfolio()
    portfolio.user = user
    portfolio.name = name
    portfolio.read_only_token = read_only_token
    portfolio.create_date = datetime.now()
    portfolio.save()
    
    return portfolio
  
class Transaction(models.Model):
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
    db_table = 'transaction'
    ordering = [ '-as_of_date', 'symbol' ]
  
  def __unicode__(self):
    return "%.2f-%s @ %.2f on %s" % (self.quantity, self.symbol, self.price, self.as_of_date.strftime('%m/%d/%Y'))
  
class Quote(models.Model):
  TIMEOUT_DELTA = timedelta(0, 0, 0, 0, 15)
  CASH_SYMBOL = '*CASH'
  
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.DecimalField(max_digits = 20, decimal_places = 10)
  previous_close_price = models.DecimalField(max_digits = 20, decimal_places = 10)
  last_trade = models.DateTimeField()
  quote_date = models.DateTimeField()
  
  class Meta:
    db_table = 'quote'
  
  def __unicode__(self):
    return "%s - %s" % (self.symbol, self.name)
  
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
        u = urlopen('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1pd1t1n&e=.csv' % self.symbol)
        row = csv.reader(u).next()
        if len(row) < 6:
          return
        
        self.name = row[5]
        self.price = Decimal(str(row[1]))
        self.previous_close_price = Decimal(str(0.0))
        
        if row[2] != 'N/A': 
          self.previous_close_price = row[2]
          
        if row[3] != 'N/A' and row[4] != 'N/A':
          month, day, year = [int(f) for f in row[3].split('/')]
          time = datetime.strptime(row[4], '%I:%M%p')
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
  
  @classmethod
  def historical_price_by_symbol(cls, symbol, asOfDate):
    u = None
    price = 0.0
    try:
      u = urlopen('http://ichart.finance.yahoo.com/table.csv?s=%s&a=%.2d&b=%.2d&c=%.4d&d=%.2d&e=%.2d&f=%.4d&g=d&ignore=.csv' % (symbol, (asOfDate.month - 1), asOfDate.day, asOfDate.year, (asOfDate.month - 1), asOfDate.day, asOfDate.year))
      reader = csv.reader(u)
      reader.next() # skip header
      try:
        row = reader.next()
        if row != None:
          price = float(row[6])
          
      except StopIteration:
        pass 
      
    finally:
      if u != None:
        u.close()
        
    return price