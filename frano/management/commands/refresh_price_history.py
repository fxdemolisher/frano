# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from sys import stdout

from django.core.management.base import BaseCommand

from frano.quotes.models import Quote
from frano.quotes.models import refresh_price_history

class Command(BaseCommand):
  help = 'Refreshes the price history for all quotes'

  def handle(self, *args, **options):
    quotes = Quote.objects.all()
    
    stdout.write('Found %d quotes to refresh price history\nStarting...\n' % quotes.count())
    for quote in quotes:
      stdout.write('Refreshing price history for: %s\n' % quote.symbol)
      refresh_price_history(quote)
    
    stdout.write('Successfully refreshed priced history\n')
