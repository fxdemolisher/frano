# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import random
import string

from datetime import datetime

from django.db import models

#-------------\
#  CONSTANTS  |
#-------------/

TOKEN_LETTERS = string.digits + string.uppercase + string.lowercase

#----------\
#  MODELS  |
#----------/

class User(models.Model):
  open_id = models.CharField(max_length = 255, unique = True)
  email = models.CharField(max_length = 255, unique = True, null = True)
  create_date = models.DateTimeField()
  
  class Meta:
    db_table = 'user'
  
  def __unicode__(self):
    return "%s - %s" % (self.email, self.open_id)
    
class Portfolio(models.Model):
  user = models.ForeignKey(User)
  name = models.CharField(max_length = 30)
  read_only_token = models.CharField(max_length = 20, unique = True)
  create_date = models.DateTimeField()
  
  class Meta:
    db_table = 'portfolio'
  
  def __unicode__(self):
    return "%s" % (self.name)
  
#------------\
#  SERVICES  |
#------------/

def create_user(open_id, email):
  """Create and save a new user with the given open ID and email address."""
  
  user = User()
  user.open_id = open_id
  user.email = email
  user.create_date = datetime.now()
  user.save()
  
  return user

def create_portfolio(user, name):
  """Create and save a new portfolio for the given user and with the given name."""
  
  read_only_token = ''
  for i in range(10):
    read_only_token += random.choice(TOKEN_LETTERS)
    
  portfolio = Portfolio()
  portfolio.user = user
  portfolio.name = name
  portfolio.read_only_token = read_only_token
  portfolio.create_date = datetime.now()
  portfolio.save()
  
  return portfolio

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/
