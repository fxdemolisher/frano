-- Issue 150 - Changes to lot details (refactor)

DELETE FROM tax_lot;

DELETE FROM position;

ALTER TABLE tax_lot
CHANGE COLUMN cost_price price double precision NOT NULL,
MODIFY COLUMN as_of_date date,
MODIFY COLUMN quantity double precision NOT NULL,
ADD COLUMN sold_as_of_date date AFTER price,
MODIFY COLUMN sold_quantity double precision NOT NULL,
MODIFY COLUMN sold_price double precision NOT NULL,
RENAME lot
;

ALTER TABLE lot
DROP KEY tax_lot_position_fk1,
DROP INDEX tax_lot_as_of_date,
ADD CONSTRAINT lot_position_fk1 FOREIGN KEY lot_position_fk1 (position_id) REFERENCES position (id),
ADD INDEX lot_as_of_date (as_of_date),
ADD INDEX lot_sold_as_of_date (sold_as_of_date)
;

-- END SEGMENT