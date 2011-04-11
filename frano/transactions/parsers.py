# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime
from exceptions import Exception

from quotes.models import CASH_SYMBOL
from quotes.models import quote_by_symbol
from quotes.models import price_as_of

#-------------\
#  CONSTANTS  |
#-------------/

FRANO_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TYPE', 'SYMBOL', 'QUANTITY', 'PRICE', 'TOTAL', 'LINKED_SYMBOL' ]
GOOGLE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Name', 'Type', 'Date', 'Shares', 'Price', 'Cash value', 'Commission', 'Notes' ]
AMERITRADE_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TRANSACTION ID', 'DESCRIPTION', 'QUANTITY', 'SYMBOL', 'PRICE', 'COMMISSION', 'AMOUNT', 'NET CASH BALANCE', 'SALES FEE', 'SHORT-TERM RDM FEE', 'FUND REDEMPTION FEE', ' DEFERRED SALES CHARGE' ]
ZECCO_TRANSACTION_EXPORT_HEADER = [ 'TradeDate', 'AccountTypeDescription', 'TransactionType', 'Symbol', 'Cusip', 'ActivityDescription', 'SecuritySubDescription', 'Quantity', 'Price', 'Currency', 'PrincipalAmount', 'NetAmount', 'TradeNumber' ]
SCOTTRADE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Quantity', 'Price', 'ActionNameUS', 'TradeDate', 'SettledDate', 'Interest', 'Amount', 'Commission', 'Fees', 'CUSIP', 'Description', 'ActionId', 'TradeNumber', 'RecordType', 'TaxLotNumber' ]
CHARLES_TRANSACTION_EXPORT_HEADER = [ 'Date', 'Action', 'Quantity', 'Symbol', 'Description', 'Price', 'Amount', 'Fees & Comm' ]
FIDELITY_TRANSACTION_EXPORT_HEADER = [ 'Trade Date', 'Action', 'Symbol', 'Security Description', 'Security Type', 'Quantity', 'Price ($)', 'Commission ($)', 'Fees ($)', 'Accrued Interest ($)', 'Amount ($)', 'Settlement Date' ]
MERCER_401_TRANSACTION_EXPORT_HEADER = [ 'Date', 'Source', 'Transaction', 'Ticker', 'Investment', 'Amount', 'Price', 'Shares/Units' ]

GOOGLE_TRANSACTION_TYPE_MAP = {
    'Buy' : 'BUY',
    'Sell' : 'SELL',
    'Deposit Cash' : 'DEPOSIT',
    'Withdraw Cash' : 'WITHDRAW',
  }

#---------------------\
#  EXPOSED FUNCTIONS  |
#---------------------/

def parse_frano_transactions(reader):
  parsed = []
  for row in reader:
    parsed.append({
        'date' : datetime.strptime(row[0], '%m/%d/%Y').date(),
        'type' : row[1],
        'symbol' : row[2],
        'quantity' : float(row[3]),
        'price' : float(row[4]),
        'total' : float(row[5]),
        'linked_symbol' : (row[6] if row[6] != '' else None),
      })
      
  return parsed

def parse_google_transactions(reader):
  parsed = []
  for row in reader:
    type = GOOGLE_TRANSACTION_TYPE_MAP.get(row[2])
    if type == None:
      raise Exception("Unknown transaction type in google finance file: %s" % row[2])
    
    if type == 'DEPOSIT' or type == 'WITHDRAW':
      symbol = CASH_SYMBOL
      quantity = abs(float(row[6]))
      price = 1.0
      commission = 0.0
      
    else:
      symbol = row[0]
      quantity = float(row[4])
      price = float(row[5])
      commission = float(row[7])
    
    commission_multiplier = 1.0
    if type == 'SELL':
      commission_multiplier = -1.0
        
    parsed.append({
        'date' : datetime.strptime(row[3], '%b %d, %Y').date(),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
      })
      
  return parsed

def parse_ameritrade_transactions(reader):
  parsed = []
  for row in reader:
    if len(row) != len(AMERITRADE_TRANSACTION_EXPORT_HEADER):
      continue
    
    date_field = row[0]
    description_field = row[2]
    quantity_field = row[3]
    symbol_field = row[4]
    price_field = row[5]
    commission_field = row[6]
    amount_field = row[7]
    net_cash_field = row[8]
    linked_symbol = None
    
    # money market interest is a special case since it doesn't have a normal amount
    if description_field.startswith('MONEY MARKET INTEREST'):
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(quantity_field)
      price = 1.0
      commission = 0.0
    
    # skip no amount and no net cash transactions...for now
    elif abs(float(amount_field)) < 0.01 or abs(float(net_cash_field)) < 0.01:
      continue
    
    # skip money market purchases and redemptions\
    elif description_field.startswith('MONEY MARKET PURCHASE') or description_field.startswith('MONEY MARKET REDEMPTION'):
      continue
    
    # symbol and price in place, buy/sell transactions
    elif symbol_field != '' and price_field != '':
      symbol = symbol_field
      type = ('SELL' if float(amount_field) >= 0 else 'BUY')
      quantity = float(quantity_field)
      price = float(price_field)
      commission = (float(commission_field) if len(commission_field) > 0 else 0.0)
      
    # symbol is there, but price is not, dividend
    elif symbol_field != '' or description_field.startswith('MONEY MARKET INTEREST'):
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = symbol_field
    
    # otherwise its a cash movement
    else:
      symbol = CASH_SYMBOL
      type = ('DEPOSIT' if float(amount_field) >= 0 else 'WITHDRAW')
      quantity = (abs(float(amount_field)))
      price = 1.0
      commission = 0.0
    
    commission_multiplier = 1.0
    if type == 'SELL':
      commission_multiplier = -1.0
    
    parsed.append({
        'date' : datetime.strptime(date_field, '%m/%d/%Y').date(),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
        'linked_symbol': linked_symbol,
      })
      
  return parsed

def parse_zecco_transactions(reader):
  split_map = { }
  
  parsed = []
  for row in reader:
    as_of_date = datetime.strptime(row[0], '%m/%d/%Y').date()
    account_type = row[1]
    transaction_type = row[2]
    description_field = row[5]
    symbol_field = row[3]
    quantity_field = row[7]
    price_field = row[8]
    net_amount_field = row[11]
    linked_symbol = None
    
    # skip credit sweeps
    if description_field.find('Credit Sweep') >= 0:
      continue
    
    # deposits/withdrawals happen on the cash journal
    elif transaction_type == 'Cash Journal' and (
        description_field.startswith('ACH DEPOSIT') or description_field.startswith('ACH DISBURSEMENT') or 
        description_field.startswith('W/T FRM CUST') or description_field.startswith('W/T TO CUST')
      ):
      
      symbol = CASH_SYMBOL
      type = ('DEPOSIT' if float(net_amount_field) >= 0 else 'WITHDRAW')
      quantity = (abs(float(net_amount_field)))
      price = 1.0
      commission = 0.0
    
    # buys/sells are marked by their transaction types
    elif transaction_type == 'B' or transaction_type == 'S':
      symbol = symbol_field
      type = ('SELL' if transaction_type == 'S' else 'BUY')
      quantity = abs(float(quantity_field))
      price = float(price_field)
      commission = abs(float(net_amount_field)) - (quantity * price)
      
    # everything else on the margin account or cash is an adjustment
    elif transaction_type in ['Interest Paid', 'Qualified Dividend', 'Short Term Capital Gain', 'Long Term Capital Gain']:
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(net_amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = symbol_field
    
      
    # splits are processed after all the parsing is done, just record and skip them
    elif transaction_type in [ 'Security Journal' ] and description_field.endswith('SPLIT'):
      _record_split(split_map, as_of_date, symbol_field, float(quantity_field))
      continue
      
    # otherwise just skip it for now
    else:
      continue
      
    commission_multiplier = 1.0
    if type == 'SELL':
      commission_multiplier = -1.0
    
    parsed.append({
        'date' : as_of_date,
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
        'linked_symbol': linked_symbol,
      })
  
  splits = [ split for sub_list in split_map.values() for split in sub_list ]
  _apply_splits(parsed, splits)
    
  return parsed

def parse_scottrade_transactions(reader):
  parsed = []
  for row in reader:
    action_field = row[3]
    symbol_field = row[0]
    quantity_field = row[1]
    price_field = row[2]
    date_field = row[4]
    amount_field = row[7]
    commission_field = row[8]
    linked_symbol = None
    
    # deposits and withdrawals
    if action_field == 'IRA Receipt' or action_field == 'Journal':
      symbol = CASH_SYMBOL
      type = ('DEPOSIT' if float(amount_field) >= 0 else 'WITHDRAW')
      quantity = abs(float(amount_field))
      price = 1.0
      commission = 0.0
    
    # buys and sells
    elif action_field == 'Buy' or action_field == 'Sell':
      symbol = symbol_field
      type = ('SELL' if action_field == 'Sell' else 'BUY')
      quantity = abs(float(quantity_field))
      price = float(price_field)
      commission = abs(float(commission_field))
      
    # incoming transfers mimic a deposit and a buy
    elif action_field == 'Transfer In':
      quantity = float(quantity_field)
      price = float(price_field) / quantity
      parsed.append({
        'date' : datetime.strptime(date_field, '%m/%d/%Y').date(),
        'type' : 'DEPOSIT',
        'symbol' : CASH_SYMBOL,
        'quantity' : (price * quantity),
        'price' : 1.0,
        'total' : (price * quantity),
      })
      
      symbol = symbol_field
      type = 'BUY'
      commission = 0.0
    
    # everything else is an adjustment
    else:
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = (symbol_field if symbol_field != 'Cash' else None)
      
    commission_multiplier = 1.0
    if type == 'SELL':
      commission_multiplier = -1.0
      
    parsed.append({
        'date' : datetime.strptime(date_field, '%m/%d/%Y').date(),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
        'linked_symbol': linked_symbol,
      })
      
  return parsed

def parse_charles_transactions(reader):
  parsed = []
  for row in reader:
    date_field = row[0][:10]
    action_field = row[1].strip(' ')
    quantity_field = row[2].strip(' ')
    symbol_field = row[3].strip(' ')
    price_field = row[5].replace('$', '').strip(' ')
    amount_field = row[6].replace('$', '').strip(' ')
    commission_field = row[7].replace('$', '').strip(' ')
    linked_symbol = None
    
    # deposits and withdrawals have no symbols or prices
    if symbol_field == '' and price_field == '':
      symbol = CASH_SYMBOL
      type = ('DEPOSIT' if float(amount_field) >= 0 else 'WITHDRAW')
      quantity = abs(float(amount_field))
      price = 1.0
      commission = 0.0
    
    # buys and sells
    elif action_field == 'Buy' or action_field == 'Sell':
      symbol = symbol_field
      type = ('SELL' if action_field == 'Sell' else 'BUY')
      quantity = float(quantity_field)
      price = float(price_field)
      commission = (float(commission_field) if commission_field != '' else 0.0)
      
    # transfers have a symbol and quantity, and little else
    elif symbol_field != '' and quantity_field != '' and amount_field == '':
      as_of_date = datetime.strptime(date_field, '%m/%d/%Y')
      symbol = symbol_field
      quantity = float(quantity_field)
      price = price_as_of(quote_by_symbol(symbol), as_of_date)
                          
      parsed.append({
        'date' : as_of_date.date(),
        'type' : 'DEPOSIT',
        'symbol' : CASH_SYMBOL,
        'quantity' : (price * quantity),
        'price' : 1.0,
        'total' : (price * quantity),
      })
      
      type = 'BUY'
      commission = 0.0
      
    # everything else is an adjustment
    else:
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = symbol_field
      
    commission_multiplier = 1.0
    if type == 'SELL':
      commission_multiplier = -1.0
      
    parsed.append({
        'date' : datetime.strptime(date_field, '%m/%d/%Y').date(),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
        'linked_symbol': linked_symbol,
      })
      
  return parsed

def parse_fidelity_transactions(reader):
  parsed = []
  for row in reader:
    if len(row) < 11:
      continue
    
    date_field = row[0].strip()
    action_field = row[1].strip()
    symbol_field = row[2].strip()
    symbol_description_field = row[3].strip()
    quantity_field = row[5].strip()
    price_field = row[6].strip()
    amount_field = row[10].strip()
    
    linked_symbol = None
    
    # deposits and withdrawals have no symbols or prices
    if symbol_field == '' and price_field == '':
      symbol = CASH_SYMBOL
      type = ('DEPOSIT' if float(amount_field) >= 0 else 'WITHDRAW')
      quantity = abs(float(amount_field))
      price = 1.0
      total = quantity
    
    # buys and sells
    elif action_field.startswith('YOU BOUGHT') or action_field.startswith('YOU SOLD') or (symbol_description_field != 'CASH' and (action_field in [ 'PURCHASE INTO CORE ACCOUNT', 'REDEMPTION FROM CORE ACCOUNT', 'REINVESTMENT' ])):
      symbol = symbol_field
      type = ('SELL' if (action_field.startswith('YOU SOLD') or action_field == 'REDEMPTION FROM CORE ACCOUNT') else 'BUY')
      quantity = abs(float(quantity_field))
      price = float(price_field)
      total = abs(float(amount_field))
      
    # certain known actions are adjustments
    elif action_field in [ 'SHORT-TERM CAP GAIN', 'LONG-TERM CAP GAIN', 'DIVIDEND RECEIVED', 'INTEREST EARNED' ]:
      symbol = CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(amount_field)
      price = 1.0
      total = abs(float(amount_field))
      linked_symbol = (symbol_field if symbol_description_field != 'CASH' else None)
      
    # ignore everything else
    else:
      continue
      
    parsed.append({
        'date' : datetime.strptime(date_field, '%m/%d/%Y').date(),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : total,
        'linked_symbol': linked_symbol,
      })
      
  return parsed

def parse_mercer_401_transactions(reader):
  parsed = []
  for row in reader:
    if len(row) != 8 or row[0] == 'Total':
      continue
    
    as_of_date = datetime.strptime(row[0].strip(' '), '%m/%d/%Y').date()
    action = row[2].strip(' ')
    symbol = row[3].strip(' ')
    amount_field = row[5].replace('$', '').replace(',', '').strip(' ')
    price = float(row[6].replace('$', '').replace(',', '').strip(' '))
    quantity = float(row[7].replace('$', '').replace(',', '').strip(' '))
    linked_symbol = None
    
    if amount_field[:1] == '(' and amount_field[-1:] == ')':
      amount = 0 - float(amount_field[1:-1])
    else:
      amount = float(amount_field)
    
    # deposits are contributions or conversions and are treated like transfers
    if action in [ 'CONTRIBUTIONS', 'CONVERSION' ]:
      parsed.append({
        'date' : as_of_date,
        'type' : 'DEPOSIT',
        'symbol' : CASH_SYMBOL,
        'quantity' : amount,
        'price' : 1.0,
        'total' : amount,
      })
      
      type = 'BUY'
    
    # buys and sells are transfer in/out actions
    elif action in [ 'TRANSFER OUT', 'TRANSFER IN' ] and symbol != None and symbol != '':
      type = ('SELL' if action == 'TRANSFER OUT' else 'BUY')
      quantity = abs(quantity)
      amount = abs(amount)
      
    # dividends are adjustments and reinvestments. fees are sells and negative adjustments.
    elif action in [ 'DIVIDEND', 'FEE' ]:
      parsed.append({
        'date' : as_of_date,
        'type' : 'ADJUST',
        'symbol' : CASH_SYMBOL,
        'quantity' : amount,
        'price' : 1.0,
        'total' : amount,
        'linked_symbol' : symbol,
      })
      
      type = ('BUY' if action == 'DIVIDEND' else 'SELL')
      quantity = abs(quantity)
      amount = abs(amount)
      
    else:
      continue
      
    parsed.append({
        'date' : as_of_date,
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : amount,
        'linked_symbol' : linked_symbol,
      })
      
  return parsed

#-----------------\
#  VALUE OBJECTS  |
#-----------------/

class Split:
  def __init__(self, as_of_date, symbol, quantity):
    self.as_of_date = as_of_date
    
    if quantity > 0:
      self.to_symbol = symbol
      self.to_quantity = quantity
      
    else:
      self.from_symbol = symbol
      self.from_quantity = abs(quantity)

  def __repr__(self):
    return "Split: %.4f of %s to %.4f of %s" % (self.from_quantity, self.from_symbol, self.to_quantity, self.to_symbol)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _record_split(split_map, as_of_date, symbol, quantity):
  splits_on_date = split_map.get(as_of_date, None)
  if splits_on_date == None:
    splits_on_date = [ Split(as_of_date, symbol, quantity) ]
    split_map[as_of_date] = splits_on_date
  
  else:
    found = False
    for split in splits_on_date:
      if quantity > 0 and split.from_symbol != None and split.from_symbol.startswith(symbol):
        split.to_symbol = symbol
        split.to_quantity = quantity
        found = True
        break
        
      elif split.to_symbol != None and symbol.startswith(split.to_symbol):
        split.from_symbol = symbol
        split.from_quantity = abs(quantity)
        found = True
        break
        
    if not found:
      splits_on_date.append(Split(as_of_date, symbol, quantity))

def _apply_splits(parsed, splits):
  """
    split processing - adjust price and quantity of all pre-split transactions
    the double loop is intentional since a stock can split more than once, start processing by earliest date
  """
  
  for split in sorted(splits, key = (lambda split: split.as_of_date)):
    for transaction in parsed:
      if transaction.get('symbol') == split.from_symbol and transaction.get('date') <= split.as_of_date:
        factor = split.to_quantity / split.from_quantity
        transaction['symbol'] = split.to_symbol
        transaction['quantity'] = transaction.get('quantity') * factor
        transaction['price'] = transaction.get('price') / factor

