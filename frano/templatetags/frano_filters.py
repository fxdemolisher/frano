from django import template
from django.template.defaultfilters import stringfilter
import locale

register = template.Library()

#-----------\
#  FILTERS  |
#-----------/

@register.filter
@stringfilter
def num_format(value, places = 2, min_places = 2):
  return format(value, '.', int(places), 3, ',', int(min_places))

@register.filter
@stringfilter
def sign_choice(value, args = 'positive,negative,zero'):
  positive, negative, zero = args.split(',')
  value = float(value)
  if value == 0:
    return zero
  
  elif value > 0:
    return positive
  
  else:
    return negative

@register.filter
def sorted_set(value):
  return sorted(value)

#-------------\
#  UTILITIES  |
#-------------/

def format(number, decimal_sep, decimal_pos, grouping=0, thousand_sep='', min_decimal_pos = None):
    """
    NOTE: taken from django 1.2.3 source
    
    Gets a number (as a number or string), and returns it as a string,
    using formats definied as arguments:
 
    * decimal_sep: Decimal separator symbol (for example ".")
    * decimal_pos: Number of decimal positions
    * grouping: Number of digits in every group limited by thousand separator
    * thousand_sep: Thousand separator symbol (for example ",")
 
    """
    # sign
    if float(number) < 0:
        sign = '-'
    else:
        sign = ''
    # decimal part
    str_number = unicode(number)
    if str_number[0] == '-':
        str_number = str_number[1:]
    if '.' in str_number:
        int_part, dec_part = str_number.split('.')
        if decimal_pos:
            dec_part = dec_part[:decimal_pos]
    else:
        int_part, dec_part = str_number, ''
        
    # do not zero pad when its not needed
    #if decimal_pos:
    #    dec_part = dec_part + ('0' * (decimal_pos - len(dec_part)))
    
    # zero pad to minimum decimal positions
    if min_decimal_pos:
        dec_part = dec_part + ('0' * (min_decimal_pos - len(dec_part)))
    
    if dec_part: dec_part = decimal_sep + dec_part
    # grouping
    if thousand_sep != '' and grouping:
        int_part_gd = ''
        for cnt, digit in enumerate(int_part[::-1]):
            if cnt and not cnt % grouping:
                int_part_gd += thousand_sep
            int_part_gd += digit
        int_part = int_part_gd[::-1]
 
    return sign + int_part + dec_part
