# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import json

from datetime import date
from datetime import datetime
from datetime import timedelta
from urllib import quote_plus
from urllib import urlopen

from django.db import models

#-------------\
#  CONSTANTS  |
#-------------/

CASH_SYMBOL = '*CASH'
PRICE_HISTORY_LIMIT_IN_DAYS = 365 * 10

#----------\
#  MODELS  |
#----------/

class Quote(models.Model):
  symbol = models.CharField(max_length = 10, unique = True)
  name = models.CharField(max_length = 255)
  price = models.FloatField()
  last_trade = models.DateTimeField()
  cash_equivalent = models.BooleanField()
  
  class Meta:
    db_table = 'quote'
  
  def __unicode__(self):
    return '%s - %s' % (self.symbol, self.name)
    
class PriceHistory(models.Model):
  quote = models.ForeignKey(Quote)
  as_of_date = models.DateTimeField()
  price = models.FloatField()
  
  class Meta:
    db_table = 'price_history'
    unique_together = ( 'quote', 'as_of_date' )
    
  def __unicode__(self):
    return '%s @ %.2f on %s' % (self.quote.symbol, self.price, self.as_of_date.strftime('%Y-%m-%d'))
  
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
    csv_url = ('http://download.finance.yahoo.com/d/quotes.csv?s=%s&f=sl1d1t1n&e=.csv' % (','.join(symbols_to_retrieve)))
    csv_columns = 'symbol,price,date,time,name'
    for row in _yql_csv_to_json(csv_url, csv_columns):
      price = row['price']
      tradeDate = row['date']
      tradeTime = row['time']
      
      quote = quotes.get(row['symbol'])
      quote.cash_equivalent = price.endswith('%')
      quote.price = (1.0 if quote.cash_equivalent else float(price))
      quote.name = row['name']
    
      if tradeDate != 'N/A' and tradeTime != 'N/A':
        month, day, year = [int(f) for f in tradeDate.split('/')]
        time = datetime.strptime(tradeTime, '%I:%M%p')
        quote.last_trade = datetime(year, month, day, time.hour, time.minute, time.second)
        
  # save all changes
  for quote in quotes.values():
    if quote.changed:
      quote.save()
    
    if quote.pricehistory_set.count() == 0:
      refresh_price_history(quote)
    
  return quotes.values()

def refresh_price_history(quote):
  history = []
  
  start_date = quote.last_trade + timedelta(days = 0 - PRICE_HISTORY_LIMIT_IN_DAYS)
  end_date = quote.last_trade + timedelta(days = 1)
  csv_columns = 'date,open,high,low,close,volume,adj_close'
  csv_url = ('http://ichart.finance.yahoo.com/table.csv?s=%s&a=%.2d&b=%.2d&c=%.4d&d=%.2d&e=%.2d&f=%.4d&g=d&ignore=.csv' % (
      quote.symbol, 
      (start_date.month - 1), 
      start_date.day, 
      start_date.year, 
      (end_date.month - 1), 
      end_date.day, 
      end_date.year)
    )

  for row in _yql_csv_to_json(csv_url, csv_columns, PRICE_HISTORY_LIMIT_IN_DAYS, 2):
    current = PriceHistory()
    current.quote = quote
    current.as_of_date = datetime.strptime(row['date'], '%Y-%m-%d')
    current.price = float(row['adj_close'])
    
    history.append(current)
    
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

def _yql_csv_to_json(csv_url, csv_columns, limit = None, offset = None):
  u = None
  try:
    
    yql_suffix = ''
    if limit != None and offset != None:
      yql_suffix = yql_suffix + (' limit %d offset %d' % (limit, offset))
    
    yql_query = ("select * from csv where url='%s' and columns='%s' %s" % (csv_url, csv_columns, yql_suffix))
    u = urlopen('http://query.yahooapis.com/v1/public/yql?q=%s&format=json&callback=' % quote_plus(yql_query))
    
    packet = json.loads(u.read())
    out = [ ]
    if packet.has_key('query'):
      count = packet['query']['count']
      if count == 1:
        out.append(packet['query']['results']['row'])
      elif count > 0:
        out = packet['query']['results']['row']
    
    return out

  finally:
    if u != None:
      u.close()
      