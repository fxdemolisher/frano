-- Issue 138 - Zecco import failure - needed to expand symbol field

ALTER TABLE position
MODIFY COLUMN symbol VARCHAR(10) NOT NULL 
;

ALTER TABLE quote
MODIFY COLUMN symbol VARCHAR(10) NOT NULL 
;

ALTER TABLE transaction
MODIFY COLUMN symbol VARCHAR(10) NOT NULL,
MODIFY COLUMN linked_symbol VARCHAR(10)
;

-- END SEGMENT
