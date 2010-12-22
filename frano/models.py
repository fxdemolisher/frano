# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import csv
import string
import random

from datetime import date, datetime, timedelta
from django.db import models, connection
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
  
  def decorate_with_prices(self, price, previous_price):
    self.price = price
    self.previous_price = previous_price
    
    self.market_value = self.quantity * self.price
    self.cost_basis = self.quantity * self.cost_price
    self.previous_market_value = self.quantity * self.previous_price
    self.pl = (self.market_value - self.cost_basis)
    self.pl_percent = (((self.pl / self.cost_basis) * 100) if self.cost_basis != 0 else 0)
  
  @classmethod
  def refresh_if_needed(cls, portfolio, transactions = None, force = False):
    if transactions == None:
      transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
    
    positions = Position.objects.filter(portfolio__id__exact = portfolio.id)
    if (transactions.count() > 0 and positions.count() == 0) or force:
      Position.objects.filter(portfolio__id__exact = portfolio.id).delete()
      Position.refresh_from_transactions(transactions)
  
  @classmethod
  def refresh_from_transactions(cls, transactions):
    if len(transactions) == 0:
      return
    
    # presort and bucket transactions
    transactions = sorted(transactions, key = (lambda transaction: transaction.id)) 
    transactions = sorted(transactions, key = (lambda transaction: transaction.as_of_date))
    dates = sorted(set([ t.as_of_date for t in transactions]))
    transactions_by_date = dict([(date, []) for date in dates])
    for transaction in transactions:
      transactions_by_date.get(transaction.as_of_date).append(transaction)
    
    # utility functions
    def buy_in_lots(lots, date, quantity, price):
      for lot in lots:
        if lot.sold_quantity > lot.quantity:
          bought_in_lot = min(lot.sold_quantity - lot.quantity, quantity)
          total = (lot.quantity * lot.cost_price) + (bought_in_lot * price)
          lot.quantity += bought_in_lot
          lot.cost_price = ((total / lot.quantity) if lot.quantity <> 0 else 0)
          quantity -= bought_in_lot
      
      if quantity > 0:
        lot = TaxLot(as_of_date = date, 
            quantity = quantity, 
            cost_price = price, 
            sold_quantity = 0, 
            sold_price = 0)
        
        lots.append(lot)
    
    def sell_in_lots(lots, quantity, price):
      for lot in lots:
        sold_in_lot = min(lot.quantity - lot.sold_quantity, quantity)
        if sold_in_lot > 0:
          total = (lot.sold_quantity * lot.sold_price) + (sold_in_lot * price)
          lot.sold_quantity += sold_in_lot
          lot.sold_price = ((total / lot.sold_quantity) if lot.sold_quantity <> 0 else 0)
          quantity -= sold_in_lot
          
        if quantity == 0:
          break
    
      # oversell
      if quantity > 0:
        lot = TaxLot(as_of_date = date, 
          quantity = 0, 
          cost_price = 0, 
          sold_quantity = quantity, 
          sold_price = price)
      
        lots.append(lot)
    
    # get the tax lots
    lot_sets = {}
    last_lot_set = {}
    cash = {}
    last_cash = Position(portfolio = transactions[0].portfolio,
        as_of_date = datetime.now().date(),
        symbol = Quote.CASH_SYMBOL,
        quantity = 0,
        cost_price = 1.0,
        realized_pl = 0.0
      )
    
    for date in dates:
      current_transactions = transactions_by_date.get(date)
      current_lot_set = dict([ (symbol, [lot.clone() for lot in lots]) for symbol, lots in last_lot_set.items()])
      current_cash = last_cash.clone(date)
      
      for transaction in current_transactions:
        if transaction.type == 'DEPOSIT' or transaction.type == 'SELL':
          current_cash.quantity += transaction.total
                  
        elif transaction.type == 'WITHDRAW' or transaction.type == 'BUY':
          current_cash.quantity -= transaction.total
          
        elif  transaction.type == 'ADJUST':
          current_cash.quantity += transaction.total
          current_cash.realized_pl += transaction.total
        
        if transaction.type == 'BUY' or transaction.type == 'SELL':
          lots = current_lot_set.get(transaction.symbol, [])
          current_lot_set[transaction.symbol] = lots
          
          if transaction.type == 'BUY':
            buy_in_lots(lots, transaction.as_of_date, transaction.quantity, transaction.price)
                        
          elif transaction.type == 'SELL':
            sell_in_lots(lots, transaction.quantity, transaction.price)
      
      last_lot_set = lot_sets[date] = current_lot_set
      last_cash = cash[date] = current_cash
      
    # compose positions
    for date in dates:
      cash.get(date).save() # save cash position first
      
      for symbol, lots in lot_sets.get(date).items():
        position = Position(portfolio = transactions[0].portfolio, 
            as_of_date = date,
            symbol = symbol, 
            quantity = 0.0, 
            cost_price = 0.0, 
            realized_pl = 0.0
          )
        
        for lot in lots:
          cur_quantity = (lot.quantity - lot.sold_quantity)
          if cur_quantity > 0:
            total = (position.quantity * position.cost_price) + (cur_quantity * lot.cost_price)
            position.quantity += cur_quantity
            position.cost_price = (total / position.quantity if lot.quantity <> 0.0 else 0.0)
        
          if lot.sold_quantity > 0:
            position.realized_pl += (lot.sold_quantity * (lot.sold_price - lot.cost_price))
        
        position.save()
        for lot in lots:
          lot.position = position
          lot.save()

  # done here      
  
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
  CASH_SYMBOL = '*CASH'
  HISTORY_START_DATE = date(1900, 1, 1)
  
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
      Quote.get_quotes_by_symbols([ symbol ])
    
    quote = quotes[0]
    
    if quote.pricehistory_set.count() == 0:
      quote.refresh_history()
          
    return quote
  
  @classmethod
  def get_quotes_by_symbols(cls, symbols):
    
    # load or prime quotes for each symbol
    existing_quotes = dict([ (q.symbol, q) for q in Quote.objects.filter(symbol__in = symbols) ])
    quotes = { }
    symbols_to_retrieve = []
    for symbol in symbols:
      quote = existing_quotes.get(symbol, None)
      if quote == None:
        quote = Quote(symbol = symbol, last_trade = datetime.now())
        
      quotes[symbol] = quote
      if symbol != Quote.CASH_SYMBOL:
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
  
  def refresh_history(self):
    history = []
    u = None
    try:
      end_date = self.last_trade + timedelta(days = 1)
      u = urlopen('http://ichart.finance.yahoo.com/table.csv?s=%s&a=%.2d&b=%.2d&c=%.4d&d=%.2d&e=%.2d&f=%.4d&g=d&ignore=.csv' % (
          self.symbol, 
          (Quote.HISTORY_START_DATE.month - 1), 
          Quote.HISTORY_START_DATE.day, 
          Quote.HISTORY_START_DATE.year, 
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
    if self.cash_equivalent or self.last_trade.date() == as_of:
      return self.price
    else:
      candidates = self.pricehistory_set.filter(as_of_date__lte = as_of.strftime('%Y-%m-%d')).order_by('-as_of_date')
      return (candidates[0].price if candidates.count() > 0 else 0)
  
  def previous_close_price(self):
    return self.price_as_of(self.last_trade - timedelta(days = 1))
  
class PriceHistory(models.Model):
  quote = models.ForeignKey('Quote')
  as_of_date = models.DateTimeField()
  price = models.FloatField()
  
  class Meta:
    db_table = 'price_history'
    unique_together = ( 'quote', 'as_of_date' )
    
  def __unicode__(self):
    return "%s @ %.2f on %s" % (self.quote.symbol, self.price, self.as_of_date.strftime('%Y-%m-%d'))
  