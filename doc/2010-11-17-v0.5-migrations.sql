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