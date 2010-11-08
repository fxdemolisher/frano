-- Issue 37 - Decimal to float refactor 

ALTER TABLE transaction
MODIFY COLUMN quantity double precision NOT NULL,
MODIFY COLUMN price double precision NOT NULL,
MODIFY COLUMN total double precision NOT NULL
;

ALTER TABLE quote
MODIFY COLUMN price double precision NOT NULL,
MODIFY COLUMN previous_close_price double precision NOT NULL
;

-- END SEGMENT