# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import string
import random

from datetime import date
from datetime import datetime
from datetime import timedelta
from django.db import models
from django.db import connection
from exceptions import StopIteration

from quotes import get_quotes_by_symbols

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
  linked_symbol = models.CharField(max_length = 5, null = True)
  
  class Meta:
    db_table = 'transaction'
    ordering = [ '-as_of_date', 'symbol' ]
  
  def __unicode__(self):
    return "%.2f-%s @ %.2f on %s" % (self.quantity, self.symbol, self.price, self.as_of_date.strftime('%m/%d/%Y'))
  
  def clone(self, portfolio = None):
    out = Transaction()
    out.portfolio = (portfolio if portfolio != None else self.portfolio)
    out.type = self.type
    out.as_of_date = self.as_of_date
    out.symbol = self.symbol
    out.quantity = self.quantity
    out.price = self.price
    out.total = self.total
    out.linked_symbol = self.linked_symbol
    return out
  
class Position(models.Model):
  portfolio = models.ForeignKey(Portfolio)
  as_of_date = models.DateField()
  symbol = models.CharField(max_length = 5)
  quantity = models.FloatField()
  cost_price = models.FloatField()
  realized_pl = models.FloatField()
  
  class Meta:
    db_table = 'position'
    
  def __unicode__(self):
    return "%.2f of %s on %s @ %.2f" % (self.quantity, self.symbol, self.as_of_date.strftime('%m/%d/%Y'), self.cost_price)
  
  def clone(self, as_of_date = None):
    out = Position()
    out.portfolio = self.portfolio
    out.as_of_date = (self.as_of_date if as_of_date == None else as_of_date)
    out.symbol = self.symbol
    out.quantity = self.quantity
    out.cost_price = self.cost_price
    out.realized_pl = self.realized_pl
    
    return out;
  
  @classmethod
  def get_latest(cls, portfolio):
    latest_date = Position.objects.filter(portfolio__id__exact = portfolio.id).dates('as_of_date', 'day', order = 'DESC')
    if latest_date.count() > 0:
      return Position.objects.filter(portfolio__id__exact = portfolio.id, as_of_date = latest_date[0]).order_by('symbol')
    else:
      return []
  
class TaxLot(models.Model):
  position = models.ForeignKey(Position)
  as_of_date = models.DateField()
  quantity = models.FloatField()
  cost_price = models.FloatField()
  sold_quantity = models.FloatField()
  sold_price = models.FloatField()
  
  class Meta:
    db_table = 'tax_lot'
    
  def __unicode__(self):
    return "%.2f on %s @ %.2f with %.2f sold at %.2f" % (self.quantity, self.as_of_date.strftime('%m/%d/%Y'), self.cost_price, self.sold_quantity, self.sold_price)
  
  def clone(self):
    return TaxLot(as_of_date = self.as_of_date,
        quantity = self.quantity,
        cost_price = self.cost_price,
        sold_quantity = self.sold_quantity,
        sold_price = self.sold_price
      )
  
class Quote(models.Model):
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.FloatField()
  last_trade = models.DateTimeField()
  cash_equivalent = models.BooleanField()
  
  class Meta:
    db_table = 'quote'
  
  def __unicode__(self):
    return "%s - %s" % (self.symbol, self.name)
  
  @classmethod
  def by_symbol(cls, symbol):
    quotes = Quote.objects.filter(symbol = symbol)
    if quotes.count() == 0:
      get_quotes_by_symbols([ symbol ])
    
    quote = quotes[0]
    
    if quote.pricehistory_set.count() == 0:
      refresh_price_history_for_quote(quote)
          
    return quote
  
  def price_as_of(self, as_of):
    if self.cash_equivalent or self.last_trade.date() == as_of:
      return self.price
    else:
      candidates = self.pricehistory_set.filter(as_of_date__lte = as_of.strftime('%Y-%m-%d')).order_by('-as_of_date')
      return (candidates[0].price if candidates.count() > 0 else 0)
  
  def previous_close_price(self):
    return self.price_as_of(self.last_trade.date() - timedelta(days = 1))
  
class PriceHistory(models.Model):
  quote = models.ForeignKey('Quote')
  as_of_date = models.DateTimeField()
  price = models.FloatField()
  
  class Meta:
    db_table = 'price_history'
    unique_together = ( 'quote', 'as_of_date' )
    
  def __unicode__(self):
    return "%s @ %.2f on %s" % (self.quote.symbol, self.price, self.as_of_date.strftime('%Y-%m-%d'))
  