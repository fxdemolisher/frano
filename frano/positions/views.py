# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime
from datetime import timedelta

from django.db import connection
from django.db import transaction

from main.decorators import portfolio_manipulation_decorator
from main.decorators import read_only_decorator
from main.models import Portfolio
from main.view_utils import render_page
from models import decorate_position_with_prices
from models import latest_positions
from models import refresh_positions
from quotes.models import CASH_SYMBOL
from quotes.models import quote_by_symbol
from quotes.models import quotes_by_symbols
from quotes.models import previous_close_price
from transactions.models import Transaction

#-------------\
#  CONSTANTS  |
#-------------/

DAYS_IN_PERFORMANCE_HISTORY = 90
PERFORMANCE_BENCHMARK_SYMBOL = 'ACWI'

#---------\
#  VIEWS  |
#---------/

@portfolio_manipulation_decorator
def positions(request, portfolio, is_sample, read_only):
  
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  refresh_positions(portfolio, transactions)
  
  positions = latest_positions(portfolio)
  _decorate_positions_for_display(positions, request.GET.get("showClosedPositions", False))
  _decorate_positions_with_lots(positions)
  summary = _get_summary(positions, transactions)
  performance_history = _get_performance_history(portfolio, DAYS_IN_PERFORMANCE_HISTORY)
  
  context = {
      'read_only' : read_only, 
      'is_sample' : is_sample, 
      'positions': positions, 
      'summary' : summary, 
      'current_tab' : 'positions',
      'performance_history' : performance_history, 
      'benchmark_symbol' : PERFORMANCE_BENCHMARK_SYMBOL,
    }
  
  return render_page('positions.html', request, portfolio = portfolio, extra_dictionary = context)

@read_only_decorator
def read_only_positions(request, portfolio):
  return positions(request, portfolio.id, read_only = True)

@portfolio_manipulation_decorator
def allocation(request, portfolio, is_sample, read_only):
  refresh_positions(portfolio)
  
  positions = latest_positions(portfolio)
  _decorate_positions_for_display(positions, False)
  
  context = { 
      'positions': positions, 
      'current_tab' : 'allocation',
    }
  
  return render_page('allocation.html', request, portfolio = portfolio, extra_dictionary = context)
  
@portfolio_manipulation_decorator
def income(request, portfolio, is_sample, read_only):
  transactions = Transaction.objects.filter(portfolio__id__exact = portfolio.id).order_by('-as_of_date', '-id')
  refresh_positions(portfolio, transactions)
  
  positions = latest_positions(portfolio)
  _decorate_positions_for_display(positions, request.GET.get("showClosedPositions", False))
  
  summary_map = {}
  for position in positions:
    summary_map[position.symbol] = IncomeSummary(position.symbol, position.market_value, position.cost_basis, position.pl, position.pl_percent, position.realized_pl, position.show)
  
  total_summary = IncomeSummary('*TOTAL*', 0.0, 0.0, 0.0, 0.0, 0.0, True)
  for transaction in transactions:
    if transaction.type != 'ADJUST':
      continue
    
    symbol = transaction.linked_symbol
    if symbol == None or symbol == '':
      symbol = transaction.symbol
      
    summary = summary_map.get(symbol)
    summary.add_income(transaction.as_of_date, transaction.total)
    
    if summary.show:
      total_summary.add_income(transaction.as_of_date, transaction.total)
    
  summaries = sorted(summary_map.values(), key = (lambda summary: summary.symbol))
  
  for summary in summaries:
      total_summary.market_value = total_summary.market_value + summary.market_value
      total_summary.cost_basis = total_summary.cost_basis + summary.cost_basis
      total_summary.unrealized_pl = total_summary.unrealized_pl + summary.unrealized_pl
      total_summary.realized_pl = total_summary.realized_pl + summary.realized_pl
  
  total_summary.unrealized_pl_percent = ((total_summary.market_value / total_summary.cost_basis) - 1) * 100
  
  context = {
      'read_only' : read_only,
      'summaries': summaries,
      'total_summary' : total_summary,
      'current_tab' : 'income',
    }

  return render_page('income.html', request, portfolio = portfolio, extra_dictionary = context)

@read_only_decorator
def read_only_income(request, portfolio):
  return income(request, portfolio.id, read_only = True)

#---------\
#  FORMS  |
#---------/

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/

def _decorate_positions_for_display(positions, showClosedPositions):
  
  symbols = [ position.symbol for position in positions ] + [ CASH_SYMBOL ]
  quotes = dict((quote.symbol, quote) for quote in quotes_by_symbols(symbols))
  as_of_date = min([quote.last_trade.date() for symbol, quote in quotes.items()])
  
  total_market_value = 0
  for position in positions:
    price = (1.0 if position.symbol == CASH_SYMBOL else quotes[position.symbol].price)
    previous_price = (1.0 if position.symbol == CASH_SYMBOL else previous_close_price(quotes[position.symbol]))
    
    decorate_position_with_prices(position, price, previous_price)
    position.show = (showClosedPositions or abs(position.quantity) > 0.01 or position.symbol == CASH_SYMBOL)
    
    total_market_value += position.market_value
    
  for position in positions:
    position.allocation = ((position.market_value / total_market_value * 100) if total_market_value != 0 else 0)
    position.effective_as_of_date = as_of_date

def _decorate_positions_with_lots(positions):
  for position in positions:
    lots = []
    for lot in position.taxlot_set.order_by('-as_of_date'):
      lot.cost_basis = lot.cost_price * lot.quantity
      lot.unrealized_pl = (lot.quantity - lot.sold_quantity) * (position.price - lot.cost_price)
      lot.unrealized_pl_percent = ((((position.price / lot.cost_price) - 1) * 100) if lot.cost_price <> 0 and abs(lot.unrealized_pl) > 0.01 else 0)
      lot.realized_pl = lot.sold_quantity * (lot.sold_price - lot.cost_price)
      
      days_open = (datetime.now().date() - lot.as_of_date).days
      if abs(lot.quantity - lot.sold_quantity) < 0.0001:
        lot.status = 'Closed'
        
      elif days_open <= 365:
        lot.status = 'Short'
        
      else:
        lot.status = 'Long'
    
      lots.append(lot)
    
    position.lots = lots

def _get_summary(positions, transactions):
  as_of_date = max([position.effective_as_of_date for position in positions]) if len(positions) > 0 else datetime.now().date()
  start_date = min([transaction.as_of_date for transaction in transactions]) if len(transactions) > 0 else datetime.now().date()
  
  risk_capital = 0
  for transaction in transactions:
    if transaction.type == 'DEPOSIT':
      risk_capital = risk_capital + transaction.total
    elif transaction.type == 'WITHDRAW':
      risk_capital = risk_capital - transaction.total
  
  market_value = 0  
  cost_basis = 0
  realized_pl = 0
  previous_market_value = 0
  for position in positions:
    market_value += position.market_value
    cost_basis += position.cost_price * position.quantity
    realized_pl += position.realized_pl
    previous_market_value += position.previous_market_value
  
  return Summary(as_of_date, start_date, market_value, cost_basis, risk_capital, realized_pl, previous_market_value)

def _get_performance_history(portfolio, days):
  query = """
      SELECT D.portfolio_date,
             D.deposit,
             D.withdrawal,
             SUM(P.quantity * ((CASE WHEN P.symbol = '*CASH' OR Q.cash_equivalent = '1' THEN 1.0 ELSE H.price END))) as market_value
        FROM position P
             JOIN
             (
                 SELECT D.portfolio_id,
                        D.portfolio_date,
                        D.position_date,
                        SUM(CASE WHEN T.type = 'DEPOSIT' THEN T.total ELSE 0 END) as deposit,
                        SUM(CASE WHEN T.type = 'WITHDRAW' THEN T.total ELSE 0 END) as withdrawal
                   FROM (
                            SELECT P.portfolio_id,
                                   D.portfolio_date,
                                   MAX(P.as_of_date) as position_date
                              FROM (
                                     SELECT DISTINCT
                                            D.portfolio_id,
                                            DATE(H.as_of_date) as portfolio_date
                                       FROM (
                                              SELECT DISTINCT
                                                     P.portfolio_id,
                                                     P.symbol
                                                FROM position P
                                               WHERE P.symbol != '*CASH'
                                                 AND P.portfolio_id = %(portfolio_id)s
                                            ) S
                                            JOIN quote Q ON (Q.symbol = S.symbol)
                                            JOIN price_history H ON (H.quote_id = Q.id)
                                            JOIN
                                            (
                                                SELECT P.portfolio_id,
                                                       MIN(as_of_date) as start_date
                                                  FROM position P
                                                 WHERE P.portfolio_id = %(portfolio_id)s
                                              GROUP BY P.portfolio_id
                                            ) D ON (D.portfolio_id = S.portfolio_id AND H.as_of_date >= D.start_date)
                                      WHERE DATEDIFF(NOW(), H.as_of_date) < %(days)s
                                   ) D
                                   JOIN 
                                   (
                                     SELECT DISTINCT 
                                            P.portfolio_id,
                                            P.as_of_date
                                       FROM position P
                                      WHERE P.portfolio_id = %(portfolio_id)s
                                   )  P ON (P.portfolio_id = D.portfolio_id AND P.as_of_date <= D.portfolio_date)
                          GROUP BY D.portfolio_id,
                                   D.portfolio_date
                        ) D
                        LEFT JOIN
                        (
                          SELECT T.portfolio_id,
                                 T.as_of_date,
                                 T.type,
                                 T.total
                            FROM transaction T
                           WHERE T.type IN ('DEPOSIT', 'WITHDRAW')
                             AND T.portfolio_id = %(portfolio_id)s
                        ) T ON (T.portfolio_id = D.portfolio_id AND T.as_of_date = D.portfolio_date)
               GROUP BY D.portfolio_id,
                        D.portfolio_date
             ) D ON (P.portfolio_id = D.portfolio_id AND P.as_of_date = D.position_date)
             LEFT JOIN quote Q ON (Q.symbol = P.symbol)
             LEFT JOIN price_history H ON (H.quote_id = Q.id AND H.as_of_date = D.portfolio_date)
       WHERE P.quantity <> 0
         AND P.portfolio_id = %(portfolio_id)s
    GROUP BY D.portfolio_date
    ORDER BY D.portfolio_date"""
  
  cursor = connection.cursor()
  cursor.execute(query, { 'days' : days, 'portfolio_id' : portfolio.id })
  
  benchmark_quote = quote_by_symbol(PERFORMANCE_BENCHMARK_SYMBOL)
  cutoff_date = datetime.now().date() - timedelta(days = DAYS_IN_PERFORMANCE_HISTORY)
  benchmark_price = {}
  for history in benchmark_quote.pricehistory_set.filter(as_of_date__gte = cutoff_date).order_by('as_of_date'):
    benchmark_price[history.as_of_date.date()] = history.price
    
  shares = None
  last_price = None
  first_benchmark = None
  out = []
  for row in cursor.fetchall():
    as_of_date = row[0]
    deposit = float(row[1])
    withdraw = float(row[2])
    market_value = float(row[3])
    
    benchmark = benchmark_price.get(as_of_date, 0.0)
    if first_benchmark == None:
      first_benchmark = benchmark
    
    performance = 0
    if shares == None:
      shares = market_value
      
    else:
      net_inflow = deposit - withdraw
      shares += net_inflow / last_price
      performance = (((market_value / shares) - 1) if shares <> 0 else 0) 
    
    last_price = ((market_value / shares) if shares <> 0 else 1.0)
    benchmark_performance = (((benchmark / first_benchmark) - 1) if first_benchmark <> 0 else 0)
    out.append(PerformanceHistory(as_of_date, performance, benchmark_performance))
    
  cursor.close()
  return out

#-----------------\
#  VALUE OBJECTS  |
#-----------------/

class Summary:
  def __init__(self, as_of_date, start_date, market_value, cost_basis, risk_capital, realized_pl, previous_market_value):
    self.as_of_date = as_of_date
    self.start_date = start_date
    self.market_value = market_value
    self.cost_basis = cost_basis
    self.risk_capital = risk_capital
    self.realized_pl = realized_pl
    self.previous_market_value = previous_market_value
    
    self.day_pl = market_value - previous_market_value
    self.day_pl_percent = ((self.day_pl / previous_market_value) * 100) if previous_market_value != 0 else 0
    self.pl = market_value - cost_basis
    self.pl_percent = ((self.pl / cost_basis) * 100) if cost_basis != 0 else 0
    self.risk_capital_pl = market_value - risk_capital
    self.risk_capital_pl_percent = ((self.risk_capital_pl / risk_capital) * 100) if risk_capital != 0 else 0
    
class PerformanceHistory:
  def __init__(self, as_of_date, percent, benchmark_percent):
    self.as_of_date = as_of_date
    self.percent = percent
    self.benchmark_percent = benchmark_percent

class IncomeSummary:
  def __init__(self, symbol, market_value, cost_basis, unrealized_pl, unrealized_pl_percent, realized_pl, show):
    self.symbol = symbol
    self.market_value = market_value
    self.cost_basis = cost_basis
    self.unrealized_pl = unrealized_pl
    self.unrealized_pl_percent = unrealized_pl_percent
    self.realized_pl = realized_pl
    self.show = show
     
    self.income_one_month = 0.0
    self.income_three_months = 0.0
    self.income_six_months = 0.0
    self.income_one_year = 0.0
    self.total_income = 0.0
    
  def add_income(self, as_of_date, amount):
    current = datetime.now().date()
    self.total_income += amount
    if (current - as_of_date).days < 365:
      self.income_one_year += amount
      
    if (current - as_of_date).days < 180:
      self.income_six_months += amount
      
    if (current - as_of_date).days < 90:
      self.income_three_months += amount
      
    if (current - as_of_date).days < 30:
      self.income_one_month += amount
