import codecs, csv

from datetime import datetime

from models import Quote, Transaction

#------------\
#  CONSTANTS |
#------------/

FRANO_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TYPE', 'SYMBOL', 'QUANTITY', 'PRICE', 'TOTAL', 'LINKED_SYMBOL' ]
GOOGLE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Name', 'Type', 'Date', 'Shares', 'Price', 'Cash value', 'Commission', 'Notes' ]
AMERITRADE_TRANSACTION_EXPORT_HEADER = [ 'DATE', 'TRANSACTION ID', 'DESCRIPTION', 'QUANTITY', 'SYMBOL', 'PRICE', 'COMMISSION', 'AMOUNT', 'NET CASH BALANCE', 'SALES FEE', 'SHORT-TERM RDM FEE', 'FUND REDEMPTION FEE', ' DEFERRED SALES CHARGE' ]
ZECCO_TRANSACTION_EXPORT_HEADER = [ 'TradeDate', 'AccountTypeDescription', 'TransactionType', 'Symbol', 'Cusip', 'ActivityDescription', 'SecuritySubDescription', 'Quantity', 'Price', 'Currency', 'PrincipalAmount', 'NetAmount', 'TradeNumber' ]
SCOTTRADE_TRANSACTION_EXPORT_HEADER = [ 'Symbol', 'Quantity', 'Price', 'ActionNameUS', 'TradeDate', 'SettledDate', 'Interest', 'Amount', 'Commission', 'Fees', 'CUSIP', 'Description', 'ActionId', 'TradeNumber', 'RecordType' ]
CHARLES_TRANSACTION_EXPORT_HEADER = [ 'Date', 'Action', 'Quantity', 'Symbol', 'Description', 'Price', 'Amount', 'Fees & Comm' ]

GOOGLE_TRANSACTION_TYPE_MAP = {
    'Buy' : 'BUY',
    'Sell' : 'SELL',
    'Deposit Cash' : 'DEPOSIT',
    'Withdraw Cash' : 'WITHDRAW',
  }

HEADER_TO_IMPORT_TYPE_MAP = {
    ",".join(FRANO_TRANSACTION_EXPORT_HEADER) : 'FRANO',
    ("\xef\xbb\xbf" + ",".join(GOOGLE_TRANSACTION_EXPORT_HEADER)) : 'GOOGLE',
    ",".join(AMERITRADE_TRANSACTION_EXPORT_HEADER) : 'AMERITRADE',
    ",".join(ZECCO_TRANSACTION_EXPORT_HEADER) : 'ZECCO',
    ",".join(SCOTTRADE_TRANSACTION_EXPORT_HEADER) : 'SCOTTRADE',
    ",".join([ ('"%s"' % v) for v in CHARLES_TRANSACTION_EXPORT_HEADER]) : 'CHARLES',
  }

#------------------\
#  MAIN FUNCTIONS  |
#------------------/

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
    
  elif type == 'ZECCO':
    reader = csv.reader(file)
    verify_transaction_file_header(reader, ZECCO_TRANSACTION_EXPORT_HEADER)
    parsed = parse_zecco_transactions(reader)

  elif type == 'SCOTTRADE':
    reader = csv.reader(null_byte_line_filter(file))
    verify_transaction_file_header(reader, SCOTTRADE_TRANSACTION_EXPORT_HEADER)
    parsed = parse_scottrade_transactions(reader)
    
  elif type == 'CHARLES':
    reader = csv.reader(null_byte_line_filter(file))
    reader.next() # skip header line
    verify_transaction_file_header(reader, CHARLES_TRANSACTION_EXPORT_HEADER)
    parsed = parse_charles_transactions(reader)

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
    
    if first_line != None and not first_line.startswith('"Transactions  for account'):
      break
  
  return HEADER_TO_IMPORT_TYPE_MAP.get(line.strip(), None)
  
#----------------------\
#  PER SOURCE PARSERS  |
#----------------------/
    
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
    linked_symbol = None
    
    # skip no amount and no net cash transactions...for now
    if abs(float(amount_field)) < 0.01 or abs(float(net_cash_field)) < 0.01:
      continue
    
    # symbol and price in place, buy/sell transactions
    if symbol_field != '' and price_field != '':
      symbol = symbol_field
      type = ('SELL' if float(amount_field) >= 0 else 'BUY')
      quantity = float(quantity_field)
      price = float(price_field)
      commission = float(commission_field)
      
    # symbol is there, but price is not, dividend
    elif symbol_field != '':
      symbol = Quote.CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = symbol_field
    
    # otherwise its a cash movement
    else:
      symbol = Quote.CASH_SYMBOL
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
      });
      
  return parsed

def parse_zecco_transactions(reader):
  parsed = []
  for row in reader:
    account_type = row[1]
    transaction_type = row[2]
    description_field = row[5]
    date_field = row[0]
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
      
      symbol = Quote.CASH_SYMBOL
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
      symbol = Quote.CASH_SYMBOL
      type = 'ADJUST'
      quantity = float(net_amount_field)
      price = 1.0
      commission = 0.0
      linked_symbol = symbol_field
      
    # otherwise just skip it for now
    else:
      continue
      
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
      });
      
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
      symbol = Quote.CASH_SYMBOL
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
        'symbol' : Quote.CASH_SYMBOL,
        'quantity' : (price * quantity),
        'price' : 1.0,
        'total' : (price * quantity),
      });
      
      symbol = symbol_field
      type = 'BUY'
      commission = 0.0
    
    # everything else is an adjustment
    else:
      symbol = Quote.CASH_SYMBOL
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
      });
      
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
      symbol = Quote.CASH_SYMBOL
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
      price = Quote.by_symbol(symbol).price_as_of(as_of_date)
                          
      parsed.append({
        'date' : as_of_date.date(),
        'type' : 'DEPOSIT',
        'symbol' : Quote.CASH_SYMBOL,
        'quantity' : (price * quantity),
        'price' : 1.0,
        'total' : (price * quantity),
      });
      
      type = 'BUY'
      commission = 0.0
      
    # everything else is an adjustment
    else:
      symbol = Quote.CASH_SYMBOL
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
      });
      
  return parsed

#-------------\
#  UTILITIES  |
#-------------/

def null_byte_line_filter(stream):
  for line in stream:
    yield line.replace('\x00', '')

def verify_transaction_file_header(reader, required_header):
  header = reader.next()
  if len(header) != len(required_header):
    raise Exception('Header mismatch for transaction file')
  
  for i in range(len(required_header)):
    if header[i] != required_header[i]:
      raise Exception("Header mismatch at %d: %s <> %s" % (i, header[i], required_header[i]))
    