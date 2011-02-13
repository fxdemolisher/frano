-- Copyright (c) 2011 Gennadiy Shafranovich
-- Licensed under the MIT license
-- see LICENSE file for copying permission.

DROP DATABASE IF EXISTS frano;
CREATE DATABASE frano;
GRANT ALL ON frano.* TO tracker IDENTIFIED BY 'trackmystocks' WITH GRANT OPTION;