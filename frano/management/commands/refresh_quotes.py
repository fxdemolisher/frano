# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from django.core.management.base import BaseCommand
from frano.models import Quote
from sys import stdout

class Command(BaseCommand):
  help = 'Refreshes all quotes from yahoo finance'

  def handle(self, *args, **options):
    symbols = []
    for quote in Quote.objects.all():
      symbols.append(quote.symbol)
    
    stdout.write('Found %d quotes to refresh\nStarting...\n' % len(symbols))
    
    Quote.get_quotes_by_symbols(symbols)
    stdout.write('Successfully refreshed quotes\n')
