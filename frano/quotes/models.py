# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv

from datetime import date
from datetime import datetime
from datetime import timedelta
from urllib import urlopen

from django.db import models

#-------------\
#  CONSTANTS  |
#-------------/

CASH_SYMBOL = '*CASH'
HISTORY_START_DATE = date(1900, 1, 1)

#----------\
#  MODELS  |
#----------/

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
    
class PriceHistory(models.Model):
  quote = models.ForeignKey(Quote)
  as_of_date = models.DateTimeField()
  price = models.FloatField()
  
  class Meta:
    db_table = 'price_history'
    unique_together = ( 'quote', 'as_of_date' )
    
  def __unicode__(self):
    return "%s @ %.2f on %s" % (self.quote.symbol, self.price, self.as_of_date.strftime('%Y-%m-%d'))
  
#------------\
#  SERVICES  |
#------------/

def price_as_of(quote, as_of):
  """Get the price for quote as of a specific date."""
  
  if quote.cash_equivalent or quote.last_trade.date() == as_of:
    return quote.price
  else:
    candidates = quote.pricehistory_set.filter(as_of_date__lte = as_of.strftime('%Y-%m-%d')).order_by('-as_of_date')[0:1]
    return (candidates[0].price if candidates.count() > 0 else 0)
  
def previous_close_price(quote):
  """Get the previous close price for a quote."""
  
  return price_as_of(quote, quote.last_trade.date() - timedelta(days = 1))

def quote_by_symbol(symbol):
  """Retrieve a quote by symbol."""

  return quotes_by_symbols([ symbol ])[0]

def quotes_by_symbols(symbols, force_retrieve = False):
  """Retrieve a quotes by a list of symbols."""
  
  # load or prime quotes for each symbol
  existing_quotes = dict([ (q.symbol, q) for q in Quote.objects.filter(symbol__in = symbols) ])
  quotes = { }
  symbols_to_retrieve = []
  for symbol in symbols:
    quote = existing_quotes.get(symbol, None)
    exists = True
    if quote == None:
      quote = Quote(symbol = symbol, last_trade = datetime.now())
      exists = False
            
    quotes[symbol] = quote
    if symbol == CASH_SYMBOL and not exists:
      quote.name = 'US Dollars'
      quote.price = 1.0
      quote.cash_equivalent = True
      quote.changed = True
      
    elif not exists or force_retrieve:
      symbols_to_retrieve.append(symbol)
      quote.changed = True
      
    else:
      quote.changed = False
  
  # retrieve fresh prices from yahoo
  if len(symbols_to_retrieve) > 0:
    u = None
    try:
      u = urlopen('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1n&e=.csv' % (",".join(symbols_to_retrieve)))
      for row in csv.reader(u):
        if len(row) < 5:
          continue
      
        quote = quotes.get(row[0])
        quote.cash_equivalent = row[1].endswith('%')
        quote.price = (1.0 if quote.cash_equivalent else float(row[1]))
        quote.name = row[4]
      
        if row[2] != 'N/A' and row[3] != 'N/A':
          month, day, year = [int(f) for f in row[2].split('/')]
          time = datetime.strptime(row[3], '%I:%M%p')
          quote.last_trade = datetime(year, month, day, time.hour, time.minute, time.second)
        
    finally:
      if u != None:
        u.close()
      
  # save all changes
  for quote in quotes.values():
    if quote.changed:
      quote.save()
    
    if quote.pricehistory_set.count() == 0:
      refresh_price_history(quote)
    
  return quotes.values()

def refresh_price_history(quote):
  history = []
  u = None
  try:
    end_date = quote.last_trade + timedelta(days = 1)
    u = urlopen('http://ichart.finance.yahoo.com/table.csv?s=%s&a=%.2d&b=%.2d&c=%.4d&d=%.2d&e=%.2d&f=%.4d&g=d&ignore=.csv' % (
        quote.symbol, 
        (HISTORY_START_DATE.month - 1), 
        HISTORY_START_DATE.day, 
        HISTORY_START_DATE.year, 
        (end_date.month - 1), 
        end_date.day, 
        end_date.year)
      )
    
    reader = csv.reader(u)
    header_row = reader.next()
    if len(header_row) < 7:
      return
    
    for row in reader:
      current = PriceHistory()
      current.quote = quote
      current.as_of_date = datetime.strptime(row[0], '%Y-%m-%d')
      current.price = float(row[6])
      
      history.append(current)
    
  finally:
    if u != None:
      u.close()

  if len(history) > 0:
    PriceHistory.objects.filter(quote__id__exact = quote.id).delete()
    for current in history:
      current.save()

  quote.history_date = datetime.now()
  quote.save()
  return quote

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/
