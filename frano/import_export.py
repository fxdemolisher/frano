import codecs, csv

from datetime import datetime
from decimal import Decimal

from models import Quote, Transaction

FRANO_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TYPE', 'SYMBOL', 'QUANTITY', 'PRICE', 'TOTAL' ]
GOOGLE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Name', 'Type', 'Date', 'Shares', 'Price', 'Cash value', 'Commission', 'Notes' ]

GOOGLE_TRANSACTION_TYPE_MAP = {
    'Buy' : 'BUY',
    'Sell' : 'SELL',
    'Deposit Cash' : 'DEPOSIT',
    'Withdraw Cash' : 'WITHDRAW',
  }

AMERITRADE_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TRANSACTION ID', 'DESCRIPTION', 'QUANTITY', 'SYMBOL', 'PRICE', 'COMMISSION', 'AMOUNT', 'NET CASH BALANCE', 'SALES FEE', 'SHORT-TERM RDM FEE', 'FUND REDEMPTION FEE', ' DEFERRED SALES CHARGE' ]

def transactions_as_csv(target, portfolio):
  writer = csv.writer(target)
  writer.writerow(FRANO_TRANSACTION_EXPORT_HEADER)
  
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  for transaction in transactions:
    writer.writerow([transaction.as_of_date.strftime('%m/%d/%Y'), transaction.type, transaction.symbol, transaction.quantity, transaction.price, transaction.total])

def parse_transactions(type, file):
  parsed = None
  if type == 'FRANO':
    reader = csv.reader(file)
    verify_transaction_file_header(reader, FRANO_TRANSACTION_EXPORT_HEADER)
    parsed = parse_frano_transactions(reader)
    
  elif type == 'GOOGLE':
    reader = csv.reader(codecs.iterdecode(file, 'utf_8_sig'))
    verify_transaction_file_header(reader, GOOGLE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_google_transactions(reader)
    
  elif type == 'AMERITRADE':
    reader = csv.reader(file)
    verify_transaction_file_header(reader, AMERITRADE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_ameritrade_transactions(reader)

  transactions = []
  for row in parsed:
    transaction = Transaction()
    transaction.as_of_date = row['date']
    transaction.type = row['type']
    transaction.symbol = row['symbol']
    transaction.quantity = row['quantity']
    transaction.price = row['price']
    transaction.total = row['total']
    
    transactions.append(transaction)
    
  return transactions

def verify_transaction_file_header(reader, required_header):
  header = reader.next()
  if len(header) != len(required_header):
    raise Exception('Header mismatch for transaction file')
  
  for i in range(len(required_header)):
    if header[i] != required_header[i]:
      raise Exception("Header mismatch at %d: %s <> %s" % (i, header[i], required_header[i]))
    
def parse_frano_transactions(reader):
  parsed = []
  for row in reader:
    parsed.append({
        'date' : datetime.strptime(row[0], '%m/%d/%Y'),
        'type' : row[1],
        'symbol' : row[2],
        'quantity' : Decimal(row[3]),
        'price' : Decimal(row[4]),
        'total' : Decimal(row[5]),
      });
      
  return parsed

def parse_google_transactions(reader):
  parsed = []
  for row in reader:
    type = GOOGLE_TRANSACTION_TYPE_MAP.get(row[2])
    if type == None:
      raise Exception("Unknown transaction type in google finance file: %s" % row[2])
    
    if type == 'DEPOSIT' or type == 'WITHDRAW':
      symbol = Quote.CASH_SYMBOL
      quantity = abs(Decimal(row[6]))
      price = Decimal('1.0')
      commission = Decimal('0')
      
    else:
      symbol = row[0]
      quantity = Decimal(row[4])
      price = Decimal(row[5])
      commission = Decimal(row[7])
    
    commission_multiplier = Decimal('1.0')
    if type == 'SELL':
      commission_multiplier = Decimal('-1.0')
        
    parsed.append({
        'date' : datetime.strptime(row[3], '%b %d, %Y'),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
      });
      
  return parsed

def parse_ameritrade_transactions(reader):
  parsed = []
  for row in reader:
    if len(row) != len(AMERITRADE_TRANSACTION_EXPORT_HEADER):
      continue
    
    date_field = row[0]
    quantity_field = row[3]
    symbol_field = row[4]
    price_field = row[5]
    commission_field = row[6]
    amount_field = row[7]
    net_cash_field = row[8]
    
    # skip no amount and no net cash transactions...for now
    if abs(float(amount_field)) < 0.01 or abs(float(net_cash_field)) < 0.01:
      continue
    
    # symbol and price in place, buy/sell transactions
    if symbol_field != '' and price_field != '':
      symbol = symbol_field
      type = ('SELL' if float(amount_field) >= 0 else 'BUY')
      quantity = Decimal(quantity_field)
      price = Decimal(price_field)
      commission = Decimal(commission_field)
      
    # symbol is there, but price is not, dividend
    elif symbol_field != '':
      symbol = symbol_field
      type = 'ADJUST'
      quantity = Decimal(amount_field)
      price = Decimal('1.0')
      commission = Decimal('0')
    
    # otherwise its a cash movement
    else:
      symbol = Quote.CASH_SYMBOL
      type = ('DEPOSIT' if float(amount_field) >= 0 else 'WITHDRAW')
      quantity = (abs(Decimal(amount_field)))
      price = Decimal('1.0')
      commission = Decimal('0')
    
    commission_multiplier = Decimal('1.0')
    if type == 'SELL':
      commission_multiplier = Decimal('-1.0')
    
    parsed.append({
        'date' : datetime.strptime(row[0], '%m/%d/%Y'),
        'type' : type,
        'symbol' : symbol,
        'quantity' : quantity,
        'price' : price,
        'total' : ((quantity * price) + (commission_multiplier * commission)),
      });
      
  return parsed