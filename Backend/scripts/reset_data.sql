-- =====================================================================
-- MAAGAP reset script — clears ALL business data before a fresh data load.
-- DESTRUCTIVE and NOT reversible (TRUNCATE auto-commits). Take a full backup
-- FIRST, e.g. from a terminal:
--   mysqldump -u root -p --single-transaction insurance_db > insurance_db_backup_pre_reset_<date>.sql
--
-- CLEARS (TRUNCATE = empty + auto-increment reset to 1), 22 tables:
--   policyholders, insurance_cases,
--   fire_property_surveys, fire_property_quotations, fire_property_policies, fire_property_claims,
--   vehicles, motor_quotations, motor_policies, motor_claims,
--   import_records, risk_predictions,
--   every deleted_* archive table (10).
-- KEEPS: geocode_cache (address memory — never cleared),
--        users row with username exactly 'Aaron James' (all other users deleted).
-- No migration/version table exists in this project (no Alembic).
-- If a NEW table is added later, add it here (see CLAUDE.md "Reset script").
-- =====================================================================

-- ---- Guard: stop BEFORE touching anything unless exactly one 'Aaron James' exists.
-- The subquery returns 2 rows when the check fails, which raises
-- "Subquery returns more than 1 row" and stops the script (Workbench and the
-- mysql client both stop on the first error by default).
SELECT IF(
  (SELECT COUNT(*) FROM users WHERE BINARY username = 'Aaron James') = 1,
  'OK: keeper user found',
  (SELECT 'ABORT: expected exactly one user named Aaron James' UNION ALL SELECT 'ABORT')
) AS reset_guard;

SET @old_safe_updates = @@SQL_SAFE_UPDATES;
SET SQL_SAFE_UPDATES = 0;          -- Workbench Safe Update Mode would block the users DELETE
SET FOREIGN_KEY_CHECKS = 0;

-- ---- Claims, policies, quotations, surveys, vehicles, cases, people
TRUNCATE TABLE motor_claims;
TRUNCATE TABLE fire_property_claims;
TRUNCATE TABLE motor_policies;
TRUNCATE TABLE fire_property_policies;
TRUNCATE TABLE motor_quotations;
TRUNCATE TABLE fire_property_quotations;
TRUNCATE TABLE vehicles;
TRUNCATE TABLE fire_property_surveys;
TRUNCATE TABLE risk_predictions;
TRUNCATE TABLE import_records;
TRUNCATE TABLE insurance_cases;
TRUNCATE TABLE policyholders;

-- ---- Delete-archive tables
TRUNCATE TABLE deleted_motor_claims;
TRUNCATE TABLE deleted_fire_property_claims;
TRUNCATE TABLE deleted_motor_policies;
TRUNCATE TABLE deleted_fire_property_policies;
TRUNCATE TABLE deleted_motor_quotations;
TRUNCATE TABLE deleted_fire_property_quotations;
TRUNCATE TABLE deleted_vehicles;
TRUNCATE TABLE deleted_fire_property_surveys;
TRUNCATE TABLE deleted_import_records;
TRUNCATE TABLE deleted_policyholders;

SET FOREIGN_KEY_CHECKS = 1;

-- ---- Users: keep only 'Aaron James'. The EXISTS is a second safety net — if the
-- keeper were somehow missing, this deletes nothing instead of every user.
DELETE FROM users
 WHERE BINARY username <> 'Aaron James'
   AND EXISTS (SELECT 1 FROM (SELECT id FROM users WHERE BINARY username = 'Aaron James') AS keeper);

SET SQL_SAFE_UPDATES = @old_safe_updates;

-- ---- Verify: every cleared table should show 0; users 1; geocode_cache unchanged.
SELECT 'policyholders' AS t, COUNT(*) AS n FROM policyholders
UNION ALL SELECT 'insurance_cases', COUNT(*) FROM insurance_cases
UNION ALL SELECT 'fire_property_surveys', COUNT(*) FROM fire_property_surveys
UNION ALL SELECT 'fire_property_quotations', COUNT(*) FROM fire_property_quotations
UNION ALL SELECT 'fire_property_policies', COUNT(*) FROM fire_property_policies
UNION ALL SELECT 'fire_property_claims', COUNT(*) FROM fire_property_claims
UNION ALL SELECT 'vehicles', COUNT(*) FROM vehicles
UNION ALL SELECT 'motor_quotations', COUNT(*) FROM motor_quotations
UNION ALL SELECT 'motor_policies', COUNT(*) FROM motor_policies
UNION ALL SELECT 'motor_claims', COUNT(*) FROM motor_claims
UNION ALL SELECT 'import_records', COUNT(*) FROM import_records
UNION ALL SELECT 'risk_predictions', COUNT(*) FROM risk_predictions
UNION ALL SELECT 'deleted_policyholders', COUNT(*) FROM deleted_policyholders
UNION ALL SELECT 'deleted_import_records', COUNT(*) FROM deleted_import_records
UNION ALL SELECT 'deleted_fire_property_surveys', COUNT(*) FROM deleted_fire_property_surveys
UNION ALL SELECT 'deleted_fire_property_quotations', COUNT(*) FROM deleted_fire_property_quotations
UNION ALL SELECT 'deleted_fire_property_policies', COUNT(*) FROM deleted_fire_property_policies
UNION ALL SELECT 'deleted_fire_property_claims', COUNT(*) FROM deleted_fire_property_claims
UNION ALL SELECT 'deleted_vehicles', COUNT(*) FROM deleted_vehicles
UNION ALL SELECT 'deleted_motor_quotations', COUNT(*) FROM deleted_motor_quotations
UNION ALL SELECT 'deleted_motor_policies', COUNT(*) FROM deleted_motor_policies
UNION ALL SELECT 'deleted_motor_claims', COUNT(*) FROM deleted_motor_claims
UNION ALL SELECT 'users (expect 1)', COUNT(*) FROM users
UNION ALL SELECT 'geocode_cache (kept)', COUNT(*) FROM geocode_cache;
SELECT id, username, role FROM users;
