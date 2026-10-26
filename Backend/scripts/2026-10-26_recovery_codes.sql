-- Forgot password with recovery codes (branch forgot-password, 2026-10-26).
-- create_all() never ALTERs an existing table, so the 3 new users columns come from here; it would
-- create account_events by itself, but the hosted app user (firemap_app) may not CREATE, so this
-- script makes it too.
--
-- ORDER: take a full backup, run this script, THEN start the new backend (the new code reads these
-- columns on every login). The old code ignores them, so running it first is safe.
--   Laptop:  mysqldump --single-transaction --result-file=<backup>.sql insurance_db, then
--            mysql -u root -p insurance_db -e "source C:/path/without/spaces/2026-10-26_recovery_codes.sql"
--   Aiven:   as avnadmin (not firemap_app), after a backup, before redeploying Render.
-- Run it again after restoring any backup made before this date (the restore brings back the old
-- users table).
--
-- Existing accounts keep their passwords: no code yet (NULL) and no forced change (0).

ALTER TABLE users
  ADD COLUMN recovery_code_hash VARCHAR(255) NULL,
  ADD COLUMN recovery_code_set_at DATETIME NULL,
  ADD COLUMN must_change_password TINYINT(1) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS account_events (
  id INT NOT NULL AUTO_INCREMENT,
  occurred_at DATETIME NOT NULL,
  user_id INT NOT NULL,
  event VARCHAR(30) NOT NULL,
  actor_username VARCHAR(255) NULL,
  ip_address VARCHAR(45) NULL,
  seen TINYINT(1) NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY ix_account_events_occurred_at (occurred_at),
  KEY ix_account_events_user_id (user_id)
);

-- Check: 3 new columns; every existing account with no code and no forced change.
SELECT COUNT(*) AS users_total,
       SUM(recovery_code_hash IS NULL) AS without_code,
       SUM(must_change_password = 0) AS no_forced_change
  FROM users;
