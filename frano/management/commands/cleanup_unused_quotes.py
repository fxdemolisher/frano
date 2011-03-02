# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from sys import stdout

from django.core.management.base import BaseCommand
from django.db import connection

from frano.quotes.models import Quote
from frano.positions.views import PERFORMANCE_BENCHMARK_SYMBOL

class Command(BaseCommand):
  help = 'Cleanup any quotes and price history that are unused'

  def handle(self, *args, **options):
    query = '''
        SELECT DISTINCT
               Q.symbol
          FROM quote Q
         WHERE Q.symbol NOT IN 
               (
                 SELECT DISTINCT
                        T.symbol
                   FROM transaction T
               )
      '''
    
    symbols = []
    cursor = connection.cursor()
    cursor.execute(query)
    for row in cursor.fetchall():
      symbols.append(row[0])
      
    cursor.close()
    
    symbols.remove(PERFORMANCE_BENCHMARK_SYMBOL)
    unused = Quote.objects.filter(symbol__in = symbols)
    stdout.write('Found %d unused quotes\n' % unused.count())
    
    for quote in unused:
      stdout.write('Removing quote and price history for: %s\n' % quote.symbol)
      quote.delete()
    
    stdout.write('Successfully removed unused quotes and price history\n')
