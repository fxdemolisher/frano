# Copyright (c) 2011 Gennadiy Shafranovich
# Licensed under the MIT license
# see LICENSE file for copying permission.

from datetime import date
from datetime import datetime

from django.http import HttpResponse

from models import price_as_of
from models import quote_by_symbol

#-------------\
#  CONSTANTS  |
#-------------/

#---------\
#  VIEWS  |
#---------/

def price_quote(request):
  today = datetime.now().date()
  
  year = int(request.GET.get('year', today.year))
  month = int(request.GET.get('month', today.month))
  day = int(request.GET.get('day', today.day))
  
  quote = quote_by_symbol(request.GET.get('symbol'))
  
  return HttpResponse("{ \"price\": %f }" % price_as_of(quote, date(year, month, day)), mimetype="application/json")

#-------------------\
#  LOCAL FUNCTIONS  |
#-------------------/
