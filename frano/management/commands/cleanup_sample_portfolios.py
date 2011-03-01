# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime, timedelta
from sys import stdout

from django.core.management.base import BaseCommand

from frano.main.models import Portfolio
from frano.main.models import User
from frano.main.view_utils import get_demo_user

class Command(BaseCommand):
  help = 'Cleanup sample portfolios older than two weeks'

  def handle(self, *args, **options):
    user = get_demo_user()
    cutoff_date = datetime.now() - timedelta(weeks = 2)
    portfolios = Portfolio.objects.filter(user__id__exact = user.id, create_date__lte = cutoff_date)
    
    stdout.write('Found %d sample portfolios to clean up\n' % portfolios.count())
    
    portfolios.delete()
    
    stdout.write('Successfully removed old sample portfolios\n')
