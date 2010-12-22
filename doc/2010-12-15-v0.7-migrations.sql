-- Issue 98 - Quote/price history refactor

ALTER TABLE quote
DROP COLUMN quote_date,
DROP COLUMN history_date
;

-- END SEGMENT

-- Issue 102 - Income tab

ALTER TABLE transaction
ADD COLUMN linked_symbol VARCHAR(5) NULL
;

-- END SEGMENT
