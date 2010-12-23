# Copyright (c) 2010 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from frano.models import Portfolio, User
from frano.views import get_sample_user
from sys import stdout


class Command(BaseCommand):
  help = 'Cleanup sample portfolios older than two weeks'

  def handle(self, *args, **options):
    user = get_sample_user()
    cutoff_date = datetime.now() - timedelta(weeks = 2)
    portfolios = Portfolio.objects.filter(user__id__exact = user.id, create_date__lte = cutoff_date)
    
    stdout.write('Found %d sample portfolios to clean up\n' % portfolios.count())
    
    portfolios.delete()
    
    stdout.write('Successfully removed old sample portfolios\n')
