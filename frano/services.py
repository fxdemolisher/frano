# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import datetime, csv

from decimal import *
from urllib import urlopen

from frano import settings
from models import Quote

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
    
