-- hotfix for lowecase symbols

UPDATE transaction
   SET symbol = UPPER(symbol)
;

UPDATE position
   SET symbol = UPPER(symbol)
;

UPDATE quote
   SET symbol = UPPER(symbol)
;

-- END SEGMENT
