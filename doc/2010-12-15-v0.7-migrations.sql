-- Issue 98 - Quote/price history refactor

ALTER TABLE quote
DROP COLUMN quote_date,
DROP COLUMN history_date
;

-- END SEGMENT
