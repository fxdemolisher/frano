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

-- Issue 136 - Resetting indexes and foreign keys, seemed to have been lost at some point

  -- rename first
  
ALTER TABLE django_session RENAME TO django_session_backup;
ALTER TABLE user RENAME TO user_backup;
ALTER TABLE portfolio RENAME TO portfolio_backup;
ALTER TABLE quote RENAME TO quote_backup;
ALTER TABLE price_history RENAME TO price_history_backup;
ALTER TABLE transaction RENAME TO transaction_backup;
ALTER TABLE position RENAME TO position_backup;
ALTER TABLE tax_lot RENAME TO tax_lot_backup;

  -- recreate

CREATE TABLE `django_session` (
    `session_key` varchar(40) NOT NULL PRIMARY KEY,
    `session_data` longtext NOT NULL,
    `expire_date` datetime NOT NULL
) Engine=InnoDB;

CREATE TABLE `user` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `open_id` varchar(255) NOT NULL UNIQUE,
    `email` varchar(255) UNIQUE,
    `create_date` datetime NOT NULL
) Engine=InnoDB;

CREATE TABLE `portfolio` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `user_id` integer NOT NULL,
    `name` varchar(30) NOT NULL,
    `read_only_token` varchar(20) NOT NULL UNIQUE,
    `create_date` datetime NOT NULL
) Engine=InnoDB;

ALTER TABLE `portfolio` ADD CONSTRAINT `portfolio_user_fk1` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`);

CREATE TABLE `quote` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `symbol` varchar(10) NOT NULL UNIQUE,
    `name` varchar(255) NOT NULL,
    `price` double precision NOT NULL,
    `last_trade` datetime NOT NULL,
    `cash_equivalent` bool NOT NULL
) Engine=InnoDB;

CREATE TABLE `price_history` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `quote_id` integer NOT NULL,
    `as_of_date` datetime NOT NULL,
    `price` double precision NOT NULL,
    UNIQUE (`quote_id`, `as_of_date`)
) Engine=InnoDB;

ALTER TABLE `price_history` ADD CONSTRAINT `price_history_quote_fk1` FOREIGN KEY (`quote_id`) REFERENCES `quote` (`id`);

CREATE INDEX `price_history_as_of_date` ON `price_history` (`as_of_date`);

CREATE TABLE `transaction` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `portfolio_id` integer NOT NULL,
    `type` varchar(10) NOT NULL,
    `as_of_date` date NOT NULL,
    `symbol` varchar(10) NOT NULL,
    `quantity` double precision NOT NULL,
    `price` double precision NOT NULL,
    `total` double precision NOT NULL,
    `linked_symbol` varchar(10)
) Engine=InnoDB;

ALTER TABLE `transaction` ADD CONSTRAINT `transaction_portfolio_fk1` FOREIGN KEY (`portfolio_id`) REFERENCES `portfolio` (`id`);

CREATE INDEX `transaction_as_of_date` ON `transaction` (`as_of_date`);
CREATE INDEX `transaction_symbol` ON `transaction` (`symbol`);

CREATE TABLE `position` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `portfolio_id` integer NOT NULL,
    `as_of_date` date NOT NULL,
    `symbol` varchar(10) NOT NULL,
    `quantity` double precision NOT NULL,
    `cost_price` double precision NOT NULL,
    `realized_pl` double precision NOT NULL
) Engine=InnoDB;

ALTER TABLE `position` ADD CONSTRAINT `position_portfolio_fk1` FOREIGN KEY (`portfolio_id`) REFERENCES `portfolio` (`id`);

CREATE INDEX `position_as_of_date` ON `position` (`as_of_date`);
CREATE INDEX `position_symbol` ON `position` (`symbol`);

CREATE TABLE `tax_lot` (
    `id` integer AUTO_INCREMENT NOT NULL PRIMARY KEY,
    `position_id` integer NOT NULL,
    `as_of_date` date NOT NULL,
    `quantity` double precision NOT NULL,
    `cost_price` double precision NOT NULL,
    `sold_quantity` double precision NOT NULL,
    `sold_price` double precision NOT NULL
) Engine=InnoDB;

ALTER TABLE `tax_lot` ADD CONSTRAINT `tax_lot_position_fk1` FOREIGN KEY (`position_id`) REFERENCES `position` (`id`);

CREATE INDEX `tax_lot_as_of_date` ON `tax_lot` (`as_of_date`);

  -- inserts

INSERT INTO django_session SELECT * FROM django_session_backup;
INSERT INTO user SELECT * FROM user_backup;
INSERT INTO portfolio SELECT * FROM portfolio_backup;
INSERT INTO quote SELECT * FROM quote_backup;
INSERT INTO price_history SELECT * FROM price_history_backup;
INSERT INTO transaction SELECT * FROM transaction_backup;
INSERT INTO position SELECT * FROM position_backup;
INSERT INTO tax_lot SELECT * FROM tax_lot_backup;

  -- drop copies

DROP TABLE django_session_backup;
DROP TABLE price_history_backup;
DROP TABLE quote_backup;
DROP TABLE tax_lot_backup;
DROP TABLE position_backup;
DROP TABLE transaction_backup;
DROP TABLE portfolio_backup;
DROP TABLE user_backup;

-- END SEGMENT
