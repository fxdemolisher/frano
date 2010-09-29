# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.db import models

class User(models.Model):
  """A registered user in the system"""
  
  username = models.CharField(max_length = 255, unique = True)
  salt = models.CharField(max_length = 40)
  salted_hash = models.CharField(max_length = 40)
  create_date = models.DateTimeField()
  
  def __unicode__(self):
    return self.username

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
  
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.DecimalField(max_digits = 20, decimal_places = 10)
  previous_close_price = models.DecimalField(max_digits = 20, decimal_places = 10)
  last_trade = models.DateTimeField()
  quote_date = models.DateTimeField()
  
  def __unicode__(self):
    return self.symbol