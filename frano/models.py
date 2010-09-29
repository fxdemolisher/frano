# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.db import models

from utilities import salted_hash, generate_salt

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
    return User.objects.filter(username = usenameToCheck).count() > 0
  
  @classmethod
  def register(cls, username, password):
    user = User()
    user.username = username
    user.salt = generate_salt(40)
    user.salted_hash = salted_hash(password, user.salt)
    user.create_date = datetime.datetime.now()
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
  
  symbol = models.CharField(max_length = 5, unique = True)
  name = models.CharField(max_length = 255)
  price = models.DecimalField(max_digits = 20, decimal_places = 10)
  previous_close_price = models.DecimalField(max_digits = 20, decimal_places = 10)
  last_trade = models.DateTimeField()
  quote_date = models.DateTimeField()
  
  def __unicode__(self):
    return self.symbol