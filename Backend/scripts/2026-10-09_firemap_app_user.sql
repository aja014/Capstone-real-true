-- IAS2 least privilege (branch deploy-ias2): the hosted app connects as firemap_app, not avnadmin.
-- Run as avnadmin on the Aiven MySQL service, AFTER the app has started once with LOGIN_AUDIT=true
-- (that first startup, still as avnadmin, creates login_events; firemap_app can't create tables).
--
-- Rights the app needs on insurance_db, and why only these (checked 2026-10-09):
--   SELECT, INSERT, UPDATE, DELETE  - all the app does at run time. Archive-first deletes are an
--     INSERT into deleted_* then a DELETE; the model refresh rewrites ml_models / ml_predictions;
--     geocode_cache uses INSERT ... ON DUPLICATE KEY UPDATE; login_events gets INSERT + DELETE (90 days).
--   Not needed: CREATE / ALTER / DROP / INDEX (Base.metadata.create_all() only CREATEs MISSING tables;
--     all 26 exist on Aiven, so it issues no DDL), EXECUTE / TRIGGER / SHOW VIEW (the app uses no stored
--     procedures, triggers, views or events: information_schema shows 0 of each), LOCK TABLES,
--     CREATE TEMPORARY TABLES, FILE, PROCESS, SUPER, GRANT OPTION, and nothing outside insurance_db.
--
-- Password: use a LONG password of only letters and digits (e.g. 32 characters, A-Z a-z 0-9) so it can
-- go into DATABASE_URL without URL-encoding. Replace <PASSWORD> below; never commit the filled-in file.

CREATE USER 'firemap_app'@'%' IDENTIFIED BY '<PASSWORD>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_db.* TO 'firemap_app'@'%';
SHOW GRANTS FOR 'firemap_app'@'%';
-- Expected, exactly two lines:
--   GRANT USAGE ON *.* TO `firemap_app`@`%`
--   GRANT SELECT, INSERT, UPDATE, DELETE ON `insurance_db`.* TO `firemap_app`@`%`

-- FALLBACK if CREATE USER is refused (error 1227 "Access denied; you need the CREATE USER privilege"):
--   1. Aiven console -> the MySQL service -> Users -> Add service user "firemap_app" (Aiven generates
--      the password; if it contains characters other than letters/digits, URL-encode it in DATABASE_URL
--      or reset it in the console until it is letters/digits only).
--   2. Then, as avnadmin, take away whatever Aiven gave it and grant only the 4 rights:
--        REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'firemap_app'@'%';
--        GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_db.* TO 'firemap_app'@'%';
--        ALTER USER 'firemap_app'@'%' REQUIRE SSL;
--        SHOW GRANTS FOR 'firemap_app'@'%';     -- the same two lines as above
--
-- To undo (back to avnadmin): set Render's DATABASE_URL back to the avnadmin one, then
--   DROP USER 'firemap_app'@'%';
