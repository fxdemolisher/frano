# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from bisect import insort
from datetime import datetime

from django.db import models

from main.models import Portfolio
from quotes.models import CASH_SYMBOL
from transactions.models import Transaction

#-------------\
#  CONSTANTS  |
#-------------/

QUANTITY_TOLERANCE = 0.000001

#----------\
#  MODELS  |
#----------/

class Position(models.Model):
  portfolio = models.ForeignKey(Portfolio)
  as_of_date = models.DateField()
  symbol = models.CharField(max_length = 10)
  quantity = models.FloatField()
  cost_price = models.FloatField()
  realized_pl = models.FloatField()
  
  class Meta:
    db_table = 'position'
    
  def __unicode__(self):
    return "%.2f of %s on %s @ %.2f" % (self.quantity, self.symbol, self.as_of_date.strftime('%m/%d/%Y'), self.cost_price)
    
class Lot(models.Model):
  position = models.ForeignKey(Position)
  as_of_date = models.DateField(null = True)
  quantity = models.FloatField()
  price = models.FloatField()
  sold_as_of_date = models.DateField(null = True)
  sold_quantity = models.FloatField()
  sold_price = models.FloatField()
  
  class Meta:
    db_table = 'lot'
    
  def __unicode__(self):
    return "Lot: Bought %.4f @ %.4f on %s, Sold %.4f @ %.4f on %s " % ( 
        self.quantity, 
        self.price, 
        self.as_of_date.strftime('%m/%d/%Y') if self.as_of_date != None else None,
        self.sold_quantity,
        self.sold_price,
        self.sold_as_of_date.strftime('%m/%d/%Y') if self.sold_as_of_date != None else None,
      )
    
  def __cmp__(self, other):
    my_date = min([ date for date in [self.as_of_date, self.sold_as_of_date] if date is not None ])
    other_date = min([ date for date in [other.as_of_date, other.sold_as_of_date] if date is not None ])
    if my_date == other_date:
      return 0
    else:
      return (-1 if my_date < other_date else 1)
  
#------------\
#  SERVICES  |
#------------/

def latest_positions(portfolio):
  """Retrieve a list of latest positions for the given portfolio."""
  
  latest_date = Position.objects.filter(portfolio__id__exact = portfolio.id).dates('as_of_date', 'day', order = 'DESC')[0:1]
  if latest_date.count() > 0:
    return Position.objects.filter(portfolio__id__exact = portfolio.id, as_of_date = latest_date[0]).order_by('symbol')
  else:
    return []

def decorate_position_with_prices(position, price, previous_price):
  """Decorate the given position with various pieces of data that require pricing (p/l, cost_basis, market_value)"""
  
  position.price = price
  position.previous_price = previous_price
  
  position.market_value = position.quantity * position.price
  position.cost_basis = position.quantity * position.cost_price
  position.previous_market_value = position.quantity * position.previous_price
  position.pl = (position.market_value - position.cost_basis)
  position.pl_percent = (((position.pl / position.cost_basis) * 100) if position.cost_basis != 0 else 0)
  position.day_pl = (position.market_value - position.previous_market_value)
  position.day_pl_percent = (((position.day_pl / position.previous_market_value) * 100) if position.previous_market_value != 0 else 0)
    
def refresh_positions(portfolio, transactions = None, force = False):
  """Refresh all positions in the given portfolio if needed or if the caller requests a forced refresh"""
  
  if transactions == None:
    transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id)
    
  positions = Position.objects.filter(portfolio__id__exact = portfolio.id)
  if (transactions.count() > 0 and positions.count() == 0) or force:
    positions.delete()
    _refresh_positions_from_transactions(transactions)

#-----------------\
#  VALUE OBJECTS  |
#-----------------/

class LotBuilder:
  def __init__(self):
    self.long_lots = []
    self.short_lots = []
    self.closed_lots = []
    
  def __repr__(self):
    return "Open (Long):\n %s\n\nOpen (Short):\n %s\n\nClosed:\n %s" % (self.long_lots, self.short_lots, self.closed_lots)
  
  def add_transaction(self, transaction):
    if transaction.type == 'BUY':
      quantity_to_buy = transaction.quantity
      while quantity_to_buy > 0 and len(self.short_lots) > 0:
        lot = self.short_lots.pop(0)
        if (quantity_to_buy - lot.sold_quantity) > -0.000001:
          lot.as_of_date = transaction.as_of_date
          lot.quantity = lot.sold_quantity
          lot.price = transaction.price
          
          insort(self.closed_lots, lot)          
          quantity_to_buy = quantity_to_buy - lot.quantity
          
        else:
          new_lot = Lot(as_of_date = transaction.as_of_date, 
              quantity = quantity_to_buy, 
              price = transaction.price, 
              sold_as_of_date = lot.sold_as_of_date, 
              sold_quantity = quantity_to_buy, 
              sold_price = lot.sold_price
            )
          
          lot.sold_quantity = lot.sold_quantity - quantity_to_buy
          self.short_lots.insert(0, lot)
          insort(self.closed_lots, new_lot)
          quantity_to_buy = 0
      
      if quantity_to_buy > 0.000001:
        self.long_lots.append(
            Lot(as_of_date = transaction.as_of_date, 
              quantity = quantity_to_buy, 
              price = transaction.price,
              sold_quantity = 0,
              sold_price = 0,
            )
          )
      
    elif transaction.type == 'SELL':
      quantity_to_sell = transaction.quantity
      while quantity_to_sell > 0 and len(self.long_lots) > 0:
        lot = self.long_lots.pop(0)
        if (quantity_to_sell - lot.quantity) > -0.000001:
          lot.sold_as_of_date = transaction.as_of_date
          lot.sold_quantity = lot.quantity
          lot.sold_price = transaction.price
          
          insort(self.closed_lots, lot)          
          quantity_to_sell = quantity_to_sell - lot.sold_quantity
          
        else:
          new_lot = Lot(as_of_date = lot.as_of_date, 
              quantity = quantity_to_sell, 
              price = lot.price, 
              sold_as_of_date = transaction.as_of_date, 
              sold_quantity = quantity_to_sell, 
              sold_price = transaction.price
            )
          lot.quantity = lot.quantity - quantity_to_sell
          self.long_lots.insert(0, lot)
          insort(self.closed_lots, new_lot)
          quantity_to_sell = 0
      
      if quantity_to_sell > 0.000001:
        self.short_lots.append(
            Lot(quantity = 0,
              price = 0,
              sold_as_of_date = transaction.as_of_date, 
              sold_quantity = quantity_to_sell, 
              sold_price = transaction.price
            )
          )
        
    return self
  
  def get_lots(self):
    out = []
    for lot in self.closed_lots:
      insort(out, _clone_lot(lot))
      
    for lot in self.long_lots:
      insort(out, _clone_lot(lot))

    for lot in self.short_lots:
      insort(out, _clone_lot(lot))
      
    return out

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _refresh_positions_from_transactions(transactions):
  if len(transactions) == 0:
    return
  
  # presort and bucket transactions
  transactions = sorted(transactions, key = (lambda transaction: transaction.id)) 
  transactions = sorted(transactions, key = (lambda transaction: transaction.as_of_date))
  dates = sorted(set([ t.as_of_date for t in transactions]))
  transactions_by_date = dict([(date, []) for date in dates])
  for transaction in transactions:
    transactions_by_date.get(transaction.as_of_date).append(transaction)
    
  # prepare trackers
  builder_by_symbol = { }
  cash = Position(portfolio = transactions[0].portfolio,
      as_of_date = datetime.now().date(),
      symbol = CASH_SYMBOL,
      quantity = 0,
      cost_price = 1.0,
      realized_pl = 0.0
    )
  
  # go through days and build positions
  lots = None
  positions = []
  for date in dates:
    current_transactions = transactions_by_date.get(date)
    
    # process transactions either through cash or lot builder
    for transaction in current_transactions:
      if transaction.type == 'DEPOSIT' or transaction.type == 'SELL':
        cash.quantity += transaction.total
                
      elif transaction.type == 'WITHDRAW' or transaction.type == 'BUY':
        cash.quantity -= transaction.total
        
      elif  transaction.type == 'ADJUST':
        cash.quantity += transaction.total
        cash.realized_pl += transaction.total
      
      if transaction.type == 'BUY' or transaction.type == 'SELL':
        builder = builder_by_symbol.get(transaction.symbol, None)
        if builder == None:
          builder = LotBuilder()
          builder_by_symbol[transaction.symbol] = builder
          
        builder.add_transaction(transaction)
      
    # add current cash to positions.
    positions.append(_clone_position(cash, date))
        
    # compose current lots into a position.
    lots = []
    for symbol, builder in builder_by_symbol.items():
      position = Position(portfolio = transactions[0].portfolio, 
          as_of_date = date,
          symbol = symbol, 
          quantity = 0.0, 
          cost_price = 0.0, 
          realized_pl = 0.0
        )
      
      for lot in builder.get_lots():
        lot.position = position
        lots.append(lot)
        
        quantity = (lot.quantity - lot.sold_quantity)
        if abs(quantity) < QUANTITY_TOLERANCE:
          quantity = 0.0
          
        if abs(quantity) > QUANTITY_TOLERANCE:
          total = (position.quantity * position.cost_price) + (quantity * lot.price)
          position.quantity += quantity
          position.cost_price = (total / position.quantity if quantity <> 0.0 else 0.0)
      
        if abs(lot.sold_quantity) > QUANTITY_TOLERANCE:
          position.realized_pl += (lot.sold_quantity * (lot.sold_price - lot.price))
          
      if abs(position.quantity) < QUANTITY_TOLERANCE:
        position.quantity = 0.0
        
      positions.append(position)
    
  # save positions
  for position in positions:
    position.save()
    
  # save latest lots
  for lot in lots:
    if abs(lot.quantity) < QUANTITY_TOLERANCE:
      lot.quantity = 0.0
    
    if abs(lot.sold_quantity) < QUANTITY_TOLERANCE:
      lot.sold_quantity = 0.0
    
    lot.position = lot.position # hack to reset position_id in lot
    lot.save()

def _clone_lot(lot):
  return Lot(as_of_date = lot.as_of_date,
      quantity = lot.quantity,
      price = lot.price,
      sold_as_of_date = lot.sold_as_of_date,
      sold_quantity = lot.sold_quantity,
      sold_price = lot.sold_price
    )

def _clone_position(position, new_as_of_date = None):
  out = Position()
  out.portfolio = position.portfolio
  out.as_of_date = (position.as_of_date if new_as_of_date == None else new_as_of_date)
  out.symbol = position.symbol
  out.quantity = position.quantity
  out.cost_price = position.cost_price
  out.realized_pl = position.realized_pl
  
  return out;