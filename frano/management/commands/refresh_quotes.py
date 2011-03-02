# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from sys import stdout

from django.core.management.base import BaseCommand

from frano.quotes.models import Quote
from frano.quotes.models import quotes_by_symbols

class Command(BaseCommand):
  help = 'Refreshes all quotes from yahoo finance'

  def handle(self, *args, **options):
    symbols = set([ quote.symbol for quote in Quote.objects.all()])
    stdout.write('Found %d quotes to refresh\nStarting...\n' % len(symbols))
    
    quotes_by_symbols(symbols, True)
    stdout.write('Successfully refreshed quotes\n')
