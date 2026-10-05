# MAAGAP Insurance Capstone — Project Memory

Concise, current guide (rewritten 2026-10-01). The full build history — every phase report,
investigation, old number and superseded backup — lives word-for-word in `docs/history/`
(see the **Index** at the end). The user-manual-level description of every page, number and
method is `docs/SYSTEM_REFERENCE.md`. When this file and a history file disagree, this file
is current; the history file explains why.

## Project overview
FIREMAP — insurance capstone for "Maagap" insurance (Bulacan). Predicts the claim
probability of a future quotation from PRE-POLICY data (survey / vehicle / quotation + GIS
flood risk), flags possible fraud on claims, and monitors policies, renewals and claims.
**Defense: October 14–15, 2026** — favor the simplest defensible change over elegance.

Study objectives (keep all in scope):
- 1.1 Policyholder Information Management — DONE (Policy Holder Info page, bulk import).
- 1.2 Predictive Risk Management — Fire/Property AND Motor/Car, predicted BEFORE the
  quotation is issued — DONE (two Logistic Regression models).
- 1.3 Fraud Detection Assessment — claim stage — DONE (Naive Bayes on claims data).
- 1.4 Client Retention Management — Renewal Ratio page DONE (computed, not predicted; no
  dedicated retention model).
- 2.1 Geospatial Flood Prone Mapping — DONE (geocoding + point-in-polygon on river flood +
  storm surge shapefiles; not the QGIS API).
- 2.2 Bulk Client Data Import & Validation — DONE (single-file + folder import, Needs Review).

## Tech stack
- Frontend: React + React Router + Vite, Tailwind CSS 4, lucide-react, axios, Recharts,
  Leaflet (GIS map). Dev server http://localhost:5173.
- Backend: Python 3.14, FastAPI + SQLAlchemy + Pydantic + bcrypt, JWT auth. Dev server
  http://127.0.0.1:8000 (`/docs` for Swagger).
- Database: MySQL 8 (`insurance_db`, via pymysql). MySQL Workbench 8.0 is the DB tool.
- GIS: `shapely` + `pyogrio` (GDAL wheels; geopandas/fiona have no Python 3.14 wheels),
  OpenStreetMap Nominatim for geocoding.
- ML: our own numpy Logistic Regression + Naive Bayes in `Backend/app/ml/`; scikit-learn is
  used ONLY in tests (listed in the "Tests only" part of `Backend/requirements.txt`) to
  cross-check them.

## Critical architecture decisions (do not relitigate)
- **Insurance Case**: internal grouping Policyholder → Insurance Case (`line_type`
  fire_property | motor_car) → Survey/Quotation/Policy (Fire) or Vehicle/Quotation/Policy
  (Motor). Exists because company documents share NO universal identifier — matching relies
  on name / address / phone / vehicle IDs.
- One case can have MANY quotations (re-quotes reuse the case); a policy always links to
  the exact quotation it came from (required FK, 1:1).
- Primary keys: auto-increment integers, not UUIDs.
- Both Fire/Property and Motor/Car MUST connect to Predictive Risk Management in every
  diagram/design (corrected once before).
- Prediction uses PRE-POLICY data only, never the issued policy.
- MySQL, not Postgres. GIS results are plain columns (lat/lng DECIMAL, flood flag/category),
  not spatial types.
- Business "Name of Insured" (Fire survey, no first/last split) is stored whole in
  `policyholders.last_name`, `first_name` NULL; `PolicyholderOut.first_name` stays Optional.
- Fire survey import: a matched policyholder's survey that duplicates an existing survey (by
  location_of_risk similarity) doesn't create a new case; otherwise a new case.
- Motor import: exact match on plate_no OR motor_engine_no OR serial_chassis_no = same
  vehicle. A re-quote for a known vehicle reuses its case; an exact duplicate quotation
  (same date + amount) is skipped. The reused vehicle gets its EMPTY plate/engine/chassis
  filled from the row (never overwrites a different value, never copies one another vehicle
  owns — both give an ImportSummary warning).
- Every schema field traces back to the REAL company paper documents (trimmed to what
  prediction needs). Keep `policy_no` / `renewing_policy_no` everywhere (renewal + claims
  anchors).
- **Never delete business data by cascade.** Deletes are archive-first (JSON snapshot into a
  `deleted_*` table, then delete); deleting something still referenced returns 409. Every
  archive row's `deleted_by` = the deleting user's username (since 2026-10-02).
- No Alembic: `Base.metadata.create_all()` creates NEW tables on startup but never ALTERs
  existing ones — any column change needs a manual `ALTER TABLE` (backup first).

## Database (25 tables)
`users`, `policyholders`, `insurance_cases`, `fire_property_surveys`,
`fire_property_quotations`, `fire_property_policies`, `fire_property_claims`, `vehicles`,
`motor_quotations`, `motor_policies`, `motor_claims`, `import_records`, `geocode_cache`,
`ml_models`, `ml_predictions`, and 10 archives `deleted_*` (policyholders, import_records,
fire_property_policies/quotations/surveys/claims, motor_policies/quotations/claims, vehicles).
- `risk_class` is one character: "a" (concrete) or "b" (concrete & wood/light).
- JSON columns: `occupancy_breakdown`, `boundaries`, `protection_facilities`,
  `perils_assessment`, `hazard_assessment` (surveys), `conditions` (fire quotations).
- GIS columns on `fire_property_surveys` and `motor_quotations`: `latitude`, `longitude`,
  `flood_risk_flag`, `flood_risk_category` (headline = worst of river / storm surge),
  `river_flood_category`, `storm_surge_category`. Fire quotations borrow GIS from their
  case's latest survey.
- `motor_quotations` / `motor_policies` have `sum_insured`.
- `fire_property_policies.premium` (was `unit_cost_premium` until 2026-10-05; renamed by
  `Backend/scripts/2026-10-05_premium_field.sql`) = Total Premium in pesos, before taxes. Maagap's
  real fire policy: Total Amount Due = Premium × 1.27 (DST 12.5% + FST 2% + VAT 12% + LGT 0.5%);
  v4 rows were filled with ROUND(total_amount_due / 1.27, 2). Upload header "Premium"; the old
  "Unit Cost Premium" header (a rate) is ignored. Fire quotation `total_premium` is unchanged (with
  taxes, as on Maagap's quotation form; policy↔quotation matching compares it with Total Amount Due).
- `import_records.import_type` is a native MySQL ENUM — a new import type needs a manual
  `ALTER TABLE ... MODIFY import_type ENUM(...)` as well as the Python enums.
- `users.username` has a unique index; the collation is case-insensitive.
- Fixed-list fields (claims) are `String(50)` + Pydantic validation via
  `schemas.canonical_choice()`, not SQL ENUMs.
- Not built (don't fabricate): renewal tables; an `insurance_cases` delete endpoint.
- A dropped table can come back if an OLD commit's `models.py` runs (e.g. `risk_predictions`
  did once) — stop uvicorn before checking out an old commit.

## Backend structure (`Backend/`)
- `main.py` — app, routers, `lifespan` → `ml.jobs.start_startup_refresh()`.
- `app/routers/`: `auth.py` (JWT login, `get_current_user` — reuse, don't rebuild),
  `users.py` (create account, change password), `policyholders.py`, `fire_property.py`,
  `motor_car.py`, `claims.py`, `stats.py` (all dashboard aggregates + `/stats/policy-forecast`),
  `ml.py` (`/ml/models`, `/ml/predictions/...`), importers `import_policyholders.py` (also the
  shared Needs Review queue + resolve), `import_fire_property.py` (survey/quotation/policy),
  `import_motor.py` (quotation/policy), `import_vehicle.py`, `import_claims.py`,
  `import_shared.py` (policy↔quotation matching, `parse_import_date`), `import_batch.py`
  (folder detect + upload). `upload.py` is an empty dead file.
- `app/services/flood_risk.py` (`lookup_flood_risk(address)`), `app/services/policy_forecast.py`.
- `app/ml/`: `features.py`, `logistic_regression.py`, `naive_bayes.py`, `metrics.py`,
  `training.py`, `predict.py`, `jobs.py`, `report.py`.
- `app/security.py`: hashing, `create_access_token`, `password_rule_error()`,
  `require_manager`.
- `scripts/reset_data.sql` — wipes business data (see "Reset script" below).
- Auth: every router requires a JWT (router-level `Depends(get_current_user)`) except
  `/login`. `require_manager` (403 "Manager access only.") guards all of `/stats`,
  `GET /ml/models/{name}` and `GET /ml/predictions/quotations`; `GET /ml/models` and
  `GET /ml/predictions/claims` and all CRUD/import endpoints are open to both roles.

## Frontend structure (`Frontend/src/`)
- Pages: `login.jsx`, `overview.jsx`, `proposal.jsx` (Quotations/Proposal),
  `distribution.jsx`, `renewal.jsx`, `claims.jsx` (all manager-only), `policy.jsx` (Policy
  Holder Information — every role; 6 tabs: Policy, Quotation, Claims, Client Information,
  Survey Report, Vehicle Information).
- `lib/`: `quotations.js` (`fetchAllQuotations()` join), `claims.js` (`fetchAllClaims()`),
  `ml.js` (predictions, `/ml/models`, `waitForModelRefresh()`), `passwordRule.js`.
- `components/`: `UploadFileModal.jsx` (single file + folder), `NeedsReviewModal.jsx`,
  `FloodRiskModal.jsx` (GIS view), `ModelShared.jsx`, `ClaimsShared.jsx`, `LegalModal.jsx`,
  `ChangePasswordModal.jsx`, renewal views. Legal text: `content/legal.js`.
- `api/api.js` — one 401 handler (clears login, "Your session has expired", back to `/`).
- Base styles must go in `@layer base` — unlayered element rules beat Tailwind classes (this
  broke light mode once).
- At phone width the sidebar (and Settings / Create Account) is hidden — known, not fixed.

## Key business rules
- **Bulk import matching**: `rapidfuzz.fuzz.token_sort_ratio`; ≥ 90 matched, 70–89
  needs_review (human), < 70 new. Fire/Property: exact normalized name alone = 100.
  Policyholder importer: exact name + exact address OR phone = 100; exact name alone is
  floored at 70 (review, never a silent duplicate). Motor matches vehicles by exact ID.
  Phones go through `normalize_phone()`; Excel cells through `clean_cell_value()` (pandas
  float ".0" bug). Each row is atomic (flush, one commit, rollback on error → `errors[]`).
- **Needs Review**: one queue for all importers; `PATCH /import/policyholders/records/{id}/resolve`
  branches on `import_type` and re-runs that importer's creation path. Policy rows can be
  resolved with a quotation pick, claims rows with a policy pick.
- **Folder import**: type detected from column headers (precision score, confident ≥ 55,
  margin 12); ambiguous files need a manual pick (minimal policy/claims files, Vehicle
  Information vs Motor Quotation). Processing order puts policies before claims.
- **⚠️ pandas NA words**: cells reading `None`, `NA`, `N/A`, `null`, `nan`, `#N/A` … are
  imported as BLANK in every importer (only Survey "Protection Facilities" keeps "None").
  Never use these words as meaningful values.
- Unreadable dates fail the row (blank dates allowed); claims amounts/dates that don't parse
  fail the row.
- Fire Quotation Location of Risk must be written exactly like its Survey's (abbreviations
  like "Brgy." don't match → new case without GIS).
- **GIS**: `lookup_flood_risk()` geocodes (Nominatim, 1 req/s, `geocode_cache` first — keep
  that table in resets), then classifies against river flood 100-yr
  (`gis_data/flood_hazard/...`) and storm surge SSA3 (`gis_data/storm_surge/...`), worst
  wins, with a 50 m boundary buffer. Never raises; failure = all-null fields, record still
  saved. Called from the 6 survey / motor quotation creation paths.
- **Claims**: link by Policy No. only; coverage-period rule on API, import and resolve;
  re-upload dedupe; policy delete with claims → 409. "Open" = final status not in Closed,
  Denied, CNC Only, Not Push Through; CNC Issuance rows are excluded from investigation pie,
  fraud rate and the fraud model.
- **Renewal rate** = Renewed ÷ (Renewed + Lost) × 100 (Pending excluded); renewal matched
  by same-line `renewing_policy_no`.
- **Policy Forecast** (Proposal card) is plain statistics, not ML: quotations/month ×
  conversion rate per line, waiting period W = p95 days quote→issue.
- **Passwords**: new ones need ≥ 8 chars incl. 2 letters, ≤ 72 bytes; login never checks the
  rule. New accounts are always role `admin`; only SQL can make a manager.
- **Usernames**: trimmed on create; `get_user_by_username` compares TRIM(username) to the
  trimmed input (login too), so "X " / " x" = "X" (case via the column collation).

## Models (current)
- Three models: `motor_lr`, `fire_lr` (Logistic Regression, Objective 1.2), `fraud_nb`
  (Naive Bayes, 1.3). LR: gradient descent, tol 1e-12, ≤ 50,000 epochs; L2 λ chosen on
  every training run by 5-fold CV from (0.0001, 0.001, 0.01, 0.1, 1, 10) — best mean ROC AUC, ties →
  larger λ; learning rate min(0.5, 1/λ) (λ = 10 at 0.5 diverged). The λ grid is in the
  fingerprint; the chosen λ + table are stored (`parameters.model.l2`, `metrics.l2_selection`).
  On 2026-10-02 data: Motor → 0.01, Fire → 0.001 (both inside the grid; λ = 0.0001 hits
  the 50,000-epoch cap).
  NB: Laplace α = 1, unseen-value rule, fraud cutoff **0.3**.
- LR row = ended policy (`period_to` < data date) described by its quotation; label =
  ≥ 1 Paid Claim with final status Closed / Waiting for LOA / Billing / Claim Check. NB row =
  investigated Paid Claim; Fraud = Suspected or Confirmed.
- `prior_counted_loss` (name kept) = the previous policy had a Paid Claim REPORTED before the
  quotation date, any outcome (since 2026-10-02; before: only counted losses). NB clues are
  known by the time a claim is investigated (8 at filing; docs date + repair estimate after).
- Risk levels: Low < base rate ≤ Medium < 2 × base rate ≤ High (Motor 0.21/0.41, Fire
  0.09/0.18).
- Active (v4 backup): motor_lr v2 (id 93), fire_lr v2 (94), fraud_nb v3 (95), all trained
  2026-09-27; accuracy cards = 5-fold CV means: Motor 64% / catches 51%, Fire 60% / 68%,
  Fraud 85% / 39%.
- Retraining: `Depends(schedule_model_refresh)` on 9 learning-data endpoints (survey, fire
  + motor quotation/policy uploads, both claims uploads, folder upload, Needs Review
  resolve) → background refresh after the response; retrains only if the data fingerprint
  changed, then rewrites all predictions. Startup trains only models with no active
  version. The fix round changed both LR fingerprints, so after a v4 restore the next
  refresh (upload / warm-up) retrains motor_lr and fire_lr (fraud_nb stays).
- Reports: `model_reports/<date>_<model>_v<N>.md` (gitignored). `python -m app.ml.training`
  (from `Backend/`) trains all three by hand.
- Paper notes: the walkthrough doesn't mention L2 (and its CV choice), Laplace smoothing, the
  unseen-value rule or the risk-level thresholds — each needs a sentence in Chapter 3/4.
- Known: a retrain slows other requests (same process); with the λ search (31 fits per LR,
  λ = 0.0001 runs the full 50,000 epochs) a refresh retraining Motor + Fire ≈ 3 min — the
  defense-morning warm-up measured 3 min 2 s on 2026-10-02 (was 28.6 s).
- Cards show CV accuracy, recall ("catches X%") and "AUC 0.NN (0.5 = guessing)".

## How to run
```
cd Backend
./venv/Scripts/python -m uvicorn main:app --reload --reload-dir app   # dev, http://127.0.0.1:8000
./venv/Scripts/python -m uvicorn main:app                             # DEMO / defense: no reloader
cd Frontend
npm run dev                                              # http://localhost:5173
npm run build / npm run lint
```
- Always `--reload-dir app` with `--reload`: `watchfiles` isn't installed, so uvicorn's fallback
  reloader polls every `.py` under the watched folder 4×/s — the whole `Backend/` (6,240 files,
  venv included) used ≈ 92 % of a CPU core while idle and slowed every page; `app/` only ≈ 9 %,
  no reloader ≈ 0 %. Edits to `main.py` (outside `app/`) need a manual restart.
- `--reload` doesn't watch `Backend/.env` — restart uvicorn after changing it. Stop uvicorn
  before checking out an old commit (see Database).
- `npm run lint` reports 45 old errors (mostly react-hooks `set-state-in-effect`); a change
  should not add any.
First-time setup (Python 3.14), from `Backend/`: `python -m venv venv`, then
`./venv/Scripts/python -m pip install -r requirements.txt` — it pins EVERY package (app +
tests + their dependencies) with `==`; `requirements-dev.txt` is only `-r requirements.txt`.
Frontend: `npm ci` (uses the committed `package-lock.json`).

## How to test
- From `Backend/`: `./venv/Scripts/python -m pip install -r requirements.txt` once, then
  `./venv/Scripts/python -m pytest tests` (186 tests, ≈ 14 min alone, ≈ 30 min while the backend runs — the LR λ search makes training tests slow). The `db` fixture runs on the dev DB
  inside one transaction that is always rolled back (no rows left; auto-increment ids are
  used up). API tests use `TestClient(app)` without `with`; stubs of `get_current_user` must
  return a manager-like object.
- Test records use a `ZZTEST` prefix; give unrelated test entities distinct name roots
  (Alpha/Bravo/…) — a shared prefix word makes rapidfuzz match them to each other.
- Build small Excel files that target the exact edge case; verify with direct queries, not
  just summary counts. Delete test rows by exact id, or restore v4b afterwards.
- MySQL Workbench Safe Update Mode blocks `DELETE ... WHERE id NOT IN (...)`.

## How to restore (v4b presentation backup — the one to use until the Oct 12 load)
`Desktop\insurance_db_backup_loaded_v4b_premium_20261005_233915.sql` = v4 (v2 synthetic dataset +
trained models) after the 2026-10-05 Premium migration (`fire_property_policies.premium`, 876 rows
filled). 25 tables; users = Aaron James only, with the password as of the backup. Test-restored
into a scratch database on 2026-10-05: all 25 counts and CHECKSUM TABLE values identical.
**Do not restore the old v4 file** (`…_v4_20260928_195453.sql`): it still has `unit_cost_premium`,
and the app now expects `premium`. Stop uvicorn first, then:
```
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p insurance_db -e "source C:/Users/aaron/OneDrive/Desktop/insurance_db_backup_loaded_v4b_premium_20261005_233915.sql"
```
⚠️ Never pipe a dump into mysql with PowerShell 5.1 (`Get-Content … | mysql`): it sends ASCII and
turns "ñ" into "?" (seen 2026-10-05 in a test restore). Use `-e "source <path>"` (path without
spaces) or Workbench. Write dumps with `mysqldump --result-file=…`, not `>` (UTF-16).
(Workbench: Server → Data Import → Self-Contained File → target `insurance_db`.) Start the
backend; it doesn't retrain (models are active), it only rewrites predictions (~10 s).
Expected counts: policyholders 1,129 · cases 1,224 · surveys 481 · vehicles 743 · motor
quotations 1,450 · fire quotations 1,032 · fire policies 876 · motor policies 1,139 · motor
claims 351 · fire claims 90 · import_records 6,548 · geocode_cache 500 · ml_models 7 · users
1 · all `deleted_*` 0 · ml_predictions ≈ 1,045–1,051 (date-dependent). Afterwards delete any
`model_reports/` files created since (list by exact name first). Older backups (v3, v2, v1,
pre-reset): see `docs/history/backups_and_demo.md`.

**Reset script** `Backend/scripts/reset_data.sql`: empties 23 tables, keeps `geocode_cache`
and the user `Aaron James`. TRUNCATE can't be undone — full `mysqldump` backup first. Never
run it without an explicit instruction. Any new table must be added to it (or listed as kept).

## Defense demo (summary)
Script `data_prep/demo/make_demo_upload.py --quote-date <yesterday> --copy-to
"C:/Users/aaron/OneDrive/Desktop/FIREMAP_demo_upload"` writes 4 Excel files (2 new clients:
Dimaculangan / Panghulo → High storm surge; Pagsisihan / Canalate → Medium river).
Morning: restore v4b → start backend the demo way (`./venv/Scripts/python -m uvicorn main:app`,
no `--reload`) → warm-up from `Backend/`:
`./venv/Scripts/python -c "from app.ml import jobs; jobs.refresh_now('pre-demo warm-up'); print(jobs.status)"`
→ regenerate the folder → open Proposal once. Live: Policy Holder Info → Upload → Folder →
Import All → Proposal, search the client names, GIS View. Fallbacks: FQ-1002 Reynaldo
Isidro Pelayo (High river); claims MS2602030016 (#83, Suspicious 56%) and MS2501030071 (#248,
39%). Screenshots: `Desktop\FIREMAP_demo_screenshots\`. Full steps, timings and caveats:
`docs/history/backups_and_demo.md`.

## Security notes
- Never read or print passwords, hashes, tokens or `.env` values. Never change the Aaron
  James account. For API tests, mint tokens with the app's own `create_access_token`; for a
  real login test, use a temporary ZZTEST user.
- `.env` and `Backend/.env` are gitignored, but `Backend/.env` WAS committed in the initial
  commit (still in pushed history). SECRET_KEY was rotated on 2026-10-01 (only in
  `Backend/.env`, never committed). The `DATABASE_URL` in that initial commit contains the
  old MySQL root password, which was already rotated earlier in the project, so it no
  longer works.
- JWTs are stateless, 60 min, never revoked; no forgot-password flow.
- No response ever contains a password hash: `POST /users` returns `schemas.UserOut` (id,
  username, role) via `response_model`; reuse `UserOut` for any future user endpoint
  (`tests/test_user_responses.py`, 2026-10-03).
- Geocoding sends only the address and a generic User-Agent to Nominatim — no personal
  contact data.

## Current status and open items
- All objectives built; main is at the pre-defense fixes (`244bfdb`), data = v4b (v4 + Premium migration, 2026-10-05). The fix
  round for validation Phases 0–8 is on branch `fix-round` (2026-10-02, not yet merged).
- Open / known (not fixed):
  - Backend requests slow down while a retrain runs (refresh shares the web process).
  - No `insurance_cases` delete endpoint.
  - Phone width hides the sidebar (Settings / Create Account unreachable on a phone).
  - Motor colour control weight is still ≈ +0.37 (P6.28 "Addressed": CV keeps λ = 0.01).
  - λ = 0.0001 fits stop at the 50,000-epoch cap (not converged; never chosen so far).
  - Created/changed records store no user (only deletes record `deleted_by`).
  - Policy Forecast card makes the Proposal right column taller (white space under table).
  - Some real barangay addresses no longer geocode via Nominatim (`not_found`).

## Validation in progress
Full pre-defense validation in 11 phases (0–10), prompts in
`C:\Users\aaron\Downloads\firemap_validation_prompts\validation\validation-phase-NN.md`,
log in `docs/validation/VALIDATION_LOG.md` (not committed). Rules: never change code/tests/
docs during it (report, don't fix); write phases use only ZZTEST records and end with a v4
restore + proof (25 counts, highest ids, 3 active models); stop after each phase. Phases
0–8 COMPLETE (2026-10-01); their items were fixed in the fix round (branch `fix-round`,
2026-10-02, each marked in the log). Phases 9–10 run later, on the new v3 dataset.

## Index — docs/history and references
- `docs/SYSTEM_REFERENCE.md` — every page, number, method, glossary, §18 found issues.
- `docs/history/CLAUDE_full_2026-10-01.md` — the complete CLAUDE.md before this rewrite.
- `docs/history/architecture.md` — Project Overview, Tech Stack, Critical Architecture
  Decisions, Database Schema, Backend Structure (original versions).
- `docs/history/imports.md` — Bulk Import Matching Logic, Needs-Review Resolution,
  Folder-Based Bulk Import, Importer-wide None/NA warning.
- `docs/history/gis.md` — GIS Flood-Risk Lookup Service, Hazard Boundary Buffer (50 m)
  investigation, Storm Surge Hazard Data.
- `docs/history/claims.md` — Claims Phases 1–4 (tables, API, importer, frontend).
- `docs/history/models.md` — Models Phases 1–3, Policy Forecast.
- `docs/history/data_prep.md` — Data Prep Changes 1–6, Steps 3–5 (address pool, synthetic
  v1/v2 loads).
- `docs/history/backups_and_demo.md` — v3 and v4 backups, How to restore (all backups),
  Demo upload folder.
- `docs/history/polish_and_fixes.md` — Polish pass, Pre-defense fixes, Known Remaining
  Issues, Duplicate usernames, Password rules, Terms of Service + Privacy Policy.
- `docs/history/frontend.md` — Frontend Status (page-by-page build history).
- `docs/history/testing_and_next_steps.md` — Testing Conventions, Immediate Next Steps.
- `docs/Algorithm_Walkthrough_LogisticRegression_NaiveBayes.docx`,
  `docs/Naive_Bayes_Paper_Section.docx` — the algorithm documents the models follow.
