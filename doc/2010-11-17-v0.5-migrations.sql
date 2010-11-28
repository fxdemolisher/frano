-- Issue 50 - Shorten read-only token 

UPDATE portfolio
   SET read_only_token = LEFT(read_only_token, 10)
 WHERE user_id NOT IN (SELECT id FROM user WHERE email = 'SAMPLE_USER_ONLY')
;

-- END SEGMENT

-- Issue 55 - Handling of cash equivalents

ALTER TABLE quote
ADD COLUMN cash_equivalent bool NOT NULL
;

-- END SEGMENT

-- price history was created with the wrong engine

ALTER TABLE price_history ENGINE=InnoDb;

-- END SEGMENT

-- Issue 27 - P/L charts

CREATE TABLE position (
    id integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    portfolio_id integer NOT NULL,
    as_of_date date NOT NULL,
    symbol varchar(5) NOT NULL,
    quantity double precision NOT NULL,
    cost_price double precision NOT NULL
) ENGINE=InnoDb
;

ALTER TABLE position ADD CONSTRAINT portfolio_id_refs_id_a56922ad FOREIGN KEY (portfolio_id) REFERENCES portfolio (id);

CREATE TABLE tax_lot (
    id integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    position_id integer NOT NULL,
    as_of_date date NOT NULL,
    quantity double precision NOT NULL,
    cost_price double precision NOT NULL,
    sold_quantity double precision NOT NULL,
    sold_price double precision NOT NULL
) ENGINE=InnoDb
;

ALTER TABLE tax_lot ADD CONSTRAINT position_id_refs_id_7f9d0db8 FOREIGN KEY (position_id) REFERENCES position (id);

-- END SEGMENT