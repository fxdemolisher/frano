# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime
from datetime import timedelta
from math import ceil
from math import floor
from random import choice
from random import randint
from random import random
from random import sample

from quotes.models import CASH_SYMBOL
from quotes.models import quotes_by_symbols
from transactions.models import Transaction

#-------------\
#  CONSTANTS  |
#-------------/

# set of instruments a demo portfolio will choose from
DEMO_INSTRUMENTS = [
    'AA',    # Alcoa
    'AAPL',  # Apple
    'ACWI',  # MSCI ACWI
    'AGG',   # Barclays Aggregate Bond Fund
    'BND',   # Vanguard Total Bond Market
    'DBC',   # PowerShares DB Commodity Index
    'DBO',   # PowerShares DB Oil Fund
    'DIA',   # Dow Jones Industrial Average
    'EEM',   # MSCI Emerging Markets
    'EFA',   # MSCI EAFE
    'EMB',   # JP Morgan USD Emerging Markets
    'FFNOX', # Fidelity Four-in-One
    'GE',    # General Electric
    'GLD',   # GLD Trust
    'GOOG',  # Google
    'IJH',   # S&P MidCap 400
    'INTC',  # Intel
    'IWM',   # Rusell 2000
    'IWV',   # Russell 3000
    'IYR',   # Dow Jones US Real Estate
    'MSFT',  # Microsoft
    'QQQ',   # PowerShares QQQ (Nasdaq)
    'SCZ',   # MSCI EAFE Small Cap
    'SLV',   # Silver Trust
    'SPY',   # S&P 500
    'TIP',   # Barclays TIPS Bond fund
    'XOM',   # Exxon Mobil
    'YACKX', # Yacktman Fund
]

# demo portfolio commissions, chosen at random once per portfolio
DEMO_COMMISSIONS = [ 4.5, 7.99, 9.99 ]

# Min/max number of instruments in a demo portfolio
DEMO_MIN_INSTRUMENTS = 4
DEMO_MAX_INSTRUMENTS = 8

# Min/max investment in a demo portfolio
DEMO_MIN_INVESTMENT = 10000
DEMO_MAX_INVESTMENT = 100000

# Number of demo portfolios to generate
DEMO_PORTFOLIOS = 10

# Nunmber of days to go back in history to make the demo portfolios
DEMO_DAYS_CUTOFF = 365

# Approximate number of transactions to have in a demo portfolios
DEMO_TARGET_TRANSACTIONS = 40

# Approximate number of deposits in a demo portfolio
DEMO_TARGET_DEPOSITS = 5

# Ratio of buys vs. sells
DEMO_BUY_SELL_RATIO = 4

# List of lists of demo transactions
DEMO = []

#------------\
#  SERVICES  |
#------------/

def get_demo_transactions():
  global DEMO
  if len(DEMO) == 0:
    print '==============GEN==============='
    DEMO = _generate_demo_portfolios(DEMO_PORTFOLIOS)

  
  return choice(DEMO)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _generate_demo_portfolios(count):
  out = []
  for i in range(count):
    instruments = sample(DEMO_INSTRUMENTS, randint(DEMO_MIN_INSTRUMENTS, DEMO_MAX_INSTRUMENTS))
    total_investment = randint(DEMO_MIN_INVESTMENT, DEMO_MAX_INVESTMENT)
    commission = choice(DEMO_COMMISSIONS)
    out.append(_generate_random_transactions(instruments, 
        total_investment, 
        commission)
      )
  
  return out
  
def _generate_random_transactions(instruments, total_amount, commission):
  
  # Load historic prices
  quotes = quotes_by_symbols(instruments)
  
  cutoff_date = datetime.now().date() - timedelta(days = DEMO_DAYS_CUTOFF)
  prices = dict([ (quote.symbol, {}) for quote in quotes ])
  dates = set([])
  quote_map = { }
  for quote in quotes:
    quote_map[quote.symbol] = quote
    for history in quote.pricehistory_set.filter(as_of_date__gte = cutoff_date).order_by('as_of_date'):
      cur_date =  history.as_of_date.date()
      prices.get(quote.symbol)[cur_date] = history.price
      dates.add(cur_date)

  # portfolio probabilities
  transaction_probability = DEMO_TARGET_TRANSACTIONS / float(len(dates))
  deposit_probability = DEMO_TARGET_DEPOSITS / float(DEMO_TARGET_TRANSACTIONS)
  buy_sell_probability = DEMO_BUY_SELL_RATIO / float(DEMO_BUY_SELL_RATIO + 1)

  # generate transactions
  transactions = []
  quantities = dict([ (symbol, 0.0) for symbol in instruments ])
  undeposited_cash = total_amount
  cash = 0
  for date in sorted(dates):
    sell_candidates = [ q[0] for q in quantities.items() if q[1] > 0 ]
    
    # see if there is a transaction today or if we are just starting out
    if random() <= transaction_probability or len(transactions) == 0:
      
      # deposits
      if undeposited_cash > 1 and random() <= deposit_probability:
        deposit = min([ undeposited_cash, round(undeposited_cash * (randint(10, 100) / 100.0), -2), total_amount * 0.5 ])
        undeposited_cash -= deposit
        cash += deposit
        transactions.append(Transaction(type = 'DEPOSIT',
            as_of_date = date,
            symbol = CASH_SYMBOL,
            quantity = deposit,
            price = 1.0,
            total = deposit,
          ))
        
      # buys - if we have any cash
      elif random() <= buy_sell_probability:
        amount = min([ cash, round(cash * (randint(20, 100) / 100.0)), total_amount * 0.1 ])
        symbol = choice(instruments)
        price = (prices.get(symbol).get(date) if not quote_map.get(symbol).cash_equivalent else 1.0)
        quantity = floor((amount - commission) / price)
        if quantity > 0:
          total = (quantity * price) + commission
          cash -= total
          quantities[symbol] = quantities.get(symbol) + quantity
          transactions.append(Transaction(type = 'BUY',
              as_of_date = date,
              symbol = symbol,
              quantity = quantity,
              price = price,
              total = total,
            ))
        
      # sells - if there is anything to sell
      elif len(sell_candidates) > 0:
        symbol = choice(sell_candidates)
        price = (prices.get(symbol).get(date) if not quote_map.get(symbol).cash_equivalent else 1.0)
        available_quantity = quantities.get(symbol)
        quantity = min(available_quantity, round(available_quantity * (randint(20, 100) / 100.0)))
        if quantity > 0:
          total = (quantity * price) - commission
          cash += total
          quantities[symbol] = quantities.get(symbol) - quantity
          transactions.append(Transaction(type = 'SELL',
              as_of_date = date,
              symbol = symbol,
              quantity = quantity,
              price = price,
              total = total,
            ))

  return transactions
