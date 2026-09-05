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

Every field in this schema traces back to the REAL company paper documents
(surveys, quotations, policies) — the user extracted the fields directly
from that paperwork, then had a Claude session clean/trim the extracted
set down to what's actually useful for predictive risk. The schema below
is that trimmed result, not a cut-down version of some other pre-existing
design:
- Dropped paperwork-only identity fields (proof_provided, beneficiaries_names,
  gsis_umid, other_identity_evidence, source_of_income_funds,
  application_number, place_of_birth) — present on the real paperwork, but
  no prediction value, so left out of the schema.
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
- `import_policyholders.py` — bulk import for Customer Information; also
  hosts the shared needs-review queue/resolve endpoint used by ALL importers
- `import_fire_property.py` — bulk import for Fire/Property Surveys,
  Quotations, and Policies (3 importers in one file, see "Folder-Based Bulk
  Import" below)
- `import_motor.py` — bulk import for Motor/Car Quotations and Policies (2
  importers in one file)
- `import_shared.py` — cross-cutting logic reused by the 2 Policy importers
  only (quotation-matching heuristic, name/address splitting) — see below
- `import_batch.py` — folder upload: column-header type detection +
  dispatches each file to the importer above matching its confirmed type

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
All importers share ONE `needs_review` queue and ONE resolve endpoint
(`PATCH /import/policyholders/records/{id}/resolve`, historically named
after the Policyholders importer but generic in practice). `ImportRecord`
has an `import_type` column (`models.ImportType`: `policyholder` |
`fire_property` | `motor` | `fire_property_quotation` |
`fire_property_policy` | `motor_policy`) set by whichever importer created
the row — added
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

## Folder-Based Bulk Import (batch upload, all 6 document types)
User can now select a whole FOLDER of mixed Excel/CSV files at once and the
system figures out which importer each file belongs to by reading its
COLUMN HEADERS (not filename), rather than uploading one file at a time
with a manually-picked type. Covers all 6 real document types: Customer/
Policyholder Info, Fire/Property Survey, Fire/Property Quotation, Fire/
Property Policy, Motor Quotation, Motor Policy. The last 3 of those had
**no bulk-import logic at all before this** (only one-at-a-time CRUD) —
built from scratch this session.

**⚠️ Header WORDING (not the fields themselves) is unconfirmed for
Fire/Property Quotation, Fire/Property Policy, and Motor Policy.** The
`models.py` fields these 3 importers map to are NOT a guess — they trace
back to the real company paper documents (user extracted the fields from
the actual paperwork, had them cleaned/trimmed down to what predictive
risk needs, and the schema is that trimmed result — same origin as every
other table in this schema). What's genuinely unconfirmed is only the
exact HEADER TEXT a real spreadsheet export would use for each field
(e.g. "Policy No." vs "Policy Number" vs "Policy #") — the `*_COLUMN_MAP`s
in `import_fire_property.py`/`import_motor.py` guess plausible header
wording for the right fields, but that exact wording needs confirming
against a real export once one is available, since both the column
mapping AND the header-detection scoring below match on exact text.

**Policy-to-quotation matching (the hard part)**: `FirePropertyPolicy.
quotation_id` / `MotorPolicy.quotation_id` are REQUIRED FKs, but there's no
shared ID between a policy row and a quotation row in the source data
(only `insured_name_address`, a single combined field — no policy/
quotation number that ties them together). `import_shared.
find_best_unattached_quotation()` scores a policyholder's still-open
quotations (no policy attached yet) by amount + date proximity to the
policy row being imported (`amount_score*0.7 + date_score*0.3`,
`CONFIDENT_THRESHOLD=75`, `AMBIGUITY_MARGIN=15` between top two
candidates) — same "tune later with real data" status as every other
threshold in this file. Zero or ambiguous candidates → the row lands in
`needs_review` with `matched_policyholder_id` ALREADY set (unlike the other
importers' needs_review rows) — this is what lets the frontend tell "still
need a policyholder decision" apart from "policyholder known, still need a
quotation pick" without a new status value.

**Quotation-picker in Needs Review** (per user's explicit choice — not
punted to `/docs`): for a stuck Policy row, `NeedsReviewModal.jsx` calls
`GET /import/policyholders/records/{id}/quotation-candidates` and shows a
dropdown of that policyholder's open quotations (amount/date/case) instead
of the usual Link/Create-as-new policyholder controls. Confirming calls
`PATCH .../resolve` with a NEW `matched_quotation_id` field (third
resolution path in `resolve_import_record()`, checked before the
policyholder-link/create-new paths) which directly creates the Policy from
the chosen quotation — bypassing the amount/date heuristic entirely since a
human already decided.

**Policyholder-matching consistency fix during implementation**: the two
Policy importers initially used a separate 3-signal (name/address/phone)
matcher in `import_shared.py`, modeled on the Policyholder importer's own
individual-collision-averse formula. Caught via testing that this was
inconsistent — Fire/Property entities are predominantly businesses (same
as Survey/Quotation, which use a lenient exact-name-matches formula), so a
policyholder that already auto-matches via Survey needed EXTRA
corroboration to match via Policy, purely because of which importer it
came through. Fixed by having each Policy importer reuse ITS OWN line's
existing `match_score()` (Fire/Property's exact-name short-circuit, or
Motor's plain name fuzzy-ratio) on just the extracted name, dropping the
separate 3-signal formula entirely (removed from `import_shared.py`).

**Header-detection scoring** (`import_batch.py`'s `score_against_map()`):
started as an F1 (precision+recall) score against each importer's column
map, which badly UNDER-scored realistic files — a real customer-info
export with only 2 populated columns scored 21/100 against a 17-column map
purely from low recall, even though every header it had was an exact,
unambiguous match. Switched to PRECISION-only (what fraction of the
file's OWN headers belong to this type), with a single coincidentally-
shared column (e.g. "Date", used by several types) dampened rather than
trusted at full strength. `DETECT_CONFIDENT_SCORE=55`, `AMBIGUITY_MARGIN=
12`. Fire/Property Policy and Motor Policy share almost all their columns
(only a handful of line-specific ones differ, e.g. `sum_insured`/
`construction` vs `coc_no`/`endorsement_no`) — a minimal policy file using
only the shared columns is DELIBERATELY left undetected
(`ambiguous: true`, `best_guess: null`) rather than silently guessed, and
the UI forces a manual type pick for it. This is real, not just a testing
edge case — expect genuinely minimal policy exports to need manual
selection until enough distinguishing columns are typically present.

**Testing gotcha worth remembering**: rapidfuzz's `token_sort_ratio`
treats a shared prefix WORD as a guaranteed matching token — test entities
that are all prefixed with the same marker word (e.g. every test policyholder
named "ZZBATCH ...") can fuzzy-match EACH OTHER above `REVIEW_THRESHOLD`
purely from that one shared token, even when otherwise completely
unrelated (e.g. "ZZBATCH Motor Owner" vs "ZZBATCH Client One" scored
70.27 — just over the line). Cost real debugging time before being traced
to test data, not app logic. Real customer names won't share an artificial
common prefix like this, so it's a testing convention to avoid, not a
product bug: give unrelated test entities in the same run genuinely
distinct name roots (this session settled on different NATO-alphabet words
— Alpha/Bravo/Charlie/... — as prefixes instead of a shared marker).

Verified via a 33-check automated regression (header detection for all 6
types + 1 deliberately-ambiguous file, folder upload end-to-end, zero/one/
many-candidate policy matching, the quotation-picker resolve path, and
re-verification of all 3 pre-existing importers' resolve flows for
regressions) plus a live browser pass (drag a real folder of 6 files
through the new UI, confirm/override detected types, Import All, verify
data in the Policy/Quotation tabs, and resolve a stuck policy row through
the quotation picker) — all green, no console errors.

## Known Remaining Issues (not yet fixed)
- No delete endpoint exists yet for `insurance_cases` (quotations got one
  in a later session — see Frontend Status's Delete buttons bullet; the
  original gap was surfaced when a leftover test quotation, `FP-Q-3`, had
  to be removed via raw SQL instead of through the API).
- Claims tab remains fully mock/blocked — no claims backend exists yet
  (see Study Objective 1.3 above; not new, just reconfirmed this session).

See "Duplicate usernames in `users`" below for the last previously-tracked
issue, which is fixed.

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
- `pages/policy.jsx` — Policyholder Information page, 6 tabs (Policy,
  Quotation, Claims, Client Information, Survey Report, Vehicle
  Information) via a type dropdown + shared table/search/pagination
  toolbar.
  - "Client Information" tab: DONE — fetches `GET /policyholders`
    (axios, `API_BASE_URL = "http://127.0.0.1:8000"`, sends
    `Authorization: Bearer <token>` from `localStorage` when present) via a
    `fetchClients` callback run on mount. `DATA_MAP` is built inside the
    component (not module scope) so it can include live `clientRecords`
    state. Stat card shows `clientRecords.length` (real count), not a
    hardcoded number. Mock `clientData` array is gone.
  - `ClientTable` now shows all 18 real `PolicyholderOut` fields (Last/
    First/Middle Name as separate columns, Sex, Nationality, Marital
    Status, Spouse Name, Present + Permanent Address, Residence Phone,
    Mobile Number, Email Address, Zip Code, Occupation, Employer, TIN,
    SSS No.) plus an Actions column — up from the original 6-column view.
    Table scrolls horizontally (`overflow-x-auto` + `whitespace-nowrap` +
    `min-w-max`) rather than truncating; nulls render as `—` via
    `formatOrDash`. The "Age" column was removed (backend has no age/
    birthdate field) — do not re-add it. `clientDisplayName()`
    (`last_name, first_name`, falling back to `Client #{id}`) is the one
    display-label helper shared by `ClientTable`'s delete-confirm text and
    `NeedsReviewModal`'s "link to existing client" dropdown — fixed this
    session after the dropdown broke on a since-removed merged name field.
  - **Needs Review UI**: `components/NeedsReviewModal.jsx` (new) — lists
    rows from `GET /import/policyholders/needs-review`, lets staff either
    link a row to an existing client (dropdown populated from
    `clientRecords`) via `PATCH .../records/{id}/resolve`, or force-create
    it as new. Opened via a "Needs Review" button next to Upload with a
    red count badge. `policy.jsx` holds `needsReviewRecords` state and a
    shared `refreshClientData()` (refetches both clients and needs-review)
    called after upload success, resolve, and delete.
  - **Delete buttons**: `ClientTable`, `NeedsReviewModal`,
    `GenericPolicyTable` (used across all 5 column sets in the Policy,
    Quotation, and Survey Report tabs), and `VehicleTable` rows all have a
    trash icon → `window.confirm()` → `DELETE` call → archive → refetch.
    Deleting a client with existing insurance cases still fails with a 409
    (backend-enforced). The same archive-first pattern (snapshot to a
    `deleted_*` table, then delete the live row — see "Delete + archive
    pattern" above) was extended across sessions to `fire_property_policies`
    and `motor_policies` (both unconditional — nothing depends on a
    policy), `vehicles` (blocking: 409 if the vehicle still has
    `motor_quotations` referencing it), `fire_property_quotations` /
    `motor_quotations` (blocking: 409 — "Cannot delete: this quotation has
    a policy on file. Remove or reassign it first." — if a policy already
    references the quotation via its required `quotation_id` FK, same
    shape as the Vehicle case), and — most recently —
    `fire_property_surveys` (unconditional again: nothing in the schema
    has a FK pointing at a survey, same shape as Policy). New model
    classes `DeletedFirePropertyPolicy` / `DeletedMotorPolicy` /
    `DeletedVehicle` / `DeletedFirePropertyQuotation` /
    `DeletedMotorQuotation` / `DeletedFirePropertySurvey` and matching
    `GET /deleted-fire-property-policies` / `/deleted-motor-policies` /
    `/deleted-vehicles` / `/deleted-fire-property-quotations` /
    `/deleted-motor-quotations` / `/deleted-fire-property-surveys`
    endpoints, same router-wide auth convention as everywhere else — every
    new delete/archive endpoint across these sessions, survey ones
    included, was individually hit with no Authorization header and
    confirmed to return 401, not just assumed from the router-level
    dependency. There is still no delete endpoint for `insurance_cases`
    (see Known Remaining Issues).
  - **Policy tab**: DONE, reworked this session after a few iterations.
    ONE "Policy" entry in the main type dropdown (not split into two tabs)
    with a dedicated secondary "Insurance Line" dropdown (Fire & Property /
    Motor Car, defaulting to Fire & Property) shown only on this tab,
    sharing `LINE_ONLY_OPTIONS` with the Quotation tab's own line filter —
    both dropped a merged "All Lines" view for the same reason (see
    Quotation tab below). Each line keeps its own full ~20-22 column set
    (`FIRE_POLICY_COLUMNS` / `MOTOR_POLICY_COLUMNS`, rendered via a shared
    `GenericPolicyTable`),
    covering every real field on `FirePropertyPolicyOut` /
    `MotorPolicyOut`. Both column sets add one synthesized "Client Name"
    column that resolves the real policyholder via
    `quotation_id → insurance_case → policyholder` — the same join
    Vehicle Information uses — kept deliberately separate from the raw
    "Insured Name & Address" literal field already on the policy record;
    the two usually agree but a mismatch is a real data signal, not
    something to reconcile away (verified with a deliberate mismatch
    test). Date filter runs on `issue_date` via a new `extractDateParts()`
    helper that handles both raw ISO date strings (Policy, Client
    Information) and the pre-formatted "MM/DD/YYYY" strings other tabs
    use, so one filter works against both shapes. `handleTypeChange` now
    resets `fromDate` on every tab switch (previously didn't — fixed
    bug).
  - **Quotation tab**: DONE, given the same full-column treatment as
    Policy this session. Dropped its old "All Lines" merged view (same
    reason Policy never had one): Fire/Property and Motor/Car have
    genuinely incompatible column sets (e.g. Location of Risk/Conditions
    vs Plate No./Vehicle ID), so the old `LINE_OPTIONS` (which included
    "All Lines") was replaced by `LINE_ONLY_OPTIONS`, now shared with the
    Policy tab's own line dropdown. Two full column sets
    (`FIRE_QUOTATION_COLUMNS` / `MOTOR_QUOTATION_COLUMNS`) cover every
    real field on `FirePropertyQuotationOut` / `MotorQuotationOut`,
    rendered through the same `GenericPolicyTable` Policy uses. Same
    synthesized "Client Name" (resolved via `insurance_case_id →
    policyholder`) vs raw "Insured Name" relationship as Policy's Client
    Name vs Insured Name & Address — verified independent with a
    deliberate mismatch (Client Name "Dennis Reyes" vs Insured Name
    "Dennis Reyes Trading" on one real row). "Converted Policy No."
    (resolves `quotation_id → policy_no` from `fire_property_policies` /
    `motor_policies`, `—` if no policy exists yet) was dropped when
    `fetchQuotations` was first simplified, then restored as its own
    column near Insured Name once flagged — verified against real data
    (Fire quotation #2 → `FP-2026-0102`, Motor quotation #2 →
    `MC-2026-0202`, both matching the Policy tab exactly). Fire/Property's
    "Conditions" column (the `conditions` JSON field) renders a "View"
    button (`—` if null/empty) that opens a `ConditionsModal` showing
    pretty-printed JSON — `GenericPolicyTable` gained a `col.type ===
    "json"` case + `onViewJson` prop for this rather than a separate table
    component. `DATE_FIELD_MAP["Quotation"]` now points at the raw
    `quotation_date` field (was a pre-formatted `date` string). The old
    merged `QuotationTable` component was deleted as dead code.
  - **Survey Report tab**: DONE, given the same full-column treatment as
    Policy/Quotation. `SURVEY_COLUMNS` covers every real field on
    `FirePropertySurveyOut`, rendered through the same shared
    `GenericPolicyTable` (now used by 5 different column sets across 3
    tabs, not just Policy/Quotation). Same "Client Name" (resolved via
    `insurance_case_id → policyholder`) vs raw "Name of Insured"
    relationship as the other tabs — verified independent with a
    deliberate mismatch test. "Quotation ID(s)" groups by
    `insurance_case_id` (correct here, unlike Vehicle Information's
    `vehicle_id` grouping — a survey has no more specific sub-entity to
    key by than the shared case) and sits as the 3rd column, right after
    Survey ID/Case ID — originally placed near the end of `SURVEY_COLUMNS`
    with the other real fields, moved up front per explicit follow-up
    request, confirmed visually in a live logged-in browser pass (column
    header order read directly from the DOM, not assumed from source).
    Dropped the
    `SURV-`/`FP-Q-` display prefixes on Survey ID and Quotation ID(s) —
    same fix as Vehicle Information's `VEH-`/`MC-Q-` prefixes, raw numbers
    now match across every tab. Occupancy Breakdown / Boundaries /
    Protection Facilities (all JSON fields) each get a "View" button
    (`—` if null/empty) — the JSON-modal machinery built for Quotation's
    Conditions field was generalized rather than rebuilt 3 more times:
    `ConditionsModal` → `JsonModal` (now takes a `title`), `JsonViewButton`
    passes the column header through as that title, and a single
    `jsonModal`/`openJsonModal` pair on the page replaces the old
    Quotation-only `conditionsModalValue` state — both tabs' JSON columns
    share one modal instance. Latitude/Longitude/Flood Risk Flag/Flood
    Risk Category are real columns, just null on every row until GIS
    (Objective 2.1) exists — render as `—` like any other empty field, no
    special casing. `DATE_FIELD_MAP["Survey Report"]` now points at the
    raw `created_at` field (the old synthetic pre-formatted `date` field
    is gone) — same "not really a business date" caveat noted for Vehicle
    Information, but kept working since the filter already worked before
    this tab's columns were raw-ified and nobody asked to remove it. Old
    `SurveyTable` and `RiskClassBadge` components deleted as dead code —
    Risk Class now renders as a plain value via `formatCell` like every
    other column, not a colored badge.
  - **Vehicle Information tab**: DONE — fetches `GET /motor/vehicles`,
    gained a delete/Actions column this session (same blocking archive
    pattern as the Policy tab's vehicle case above). Also fixed: the
    "Quotation ID(s)" column was grouping by `insurance_case_id`, which
    could show a quotation belonging to a sibling vehicle on the same
    case — now correctly grouped by `vehicle_id`, the direct FK
    `MotorQuotation` actually has.
  - **Claims tab**: still mock `claimsData` — correctly blocked, no claims
    backend exists (see Study Objectives 1.3/scope notes above).
  - `components/UploadFileModal.jsx`: DONE, two modes. **Single file**
    (original): drag-drop + an importer-select dropdown covering only the
    original 3 types (Policyholders/Fire-Property Surveys/Motor
    Quotations) — deliberately NOT extended to the 3 new Policy/Quotation
    types, still useful for one-off corrections. **Folder** (new): pick a
    folder (`<input type="file" webkitdirectory multiple>`, set
    imperatively via a ref since React has no first-class prop for it) →
    `POST /import/batch/detect` → per-file results table with an
    editable/overridable type dropdown (forced blank + amber-highlighted
    when detection is ambiguous or low-confidence) → "Import All" →
    `POST /import/batch/upload` (files + import_types as matched-order
    form fields) → per-file summary. See "Folder-Based Bulk Import" above
    for the detection/matching design.
  - `components/NeedsReviewModal.jsx`: extended with a quotation-picker
    branch (see "Folder-Based Bulk Import" above) — rows for the 2 Policy
    import types, once their policyholder is already resolved, show a
    quotation `<select>` (fetched from `GET .../quotation-candidates`) +
    Confirm instead of the usual Link/Create-as-new controls. Everything
    else (policyholder-centric rows, `raw_data` rendering, delete) is
    unchanged and still generic across all 6 import types.
- `pages/overview.jsx`, `pages/proposal.jsx`, `pages/distribution.jsx` —
  all mock dashboard/chart data, would need new backend aggregation
  endpoints (none exist yet) before connecting.
- `pages/renewal.jsx` — DONE. Renewal Ratio Monitoring (Objective 1.4
  groundwork) is a live, fully wired, fully tested feature — not blocked,
  no separate Renewal table or import needed. Computed entirely from
  existing `FirePropertyPolicy`/`MotorPolicy` data already on file
  (`renewing_policy_no` + `period_to`), same anchor fields called out in
  the Database Schema section above.
  - **Backend**: `GET /stats/renewal-ratio` in `routers/stats.py`, params
    `period` (`daily`/`mtd`/`ytd`) + `date`. `_expiry_range_for_period()`
    scopes which policies are in view (period_to within today/current
    month/current year — always the FULL month/year for mtd/ytd, no
    cutoff at today, unlike `_range_for_period()`'s Policy Distribution
    behavior). `_renewal_status()` classifies each in-range policy into
    exactly 3 states (the old "New" category and its 90-day pending
    window are gone):
    - Renewed: some other same-line policy's `renewing_policy_no` matches
      this one's `policy_no`.
    - Lost: not renewed, and today is already past `period_to`.
    - Pending: not renewed, and `period_to` hasn't passed yet — no day-
      count check anymore, however far out the expiry is.
    A policy whose `period_to` falls outside the selected period's range
    is simply omitted from that view entirely (not counted, not shown) —
    a past month/year can therefore only ever contain Lost/Renewed, which
    falls out of the logic above rather than being special-cased.
    "Expiring" = Renewed + Lost + Pending; Renewal Rate = Renewed ÷
    Expiring × 100. Same-line-only renewal matching (fire only renews
    fire, motor only renews motor) — verified via a deliberate cross-line
    test (a motor policy's `renewing_policy_no` textually matching a fire
    policy's `policy_no` does NOT mark the fire policy Renewed).
  - **Frontend**: `pages/renewal.jsx` + `components/RenewalDailyView.jsx`
    / `RenewalMTDView.jsx` / `RenewalYTDView.jsx` (bar chart + fire/motor
    pies + policy table per period) sharing `RenewalRatioShared.jsx`
    (`mapRenewalRow`, `RenewalRateCard`, `RENEWAL_STATUS_OPTIONS` — now
    `["Status: All", "Renewed", "Lost", "Pending"]`, "New" removed since
    the backend can no longer emit it).
  - **Verified** with real fixture data (full policyholder → case →
    quotation → policy chains inserted directly, not mocked): renewal
    chain classification, cross-line isolation, a policy expiring next
    year correctly absent from this year's YTD view entirely, a past
    month's bar bucket containing zero Pending (checked globally across
    all existing data, not just fixtures), a policy expiring later in the
    current month/year showing Pending regardless of days remaining
    (including a >90-days-out case that the old rule would have excluded
    as "New"), and Expiring/Renewal Rate arithmetic against the real
    computed numbers. Fixtures deleted after verification.
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
1. GIS/flood-risk integration (Objective 2.1) — not started. All 6 data
   tabs (Client Information/Policy/Vehicle Information/Quotation/Survey
   Report, plus Claims correctly still blocked) now have the full-column
   treatment, so this is the next real gap.
2. Predictive risk model (Objective 1.2 core) — not started, blocked on
   having enough real data flowing through the system first.