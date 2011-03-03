# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

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
  
#------------\
#  SERVICES  |
#------------/

def clone_tax_lot(tax_lot):
  """Return a copy of the given tax lot."""
  
  return TaxLot(as_of_date = tax_lot.as_of_date,
      quantity = tax_lot.quantity,
      cost_price = tax_lot.cost_price,
      sold_quantity = tax_lot.sold_quantity,
      sold_price = tax_lot.sold_price
    )

def clone_position(position, new_as_of_date = None):
  """Returns a copy of the given position, optionally overriding the as_of_date."""
  
  out = Position()
  out.portfolio = position.portfolio
  out.as_of_date = (position.as_of_date if new_as_of_date == None else new_as_of_date)
  out.symbol = position.symbol
  out.quantity = position.quantity
  out.cost_price = position.cost_price
  out.realized_pl = position.realized_pl
  
  return out;
  
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
    
  # get the tax lots
  lot_sets = {}
  last_lot_set = {}
  cash = {}
  last_cash = Position(portfolio = transactions[0].portfolio,
      as_of_date = datetime.now().date(),
      symbol = CASH_SYMBOL,
      quantity = 0,
      cost_price = 1.0,
      realized_pl = 0.0
    )
  
  for date in dates:
    current_transactions = transactions_by_date.get(date)
    current_lot_set = dict([ (symbol, [clone_tax_lot(lot) for lot in lots]) for symbol, lots in last_lot_set.items()])
    current_cash = clone_position(last_cash, date)
    
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
          _buy_in_lots(lots, transaction.as_of_date, transaction.quantity, transaction.price)
                      
        elif transaction.type == 'SELL':
          _sell_in_lots(lots, transaction.as_of_date, transaction.quantity, transaction.price)
    
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
          
      if abs(position.quantity) < QUANTITY_TOLERANCE:
        position.quantity = 0.0
      
      position.save()
      for lot in lots:
        lot.position = position
        
        if abs(lot.quantity) < QUANTITY_TOLERANCE:
          lot.quantity = 0.0
        
        if abs(lot.sold_quantity) < QUANTITY_TOLERANCE:
          lot.sold_quantity = 0.0
        
        lot.save()
        
def _buy_in_lots(lots, date, quantity, price):
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
  
def _sell_in_lots(lots, date, quantity, price):
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
    