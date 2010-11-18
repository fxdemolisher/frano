# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv
import string
import random

from datetime import date, datetime, timedelta
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
    for i in range(10):
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
  quantity = models.FloatField()
  price = models.FloatField()
  total = models.FloatField()
  
  class Meta:
    db_table = 'transaction'
    ordering = [ '-as_of_date', 'symbol' ]
  
  def __unicode__(self):
    return "%.2f-%s @ %.2f on %s" % (self.quantity, self.symbol, self.price, self.as_of_date.strftime('%m/%d/%Y'))
  
class Quote(models.Model):
  TIMEOUT_DELTA = timedelta(minutes = 15)
  HISTORY_TIMEOUT_DELTA = timedelta(days = 1)
  HISTORY_START_DATE = date(1900, 1, 1)
  CASH_SYMBOL = '*CASH'
  
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.FloatField()
  last_trade = models.DateTimeField()
  quote_date = models.DateTimeField()
  history_date = models.DateTimeField()
  
  class Meta:
    db_table = 'quote'
  
  def __unicode__(self):
    return "%s - %s" % (self.symbol, self.name)
  
  def refresh(self):
    self.last_trade = self.history_date = self.quote_date = datetime.now()
      
    if self.symbol == Quote.CASH_SYMBOL:
      self.name = 'US Dollars'
      self.price = 1.0
            
    else:
      u = None
      try:
        u = urlopen('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1n&e=.csv' % self.symbol)
        row = csv.reader(u).next()
        if len(row) < 5:
          return
        
        self.name = row[4]
        self.price = float(row[1])
        
        if row[2] != 'N/A' and row[3] != 'N/A':
          month, day, year = [int(f) for f in row[2].split('/')]
          time = datetime.strptime(row[3], '%I:%M%p')
          self.last_trade = datetime(year, month, day, time.hour, time.minute, time.second)
          
      finally:
        if u != None:
          u.close()
        
    self.save()
    return self
  
  def refresh_history(self):
    history = []
    u = None
    try:
      u = urlopen('http://ichart.finance.yahoo.com/table.csv?s=%s&a=%.2d&b=%.2d&c=%.4d&d=%.2d&e=%.2d&f=%.4d&g=d&ignore=.csv' % (
          self.symbol, 
          (Quote.HISTORY_START_DATE.month - 1), 
          Quote.HISTORY_START_DATE.day, 
          Quote.HISTORY_START_DATE.year, 
          (self.quote_date.month - 1), 
          self.quote_date.day, 
          self.quote_date.year)
        )
      
      reader = csv.reader(u)
      reader.next() # skip header
      
      for row in reader:
        current = PriceHistory()
        current.quote = self
        current.as_of_date = datetime.strptime(row[0], '%Y-%m-%d')
        current.price = float(row[6])
        
        history.append(current)
      
    finally:
      if u != None:
        u.close()

    if len(history) > 0:
      PriceHistory.objects.filter(quote__id__exact = self.id).delete()
      for current in history:
        current.save()

    self.history_date = datetime.now()
    self.save()
    return self
  
  def price_as_of(self, as_of):
    return self.pricehistory_set.filter(as_of_date__lte = as_of.strftime('%Y-%m-%d')).order_by('-as_of_date')[0].price
  
  def previous_close_price(self):
    return self.price_as_of(self.last_trade - timedelta(days = 1))
  
  @classmethod
  def by_symbol(cls, symbol_to_find):
    candidate = Quote.objects.filter(symbol = symbol_to_find)
    quote = None
    if candidate.count() > 0:
      quote = candidate[0]
    else:
      quote = Quote(symbol = symbol_to_find)
    
    needs_refresh = (quote.quote_date == None or (datetime.now() - quote.quote_date) > Quote.TIMEOUT_DELTA) 
    needs_history_refresh = (quote.symbol != Quote.CASH_SYMBOL and (quote.history_date == None or (datetime.now() - quote.history_date) > Quote.HISTORY_TIMEOUT_DELTA))
    
    if needs_refresh:
      quote.refresh()
    
    if needs_history_refresh:
      quote.refresh_history()
          
    return quote
  
class PriceHistory(models.Model):
  quote = models.ForeignKey('Quote')
  as_of_date = models.DateTimeField()
  price = models.FloatField()
  
  class Meta:
    db_table = 'price_history'
    unique_together = ( 'quote', 'as_of_date' )
    
  def __unicode__(self):
    return "%s @ %.2f on %s" % (self.quote.symbol, self.price, self.as_of_date.strftime('%Y-%m-%d'))
  