# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

import codecs
import csv

from exceptions import Exception 

from django.db import models

from parsers import parse_frano_transactions
from parsers import parse_google_transactions
from parsers import parse_ameritrade_transactions
from parsers import parse_zecco_transactions
from parsers import parse_scottrade_transactions
from parsers import parse_charles_transactions
from parsers import parse_fidelity_transactions
from parsers import parse_mercer_401_transactions
from main.models import Portfolio

#-------------\
#  CONSTANTS  |
#-------------/

FRANO_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TYPE', 'SYMBOL', 'QUANTITY', 'PRICE', 'TOTAL', 'LINKED_SYMBOL' ]
GOOGLE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Name', 'Type', 'Date', 'Shares', 'Price', 'Cash value', 'Commission', 'Notes' ]
AMERITRADE_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TRANSACTION ID', 'DESCRIPTION', 'QUANTITY', 'SYMBOL', 'PRICE', 'COMMISSION', 'AMOUNT', 'NET CASH BALANCE', 'SALES FEE', 'SHORT-TERM RDM FEE', 'FUND REDEMPTION FEE', ' DEFERRED SALES CHARGE' ]
ZECCO_TRANSACTION_EXPORT_HEADER = [ 'TradeDate', 'AccountTypeDescription', 'TransactionType', 'Symbol', 'Cusip', 'ActivityDescription', 'SecuritySubDescription', 'Quantity', 'Price', 'Currency', 'PrincipalAmount', 'NetAmount', 'TradeNumber' ]
SCOTTRADE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Quantity', 'Price', 'ActionNameUS', 'TradeDate', 'SettledDate', 'Interest', 'Amount', 'Commission', 'Fees', 'CUSIP', 'Description', 'ActionId', 'TradeNumber', 'RecordType' ]
CHARLES_TRANSACTION_EXPORT_HEADER = [ 'Date', 'Action', 'Quantity', 'Symbol', 'Description', 'Price', 'Amount', 'Fees & Comm' ]
FIDELITY_TRANSACTION_EXPORT_HEADER = [ 'Trade Date', 'Action', 'Symbol', 'Security Description', 'Security Type', 'Quantity', 'Price ($)', 'Commission ($)', 'Fees ($)', 'Accrued Interest ($)', 'Amount ($)', 'Settlement Date' ]
MERCER_401_TRANSACTION_EXPORT_HEADER = [ 'Date', 'Source', 'Transaction', 'Ticker', 'Investment', 'Amount', 'Price', 'Shares/Units' ]

HEADER_TO_IMPORT_TYPE_MAP = {
    ",".join(FRANO_TRANSACTION_EXPORT_HEADER) : 'FRANO',
    ("\xef\xbb\xbf" + ",".join(GOOGLE_TRANSACTION_EXPORT_HEADER)) : 'GOOGLE',
    ",".join(AMERITRADE_TRANSACTION_EXPORT_HEADER) : 'AMERITRADE',
    ",".join(ZECCO_TRANSACTION_EXPORT_HEADER) : 'ZECCO',
    ",".join(SCOTTRADE_TRANSACTION_EXPORT_HEADER) : 'SCOTTRADE',
    ",".join([ ('"%s"' % v) for v in CHARLES_TRANSACTION_EXPORT_HEADER]) : 'CHARLES',
    ",".join(FIDELITY_TRANSACTION_EXPORT_HEADER) : 'FIDELITY',
    ",".join(MERCER_401_TRANSACTION_EXPORT_HEADER) : 'MERCER_401',
  }

TRANSACTION_TYPES = (
    ('BUY', 'Buy'),
    ('SELL', 'Sell'),
    ('DEPOSIT', 'Deposit'),
    ('WITHDRAW', 'Withdraw'),
    ('ADJUST', 'Adjust'),
  )

#----------\
#  MODELS  |
#----------/

class Transaction(models.Model):
  portfolio = models.ForeignKey(Portfolio)
  type = models.CharField(max_length = 10, choices = TRANSACTION_TYPES)
  as_of_date = models.DateField()
  symbol = models.CharField(max_length = 5)
  quantity = models.FloatField()
  price = models.FloatField()
  total = models.FloatField()
  linked_symbol = models.CharField(max_length = 5, null = True)
  
  class Meta:
    db_table = 'transaction'
    ordering = [ '-as_of_date', 'symbol' ]
  
  def __unicode__(self):
    return "%.2f-%s @ %.2f on %s" % (self.quantity, self.symbol, self.price, self.as_of_date.strftime('%m/%d/%Y'))
  
#------------\
#  SERVICES  |
#------------/

def clone_transaction(transaction, new_portfolio = None):
  """Return a copy of the given transaction, optionally overriding which portfolio the transaction belongs to."""
  
  out = Transaction()
  out.portfolio = (new_portfolio if new_portfolio != None else transaction.portfolio)
  out.type = transaction.type
  out.as_of_date = transaction.as_of_date
  out.symbol = transaction.symbol
  out.quantity = transaction.quantity
  out.price = transaction.price
  out.total = transaction.total
  out.linked_symbol = transaction.linked_symbol
  
  return out

def transactions_as_csv(target, portfolio):
  writer = csv.writer(target)
  writer.writerow(FRANO_TRANSACTION_EXPORT_HEADER)
  
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  for transaction in transactions:
    writer.writerow([transaction.as_of_date.strftime('%m/%d/%Y'), transaction.type, transaction.symbol, transaction.quantity, transaction.price, transaction.total, transaction.linked_symbol])

def parse_transactions(type, file):
  parsed = None
  if type == 'FRANO':
    reader = csv.reader(file)
    _verify_transaction_file_header(reader, FRANO_TRANSACTION_EXPORT_HEADER)
    parsed = parse_frano_transactions(reader)
    
  elif type == 'GOOGLE':
    reader = csv.reader(codecs.iterdecode(file, 'utf_8_sig'))
    _verify_transaction_file_header(reader, GOOGLE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_google_transactions(reader)
    
  elif type == 'AMERITRADE':
    reader = csv.reader(file)
    _verify_transaction_file_header(reader, AMERITRADE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_ameritrade_transactions(reader, len(AMERITRADE_TRANSACTION_EXPORT_HEADER))
    
  elif type == 'ZECCO':
    reader = csv.reader(file)
    _verify_transaction_file_header(reader, ZECCO_TRANSACTION_EXPORT_HEADER)
    parsed = parse_zecco_transactions(reader)

  elif type == 'SCOTTRADE':
    reader = csv.reader(_null_byte_line_filter(file))
    _verify_transaction_file_header(reader, SCOTTRADE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_scottrade_transactions(reader)
    
  elif type == 'CHARLES':
    reader = csv.reader(_null_byte_line_filter(file))
    reader.next() # skip header line
    _verify_transaction_file_header(reader, CHARLES_TRANSACTION_EXPORT_HEADER)
    parsed = parse_charles_transactions(reader)
    
  elif type == 'FIDELITY':
    reader = csv.reader(file)
    
    # fidelity leaves three blank lines on top of the file...go figure
    for x in range(3):
      reader.next()
      
    _verify_transaction_file_header(reader, FIDELITY_TRANSACTION_EXPORT_HEADER)
    parsed = parse_fidelity_transactions(reader)
    
  elif type == 'MERCER_401':
    reader = csv.reader(file)
    _verify_transaction_file_header(reader, MERCER_401_TRANSACTION_EXPORT_HEADER)
    parsed = parse_mercer_401_transactions(reader)

  transactions = []
  for row in parsed:
    transaction = Transaction()
    transaction.as_of_date = row['date']
    transaction.type = row['type']
    transaction.symbol = row['symbol'].upper()
    transaction.quantity = row['quantity']
    transaction.price = row['price']
    transaction.total = row['total']
    transaction.linked_symbol = row.get('linked_symbol', None)
    
    transactions.append(transaction)
    
  return transactions

def detect_transaction_file_type(file):
  first_line = None
  for line in file:
    first_line = line
    
    if first_line != None and not first_line.startswith('"Transactions  for account') and len(first_line.strip()) != 0:
      break
  
  return HEADER_TO_IMPORT_TYPE_MAP.get(line.strip(), None)

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _null_byte_line_filter(stream):
  for line in stream:
    yield line.replace('\x00', '')

def _verify_transaction_file_header(reader, required_header):
  header = reader.next()
  if len(header) != len(required_header):
    raise Exception('Header mismatch for transaction file')
  
  for i in range(len(required_header)):
    if header[i] != required_header[i]:
      raise Exception("Header mismatch at %d: %s <> %s" % (i, header[i], required_header[i]))
    