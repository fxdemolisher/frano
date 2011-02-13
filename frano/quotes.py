# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv

from datetime import datetime
from datetime import timedelta

from urllib import urlopen

from models import PriceHistory
from models import Quote

#-------------\
#  CONSTANTS  |
#-------------/

CASH_SYMBOL = '*CASH'
HISTORY_START_DATE = date(1900, 1, 1)

#---------------------\
#  EXPOSED FUNCTIONS  |
#---------------------/

def get_quotes_by_symbols(symbols):
  
  # load or prime quotes for each symbol
  existing_quotes = dict([ (q.symbol, q) for q in Quote.objects.filter(symbol__in = symbols) ])
  quotes = { }
  symbols_to_retrieve = []
  for symbol in symbols:
    quote = existing_quotes.get(symbol, None)
    if quote == None:
      quote = Quote(symbol = symbol, last_trade = datetime.now())
      
    quotes[symbol] = quote
    if symbol != CASH_SYMBOL:
      symbols_to_retrieve.append(symbol)
      
    else:
      quote.name = 'US Dollars'
      quote.price = 1.0
      quote.cash_equivalent = True
  
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
    quote.save()

def refresh_price_history_for_quote(quote):
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
