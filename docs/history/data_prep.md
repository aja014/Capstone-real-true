# Data preparation changes and synthetic data loads

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

## Data Prep Change 1 — Motor Sum Insured — DONE
2026-09-26, branch `data-prep`. First of 5 approved changes preparing for the
synthetic learning dataset (~850 people / ~1,750 policies / ~490 claims).
- **Schema** (manual ALTER, `create_all()` caveat as always; backup first:
  `Desktop\motor_tables_backup_pre_sum_insured_20260926_150621.sql`, 31 + 27 rows):
  `ALTER TABLE motor_quotations ADD COLUMN sum_insured DECIMAL(15,2) NULL AFTER total_amount_due`
  and the same on `motor_policies`. `SHOW CREATE TABLE` diff = only that column.
  Existing rows stay NULL.
- `models.py` (`MotorQuotation.sum_insured`, `MotorPolicy.sum_insured`),
  `schemas.py` (`MotorQuotationCreate`/`MotorPolicyCreate`; Out schemas and
  deleted-archive snapshots inherit it). There are NO motor Update schemas /
  PATCH endpoints — the manual POSTs pass `model_dump()` straight through, so
  they accept the field with no router change.
- `import_motor.py`: header "Sum Insured" (`suminsured`) in BOTH `COLUMN_MAP`
  and `MOTOR_POLICY_COLUMN_MAP`, parsed by the existing amount cleanup
  (`[^\d.]` stripped, so `₱850,000.00` → 850000.00). Added explicitly to all 4
  `models.MotorQuotation(...)` constructors (upload existing-vehicle/new-vehicle,
  resolve existing-vehicle/new-vehicle); policies already use `**policy_fields`.
- `policy.jsx`: "Sum Insured" currency column before Total Amount Due in
  `MOTOR_QUOTATION_COLUMNS` and `MOTOR_POLICY_COLUMNS` (fetches already spread raw fields).
- **Detection impact**: "Sum Insured" is now in both policy maps, so it no longer
  distinguishes Fire vs Motor Policy. No auto-detect outcome changed for any of
  15 synthetic header sets (all 9 types, full + minimal); only scores moved
  (e.g. full Fire Policy runner-up Motor 68.4 → 73.7, still auto-detected). A
  minimal policy file with only shared columns + Sum Insured was already
  ambiguous before this change (gap 7.1 < 12) and still is.
- **Verified**: ZZTEST 1-row Motor Quotation + Policy with Sum Insured → 850000.00
  in DB, API and both tabs (browser, "₱850,000.00"); a pair WITHOUT the header
  imported exactly as before (NULL, shown "—"). Regression: 23 table counts,
  12 spot-check endpoints byte-identical (the 2 motor endpoints identical after
  removing the new `sum_insured: null` key), 10 × 401 checks unchanged,
  `npm run build` ok. Test rows deleted by exact id after a ZZTEST marker check.

## Data Prep Change 2 — Protection Facilities upload column (Fire Survey) — DONE
2026-09-26, branch `data-prep`. No DB change (the JSON column already existed).
- Before this, nothing in the system defined facility names: no manual Survey
  form exists, the schema accepts any JSON object, 0/22 live surveys had a value,
  and the only real example (a deleted survey) was a flat key→bool checklist
  `{"fire_alarm": false, "sprinklers": true, "fire_extinguisher": true}`.
- `schemas.py`: `PROTECTION_FACILITY_OPTIONS` (32 display names → keys, taken
  from Maagap's real Survey Report paper form; keeps the 3 existing keys
  `sprinklers`, `fire_alarm`, `fire_extinguisher`) + `PROTECTION_FACILITY_ALIASES`
  (only "Sprinkler", "Sprinklers", "Fire Alarm", "CCTV").
- `import_fire_property.py`: header "Protection Facilities" in `SURVEY_COLUMN_MAP`;
  `parse_protection_facilities()` called from `row_to_survey_fields()` (so the
  needs-review resolve path gets it too). Cell = comma-separated names (names
  contain "/" but never commas), matched case/whitespace-insensitively with
  spaces around "/" ignored. Stores the FULL checklist — all 32 keys true/false —
  so "surveyed, not present" (false) differs from "not recorded" (NULL).
  "None" → all 32 false. Blank cell / no column → NULL, unchanged. Unknown name
  → row fails listing every allowed name; "None" mixed with names → row fails.
  MySQL's JSON type re-sorts object keys on storage (content identical).
- **pandas "None" gotcha, fixed for this column only**: pandas' default NA list
  turns the literal text `None` into NaN (even with `dtype=str`), so "None" was
  arriving as blank. `_keep_literal_protection_facilities()` in `upload_surveys`
  re-reads the sheet with `keep_default_na=False, na_values=[""]` and replaces
  ONLY the Protection Facilities column; every other Survey column keeps today's
  parsing. The folder/batch path calls the same `upload_surveys`, so it's covered;
  raw_data now keeps "None", so resolve re-parses it correctly.
- The manual create endpoint is unchanged (still accepts any JSON object).
- **Verified**: row with aliases/mixed case/"Fire Breaks / Doors" → 32 keys,
  exactly the 4 expected true; "None" → 32 false (single-file .xlsx, folder
  upload via `/import/batch/upload`, and .csv); blank cell and a file without the
  column → NULL; "Fire Blanket" and "None, Automatic Sprinklers" failed with clear
  messages without affecting other rows; stored raw_data "None" re-parses to all
  false (resolve path). Regression: 23 counts, 12 spot-check endpoints byte-
  identical, 10 × 401 unchanged, all detection outcomes unchanged (only the
  full-Survey sample's runner-up score moved 5.1 → 5.0). Test rows deleted by
  exact id after a ZZTEST marker check.

## Data Prep Change 3 — Fire Quotation picks the right property — DONE
2026-09-26, branch `data-prep`. No DB / frontend change.
- Problem: a Fire Quotation for a policyholder with 2+ fire cases always created a
  new, survey-less case → no GIS for that quotation.
- `import_fire_property.py`: new `_match_fire_case_by_location()` +
  `LOCATION_MATCH_MARGIN = 8`, used by `_resolve_or_create_fire_quotation()` ONLY
  when the person has 2+ fire cases. Compares the quotation's Location of Risk
  with the LATEST Survey (highest id) of each case using the Survey duplicate
  check's exact normalization/scorer (`.lower()` + `fuzz.token_sort_ratio`).
  Picks a case only if best >= 85 (`SURVEY_DUPLICATE_THRESHOLD`) AND best −
  runner-up >= 8; a case with no survey scores 0. Otherwise today's behavior
  exactly (new case, no duplicate check). A picked case gets the existing
  duplicate check (same quotation_date + total_premium) inside that case.
  0 or 1 fire case: unchanged.
- The needs-review resolve path (`resolve_fire_quotation_for_policyholder`) and
  folder uploads call the same function, so they follow the same rule.
- Margin 8 (not 10) chosen from measured scores: two different barangays in the
  same town already score up to 83.5; "123 Rizal St., Barangay Longos, …" vs the
  "Barangay Longos, …" survey scores 87.2 with an 8.2-point lead (would fall back
  at margin 10).
- ⚠️ **Data rule**: write a Fire Quotation's Location of Risk EXACTLY like its
  Survey's. Abbreviations don't match — "Brgy. Longos, Malolos City, Bulacan" vs
  "Barangay Longos, Malolos City, Bulacan, Philippines" scores only 79.1, so the
  quotation falls back to a new case with no Survey/GIS.
- **Verified** (real geocoded ZZTEST fixtures): 2-property person (Longos,
  Panghulo surveys → 2 cases): exact-Longos quotation → Longos case,
  Panghulo → Panghulo case, street-prefixed Longos → Longos case, unrelated
  Norzagaray → new case with no survey (today's behavior); re-uploading the first
  quotation → `matched`, no new row; 1-property person with an unrelated address
  → reused their single case (unchanged); resolve path (rolled-back direct call)
  picked the Panghulo case. Browser GIS modal (Quotations/Proposal page) showed
  the matching property's map + category for each, and "not yet available" for
  the unrelated one. Regression: 23 counts, 12 spot-check endpoints byte-
  identical, 10 × 401 unchanged, detection unchanged. Test rows deleted by exact
  id after a ZZTEST marker check.
- Side notes found while testing (not changed): "Barangay Longos, Malolos City"
  now classifies High (older notes above say Medium — likely the later 50m
  boundary buffer). The GIS modal's subtitle says "Within a mapped 100-year
  flood hazard zone" even when the headline category comes from storm surge
  (e.g. Panghulo) — pre-existing wording in `FloodRiskModal.jsx` (fixed later, see
  "Polish pass").

## Data Prep Change 4 — Address memory (`geocode_cache`) — DONE
2026-09-26, branch `data-prep`. Cuts repeat Nominatim calls during large imports
(renewal-year Motor Quotations re-geocode the same address every year).
- **New table** `geocode_cache` (created by `create_all()`, no existing table
  touched): `id`, `normalized_address VARCHAR(255) utf8mb4_bin NOT NULL UNIQUE`,
  `latitude DOUBLE`, `longitude DOUBLE`, `status VARCHAR(20)` (`found` |
  `not_found`), `created_at`. `utf8mb4_bin` because the DB default collation is
  accent-insensitive ("Peñafrancia" would collide with "Penafrancia"). DOUBLE
  (not DECIMAL) so a hit returns the exact float the original request produced →
  byte-identical GIS output. Model: `models.GeocodeCache`. KEEP it in resets.
- `services/flood_risk.py`: `_geocode()` now checks the cache first; a hit skips
  the network request AND the 1s throttle (the throttle lives in
  `_geocode_remote()`). Caches only HTTP-200 answers: `found` (≥1 result) and
  `not_found` (empty list). Exceptions, timeouts, non-200 (incl. 429/5xx) and bad
  JSON are NEVER cached — they stay retriable. Key = lowercase + trim + collapse
  whitespace (nothing else; "Brgy." ≠ "Barangay"). The network query is still
  sent as `address.strip()`, unchanged. Cache reads/writes use their own short
  `engine` connection (independent of the importer's row transaction, so a cached
  result survives a failed row); any cache/DB error silently falls back to the
  network; concurrent inserts are `ON DUPLICATE KEY UPDATE` no-ops; keys >255
  chars skip caching. Hazard classification (river flood, storm surge SSA3, 50m
  buffer) still runs on EVERY call from the coordinates. All 6 call sites benefit
  with no call-site change (they all go through `lookup_flood_risk()`).
- **Force a fresh lookup for an address** (e.g. an old `not_found` after fixing
  the address data, or after Nominatim/OSM improves): delete its cache row —
  the next lookup goes to the network and re-caches the new answer:
  ```sql
  SELECT id, normalized_address, status FROM geocode_cache
   WHERE normalized_address = LOWER(TRIM('Barangay Niugan, Angat, Bulacan, Philippines'));
  DELETE FROM geocode_cache WHERE id = <id from the SELECT>;
  -- or clear every definite miss at once:
  DELETE FROM geocode_cache WHERE status = 'not_found';
  ```
  (The key is lowercase with whitespace collapsed; `LOWER(TRIM(...))` matches
  whenever the address has no double spaces inside.) Existing Survey/Quotation
  rows keep their stored GIS values — deleting a cache row doesn't recompute them.
- **Verified** (14 checks, in-process with a counting wrapper on `requests.get`):
  4 reference addresses (Longos = High river, Panghulo = High storm surge,
  Bigte/Norzagaray = found but outside every zone, Niugan/Angat = real
  not_found) → first call 1 request, second call 0 requests, both byte-identical
  to the pre-change output recorded before the code was applied; case/whitespace
  variant = hit; ZZTEST unfindable address cached as `not_found` and reused;
  simulated timeout and HTTP 500 → all-null, NOT cached, retried on the next call;
  live Motor Quotation upload with the same address on 2 rows → identical GIS on
  both, one cache row. Cached geocode step ≈ 2ms. One timing check "failed" for
  an unrelated reason: the unchanged classification step occasionally spikes to
  ~1.2s (seen on a hit with 0 network calls, intermittent, not cache-related).
  Regression: 23 existing counts unchanged (+ new `geocode_cache`), 12 spot-check
  endpoints byte-identical, 10 × 401 unchanged. Cache test rows deleted only after
  confirming the table held exactly the ids the test created (it started empty);
  other test rows by exact id after a ZZTEST marker check.
- Found while testing: "Barangay Niugan, Angat" and "Barangay San Roque, Angat"
  (both confirmed-safe controls in the Hazard Boundary Buffer investigation above)
  no longer geocode at all via Nominatim — expect some real barangay addresses to
  come back `not_found`.

## Data Prep Change 5 — Reset script — DONE (written, NOT run)
2026-09-26, branch `data-prep`. **`Backend/scripts/reset_data.sql`** — plain SQL,
runs in MySQL Workbench or the `mysql` client. Meant to run ONCE, right before the
synthetic data load, AFTER a full backup
(`mysqldump -u root -p --single-transaction insurance_db > insurance_db_backup_pre_reset_<date>.sql`).
TRUNCATE auto-commits — not reversible without that backup. **Never run by an
assistant without an explicit instruction to run it.**
- **Clears (TRUNCATE, which also resets auto-increment to 1) — 23 tables**:
  policyholders, insurance_cases, fire_property_surveys, fire_property_quotations,
  fire_property_policies, fire_property_claims, vehicles, motor_quotations,
  motor_policies, motor_claims, import_records, ml_predictions, ml_models (models
  retrain after the next data load), and all 10 `deleted_*` archives. FK checks off
  only around the truncates. (Before Models Phase 1 it was 22 tables incl.
  `risk_predictions`, which no longer exists.)
- **Keeps**: `geocode_cache` (never cleared) and ONE user — username exactly
  `Aaron James` (id 10, role manager). All other users are deleted (as of
  2026-09-26: james 3, aldrin 5, manager 8, test 47, test1 48 — confirmed by the
  user). `users` has no archive table; `users`' auto-increment is not reset.
  There is no migration/version table (no Alembic).
- **Safety**: a guard `SELECT` runs first and raises "Subquery returns more than 1
  row" (stopping the script) unless exactly one `BINARY username = 'Aaron James'`
  exists; the users `DELETE` additionally has an `EXISTS` keeper check (deletes
  nothing if the keeper is missing). `SQL_SAFE_UPDATES` is switched off and
  restored (Workbench Safe Update Mode would block the users DELETE). Ends with a
  verification SELECT (every cleared table 0, users 1, geocode_cache count).
- **Accounts after the reset**: only Aaron James (manager) remains. A manager can
  create new accounts via Settings → Create Account (`POST /users`, manager-only,
  403 otherwise), but the new account is ALWAYS role `admin` — no UI/endpoint can
  create another manager (only SQL can). Nothing in the app is admin-only: the
  backend has no admin-role checks and the admin role can reach only `/policy`,
  which managers can also reach.
- **Maintenance**: any NEW table added later must be added to this script (or
  deliberately listed as kept).
- **Verified without running it**: static checks against `SHOW TABLES` (24
  tables = 22 cleared + geocode_cache kept + users partial; no table missing or
  duplicated; geocode_cache never truncated/deleted; users only ever DELETEd, never
  truncated; no DROP/ALTER/UPDATE/INSERT; FK checks re-enabled; guard precedes
  every destructive statement). The guard's SELECT alone (read-only) returned
  "OK: keeper user found", and with a wrong name raised error 1242 as designed.
  All 24 table counts, 12 spot-check endpoints and 10 × 401 checks identical
  before/after creating the file.

## Data Prep Change 6 — Occupancy Breakdown + Boundaries upload columns (Fire Survey) — DONE
2026-09-27, branch `data-prep`. No DB change (both JSON columns already existed).
- Shape: nothing defined it beyond the `schemas.py` examples (`{"building": 1000000,
  "stocks": 200000}`, `{"front": ..., "right": ..., "left": ..., "rear": ...}`), so:
  `occupancy_breakdown` keys `building, main_occupancy, stocks, me, fff, bi_lop, others,
  total` (plain JSON numbers — int when whole, else 2 decimals); `boundaries` keys
  `front, right, left, rear, sketch` (text).
- Headers (in `SURVEY_COLUMN_MAP`, prefixed so "Occupancy - Others" can't collide with
  the "Others" peril): "Occupancy - Building", "Occupancy - Main Occupancy",
  "Occupancy - Stocks", "Occupancy - M/E", "Occupancy - FFF", "Occupancy - BI/LOP",
  "Occupancy - Others", "Occupancy - Total", "Boundary - Front", "Boundary - Right",
  "Boundary - Left", "Boundary - Rear", "Boundary - Sketch". Same `occupancy__` /
  `boundary__` placeholder pattern as perils/hazards, folded into the JSON in
  `row_to_survey_fields()` — so the needs-review resolve path and folder uploads get it
  automatically. All 13 normalized keys are unique across every importer map.
- Amounts: same cleanup as Maximum Amount Subject (strip everything but digits and
  "."), but an unusable value FAILS the row (`Occupancy - Stocks: "abc" is not a valid
  amount`) instead of silently becoming NULL. As with Maximum Amount Subject, "-500"
  becomes 500. Blank cells are left out; a group with nothing filled stays NULL.
  pandas' NA words ("None", "N/A", …) count as blank here too.
- "Occupancy - Total" is stored as given. If it is more than ₱1 off the sum of the
  other filled parts, the row still imports and a warning is returned. New
  `schemas.ImportRowWarning` + `ImportSummary.warnings` (default `[]`, so every
  importer's upload response now has `"warnings": []`). Only rows that create a survey
  get it; the resolve path can't return warnings. API-only — the Upload modal doesn't
  show warnings (user's choice).
- **Verified** (18/18, `data_prep/test_change6.py`, ZZTEST rows via the real
  endpoints): all 13 filled → exact JSON; partial → only filled keys; columns present
  but blank → both NULL; file without the columns → both NULL, `warnings: []`; "abc" →
  row fails with that message, other rows unaffected; Total mismatch → imported +
  warning; folder upload (`/import/batch/detect` + `/upload`) → auto-detected Fire
  Survey, same JSON; resolve path (rolled-back direct call) → same JSON; browser:
  Survey Report tab View buttons show both fields, no console errors. Regression
  (`data_prep/regression_snapshot.py`, baseline taken before the code change): 24
  table counts, 12 spot-check endpoint hashes, 10 × 401 and 17 detection results
  (8 synthetic files + a minimal header set per type) all identical after cleanup. 6
  ZZTEST policyholders/cases/surveys/import_records deleted by exact id with plain SQL
  (no archive rows). Auto-increment ids 1130–1135 (policyholders), 1225–1230 (cases),
  482–487 (surveys) and 6549–6554 (import_records) are now skipped.

## Data Prep Step 3 — Address pool — DONE (check run; no data generated)
2026-09-26, branch `data-prep`. Folder `data_prep/` (repo root):
`address_pool_candidates.csv` (530 barangay-level addresses from the user, all 24
towns), `check_address_pool.py` (the checker), `address_pool_verified.csv` (the
result, one row per candidate). Logs `check_run.log` / `check_errors.log` are not
committed. No application code changed; the only DB writes went to `geocode_cache`
(through `lookup_flood_risk`).
- Run from `Backend/`: `./venv/Scripts/python ../data_prep/check_address_pool.py`
  (resumable: skips candidate_ids already in the output; transient errors aren't
  written, so a re-run retries them). `--summary` just re-prints the summary.
- Per candidate: 1 Nominatim request (system params + `addressdetails=1`, same
  User-Agent and 1 req/s throttle) → keep only if found, in Bulacan, town
  matches (accepted variants: "X City" ~ "X" for Malolos, Meycauayan, Baliwag,
  San Jose del Monte), and not town-level (barangay name, fuzzy ≥85, appears in
  a barangay-level field or display_name) → real `lookup_flood_risk()` → its
  coordinates must equal step 1's exactly.
- **Result**: 179 kept / 351 dropped (not found 265, town-level only 52,
  coordinate mismatch 25 — two requests returned points metres apart, wrong
  town 8, outside Bulacan 1). Kept by category: High 48 (5 of them High only
  because of storm surge, all in Obando), Medium 49, Low 31, none 51. Towns
  with <5 kept: Paombong 0 (all 14 not found), Pulilan 1, Bustos 2, DRT 2,
  Guiguinto 2, Norzagaray 2, Balagtas 3, Plaridel 3, San Rafael 3, Angat 4.
  11 groups (22 kept rows) share identical coordinates; ~19 kept rows landed on
  a neighbouring barangay's hall (passed only via display_name) — both listed
  in the step-3 report, NOT auto-dropped. `geocode_cache`: 204 rows (179 kept +
  25 mismatches), all `found`.
- Several SJDM candidates matched a numbered sub-barangay (Santa Cruz → Santa
  Cruz II, San Rafael → I, San Martin → I/IV, Fatima → V, Bagong Buhay → I).
- **Round 2 (user decisions)**, `--revise` then `--second-pass` (log
  `check_run_pass2.log`); CSV gained a `note` column. Dropped: 19 "other
  barangay hall", 5 "ambiguous sub-barangay" (SJDM), Tambobong "misspelled
  candidate", 11 remaining "shared coordinates". Rescued the 24 other coordinate
  mismatches as kept with lookup_flood_risk's (cached) coords/GIS, note
  "rescued: check point differed by X m" (10 of them moved >100 m, up to 2.1 km).
  Second pass: every "not found"/"town-level only" row retried once WITHOUT the
  word "Barangay" ("Atlag, Malolos City, Bulacan, Philippines"); 296 kept, the
  address column holds that exact string, note "second pass format". The
  no-"Barangay" format resolves to the barangay feature itself far more often.
- **Round 3 (user decisions)**: dropped the 10 rescues that moved >100 m
  (C078, C093, C164, C248, C262, C334, C343, C360, C453, C525 — reason "rescue
  moved over 100 m"; two of them had landed on another candidate's point, one
  in a different town). Kept C242 Sapang Bulak and C346 Binakod: our text is the
  official spelling, only OSM's differs ("Sapang Bulac", "Binacod").
- **Final**: 454 kept / 76 dropped; no two kept rows share coordinates. Every
  town ≥5 kept (lowest: Doña Remedios Trinidad 6). Kept by category: High 145
  (15 High only because of storm surge), Medium 114, Low 74, none 121.
  `geocode_cache`: 500 rows, all `found` (includes the dropped rescues' lookups —
  harmless).

## Data Prep Step 4 — Synthetic dataset loaded — DONE
2026-09-26, branch `data-prep`. The dev DB now holds ONLY the synthetic learning
dataset (seed 20260926); all earlier dev/test business data is gone.
- Package: `data_prep/synthetic/firemap_synthetic_data/` (`upload_files/` 8 xlsx,
  `generator/` generate.py + validate.py + address pool copy, `validation_report.md`
  — 38/38 of its own checks passed).
- Pre-flight (`data_prep/preflight_step4.py`, read-only): every header maps; all 8
  files auto-detect except `6_motor_policies` (ambiguous vs Fire Policy, 100 vs
  90.9 — needs a manual pick in folder mode; single-file upload unaffected); every
  address in files 1–4 already in `geocode_cache`; importer-matching simulation:
  file 1 = 1,129 new (max pair score 64.0), files 2–6 match their person ≥90 on
  every row.
- Backup before reset: `Desktop\insurance_db_backup_pre_synthetic_load_20260926_230951.sql`
  (274,714 bytes). Then `Backend/scripts/reset_data.sql` (22 tables → 0, users = Aaron
  James only, geocode_cache 500 kept).
- Load (`data_prep/load_step4.py`, single-file endpoints, in order 1→8): every file
  0 needs review, 0 failed. Times: 21s, 71s, 161s, 19s, 17s, 21s, 8s, 2s.
- Counts after load (all = expected): policyholders 1,129; insurance_cases 1,224
  (481 fire + 743 motor); fire_property_surveys 481; vehicles 743; motor_quotations
  1,450; fire_property_quotations 1,032; fire_property_policies 876; motor_policies
  1,139; motor_claims 351; fire_property_claims 90; import_records 6,548, all
  `unmatched` (created), 0 needs_review; users 1; geocode_cache still 500 (zero
  Nominatim calls). No fire case without a survey, no quotation with 2 policies.
- GIS: all 1,931 surveys + motor quotations have coordinates, and every stored
  lat/lng + category/river/storm-surge value equals `address_pool_verified.csv`.
  Spot-checked 3 random policies per line via the API (policy → quotation → case →
  person, survey/quotation GIS) — all consistent.
- Dashboards (browser, no console errors): Overview (Sept 2026: 50 policies,
  ₱1,092,348.33 GWP, 66 quotations; pie 143/44), Distribution (MTD 50, YTD 417),
  Renewal Ratio (daily 3 expiring; MTD 69.8%; YTD 52.19% — lower than the
  generator's ~71% because 138 not-yet-expired Pending policies are in the YTD
  denominator — Pending was later excluded from the rate, see "Polish pass"),
  Quotations/Proposal (6 months: 372 quotations, 291 converted, 78%).
  Overview's Filed Claims card and the Claims page were still mock at this point
  (wired in Claims Phase 4).

## Data Prep Step 5 — v2 dataset loaded — DONE
2026-09-27, branch `data-prep`. The dev DB now holds the fuller v2 synthetic dataset
(replaces the Step 4 v1 load; same people/policies/claims, more columns filled).
- Package: `data_prep/synthetic_v2/firemap_synthetic_data_v2/` (unzipped one folder
  deeper than the brief said; `validation_report.md` = 40/40). Only files 1 and 2
  changed: file 1 adds Complete Name of Spouse, Permanent Address, Residence Phone
  Number, Employer, TIN, SSS No. (+ Email Address values changed); file 2 adds the 12
  missing perils, District No./Block No., Current Block Accumulation, Zone, T.I., the 8
  "Occupancy - …" and 5 "Boundary - …" columns (v1 columns' values unchanged). Files
  3–8 have identical cell content to v1 — they differ byte-wise ONLY in the xlsx
  `docProps/core.xml` created/modified timestamp (14:45 vs 15:59 UTC).
- Pre-flight (read-only): no ignored headers; files 1/2 auto-detect (100 vs runner-up
  3.5 / 3.8); every row parses with the importers' own parsers, 0 Occupancy-Total
  warnings; all addresses cached; matching simulation clean (same as Step 4).
- Backup before reset: `Desktop\insurance_db_backup_pre_v2_load_20260927_002649.sql`
  (the v1 state). Reset verified (22 tables 0, users 1, geocode_cache 500).
- Load (`data_prep/load_step4.py --dir …/synthetic_v2/…/upload_files`, now also stops
  on warnings; log `data_prep/load_step5.log`): every file 0 needs review, 0 failed,
  0 warnings. Counts identical to Step 4 (policyholders 1,129; cases 1,224 = 481 fire +
  743 motor; surveys 481; vehicles 743; motor quotations 1,450; fire quotations 1,032;
  fire policies 876; motor policies 1,139; motor claims 351; fire claims 90;
  import_records 6,548, 0 needs_review; geocode_cache still 500 → zero Nominatim calls).
- Client Info blanks: spouse 456 (= every Single 334 + Widowed 79 + Separated 43; 0 of
  673 Married), residence phone 756, email 182, employer 71, TIN 145, SSS 370; every
  other column 0.
- Surveys (481): District/Block, Current Block Accumulation, Zone, T.I. 0 blank;
  occupancy_breakdown and boundaries on all 481 (boundaries always 5 keys; occupancy
  3–8 keys — building, fff, total always present, the other parts only where the
  generator filled them; every total = sum of parts); perils_assessment 18 perils on
  every row; hazard 6; protection 32. Browser: Survey #1's five View buttons open
  Occupancy Breakdown (6 keys), Boundaries (5), Protection Facilities (32), Perils (18),
  Hazard (6); no console errors.
