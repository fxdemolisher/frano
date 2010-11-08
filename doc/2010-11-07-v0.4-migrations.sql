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

-- Issue 29 - Price History

ALTER TABLE quote
DROP COLUMN previous_close_price,
ADD COLUMN history_date datetime NOT NULL
;

CREATE TABLE price_history (
    id integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    quote_id integer NOT NULL,
    as_of_date datetime NOT NULL,
    price double precision NOT NULL,
    UNIQUE (quote_id, as_of_date)
)
;

ALTER TABLE price_history ADD CONSTRAINT quote_id_refs_id_82867ccf FOREIGN KEY (quote_id) REFERENCES quote (id);

-- END SEGMENT