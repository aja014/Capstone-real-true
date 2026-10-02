# Presentation backups, restore and demo upload folder

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

## Models — v3 presentation backup — DONE
2026-09-27, branch `models` (after Models Phase 3). No code change.
`Desktop\insurance_db_backup_loaded_v3_20260927_211608.sql` (`mysqldump
--single-transaction --routines insurance_db`, 8,924,234 bytes, ends with "Dump
completed"). It holds the v2 synthetic dataset plus the trained models and their
predictions, so a restore needs no retraining.
- Pre-flight: tree clean, no retrain running (`/ml/models` refresh `running: False`),
  no ZZTEST/test rows (every table's max id = its row count).
- Counts (25 tables): policyholders 1,129 · insurance_cases 1,224 · fire_property_surveys
  481 · vehicles 743 · motor_quotations 1,450 · fire_property_quotations 1,032 ·
  fire_property_policies 876 · motor_policies 1,139 · motor_claims 351 ·
  fire_property_claims 90 · import_records 6,548 (0 needs_review) · users 1 (Aaron James)
  · geocode_cache 500 · ml_models 7 · ml_predictions 1,051 · all 10 `deleted_*` 0.
- Active models: motor_lr v2 (id 93, trained 2026-09-27 16:53:21, 833 rows) · fire_lr v2
  (id 94, 16:53:24, 621 rows) · fraud_nb v3 (id 95, 16:53:24, 385 rows); 4 superseded.
  Predictions: 617 Motor (Low 390 / Medium 206 / High 21), 411 Fire (244 / 142 / 25),
  23 claims (2 Fraud).
- Test restore into a temp `insurance_db_restoretest`: same 25 tables, every row count
  equal, the 3 active models' version + trained_at equal, all 1,051 predictions equal
  row by row, 481 surveys with the v2 columns; temp DB dropped.

## v4 presentation backup — DONE
2026-09-28, branch `password-rules` (after Policy Forecast + Password rules). No code change.
`Desktop\insurance_db_backup_loaded_v4_20260928_195453.sql` (`mysqldump
--single-transaction --routines insurance_db`, 8,923,167 bytes, last line "-- Dump
completed on 2026-09-28 19:54:53"). Same v2 dataset + trained models as v3; taken after the
stray `risk_predictions` table was dropped (neither backup contains it).
- Pre-flight: no retrain running (`/ml/models` refresh `running: False`).
- Credentials were handed to mysqldump/mysql through a temporary `--defaults-extra-file`
  built from `DATABASE_URL` in memory and deleted afterwards; no password or hash was
  printed or read.
- Counts (25 tables): same as v3 except **ml_predictions 1,049** (v3: 1,051 — startup
  rewrites predictions, and which quotations get one depends on today's date). users 1
  (Aaron James, **with the password as of this backup** — if the password is changed later,
  restoring v4 brings the old one back).
- Active models unchanged: fire_lr v2 (trained 2026-09-27 16:53:24), fraud_nb v3
  (16:53:24), motor_lr v2 (16:53:21).
- Test restore into a temp `insurance_db_restoretest`: 25 tables, every row count equal to
  `insurance_db`, the 3 active models' version + trained_at equal; temp DB dropped
  (confirmed gone).

## How to restore the presentation backup (v4 — dataset + models)
Presentation backup: `Desktop\insurance_db_backup_loaded_v4_20260928_195453.sql` (see
"v4 presentation backup" above). After restoring, the backend does NOT retrain on
startup because an active model already exists (`jobs.py` trains only models with no active
version), so predictions show immediately. Startup still rewrites predictions in ~10s,
replacing the table in one transaction, so the restored predictions stay visible meanwhile.
The dump has no `CREATE
DATABASE`/`USE` line, so it restores into whatever database you name; each table is
`DROP TABLE IF EXISTS` + recreated (a table that isn't in the dump is left alone).
Stop the backend (uvicorn) first so nothing writes during the restore.
- **Command line** (works in PowerShell and cmd; asks for the MySQL password):
  ```
  & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p insurance_db -e "source C:/Users/aaron/OneDrive/Desktop/insurance_db_backup_loaded_v4_20260928_195453.sql"
  ```
  (in cmd, drop the leading `& ` and keep the quoted path.)
- **MySQL Workbench**: Server → Data Import → "Import from Self-Contained File" →
  pick the `.sql` file → "Default Target Schema": `insurance_db` → Import Progress
  tab → Start Import. Afterwards refresh the schema and check a few counts, e.g.
  `SELECT COUNT(*) FROM policyholders;` → 1,129.
- Older backup with models: `insurance_db_backup_loaded_v3_20260927_211608.sql` (see
  "Models — v3 presentation backup"; same data and models, 1,051 predictions, restores the
  same way).
- Older backups (no models — restoring one makes the backend train all 3 models at startup,
  and the pages show no predictions for the first ~20s):
  `insurance_db_backup_loaded_v2_20260927_003529.sql` = the v2 load (Step 5; 24 tables,
  its own test restore also passed); `insurance_db_backup_loaded_20260926_233342.sql` =
  the v1 load (Step 4); `insurance_db_backup_pre_v2_load_20260927_002649.sql` = the same
  v1 state taken right before the v2 reset.

## Demo upload folder (live defense demo) — DONE, rehearsed 2026-09-28
Branch `demo-prep`. No app code change. Defense: October 14–15, 2026.
- **Script** `data_prep/demo/make_demo_upload.py [--quote-date YYYY-MM-DD] [--out DIR]
  [--copy-to DIR]` writes 4 Excel files (default `data_prep/demo/demo_upload/`, quote date =
  yesterday). Refuses a future date or one >7 days old; warns unless 1–2 days ago. Writes
  files only, never the DB. Only replaces a folder that holds nothing but `.xlsx` files.
- **Contents** (headers copied from `data_prep/synthetic_v2/`, all auto-detect in folder mode):
  `1_customer_information` (2 rows), `2_fire_survey` (1), `3_motor_quotation` (1),
  `4_fire_quotation` (1). Clients: **Rosalinda Manalastas Dimaculangan** (fire; sari-sari
  store with residence, Barangay Panghulo, Obando → river none / storm surge High / **High**)
  and **Joel Balagtas Pagsisihan** (motor; 2024 Toyota Sedan NDQ4817, Canalate, Malolos City →
  river Medium / **Medium**). Both addresses are in `geocode_cache` (no Nominatim call). Best
  fuzzy score vs the 1,129 existing clients: 56.7 / 51.3 (Customer Info), 66.7 / 58.3
  (name only) — all below the 70 review threshold.
- **No Vehicle Information file on purpose**: its 9 headers are all Motor Quotation headers,
  so detection scores both 100 and it can never auto-detect (manual pick). The Motor
  Quotation creates the vehicle itself.
- **Why a warm-up**: training rows = policies with `period_to < today`, so every day after
  2026-09-27 the training set grows (Motor from 9-28, Fire from ~10-05) and the first
  refresh retrains. The warm-up does that retrain before the audience arrives, so the live
  upload only rewrites predictions. The accuracy card then shows "Motor v3 · trained <that
  day>" (and Fire v3 by mid-October) — expected.
- **Defense-morning steps** (from the repo root unless noted):
  1. Stop the backend; restore v4 (see "How to restore the presentation backup"); start the
     backend and wait ~15 s (startup only rewrites predictions).
  2. Warm-up, from `Backend/`:
     `./venv/Scripts/python -c "from app.ml import jobs; jobs.refresh_now('pre-demo warm-up'); print(jobs.status)"`
     → expect `last_retrained` to list `motor_lr` (and `fire_lr` in October), `last_error: None`.
  3. Regenerate the folder with yesterday's date (e.g. defense on Oct 15 → `2026-10-14`):
     `Backend/venv/Scripts/python data_prep/demo/make_demo_upload.py --quote-date 2026-10-14 --copy-to "C:/Users/aaron/OneDrive/Desktop/FIREMAP_demo_upload"`
  4. Log in, then open Proposal once so everything is warm.
- **Demo steps**: Policy Holder Info → Upload → Folder → choose `Desktop\FIREMAP_demo_upload`
  → 4 types detected (none amber) → Import All → "Import complete", each row 0 needs review,
  0 failed → talk for ~45 s → sidebar **Quotations/Proposal** (opened AFTER the upload; it
  waits by itself if the refresh is still running) → search **Dimaculangan** → Claim
  Possibility + GIS **View** ("High Risk · Rated from the storm surge map (coastal
  flooding)") → search **Pagsisihan** → GIS View ("Medium Risk · Rated from the 100-year
  river flood map"). The table lists oldest first, so always search by name.
- **Measured (rehearsal 2026-09-28, quote date 09-27)**: warm-up 28.6 s (retrained motor_lr);
  folder → types detected 1.5 s; Import All 10.4 s; refresh after upload 40.8 s server-side
  with no retrain → predictions ready ~51 s after clicking Import All; Proposal first load
  ~10 s. Result: Fire #1033 Medium 12%, Motor #1460 Low 16% (values can shift with the
  October models). DB changes were exactly +2 policyholders, +2 cases, +1 survey, +1 vehicle,
  +2 quotations, +5 import_records (+ the warm-up's model and predictions); geocode_cache
  unchanged.
- **Fallbacks** (existing data, no upload needed): GIS — **Reynaldo Isidro Pelayo**, Fire
  Quotation **#1002** (search "Reynaldo Isidro"; "Pelayo" alone gives 9 rows), Panducot,
  Calumpit → "High Risk · Rated from the 100-year river flood map" (survey #305; Risk
  Assessment High 18% on 9-28, may change once Fire retrains). Fraud — Claims page, search
  **MS2602030016** → claim **#83 Rosa Robles Padilla** "Suspicious · 56%"; backup claim
  **#248 Sonia Francisco Magbanua** (MS2501030071) "Suspicious · 39%" (Fraud model doesn't
  retrain on these dates).
- **Screenshots** for backup slides: `Desktop\FIREMAP_demo_screenshots\` (16 files: every
  upload step, both new quotations + GIS Views, Pelayo fallback, accuracy card after the
  warm-up, Suspicious claim).
- **Caveats**: the GIS View's satellite map and Leaflet load from the internet (ArcGIS
  imagery, unpkg) — offline, the rating text still shows but the map may not. Don't re-run
  the folder on a DB that already has it; restore v4 first. After the defense, restore v4 to
  remove the demo clients (verified 2026-09-28: all 25 counts and max ids back to v4).
