# MAAGAP Insurance Capstone — Project Memory

## Project Overview
Insurance capstone system for "Maagap" insurance company. Predicts claim
probability of a future quotation using pre-policy data (survey/vehicle info),
manages customer retention, and uses GIS/flood data as a prediction variable.
Presentation deadline: ~September 2026 (tight — favor simplest defensible
architecture over theoretical elegance).

Study objectives (do not lose these from scope):
1.1 Policyholder Information Management — manage policyholder/client records
1.2 Predictive Risk Management — covers BOTH Fire/Property AND Motor/Car,
    must predict BEFORE quotation is issued (not from an already-issued policy)
1.3 Fraud Detection Assessment — claim-stage, separate from pre-policy
    prediction; blocked, no claims data available yet
1.4 Client Retention Management — retention rate from renewal data;
    blocked, no renewal data available yet, no formula invented
2.1 Geospatial Flood Prone Mapping — part of Fire/Property predictive risk,
    via QGIS API (not yet implemented)
2.2 Bulk Client Data Import & Validation — DONE (see below)

## Tech Stack
- Frontend: React + React Router + Vite, Tailwind CSS, lucide-react icons, axios
- Backend: Python FastAPI + SQLAlchemy ORM + Pydantic schemas + bcrypt
- Database: MySQL (via pymysql), dev server at http://127.0.0.1:8000
- Frontend dev server: http://localhost:5173 (Vite default)
- ML/GIS: not yet started

## Critical Architecture Decisions (do not relitigate these)
- **Insurance Case concept**: internal, system-generated grouping —
  Policyholder → Insurance Case (line_type: fire_property | motor_car) →
  Survey/Quotation/Policy (Fire/Property) or Vehicle/Quotation/Policy (Motor).
  Exists because company source documents have NO universal identifier
  linking them — matching relies on name/address/phone/vehicle-ID instead.
- One Insurance Case can have MULTIPLE quotations (re-quotes reuse the case).
- A policy always links to the exact quotation it came from (required FK).
- Primary keys: auto-increment integers, not UUIDs.
- Both Fire/Property and Motor/Car MUST connect to Predictive Risk Management
  in every diagram/design — this was explicitly corrected once before.
- Prediction must use PRE-POLICY data, never the issued policy itself.
- Database engine is MySQL (not Postgres) — GIS flood result will be stored
  as plain lat/lng + flood_risk_flag columns, not MySQL spatial types.
- Business "Name of Insured" (Fire/Property Survey has no first/last split)
  is stored in `policyholders.last_name` as the whole business name,
  `first_name` left NULL. `PolicyholderOut.first_name` is Optional for
  this reason — do not make it required again.
- Fire/Property survey import: if a matched policyholder's new survey
  duplicates an EXISTING survey (by location_of_risk similarity), skip
  creating a new case. If not a duplicate, create a new case.
- Motor/Car import: exact match on plate_no OR motor_engine_no OR
  serial_chassis_no alone is enough to call it the same vehicle. A re-quote
  for a known vehicle reuses its existing case (doesn't create a new one)
  unless it's an exact duplicate quotation (same date+amount), which is
  skipped entirely.

## Database Schema (current state)
Tables: users, policyholders, insurance_cases, import_records,
deleted_policyholders, deleted_import_records,
fire_property_surveys, fire_property_quotations, fire_property_policies,
vehicles, motor_quotations, motor_policies, risk_predictions.

- `deleted_policyholders` / `deleted_import_records`: archive tables for
  deletes (see "Delete + archive pattern" below). New tables rather than a
  soft-delete flag on the live tables specifically because `create_all()`
  doesn't ALTER existing tables — adding a column to `policyholders` would
  need a manual migration, adding a new table doesn't.

Schema was deliberately TRIMMED from the original design:
- Dropped paperwork-only identity fields (proof_provided, beneficiaries_names,
  gsis_umid, other_identity_evidence, source_of_income_funds,
  application_number, place_of_birth) — no prediction value.
- Consolidated checklist-style fields into JSON columns:
  `occupancy_breakdown`, `boundaries`, `protection_facilities` (surveys),
  `conditions` (fire property quotations) — reduces column clutter, doesn't
  lose data, doesn't affect ML feature engineering (that happens in Python
  regardless of SQL column shape).
- Deliberately KEPT `policy_no` / `renewing_policy_no` everywhere — these are
  the anchor fields future claims/renewal data will join against. Do not
  remove these even though claims/renewal aren't implemented yet.
- NOT YET BUILT (do not fabricate): Claim, FraudAssessment, Renewal tables —
  wait for real data/field definitions before designing these.
- `risk_class` is a single character: "a" (concrete) or "b" (concrete &
  wood/light materials) — validated both in Pydantic (manual endpoint) and
  explicitly in the bulk import row parser (which bypasses Pydantic).
- **Delete + archive pattern**: `DELETE /policyholders/{id}` and
  `DELETE /import/policyholders/records/{id}` don't hard-delete — they write
  a full JSON snapshot of the row into `deleted_policyholders` /
  `deleted_import_records` first, then delete the live row.
  `GET /deleted-policyholders` and `GET /import/policyholders/deleted-records`
  can read the archive back (no frontend view built for these yet).
  Deleting a policyholder is **blocked with 409** if they still have any
  `insurance_cases` on file — real business data (surveys/quotations/
  policies) is never cascade-deleted automatically; that would need an
  explicit decision first. Any `import_records` still pointing at a deleted
  policyholder get unlinked (`matched_policyholder_id → NULL`), not deleted,
  since they're independent audit-trail rows.

No Alembic — `Base.metadata.create_all(bind=engine)` in main.py auto-creates
tables on startup. It does NOT alter existing tables, so schema changes to
an existing table require manually dropping+recreating that table (or ALTER
by hand) — this bit us once already (see reset script below).

## Backend Structure
`Backend/app/routers/`:
- `auth.py` — existing JWT login system (already works, has
  `get_current_user` dependency ready to reuse — do NOT rebuild auth from
  scratch, just add `Depends(get_current_user)` to endpoints that need it)
- `users.py` — user creation (requires manager role)
- `policyholders.py` — Policyholder + InsuranceCase CRUD
- `fire_property.py` — Fire/Property survey/quotation/policy CRUD
- `motor_car.py` — Motor/Car vehicle/quotation/policy CRUD
- `import_policyholders.py` — bulk import for Customer Information
- `import_fire_property.py` — bulk import for Fire/Property Surveys
- `import_motor.py` — bulk import for Motor/Car Quotations

**Auth on CRUD/import endpoints: DONE.** `policyholders.py`, `fire_property.py`,
`motor_car.py`, `import_policyholders.py`, `import_fire_property.py`, and
`import_motor.py` all now require a valid JWT via
`dependencies=[Depends(get_current_user)]` at the `APIRouter(...)` level
(router-wide, rather than per-endpoint like `users.py` does it — same
effect, less repetition). Verified: unauthenticated `GET /policyholders`
returns 401, `/login` still works unauthenticated, `/docs` loads. All
frontend callers (`policy.jsx`, `UploadFileModal.jsx`, `NeedsReviewModal.jsx`)
already sent `Authorization: Bearer <token>` before this change, so nothing
on the frontend needed updating.
`Backend/app/routers/upload.py` exists but is empty and not imported in
`main.py` — dead file, left alone.

## Bulk Import Matching Logic (all 3 importers share this pattern)
- Fuzzy matching via `rapidfuzz.fuzz.token_sort_ratio` on name (+ phone as
  corroborating evidence for Policyholders/Fire-Property; Motor/Car matches
  vehicles by exact identifier instead, not fuzzy name).
- Thresholds: score >= 90 → matched, 70–89 → needs_review (paused for human,
  NOT auto-created), < 70 → confidently new, auto-created.
- `needs_review` rows are added to an in-memory "pending" pool so later
  duplicates IN THE SAME UPLOAD still get linked to them correctly (fixed
  bug: originally only compared against confirmed DB records).
- Policyholder-level matching for Fire/Property does NOT use location_of_risk
  as an address signal (fixed bug: same company insuring 2 different
  properties was wrongly scored as "different companies" because their
  locations differ — location-based duplicate detection happens separately,
  at the SURVEY level, not the policyholder level).
- Phone comparison uses `normalize_phone()` — strips PH country code (63)
  and local trunk prefix (0) so "+63 917 123 4567", "09171234567", and
  "9171234567" all normalize to the same value. A naive "keep last 10
  digits" approach does NOT work correctly for landlines (fixed bug).
- `clean_cell_value()` helper is critical: any blank cell in an otherwise-
  numeric Excel column (phone, plate no., engine no.) makes pandas upcast
  the WHOLE column to float64, corrupting every value with a trailing ".0".
  This silently broke duplicate-vehicle detection once (Motor/Car matching
  is EXACT string match, most vulnerable to this). Always use
  `clean_cell_value()` instead of raw `str(value)` when parsing Excel rows.
- **FIXED**: Fire/Property's `match_score()` is `name_score*0.8 +
  phone_match*0.2`. When a survey row has no phone number (common — surveys
  often have a blank `tel_fax_no`), phone_match is always 0, capping the
  score at 80 no matter how exact the name match is — inside the
  needs_review band (70–89), never reaching the 90 matched threshold. Found
  via end-to-end testing: an IDENTICAL policyholder name with no phone data
  never auto-matched, so every repeat survey from the same client routed to
  needs_review instead of being recognized automatically — and the
  survey-level duplicate check further down never even got a chance to run.
  Fixed with an explicit short-circuit in `match_score()`: a
  character-for-character identical normalized name (`cn == en`, both
  non-empty) returns 100 and matches on its own, regardless of phone data.
  Deliberately NOT a reweight of the 0.8/0.2 split — that would have also
  loosened near-matches; the short-circuit only affects the exact-match
  case, leaving fuzzy-match behavior with a wrong/missing phone unchanged.
  Re-verified end-to-end after the fix: the same 3-row test file now gives
  1 matched (true duplicate correctly auto-matched, no new survey/case
  created), 2 new (one per distinct property), 0 needs_review.
  The plain Policyholder importer's `match_score()` had the same structural
  bug, in a WORSE form — see below, also fixed.

- **FIXED**: Policyholder importer's `match_score()` is
  `name*0.6 + addr*0.25 + phone*0.15`. Same shape as the Fire/Property bug
  above, but a more dangerous failure mode: with an exact name match and no
  address/phone data, the score is only 60 — BELOW `REVIEW_THRESHOLD` (70),
  not just below `MATCH_THRESHOLD`. That means it was scored "confidently
  new" and silently created a duplicate `Policyholder` with no human review
  at all — worse than Fire/Property's version, which at least parked
  unresolved rows in needs_review instead of duplicating them outright.
  Fixed with a similar but more conservative short-circuit than
  Fire/Property's: exact name alone is NOT enough to auto-match (unlike
  company names, individual person names collide more plausibly — two
  different "Juan Dela Cruz" is a real risk). Instead: exact name +
  (exact address OR exact phone) → matched (100); exact name with NO
  corroborating signal at all → floored at exactly `REVIEW_THRESHOLD`
  instead of falling to "new", so it's always at minimum flagged for a
  human, never silently duplicated. Verified end-to-end with a 4-row test
  file: exact-name+exact-address (no phone) row 2 now matches instead of
  landing at 85/needs_review; exact-name-only (no address/phone) row 4 now
  goes to needs_review instead of silently creating policyholder #3 — only
  2 policyholders exist after the upload, not 3.
- Each row is processed atomically: intermediate creates use `db.flush()`
  (not `db.commit()`) to get IDs without finalizing, with ONE `db.commit()`
  at the very end of a successful row. Any exception → `db.rollback()`,
  record row number + error in the response, continue to next row. This
  means one bad row never crashes the whole upload AND never leaves
  orphaned partial records (both were bugs before this pattern was added).
- `ImportSummary` response includes `failed: int` and
  `errors: list[{source_row, error}]` for this reason.

## Needs-Review Resolution (`import_records.import_type`)
All three importers share ONE `needs_review` queue and ONE resolve endpoint
(`PATCH /import/policyholders/records/{id}/resolve`, historically named
after the Policyholders importer but generic in practice). `ImportRecord`
has an `import_type` column (`policyholder` | `fire_property` | `motor`,
`models.ImportType`) set by whichever importer created the row — added
specifically because the resolve endpoint used to ALWAYS create a bare
`Policyholder` regardless of origin. **Fixed bug** (found via end-to-end
browser testing of the newly-wired Fire/Property and Motor upload paths):
resolving a Fire/Property or Motor needs_review row was silently creating
an empty `Policyholder` (`first_name`/`last_name` both NULL) and NEVER
creating the associated `InsuranceCase`/`FirePropertySurvey`/`Vehicle`/
`MotorQuotation` — the row's actual survey/vehicle data was discarded with
no error. Now `resolve_import_record()` in `import_policyholders.py`
branches on `record.import_type`:
- `policyholder` → unchanged original behavior.
- `fire_property` / `motor` → after resolving the policyholder (link or
  create-new, using each importer's own field mapping via
  `new_policyholder_fields()`), calls that importer's
  `resolve_for_policyholder(db, record, policyholder_id)` — defined in
  `import_fire_property.py` / `import_motor.py` — which re-runs the SAME
  duplicate-check + case/survey/vehicle/quotation creation the main upload
  path uses, so a manually-resolved row ends up identical to what auto-
  matching would have produced.
`import_policyholders.py` imports `import_fire_property` and `import_motor`
for this (safe — neither of those two imports anything from
`import_policyholders`, no circular import).
`import_records.import_type` was added via a manual `ALTER TABLE` (the
table was empty in dev at the time — `create_all()` doesn't ALTER existing
tables, same caveat as everywhere else in this doc). If this is deployed
anywhere with existing `import_records` rows, backfill `import_type`
manually before relying on resolve for old needs_review rows.

## Known Remaining Issues (not yet fixed)
None currently tracked here — see "Duplicate usernames in `users`" below
for the last one, which is fixed.

## Duplicate usernames in `users` — FIXED
The `username` column had `unique=True` in the model but the LIVE table had
no such constraint (`create_all()` doesn't ALTER existing tables — same
caveat as everywhere else in this doc), so two duplicate pairs had already
snuck in: `test4` (ids 16 & 17) and, found while fixing that — MySQL's
`utf8mb4_0900_ai_ci` collation is case-insensitive, so `james` (id 3) and
`James` (id 4) were ALSO colliding as duplicates and blocked the fix until
resolved too. Per user decision: kept the older row in both cases (id 16
`test4`, id 3 `james`), deleted the newer duplicate (id 17, id 4). Then
added the missing constraint live: `ALTER TABLE users ADD UNIQUE INDEX
ix_users_username_unique (username)` — 16 users remain (was 18).
`users.py`'s `create_user` already pre-checks `get_user_by_username()`
before insert (and that check is case-insensitive too, same collation), so
this shouldn't recur in the normal flow — the new constraint is a
defense-in-depth safety net for a race between that check and the commit.
Wrapped the `db.commit()` in `try/except IntegrityError` so that race
returns the same clean `400 "User already exists"` instead of a raw 500.
Verified via the real `/users` endpoint (not just direct SQL): attempting
to create `test4` again now returns 400, no server error.

## Frontend Status
- `pages/login.jsx` — fully wired to `POST /login`, tested working
  end-to-end (JWT token + role stored in localStorage on success).
- `pages/policy.jsx` — Policyholder Information page, 5 tabs (Policy,
  Quotation, Claims, Client Information, Survey Report) via a type
  dropdown + shared table/search/pagination toolbar.
  - "Client Information" tab: DONE — fetches `GET /policyholders`
    (axios, `API_BASE_URL = "http://127.0.0.1:8000"`, sends
    `Authorization: Bearer <token>` from `localStorage` when present) via a
    `fetchClients` callback run on mount. `DATA_MAP` is built inside the
    component (not module scope) so it can include live `clientRecords`
    state. Stat card shows `clientRecords.length` (real count), not a
    hardcoded number. Mock `clientData` array is gone.
  - `ClientTable`'s "Age" column was removed (backend has no age/birthdate
    field) — do not re-add it. It now also has a trash-icon delete column
    (see below).
  - **Needs Review UI**: `components/NeedsReviewModal.jsx` (new) — lists
    rows from `GET /import/policyholders/needs-review`, lets staff either
    link a row to an existing client (dropdown populated from
    `clientRecords`) via `PATCH .../records/{id}/resolve`, or force-create
    it as new. Opened via a "Needs Review" button next to Upload with a
    red count badge. `policy.jsx` holds `needsReviewRecords` state and a
    shared `refreshClientData()` (refetches both clients and needs-review)
    called after upload success, resolve, and delete.
  - **Delete buttons**: both `ClientTable` rows and `NeedsReviewModal` rows
    have a trash icon → `window.confirm()` → `DELETE` call → archive (see
    "Delete + archive pattern" above) → `refreshClientData()`. Deleting a
    client with existing insurance cases will fail with a 409 — this is
    backend-enforced, not just a frontend check.
  - **Policy tab**: DONE — fetches `GET /fire-property/policies` +
    `GET /motor/policies` (both, merged) with the same auth-header pattern
    as Client Information.
  - **Quotation tab**: DONE — fetches quotations AND policies from both
    lines (fire_property + motor_car) so it can resolve each quotation's
    "Converted Policy No." via a quotation_id → policy_no map.
  - **Survey Report tab**: DONE — fetches `GET /fire-property/surveys`.
  - **Claims tab**: still mock `claimsData` — correctly blocked, no claims
    backend exists (see Study Objectives 1.3/scope notes above).
  - `components/UploadFileModal.jsx`: DONE for Policyholders only — it was
    completely unwired before this session (just faked an "Uploaded!"
    state locally, never called the backend). Now it actually
    `POST`s to `/import/policyholders/upload` as multipart form data,
    shows the real `ImportSummary` (matched/new/needs-review/failed
    counts) or the backend error, and calls an `onUploadSuccess` prop on
    success (wired to `refreshClientData`). It is NOT wired to the
    Fire/Property (`/import/fire-property/surveys/upload`) or Motor
    (`/import/motor/quotations/upload`) importers yet — do that when
    connecting the Policy/Quotation/Survey Report tabs.
- `pages/overview.jsx`, `pages/proposal.jsx`, `pages/distribution.jsx` —
  all mock dashboard/chart data, would need new backend aggregation
  endpoints (none exist yet) before connecting.
- `pages/renewnal.jsx` — blocked, no renewal data/backend yet.
- `components/FloodRiskModal.jsx` — blocked, GIS feature not built yet.

## Testing Conventions Established This Session
- Always test with a FULL DATABASE RESET first for trustworthy results —
  leftover test data from earlier manual testing has caused false results
  more than once. Reset script:
  ```sql
  SET FOREIGN_KEY_CHECKS = 0;
  TRUNCATE TABLE import_records;
  TRUNCATE TABLE risk_predictions;
  TRUNCATE TABLE motor_policies;
  TRUNCATE TABLE motor_quotations;
  TRUNCATE TABLE vehicles;
  TRUNCATE TABLE fire_property_policies;
  TRUNCATE TABLE fire_property_quotations;
  TRUNCATE TABLE fire_property_surveys;
  TRUNCATE TABLE insurance_cases;
  TRUNCATE TABLE policyholders;
  SET FOREIGN_KEY_CHECKS = 1;
  ```
  (Never touches `users`.)
- Prefer building a small realistic Excel test file that deliberately
  targets the specific edge case being tested (exact duplicate, near-
  duplicate with a different-but-related record, a genuinely different
  record that merely looks similar) over trusting aggregate pass/fail
  counts alone — aggregate counts have hidden real bugs before (e.g. a
  wrong case being reused looked identical to a correct one in the summary
  numbers; had to verify via `GET /policyholders/{id}/insurance-cases`
  directly).
- MySQL Workbench 8.0 is the DB tool in use. Safe Update Mode blocks
  `DELETE ... WHERE id NOT IN (...)` — use `WHERE id > N` instead, or
  toggle `SET SQL_SAFE_UPDATES = 0` for one query.

## Immediate Next Steps (in order)
1. ~~Finish wiring `policy.jsx`'s Client Information tab~~ — DONE. Also
   picked up along the way: wired `UploadModal` to the real
   `/import/policyholders/upload` endpoint (was previously a fake local-only
   UI), built the Needs Review modal + resolve flow, and added delete +
   archive-table endpoints for both policyholders and import records. See
   "Frontend Status" and "Delete + archive pattern" above.
2. ~~Add authentication to all CRUD and bulk import endpoints~~ — DONE, see
   Backend Structure above.
3. ~~Connect Policy/Quotation/Survey Report tabs to real backend endpoints~~
   — DONE, see Frontend Status above.
4. ~~Wire `UploadModal` to the Fire/Property and Motor importers~~ — DONE.
   `UploadModal` now has an importer-select dropdown (Policyholders /
   Fire & Property Surveys / Motor Quotations), defaulting per the active
   tab via `IMPORT_TARGET_BY_TYPE` in `policy.jsx`. End-to-end tested in a
   real browser, which surfaced two backend bugs — both FIXED this session:
   the needs_review phone-weighting issue (see Bulk Import Matching Logic
   above) and the needs-review resolve data-loss bug (see Needs-Review
   Resolution above).
5. GIS/flood-risk integration (Objective 2.1) — not started.
6. Predictive risk model (Objective 1.2 core) — not started, blocked on
   having enough real data flowing through the system first.