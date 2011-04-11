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
  cost_basis = models.FloatField()
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
  total = models.FloatField()
  sold_as_of_date = models.DateField(null = True)
  sold_quantity = models.FloatField()
  sold_price = models.FloatField()
  sold_total = models.FloatField()
  
  class Meta:
    db_table = 'lot'
    
  def __unicode__(self):
    return "Lot: Bought %.4f @ %.4f on %s (%.4f), Sold %.4f @ %.4f on %s (%.4f)" % ( 
        self.quantity, 
        self.price, 
        self.as_of_date.strftime('%m/%d/%Y') if self.as_of_date != None else None,
        self.total,
        self.sold_quantity,
        self.sold_price,
        self.sold_as_of_date.strftime('%m/%d/%Y') if self.sold_as_of_date != None else None,
        self.sold_total
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
  """Decorate the given position with various pieces of data that require pricing (p/l, market_value)"""
  
  position.price = price
  position.previous_price = previous_price
  
  position.market_value = position.quantity * position.price
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
    self.long_half_lots = []
    self.short_half_lots = []
    self.closed_lots = []
    
  def __repr__(self):
    return "Open (Long):\n %s\n\nOpen (Short):\n %s\n\nClosed:\n %s" % (self.long_lots, self.short_lots, self.closed_lots)
  
  def add_transaction(self, transaction):
    fees = transaction.total - (transaction.quantity * transaction.price)
    quantity = transaction.quantity
    poll = self.short_half_lots
    push = self.long_half_lots
    if transaction.type == 'SELL':
      push = poll
      poll = self.long_half_lots
      
    while quantity > 0 and len(poll) > 0:
      half_lot = poll.pop(0)
      if (quantity - half_lot.quantity) > -QUANTITY_TOLERANCE:
        partial_fees = fees * (half_lot.quantity / quantity)
        fees = fees - partial_fees
        quantity -= half_lot.quantity
        insort(self.closed_lots, half_lot.close(transaction.as_of_date, transaction.price, partial_fees))
         
      else:
        closed = half_lot.partial_close(transaction.as_of_date, quantity, transaction.price, fees)
        poll.insert(0, half_lot)
        insort(self.closed_lots, closed)
        quantity = 0
        fees = 0
    
    if quantity > QUANTITY_TOLERANCE:
      push.append(HalfLot(type = transaction.type,
          as_of_date = transaction.as_of_date,
          quantity = quantity,
          price = transaction.price,
          total = (quantity * transaction.price) + fees
        ))
    
    return self
  
  def get_lots(self):
    out = []
    for lot in self.closed_lots:
      insort(out, _clone_lot(lot))
      
    for half_lot in (self.long_half_lots + self.short_half_lots):
      insort(out, half_lot.to_lot(None, 0.0, 0.0, 0.0))
      
    return out

class HalfLot():
  def __init__(self, type, as_of_date, quantity, price, total):
    self.type = type
    self.as_of_date = as_of_date
    self.quantity = quantity
    self.price = price
    self.total = total
    
  def __repr__(self):
    return "%s: %.4f @ %.4f on %s (%.4f)" % (
        self.type,
        self.quantity,
        self.price,
        self.as_of_date.strftime('%m/%d/%Y'),
        self.total,
      )
    
  def close(self, as_of_date, price, fees):
    return self.to_lot(as_of_date, self.quantity, price, fees)
  
  def partial_close(self, as_of_date, quantity, price, fees):
    split_lot = HalfLot(type = self.type,
        as_of_date = self.as_of_date,
        quantity = quantity,
        price = self.price,
        total = None,
      )
    
    split_lot.total = self.total * (split_lot.quantity / self.quantity)
    self.total -= split_lot.total
    self.quantity -= quantity
    return split_lot.close(as_of_date, price, fees)
  
  def to_lot(self, as_of_date, quantity, price, fees):
    lot = None
    if self.type == 'BUY':
      lot = Lot(as_of_date = self.as_of_date,
          quantity = self.quantity,
          price = self.price,
          total = self.total,
          sold_as_of_date = as_of_date,
          sold_quantity = quantity,
          sold_price = price,
          sold_total = (quantity * price) + fees,
        )
    else:
      lot = Lot(as_of_date = as_of_date,
          quantity = quantity,
          price = price,
          total = (quantity * price) + fees,
          sold_as_of_date = self.as_of_date,
          sold_quantity= self.quantity,
          sold_price = self.price,
          sold_total = self.total,
        )
    
    return lot
      
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
      cost_basis = 0.0,
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
    days_cash = _clone_position(cash, date)
    days_cash.cost_basis = days_cash.quantity
    positions.append(days_cash)
        
    # compose current lots into a position.
    lots = []
    for symbol, builder in builder_by_symbol.items():
      position = Position(portfolio = transactions[0].portfolio, 
          as_of_date = date,
          symbol = symbol, 
          quantity = 0.0, 
          cost_price = 0.0, 
          cost_basis = 0.0,
          realized_pl = 0.0,
        )
      
      for lot in builder.get_lots():
        lot.position = position
        lots.append(lot)
        
        quantity = (lot.quantity - lot.sold_quantity)
        if abs(quantity) < QUANTITY_TOLERANCE:
          quantity = 0.0
          
        if abs(quantity) > QUANTITY_TOLERANCE:
          position.cost_basis += (lot.total - lot.sold_total)
          total = (position.quantity * position.cost_price) + (quantity * lot.price)
          position.quantity += quantity
          position.cost_price = (total / position.quantity if quantity <> 0.0 else 0.0)
          
        else:
          position.realized_pl += lot.sold_total - lot.total
          
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
      total = lot.total,
      sold_as_of_date = lot.sold_as_of_date,
      sold_quantity = lot.sold_quantity,
      sold_price = lot.sold_price,
      sold_total = lot.sold_total
    )

def _clone_position(position, new_as_of_date = None):
  out = Position()
  out.portfolio = position.portfolio
  out.as_of_date = (position.as_of_date if new_as_of_date == None else new_as_of_date)
  out.symbol = position.symbol
  out.quantity = position.quantity
  out.cost_price = position.cost_price
  out.realized_pl = position.realized_pl
  
  return out