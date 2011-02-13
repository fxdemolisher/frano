# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import datetime
from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from sys import stdout

class Command(BaseCommand):
  help = 'Cleanup any expired sessions'

  def handle(self, *args, **options):
    expired_sessions = Session.objects.filter(expire_date__lte = datetime.now())
    stdout.write('Found %d expired sessions\n' % expired_sessions.count())
    
    expired_sessions.delete()
    
    stdout.write('Successfully removed expired sessions\n')
