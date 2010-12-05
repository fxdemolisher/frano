-- Issue 72 - Realized P/L on positions

DELETE FROM tax_lot;
DELETE FROM position;

ALTER TABLE position
ADD COLUMN realized_pl double precision NOT NULL
;

-- END SEGMENT