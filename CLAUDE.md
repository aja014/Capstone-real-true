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
2.1 Geospatial Flood Prone Mapping — part of Fire/Property AND Motor/Car
    predictive risk. DONE (see "GIS Flood-Risk Lookup Service" below) —
    geocoding + point-in-polygon, not QGIS API (see that section for why)
2.2 Bulk Client Data Import & Validation — DONE (see below)

## Tech Stack
- Frontend: React + React Router + Vite, Tailwind CSS, lucide-react icons, axios
- Backend: Python FastAPI + SQLAlchemy ORM + Pydantic schemas + bcrypt
- Database: MySQL (via pymysql), dev server at http://127.0.0.1:8000
- Frontend dev server: http://localhost:5173 (Vite default)
- GIS: DONE (see "GIS Flood-Risk Lookup Service"). ML: our own numpy Logistic
  Regression + Naive Bayes in `Backend/app/ml/` (see "Models Phase 1"); scikit-learn
  only in tests (`Backend/requirements-dev.txt`)

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
vehicles, motor_quotations, motor_policies,
motor_claims, fire_property_claims (+ deleted_* archives for both — see
"Claims tables (Phase 1)"), geocode_cache, ml_models, ml_predictions (see
"Models Phase 1"; they replaced the old, never-used `risk_predictions`).

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
- NOT YET BUILT (do not fabricate): Renewal tables —
  wait for real data/field definitions before designing these. (Claims
  tables now exist — see "Claims tables (Phase 1)" below; fraud predictions
  go in `ml_predictions`, see "Models Phase 1".)
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
- `import_vehicle.py` — bulk import for Vehicle Information
  (`POST /import/vehicles/upload`). No paper-document precedent of its own
  (vehicle details normally only ever appear inside a Quotation/Policy
  form) — its 9 columns instead mirror what the Vehicle Information tab
  already displays as raw fields. Dedupes on exact plate/engine/chassis
  match (reuses `import_motor.find_existing_vehicle`); a genuinely new row
  only ever creates Policyholder → Insurance Case → Vehicle, never a
  Quotation. Wired into the shared needs-review queue via
  `models.ImportType.vehicle` / `new_policyholder_fields()` /
  `resolve_for_policyholder()`, same pattern as every other importer.
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

## GIS Flood-Risk Lookup Service (Objective 2.1) — DONE (now combines river flood + storm surge)
Shared service, not duplicated per line: `Backend/app/services/flood_risk.py`,
one entrypoint `lookup_flood_risk(address: str) -> dict` returning
`{latitude, longitude, flood_risk_flag, flood_risk_category, river_flood_category,
storm_surge_category}`. Called from all 6 creation sites where an address is
known before a policy is issued: Fire/Property Survey (manual endpoint + bulk
import + its needs-review `resolve_for_policyholder`) and Motor Quotation
(manual endpoint + bulk import + its needs-review `resolve_for_policyholder`)
— the needs-review resolve paths weren't explicitly requested but were
included so a manually-resolved row matches what auto-import would've
produced, same principle as the rest of the Needs-Review Resolution section
above. All 6 call sites merge the function's full return dict generically
(`dict.update(...)` or `**lookup_flood_risk(...)`), so the storm-surge
extension below reached every one of them with zero call-site changes —
confirmed, not assumed, via a real end-to-end test through the actual
`/fire-property/surveys` and `/motor/quotations` HTTP endpoints.

**Behavior (extended this session)**: geocode the address via OpenStreetMap
Nominatim (User-Agent `MaagapCapstoneFloodRiskLookup/1.0`, no personal
contact info in it — deliberately not the same as sending someone's real
email to a third-party service; `countrycodes=ph`), then point-in-polygon
against BOTH hazard datasets:
- River flood: `gis_data/flood_hazard/bulacan_100yr/extracted/Bulacan_Flood_100year.shp`
  (`Var` 1/2/3 = Low/Medium/High).
- Storm surge: `gis_data/storm_surge/bulacan/extracted/SSA3/Bulacan_StormSurge_SSA3.shp`
  (`HAZ` 1/2/3 = Low/Medium/High) — SSA3 (the 3rd of the 4 increasingly-severe
  advisory-level shapefiles acquired earlier, see the old "Storm Surge Hazard
  Data" section below) was picked as the one fixed scenario to combine in,
  rather than checking all 4 or exposing a scenario choice — out of scope
  for what this capstone needs.

Each dataset is classified independently (worst zone wins on overlap within
that dataset, same as before); the two results are then combined by taking
whichever is MORE SEVERE (Low < Medium < High, "outside every zone" counts as
lowest/safest) as the headline `flood_risk_flag`/`flood_risk_category` —
this is the repurposed meaning of those 2 existing columns, shown everywhere
they already were (GIS modal, table columns) with no frontend changes needed
since the field name/shape is unchanged. The 2 new columns
`river_flood_category` / `storm_surge_category` store each dataset's
individual result for future ML use — not displayed in the UI.

Every failure mode (blank address, geocode miss, network error, an invalid
polygon tripping a specific `contains()` call) is caught inside the service;
the two hazard checks fail independently of each other (one shapefile
failing to load doesn't blank the other's result or the headline it would
otherwise produce) and total failure (bad geocode) returns all 6 fields
null — never raises, never blocks the Survey/Quotation record from being
created. A caller-supplied manual value for any of the 4 original fields on
the 2 manual endpoints is respected (lookup only fills them in when all 4
are blank), same as Survey's pre-existing manual-entry support — the 2 new
breakdown columns aren't part of that manual-override check, since they're
purely a lookup byproduct, never manually entered.

**Why not geopandas/QGIS API as CLAUDE.md originally said**: geopandas/fiona
have no wheels for this project's Python 3.14 venv. `pyshp` (pure Python) was
tried first and couldn't even finish a raw read of the shapefile in several
minutes — the file is 71MB but only **3 features** (one dissolved multi-
polygon per hazard class), each with an enormous vertex count, which is a
pathological case for pure-Python per-feature parsing. Fixing formal GEOS
validity (`shapely.make_valid()`, since all 3 polygons report `is_valid ==
False` — typical of dissolved/raster-derived hazard polygons) was tried and
also killed after 4+ minutes for the same reason. Switched to `pyogrio`
(GDAL-backed, ships its own binaries, has a wheel for this Python version)
which reads all 3 features in ~2.5s; skipped `make_valid`/`simplify`
entirely and verified `contains()` directly against the raw (formally
invalid) geometries instead — correct results across 8 points spanning all
3 hazard classes plus clearly-outside points, ~0.16s/query average, wrapped
in a per-geometry try/except as the safety net for the rare point that
might trip GEOS on the unfixed geometry. New deps: `shapely`, `pyogrio` (in
`Backend/requirements.txt`, this session also gave that file its first real
content — it was empty before).

**Schema**: `motor_quotations` got the same 4 columns
`FirePropertySurvey` already had (`latitude DECIMAL(10,7)`,
`longitude DECIMAL(10,7)`, `flood_risk_flag BOOLEAN`,
`flood_risk_category VARCHAR(50)`) via a manual `ALTER TABLE` against the
live dev DB — same `create_all()`-doesn't-alter-existing-tables caveat as
everywhere else in this doc. `MotorQuotationCreate` gained the matching 4
`Optional[...]` schema fields (mirrors `FirePropertySurveyCreate`'s
pre-existing ones). Later session: both `fire_property_surveys` and
`motor_quotations` got 2 more columns each, `river_flood_category
VARCHAR(50)` and `storm_surge_category VARCHAR(50)`, same manual-`ALTER
TABLE` caveat; `FirePropertySurveyCreate`/`MotorQuotationCreate` both
gained the matching 2 `Optional[str]` schema fields.

**Progress indicator**: bulk imports of Surveys/Motor Quotations are now
slower (Nominatim's usage policy caps requests at 1/second, enforced
process-wide via a lock in `flood_risk.py`, so N addressed rows take at
least N seconds). Live per-row "Checking address 12 of 50..." progress
would need genuinely new infrastructure (background job + polling endpoint
or SSE/WebSockets — none of that exists anywhere in this codebase today).
Given this project's own "simplest defensible architecture, tight deadline"
framing and that it's a low-concurrency capstone tool, went with the
simple option instead: the Upload modal's existing spinner text swaps to
"Processing — this may take longer for larger files due to flood-risk
lookups" (`UploadFileModal.jsx`, `GEOCODED_BATCH_TYPES`), shown only when
the import type actually triggers geocoding (Fire/Property Survey or Motor
Quotation) — no new backend infrastructure.

**Verified end-to-end with real fixtures** (all 4 required scenarios plus
the needs-review resolve path as a bonus check, since it was newly wired
in): a real, known-good Bulacan address ("Barangay Longos, Malolos City,
Bulacan, Philippines") geocoded consistently to the same coordinates and
"Medium" flood risk across all call sites — manual Survey creation, manual
Motor Quotation creation, bulk Survey import, bulk Motor Quotation import,
and a Motor Quotation created via needs-review resolve. A deliberately
unfindable address left all 4 fields null in every case, with the
Survey/Quotation record still created successfully and no error surfaced
(`failed: 0` in both bulk-import summaries). All test data (9 policyholders,
8 insurance cases, their surveys/quotations/vehicles, 7 import_records) was
identified by exact test name / `zzfloodtest%` source-file match and
deleted afterward — nothing else in the dev DB was touched.

**Storm-surge integration verified (later session)**: Panghulo and Salambao
(the 2 coastal Obando addresses the storm-surge data was originally acquired
to cover, see below) now correctly come back with `river_flood_category:
null` (flood-alone genuinely still finds nothing there — unchanged) but
`storm_surge_category: "High"` and a headline `flood_risk_category: "High"`
— confirmed both via direct `lookup_flood_risk()` calls and via a real
`POST /fire-property/surveys` + `POST /motor/quotations` round trip (JWT
generated through the app's own `create_access_token`, hitting a live
`uvicorn` instance, checked against the DB row afterward, then deleted).
A real inland address (Marilao) came back `river_flood_category: "Medium"`,
`storm_surge_category: null`, headline `"Medium"` — storm surge correctly
contributes nothing inland, headline unchanged from pre-storm-surge
behavior. "Worst of both" was verified against 3 real points found by
intersecting the two shapefiles' geometries directly (river Low/storm High
→ headline High; river High/storm Low → headline High; river Medium/storm
Medium → headline Medium) — forward-geocoding barangay-level addresses
landed near but not exactly inside these small overlap polygons, so the
combine logic itself was checked at the precise overlap coordinates rather
than via a geocoded address for this specific case.

## Hazard Boundary Buffer (50m) — DONE
A wide geographic reliability pass (16 real barangay-level addresses across
8 towns, beyond the original Obando spot-check) surfaced a real problem:
**Calumpit** — a town with a well-documented real-world flood history —
came back with zero risk everywhere, including its town center at the
river confluence near Calumpit Bridge. Investigating rather than accepting
that at face value: every one of 6 tested Calumpit points (Iba, Gatbuca,
Poblacion, San Marcos, Panducot, Sergio Bayan) landed within **1.74m to
25.93m** of a river-flood hazard polygon's edge — i.e. right on the
boundary line, not genuinely outside the mapped floodplain. This is a
structural property of river-adjacent settlements, not bad data: towns
build on the highest available ground right at a floodplain's edge, so a
geocoded barangay point routinely lands within meters of the hazard
boundary in either direction, and a hard yes/no point-in-polygon test is
unstable at that margin.

**Investigation** (data-driven, not a guessed number): measured exact
distances using a local equirectangular projection (meters-per-degree
scaled for Bulacan's ~14.8°N band — no `pyproj` in this venv, but accurate
to well under 1% at this scale).
- **Near-miss group** (Calumpit's 6 points, should flip to at-risk):
  1.74m, 3.14m, 4.98m, 5.83m, 25.75m, 25.93m — max **25.93m** needed to
  close all 6.
- **Confirmed-safe group** (5 successfully-geocoded inland/upland points —
  Niugan/Angat, San Roque/Angat, San Lorenzo/Norzagaray, Bigte/Norzagaray,
  Camachin/DRT): minimum measured distance to the nearest river-flood zone
  was **900m** (Niugan, Angat) — the others ranged 1.36km–8.46km. Storm-
  surge distances for these were all 19–40km, not a constraint.
- **Verdict**: no conflict between the two goals — the gap between "largest
  distance needed to catch a real near-miss" (25.93m) and "smallest margin
  among confirmed-safe points" (900m) is ~35x. Tested candidate sizes
  25/50/100/150/200m against both groups: 25m missed 2 of 6 Calumpit points
  by under 1m; 50m+ caught all 6 with zero false positives among the 5
  inland points at any tested size up to 200m.
- **Chose 50m**: smallest tested size that reliably closes every documented
  near-miss, leaving ~24m of margin over the tightest case (Iba/Gatbuca at
  25.93m) and ~850m of headroom before the nearest genuinely-safe point.

**Bambang, Bulakan caveat (found during investigation, not swept under
the rug)**: Bambang has two very different distances to the two hazard
datasets — 324m from the nearest storm-surge zone (a genuine, different-
scale miss, correctly NOT closed by 50m) but only **14.20m** from the
nearest river-flood zone (the same near-miss phenomenon as Calumpit).
Explicit decision: no per-address exceptions — the buffer applies
uniformly, so Bambang's river-flood result changes (correctly, by the same
logic as Calumpit) while its storm-surge result stays unaffected.

**Implementation**: `Backend/app/services/flood_risk.py`'s `_classify()`
now treats a point as inside a zone if `contains()` OR the point is within
`BOUNDARY_BUFFER_METERS` (50) of the zone's edge. Rather than buffering the
zone polygons directly — which would have hit the same `make_valid()`/
`unary_union()` performance wall documented above (these 3-feature,
huge-vertex, formally-invalid geometries took 4+ minutes and were killed
twice) — the buffer is implemented as `geom.distance(point) <=
BOUNDARY_BUFFER_METERS`, mathematically equivalent but far cheaper since it
never touches the polygon's own geometry. Zone geometries are projected
once (cached, same lazy-load pattern as before) into the same local-meters
frame used for the investigation, via `shapely.transform()` (fast — ~1.1s
one-time cost for the river shapefile, ~0.02s for storm surge, negligible
against the existing ~2.5-4s one-time shapefile read this already paid).
Applies to both datasets uniformly via the same `_classify()` function —
no per-address or per-dataset special-casing.

**Verified with real data**: all 6 Calumpit points now return a real
category — Iba/Gatbuca/Poblacion/Panducot → High, San Marcos → Medium,
Sergio Bayan → Low (higher than the single nearest zone in a few cases,
because the 50m buffer can put a point within range of *multiple* tiers at
once — e.g. Iba is within 50m of both the Medium zone at 25.93m and the
High zone at 46.60m, so worst-wins correctly picks High — an expected
interaction with the tiered classification, not a bug). Bambang confirmed:
river-flood flipped to "Low" (14.20m, within buffer), storm-surge stayed
`None` (324m, outside buffer) — exactly as investigated. All 5 inland/
upland control points stayed `None`/`None`, unaffected. Re-running the same
address twice still gives byte-identical results (determinism unaffected).

**Performance — honest finding, not just "still fast"**: classification-
only cost (excluding geocoding) rose from ~0.1-0.2ms/lookup (contains()
only) to **6-115ms/lookup** depending on how many zones require the new
`distance()` fallback. Root cause, isolated and confirmed: `contains()` on
these huge (millions-of-vertices, formally-invalid) polygons already cost
~2ms/zone for a point near/inside the shape (not sub-millisecond the way a
point far outside the bounding box is) — that part is pre-existing,
unrelated to this change. The new `distance()` call, needed only for zones
where `contains()` returns False, costs roughly **~30ms/call** on these
same huge geometries — meaningfully more expensive than `contains()`, and
the actual driver of the added cost. Still a non-issue in absolute terms:
full `lookup_flood_risk()` calls remain dominated by the >=1000ms Nominatim
throttle (a real request still averages ~1-2s), so this adds roughly a
5-11% overhead per lookup, not a user-visible slowdown. Not optimized
further (e.g. checking zones highest-severity-first and early-exiting once
a hit is confirmed would cut this) since it wasn't needed to meet "still
fast" — flagged here in case a future session wants to tighten it.

## Storm Surge Hazard Data (Bulacan) — ACQUIRED AND INTEGRATED (see GIS Flood-Risk Lookup Service above)
Companion dataset to the 100yr flood data above, for the coastal-flooding gap
the flood-only data misses (surfaced via Obando's Panghulo/Salambao
barangays — see verification below). This section is data acquisition/
verification history — the actual lookup/storage/combine logic lives in the
"GIS Flood-Risk Lookup Service" section above.

**Source**: same Hugging Face mirror as the flood data,
`bettergovph/project-noah-hazard-maps`, but under `Storm Surge/` (not
`Flood/`) — 4 subfolders `StormSurgeAdvisory1`-`4` (one per SSA advisory
level), each containing a per-province `Bulacan.zip`. Downloaded all 4 into
`gis_data/storm_surge/bulacan/` (`SSA1_Bulacan.zip` ...
`SSA4_Bulacan.zip`, extracted under `extracted/SSA1/` ... `extracted/SSA4/`
as `Bulacan_StormSurge_SSA{1-4}.shp` + sidecars), plus
`metadata_stormsurge.txt` and `01ReadMe_StormSurge.pdf` (the authoritative
source for the SSA definitions — see below; the metadata txt's own
"SSA1 up to 2m ... SSA4 exceeding 4m" wording is rounded/imprecise
compared to the PDF's real thresholds, don't rely on the txt for exact
cutoffs).

**Verified properties** (via pyogrio, same tooling as the flood data):
all 4 shapefiles load cleanly, CRS EPSG:4326 (WGS84), each has exactly 3
rows with a single `HAZ` attribute (1.0/2.0/3.0 = Low/Medium/High per
water depth + velocity-depth product) — same one-dissolved-polygon-per-
hazard-class shape as the flood data's `Var` column, different column
name. Real SSA definitions per the README PDF (PAGASA/NIGS, DOST-Project
NOAH, JMA storm surge model + WXTide + FLO-2D, simulated over 721 historical
tropical cyclones 1951-2013): **SSA1 = 2.01-3m, SSA2 = 3.01-4m, SSA3 =
4.01-5m, SSA4 = 5m+ peak storm tide height** — 4 separate, INCREASINGLY
SEVERE scenario shapefiles, not 4 severity levels within one file (unlike
flood's single-file 3-tier `Var`). Bounds are notably narrower than the
flood data's whole-province extent (~120.69-120.96°E, 14.69-14.84°N vs
flood's 120.69-121.35°E, 14.72-15.27°N) — consistent with storm surge only
affecting Bulacan's western coastal strip, not the whole province.
`.xml` sidecar shows the same `CreaDate=20210719` dissolve-tool processing
date as the flood data (likely the same GIS batch), on top of the
1951-2013 simulation base — same "later processing pass on older survey
work" vintage story as flood. License: ODC-ODbL, same as flood.

**Confirmed it fills the real Obando gap**: tested real, verified (via
PhilAtlas) coordinates for Obando's Panghulo (14.6980, 120.9471) and
Salambao (14.7087, 120.9081) against both datasets. The 100yr flood
shapefile MISSES both — nearest polygon edge ~2.8km (Panghulo) / ~2.2km
(Salambao) away, i.e. genuinely outside every flood hazard polygon, not
just coordinate noise. Storm surge HITS both directly at every SSA level:
Panghulo comes back Medium at SSA1, High at SSA2-4; Salambao comes back
High at every level (SSA1-4). Inland/deep-inland controls (Marilao, a
point ~20km from the coast) correctly stayed outside the storm surge
polygons at low SSA levels and only came into range at the most severe
SSA4 scenario (Marilao ~111m from the SSA4 edge) — consistent with a real
coastal-hazard dataset, not an overly permissive one.

**Integrated (later session)**: the open design questions above were
resolved as worst-of-both (river vs. storm surge, whichever is more
severe, becomes the headline `flood_risk_flag`/`flood_risk_category`) with
SSA3 picked as the single fixed storm-surge scenario to check (not all 4,
not configurable) and each hazard's individual result kept in its own new
column (`river_flood_category`, `storm_surge_category`) for future ML use.
See "GIS Flood-Risk Lookup Service" above for the implementation and
verification.

## Claims tables (Phase 1) — DONE (tables + schemas only, no endpoints)
Objective 1.3 groundwork, 2026-09-25, branch `claims-phase1`. Purely
additive: 4 new tables `motor_claims`, `fire_property_claims`,
`deleted_motor_claims`, `deleted_fire_property_claims` (created by
`create_all()`); no existing table, router, or frontend file touched.
- `motor_claims.motor_policy_id` → `motor_policies.id` and
  `fire_property_claims.fire_property_policy_id` → `fire_property_policies.id`,
  both NOT NULL, explicit `ON DELETE RESTRICT`. Relationships are one-way
  (claim → policy); `MotorPolicy`/`FirePropertyPolicy` classes unchanged.
- Fire differs from Motor: no `plate_no`, no `coverage_type`, `adjuster`
  instead of `shop_casa`, its own `nature_of_loss` list.
- `accuterm_claim_no` is deliberately NOT unique (OD + TP rows of one
  accident share it; CNC rows may have none).
- `claim_investigation_result` (Legitimate / Suspected Fraud / Confirmed
  Fraud) is the human fraud LABEL for training — not a model prediction.
  Prediction columns come in a later phase, kept separate.
- Fixed lists are `String(50)` + Pydantic validation (same convention as
  `risk_class`), not SQL ENUM. Option tuples are module-level constants in
  `schemas.py` (`MOTOR_NATURE_OF_LOSS_OPTIONS`, `FIRE_NATURE_OF_LOSS_OPTIONS`,
  `MOTOR_COVERAGE_TYPE_OPTIONS`, `CLAIM_TYPE_OPTIONS`,
  `CLAIM_FINAL_STATUS_OPTIONS`, `CLAIM_INVESTIGATION_RESULT_OPTIONS`) plus a
  `canonical_choice()` helper (case-insensitive, stores canonical spelling).
- `created_at` + `updated_at` (claims are edited over their lifecycle, same
  as `policyholders`). Not stored, computed later: days-as-of-today, TAT.
- Schemas: `MotorClaimCreate/Out`, `FirePropertyClaimCreate/Out`,
  `DeletedMotorClaimOut`, `DeletedFirePropertyClaimOut`. No router registered.
- Backup taken before this change: `Desktop\insurance_db_backup_pre_claims_20260925_103721.sql`
  + git checkpoint `5bdcb0f` on `main`. Verified: all 19 pre-existing tables'
  row counts and raw `SHOW CREATE TABLE` identical before/after; 7 API
  spot-checks returned byte-identical bodies; 401 checks unchanged.

**MUST DO in later claims phases (agreed with user):**
1. Before ANY claim row is created, the existing policy DELETE endpoints
   (`fire_property.py` / `motor_car.py`) must check for claims and return a
   clean 409 — otherwise the RESTRICT FK makes them fail with a raw 500.
2. The future claims importer bypasses Pydantic, so it must normalize every
   fixed-list value through `schemas.canonical_choice()` / the option
   constants and store the canonical spelling — never the raw cell text.
3. The claims importer must also enforce the date-of-loss coverage-period
   rule, since PATCH re-validates the stored date of loss — an
   out-of-period imported claim would otherwise block unrelated edits.

(Item 1 is DONE — see "Claims API (Phase 2)" below. Items 2 and 3 are DONE —
see "Claims Importer (Phase 3)" below.)

## Claims API (Phase 2) — DONE (backend only, no frontend/importer yet)
2026-09-25, branch `claims-phase1`. New `Backend/app/routers/claims.py`
(`tags=["Claims"]`, router-wide `Depends(get_current_user)`), registered in
`main.py` after `stats`. No schema/DB changes.

**Endpoints** (Motor shown; Fire/Property is identical on
`/fire-property/claims...` / `/deleted-fire-property-claims` with
`fire_property_policy_id`):
- `POST /motor/claims` (`MotorClaimCreate` → `MotorClaimOut`)
- `GET /motor/claims` (optional `?motor_policy_id=` filter)
- `GET /motor/claims/{claim_id}`
- `PATCH /motor/claims/{claim_id}` (`MotorClaimUpdate` → `MotorClaimOut`)
- `DELETE /motor/claims/{claim_id}` → `DeletedMotorClaimOut` —
  unconditional archive-first (nothing depends on a claim)
- `GET /deleted-motor-claims` — newest first by `deleted_at`

**Validation rules**:
- Policy must exist → 404 "Policy not found" (create, and PATCH against
  either the new or the existing policy id). Missing claim → 404 "Claim
  not found".
- Fixed-list fields go through `canonical_choice()` (case-insensitive,
  stored in canonical spelling, e.g. "paid claim" → "Paid Claim"); an
  invalid value → 422. `MotorClaimUpdate`/`FirePropertyClaimUpdate` in
  `schemas.py` subclass the Create schemas so they inherit the validators,
  with the policy id made Optional.
- Coverage period: `check_loss_within_period()` → 400 "Date of loss X is
  outside the policy's coverage period (A to B)." Only enforced when
  `date_of_loss`, `period_from` and `period_to` are all present; bounds
  inclusive.
- PATCH semantics: `model_dump(exclude_unset=True)` — unsent fields are
  untouched, fields sent as null are cleared. Sending the policy id as null
  → 400 "motor_policy_id cannot be empty" / "fire_property_policy_id cannot
  be empty". The coverage check runs against the MERGED state (new-or-
  stored date of loss vs new-or-stored policy), so a PATCH of an unrelated
  field still fails if the stored date of loss is out of period (hence
  MUST DO item 3 above).
- Out schemas stay flat — no `policy_no` or computed aging/TAT fields in
  the response; join in the frontend.

**Policy-delete 409 fix** (MUST DO item 1): `DELETE /motor/policies/{id}`
and `DELETE /fire-property/policies/{id}` now count claims on the policy
right after the 404 check and return 409 "Cannot delete: this policy has N
claim(s) on file. Remove or reassign those first." instead of hitting the
RESTRICT FK as a raw 500. Policies with no claims behave exactly as before.

**Verified** (66/66 checks, live `--reload` server, JWT via the app's own
`create_access_token`): create/list/filter/get on both lines; PATCH
(`updated_at` moves, `created_at` doesn't, unsent fields untouched, null
clears); 404/422/400 rejections, all clean with no 500s, and rejected
requests leave the stored row unchanged; case-insensitive canonicalisation
(checked in the DB too); delete → archive snapshot + listing; throwaway
policy chains ("Kilo ClaimTest" / "Lima ClaimTest") → 409 with zero row-count
movement, then delete claim → policy delete 200 + exactly one archive row;
401 without a token on all 12 new endpoints. All test rows were cleaned up
by exact id. All 23 tables' row counts matched the pre-change baseline,
the 7 spot-check endpoints matched it byte for byte, and the existing 401
checks were unchanged.

## Claims Importer (Phase 3) — DONE (frontend wired later — see Claims Phase 4)
2026-09-25, branch `claims-phase1`. New `Backend/app/routers/import_claims.py`
(`/import/claims/motor/upload`, `/import/claims/fire-property/upload`),
registered in `main.py`. Two new import types `motor_claim` /
`fire_property_claim` (in BOTH `models.ImportType` and `schemas.ImportType`).

**Schema change (explicitly approved exception)**: `import_records.import_type`
is a native MySQL ENUM, so the 2 values were appended by hand:
`ALTER TABLE import_records MODIFY import_type ENUM(<7 existing>,'motor_claim',
'fire_property_claim') NOT NULL DEFAULT 'policyholder'`. Backup taken first
(`Desktop\import_records_backup_pre_claims_import_20260925_215241.sql`);
`SHOW CREATE TABLE` diff showed only that column changed; 251 rows and the
per-type/status breakdown unchanged. Any future import type needs the same
ALTER — adding to the Python enum alone makes inserts fail.

**Columns**: the finalized Maagap claims headers (see `_COMMON_COLUMN_MAP`
+ Motor's Plate No./Coverage Type/Shop/Casa, Fire's Adjuster). "PLA Date
(Date Reported)" and "PLA Date" both → `date_reported`. Optional "Claimant
Name". Ignored if present: SN, No. of Days (As of Today), Turn-Around-Time,
a second "Date of Loss" (pandas renames it "Date of Loss.1"), and "Assureds
Name" (used as `assured` ONLY when the sheet has no "Assured" column).
"Policy No." links the claim, it isn't stored on it.

**Row rules**:
- Read with `dtype=str`; `"-"`/`"–"`/`"—"`/blank → NULL (`clean_claim_cell`).
- A row with nothing in any claims column (Maagap formula padding) is
  skipped and left out of `total_rows`.
- Fixed-list values → `schemas.canonical_choice()` (MUST DO item 2);
  invalid → row fails, error names the field + allowed values.
- Dates via `pd.to_datetime` (month-first, same as other importers), BUT an
  unparseable date/amount FAILS the row instead of silently becoming NULL
  (a silently-NULL date of loss would skip the coverage check). Amounts strip
  commas, spaces, `₱`, `PHP` then parse as Decimal.
- Coverage period via `claims.loss_period_error()` (shared with the API's
  `check_loss_within_period`, same message) on import AND on resolve (MUST DO
  item 3).
- Policy link: `LOWER(TRIM(policy_no))` exact match on the line's policy
  table. 0 or >1 match (or blank) → `needs_review`. Link is Policy No. ONLY —
  no cross-check of Plate No. vs vehicle or Assured vs insured name
  (decided by user).
- Re-upload dedupe: a row is a duplicate (status `matched`, no claim created)
  if a claim on the SAME policy has the same accuterm_claim_no, assured,
  claimant_name, date_of_loss, nature_of_loss, claim_type (+ coverage_type,
  plate_no for Motor); text compared trimmed/case-insensitive, blank == blank.
  Progress fields are NOT in the key, so an updated re-export is skipped, not
  applied. Unknown-policy rows re-queue a new needs_review record on re-upload
  (same as other importers); resolving the copy is caught as a duplicate.
- Created rows: `import_records` gets `matched_case_id`/`matched_policyholder_id`
  from policy → quotation → case.

**Needs Review**: `GET /import/policyholders/records/{id}/policy-candidates`
(all policies of that line, closest Policy No. first) and a new
`ResolveImportRecord.matched_policy_id` — checked FIRST in
`resolve_import_record()`; claims rows reject the policyholder paths (400),
non-claims rows reject `matched_policy_id` (400). `NeedsReviewModal.jsx` has a
claims branch (policy picker + Confirm + trash). `UploadFileModal.jsx` lists
both types in all 4 type maps.

**Detection / Folder mode**: registry entries carry 2 optional keys only the
claims types use — `ignored_headers` (count toward the score, not reported)
and `excluded_headers` (the OTHER claims line's fingerprint: Adjuster → not
Motor; Plate No./Coverage Type/Shop/Casa → not Fire). Without exclusions a
Fire claims file scores ~95 against the Motor map (always ambiguous). A
minimal claims file with only shared columns is deliberately ambiguous
(manual pick), same as minimal policy files. `PROCESSING_PRIORITY` 4 for
both — claims run after policies.

**Open questions left undecided on purpose (data-planning stage; current
behavior kept)**: (1) Maagap name markers like "… - TP: NAME" in Assured are
stored verbatim, not parsed; (2) every row is its own claim — no decision on
which statuses count as losses or rolling up OD+TP rows sharing an Accuterm
No.; (3) Claim Investigation Result imported verbatim, blank stays NULL (no
default); (4) re-uploads don't update existing claims' progress/label fields;
(5) `-1500` parses as negative, `(1,500)` fails the row — meaning of
negatives unknown.

**Verified**: 41/41 feature checks + Customer Info regression (API-level,
same 2 calls the Upload modal makes) — detection, field/canonical values,
failures isolated per row, coverage period on import and resolve, `-` → NULL,
ignored columns, optional Claimant Name, needs_review resolve/delete, re-upload
dedupe, folder order (claims file sorted first alphabetically, policy still
processed first and the claim linked to it), OD+TP as separate rows, 401 on
new endpoints. Live browser click-through (later, same day) also passed:
Motor claims file auto-detected as "Motor Claims" → "2 rows — 1 new, 1 needs
review"; Needs Review policy picker → Confirm → row gone (33 → 32), claim
created on the picked policy with canonical spellings; Customer Info upload
via UI → 1 new. The Chrome extension is flaky here (screenshot timeouts;
ref-clicks on the toolbar buttons don't open the modals — coordinate clicks
do). All test data cleaned by exact id; 23 table counts, 7
spot-checks, 401 checks and all 7 existing types' detection results matched
the pre-change baseline; backend starts cleanly; `npm run build` succeeds.

## Claims Phase 4 — Frontend (real data) — DONE
2026-09-27, branch `claims-frontend` (created from `data-prep`). No DB change.
Replaces all claims mock data in 3 places.
- **Definitions used everywhere**: "filed" = `date_reported`; each claim ROW counts
  once (OD + TP rows of one accident are separate rows, same as the importer).
  Open = `final_status` NOT in {Closed Claim, Denied Claim, CNC Only, Not Push
  Through} (`stats.FINISHED_FINAL_STATUSES` / `OPEN_FINAL_STATUSES`, built from
  `schemas.CLAIM_FINAL_STATUS_OPTIONS`). **CNC Issuance rows are excluded** from the
  investigation pie, the fraud rate, the fraud trend line and the "Not yet
  investigated" filter (all 33 CNC rows have a blank label).
- **Backend (read-only additions)**: `GET /stats/claims?months=3|6|12` (anything
  else → 6; same rolling window helpers as `/stats/quotation-proposal`) →
  `schemas.ClaimsStats` (`range_start/range_end`, `period_label`, `total_claims`,
  `motor_claims`, `fire_claims`, `open_claims`, `closed_claims`,
  `total_net_liability`, `legitimate`, `suspected_fraud`, `confirmed_fraud`,
  `not_yet_investigated`, `cnc_excluded`, `fraud_rate` (null if nothing
  investigated), `investigation_pie`, `trend[]` with `motor_count`/`fire_count`/
  `fraud_labelled_count`). All of it scoped to claims filed in the window.
  `/stats/overview` gained `filed_claims` (both lines, `date_reported` in the current
  month) — its response is otherwise byte-identical.
- **`lib/claims.js` `fetchAllClaims()`**: the claim → policy → quotation → case →
  policyholder join (same pattern as `lib/quotations.js`), used by both pages. Adds
  `line`, `policy_no`, `client_name` (resolved policyholder, independent of the
  literal `assured`), `investigation_display` ("Not applicable (CNC)" for CNC rows),
  `fraud_warning` ("Pending"; null → "—" for CNC). `components/ClaimsShared.jsx`:
  `InvestigationResultCell` (Legitimate gray, Suspected amber, Confirmed red) and
  `FraudWarningCell` (gray "Pending").
- **Policy Holder Info → Claims tab**: Insurance Line switcher (Fire & Property
  default / Motor Car, like Policy), every real claim field via `GenericPolicyTable`
  (Motor 27 columns incl. Plate No., Coverage Type, Shop/Casa; Fire 25 with Adjuster),
  date filter on Date of Loss, Delete (archive-first DELETE), Upload defaults to the
  line's claims importer, "Total Claims" card = real count (441, was a hard-coded
  421). `GenericPolicyTable` gained an optional per-column `render(row)`.
- **Claims Module page** (`claims.jsx`, rewritten): Past 3/6/12 Months dropdown
  (default 6) drives 4 cards — Total, Open, Closed (= filed in period AND now Closed
  Claim), Total Net Liability — all captioned "Filed Past N Months"; stacked
  Motor/Fire "Filed Claims per Month" bars + "Investigated as Fraud (human label)"
  line; "Claim Investigation Result" pie with the CNC-excluded note (`MiniPie` gained
  an optional `note` prop); Fraud Rate card = (Suspected + Confirmed) ÷ investigated.
  Table = all 441 claims (NOT limited by the period; says so), newest filed first,
  filters: month (Date Reported), Policy Line, Final Status, Investigation Result
  (incl. "Not yet investigated"), search (policy no., client, assured, accuterm no.).
  The old mock "Fraud Flag"/"Fraud Flagged"/"Approved"/"Paid" elements are gone —
  no prediction is shown anywhere; "Fraud Warning" stays "Pending" until the Naive
  Bayes model exists.
- **Overview "Filed Claims"**: `filed_claims`, captioned "This Month (September
  2026)" — same basis/caption as Total Quotation Offered.
- **Verified**: `/stats/claims` for 3/6/12 months and `filed_claims` = independent
  SQL on every field, trend month and pie slice (6 months: 67 filed, 32 open, 22
  closed, ₱13,272,613.23, pie 44/2/5/11, rate 13.7%, 5 CNC excluded; Overview 8);
  the `fetchAllClaims()` join for all 441 rows (policy no., client, investigation
  display, fraud warning) = a SQL join, same SHA-256. Browser (no console errors):
  Overview card 8; Claims tab card 441, Fire/Motor columns, 12/44 pages, search, CNC
  row → "Not applicable (CNC)" / "—", date filter = SQL, empty state; Claims page
  cards/rate/note for all 3 periods, bar/pie labels = API, table filters = SQL
  (Motor 351, Fire 90, Closed 306, Not yet investigated 23 with no CNC rows, Confirmed
  23, Motor + Hold per Client 7, Sep 2026 = 8 / Fire 3, search 2), empty state.
  Regression: 24 table counts, 11 spot-check hashes identical, `/stats/overview`
  identical once `filed_claims` is removed, 10 × 401 + `/stats/claims` 401, detection
  unchanged, `npm run build` ok. Lint: no new errors beyond the existing
  fetch-in-`useEffect` pattern the other pages already use.
- **Found here, fixed in the Polish pass below**: a stacked Recharts `Bar`'s built-in
  `label` shows the running total on the upper segment, not its own count — fixed on
  the Claims page with an explicit `LabelList`; Quotations/Proposal got the same fix
  later. The Upload modal check for the Claims tab was done later too (see Polish pass).

## Polish pass — DONE
2026-09-27, branch `claims-frontend`. No DB change.
- **Quotations/Proposal trend chart**: both stacked segments use an explicit
  `LabelList` (same as the Claims page), so "Not Yet Converted" shows its own count,
  not the month's total; a 0 segment has no label.
- **Renewal rate = Renewed ÷ (Renewed + Lost) × 100** — Pending (not expired, not
  renewed yet) is left out of the denominator (`stats.py` `get_renewal_ratio`,
  0.0 if Renewed + Lost is 0). Only the "Current Renewal Rate" card shows it (always
  the YTD figure on all 3 tabs); its caption now says "Pending excluded". Counts,
  pies, bars, table and the Expiring card (still Renewed + Lost + Pending) are
  unchanged. Current data: YTD 52.19% → **69.59%** (286 ÷ 411); API-only MTD 69.84% →
  73.33%; daily 100% unchanged.
- **Renewal table Sum Insured**: Motor rows now use the real `motor_policies.sum_insured`
  (was hard-coded None → "—"). Fire rows unchanged.
- **GIS modal subtitle** (`FloodRiskModal.jsx` `hazardSourceText()`): says which hazard
  equals the headline category — "Rated from the 100-year river flood map", "Rated from
  the storm surge map (coastal flooding)", or "Rated from both …"; falls back to
  "Within a mapped flood hazard zone" if the breakdown is missing. `lib/quotations.js`'s
  `gisFromSurvey()` now also copies `river_flood_category` / `storm_surge_category` for
  Fire rows (Motor rows already had them from the spread).
- **Verified**: regression snapshot — 24 counts, 11 of 12 spot-check hashes, 10 × 401
  and detection identical; the 12th (`/stats/renewal-ratio` YTD) differs only in
  `renewal_rate` and the 305 Motor rows' `sum_insured` (compared field by field).
  `npm run build` ok; no new lint errors in the 4 changed frontend files. Browser (no
  console errors): Proposal bar labels = API for all 6 months (e.g. Apr 53 + 18); GIS
  modal Fire #922 Panghulo → "High Risk / Rated from the storm surge map", Fire #1027
  Buliran (river only) and Motor #1309 Hagonoy → "Rated from the 100-year river flood
  map"; Renewal card 69.59% with the new caption on Daily and YTD, YTD cards
  548/286/125/137 unchanged, Motor-filtered table shows real Sum Insured (= DB).
  Claims-tab Upload modal: `8_fire_property_claims.xlsx` → "Detected as: Fire &
  Property Claims", `7_motor_claims.xlsx` → "Detected as: Motor Claims" (cancelled,
  nothing imported). Its manual picker lists both claims types but starts blank on
  every tab (detection-first design).

## Models Phase 1 — ML core, storage, training, reports — DONE (no UI, no auto-retrain yet)
2026-09-27, branch `claims-frontend`. Objectives 1.2 (Predictive Risk, Motor + Fire) and
1.3 (Fraud). Three models, **written by us in numpy** following
`docs/Algorithm_Walkthrough_LogisticRegression_NaiveBayes.docx` and
`docs/Naive_Bayes_Paper_Section.docx` (step names/wording used in code and reports).
scikit-learn is used ONLY in `Backend/tests/ml/` to cross-check.
- **Code** `Backend/app/ml/`: `logistic_regression.py` (Steps 3–6: z = Σw·x + b → sigmoid →
  full-batch gradient descent on log-loss; lr 0.5, stop when loss changes < 1e-12, cap
  50,000 epochs, L2 λ = 0.01 on weights not bias), `naive_bayes.py` (prior × per-clue
  likelihoods, Laplace alpha = 1, higher score wins, normalized confidence),
  `features.py` (Steps 1–2 + all data/leakage rules), `metrics.py` (stratified 75/25 split
  and stratified 5-fold CV, seed 42; accuracy/precision/recall/F1/confusion; ROC AUC by
  ranks with ties = ½), `training.py` (train → evaluate → CV → save → report;
  `python -m app.ml.training` from `Backend/` trains all three), `report.py`.
- **Labels/rows**: LR row = an issued policy whose `period_to` < data date, described by
  ITS QUOTATION (+ vehicle / case survey). Positive = ≥1 Paid Claim with Final Status in
  Closed Claim / Waiting for LOA / Waiting for Billing / Waiting for Claim Check. NB row =
  Paid Claim (never CNC) with a Claim Investigation Result; Suspected + Confirmed = Fraud.
  Current data (as of 2026-09-27): Motor 833 rows / 172 losses; Fire 621 / 57;
  NB 385 / 49 (+23 Paid Claims not yet investigated).
- **Features** — Motor: flood category (quotation address), classification, make, body
  type, color (control), vehicle age (quotation year − `vehicles.model`, clipped ≥ 0), log
  sum insured, deductible, prior counted loss. Fire: survey flood category (worst of
  river/storm surge), quotation occupancy, survey overall risk assessment, log total sum
  insured, count of the 8 fire-protection items in `protection_facilities`, survey
  `risk_class` = b, survey `loss_record` starts "With loss history", prior counted loss.
  Categories one-hot (categories seen in training; unseen → all 0), numbers z-scored on
  the training rows (missing → training mean). Flood NULL with coordinates = "None"
  (outside every zone); no coordinates = "Unknown". `flood_risk_flag` not used (it only
  repeats "category not empty").
- **Leakage rules** (tested): nothing read from policy tables for LR features (Fire's
  construction comes from the SURVEY's `risk_class`). "Prior counted loss" = the most
  recent EARLIER policy on the same vehicle (Motor) / insurance case (Fire) had a counted
  loss REPORTED BEFORE this quotation date — derived from history, not
  `renewing_policy_no` (policy-only field, and 200 Motor / 139 Fire values point to
  pre-dataset policies). NB clues never use final status, LOA, net liability or the
  investigation result; "earlier claims" counts only claims reported before this one.
- **NB clues (fixed bins)**: coverage start→loss (0–15 / 16–30 / >30 days), loss→report
  (0–7 / 8–30 / >30), estimate ÷ sum insured (<0.50 / 0.50–0.69 / ≥0.70 / Unknown), same
  policyholder's Paid Claims reported in the prior 365 days (0 / 1 / 2+), loss→expiry
  (≤30 / >30), nature of loss, coverage type (+ "N/A (Fire)"), New/Renewal
  (`renewing_policy_no`), report→documents (≤30 / >30 / Not yet submitted), line.
- **Unseen-value rule (NB)**: a clue value never seen in ANY training claim is left out
  of the product (no evidence). Needed because 18 of the 23 uninvestigated claims have
  "Not yet submitted" docs + "Unknown" estimate, values no investigated claim has;
  smoothing alone made them ~6× "fraud-like" (Fraud is the smaller class).
- **Adjustable fraud cutoff**: `training.NB_FRAUD_CUTOFF`, stored per model in
  `ml_models.thresholds.fraud_cutoff`; the fraud report compares 0.5/0.4/0.3/0.2 on the
  same 5 CV folds. 0.5 = the documents' "higher score wins" (v1). **Now 0.3** (user
  decision, 2026-09-27, from the v1 table: CV recall 38.9% vs 24.2%, precision 44.6% vs
  43.3%) → `fraud_nb` **v2** (ml_models id 28, active; v1 superseded): test acc 90.6%,
  precision 61.5%, recall 66.7%, F1 64.0%, AUC 0.877 (unchanged — ranking doesn't depend
  on the cutoff); CV acc 85.2 ± 4.6%, prec 44.6 ± 16.5%, rec 38.9 ± 8.9%. Report
  `model_reports/2026-09-27_fraud_nb_v2.md`. Motor/Fire stay v1.
- **Risk levels (LR)**: Low < training loss rate ≤ Medium < 2 × that rate ≤ High, stored
  in `thresholds` (v1: Motor 0.21/0.41, Fire 0.09/0.18). Test/CV "predicted loss" =
  Medium or High; reports also show the 0.5 cutoff and the always-"no" baseline.
- **Storage**: `risk_predictions` (0 rows, never used, keyed by case) was DROPPED after a
  full backup (`Desktop\insurance_db_backup_pre_ml_phase1_20260927_161009.sql`, 24
  tables). New (by `create_all()`): `ml_models` (model_name motor_lr/fire_lr/fraud_nb,
  version, status active/superseded/failed, trained_at, data_as_of, row counts,
  parameters/metrics/thresholds JSON, report_path, error; unique name+version) and
  `ml_predictions` (model_id FK, target_type motor_quotation/fire_quotation/motor_claim/
  fire_claim, target_id, probability DECIMAL(6,5), label, predicted_at; unique
  target_type+target_id) — empty until Phase 2. Predictions never touch business
  tables. The stored model is the one trained on the 75% (its test scores belong to it).
  A failed run = a `failed` row with the error; the active model is untouched;
  `train_model()` never raises (it rolls back its session — use a dedicated session).
- **Reports**: `model_reports/<data date>_<model>_v<N>.md` at the repo root (gitignored),
  one per training: data, the documents' steps, test results + confusion matrix, 5-fold
  CV mean ± SD (accuracy, precision, recall, ROC AUC), LR loss rate by risk level + top
  weights + Motor color control check, NB cutoff table + strongest clues, and a
  synthetic-data note (the generator used these same drivers/red flags).
- **v1 (ml_models ids 17–19; 1–16 were used up by rolled-back test runs)**:
  Motor test acc 61.5% / prec 28.7% / rec 58.1% / AUC 0.615, CV acc 62.8 ± 3.4%,
  rec 48.3 ± 12.1%, AUC 0.595 ± 0.078; loss rate Low 14.9% / Medium 26.1% / High 38.9%;
  color weights −0.24…+0.41 (Black is the 2nd-largest weight — noise, reported as such).
  Fire test 65.2% / 13.0% / 50.0% / AUC 0.612, CV acc 59.7 ± 3.8%, rec 68.5 ± 9.6%,
  AUC 0.660 ± 0.067 (only 3 test rows reach High). Fraud NB test 88.5% / 55.6% / 41.7% /
  AUC 0.877, CV acc 86.2 ± 4.1%, rec 24.2 ± 16.5%, AUC 0.759 ± 0.064; cutoff 0.3 → CV
  prec 44.6%, rec 38.9%; 0.2 → 37.6% / 47.1%.
- **Tests** (33, `Backend/tests/`, all pass): walkthrough sigmoid example (w 1, 0.5; b −4
  → 0.119/0.622/0.378/0.953/0.818) and paper fraud example (alpha 0 → 0.167 vs 0.042 →
  80%); LR = sklearn (C = 1/(λn)) on random + real Motor/Fire data (weights < 1e-3,
  probabilities < 1e-4); NB = sklearn CategoricalNB (< 1e-9); split/folds/scores/AUC =
  sklearn; counts; prior-loss = independent SQL on every quotation + the late-reported
  cases are 0; no policy-stage sources; NB clue values/sources; earlier-claims recount;
  full training saves + reports; retrain supersedes and is deterministic; forced failure
  and not-enough-data → `failed` row, active kept, no exception.
- **Regression**: snapshot identical except the intended table changes (−risk_predictions,
  +ml_models 3 rows, +ml_predictions 0): 12 spot-check hashes, 10 × 401, detection.
- `Backend/requirements.txt` + `numpy==2.5.2`; new `requirements-dev.txt` (pytest 9.1.1,
  scikit-learn 1.9.1, installed in the venv). Reset script clears both ml tables.
- **Paper notes**: the walkthrough doesn't mention the L2 penalty, Laplace smoothing, the
  unseen-value rule or the risk-level thresholds — each needs one sentence in Chapter 3/4.

## Models Phase 2 — automatic retrain, startup, predictions, /ml API — DONE (no UI yet)
2026-09-27, branch `claims-frontend`. No new table; fills `ml_predictions`.
- **Trigger** (`app/ml/jobs.py`): route dependency `Depends(schedule_model_refresh)` on 9
  endpoints — Survey / Fire Quotation / Fire Policy / Motor Quotation / Motor Policy
  uploads, both Claims uploads, `POST /import/batch/upload`, and
  `PATCH /import/policyholders/records/{id}/resolve`. It queues a FastAPI background task
  that runs AFTER the response is sent, and only if the endpoint returned normally (an
  error response carries no background task). The folder upload calls each importer as a
  plain function, so a folder = ONE refresh. Customer Info / Vehicle uploads and all manual
  CRUD (claims PATCH/POST, deletes) do NOT trigger — by user decision (claims are updated
  via upload); they are picked up at the next upload.
- **Refresh** = for each model `training.retrain_if_changed()`, then
  `predict.refresh_predictions()`. Runs on its own `SessionLocal` session, catches every
  error (kept in `jobs.status`, shown by `GET /ml/models`; process-local), never fails the
  upload. Requests during a running refresh are coalesced into ONE more run.
- **Retrain only on change**: each model stores `parameters.data_signature` = SHA-256 of its
  training rows (ids, inputs, label) + settings (LR settings/spec or NB alpha/cutoff/clue
  lists, seed, split, folds, `training.MODEL_CODE_VERSION` — bump it to force a retrain after
  a code change). Equal to the latest attempt's → skip. So: a new open quotation only
  refreshes predictions; a new ended policy, a changed label or setting retrains. A failed
  attempt stores its fingerprint too, so an identical failure (e.g. not enough data after a
  reset) is not retried every upload/reload.
- **Startup** (`main.py` `lifespan` → `jobs.start_startup_refresh()`, daemon thread, startup
  not delayed): trains only models with NO active version, then rewrites predictions (~5s).
  Runs on every `--reload` too (predictions only, when all models exist).
- **Predictions** (`app/ml/predict.py`, whole table replaced in one transaction):
  `motor_quotation` / `fire_quotation` = open quotations + quotations whose policy is in force
  (period_to >= today) → probability + Low/Medium/High; `motor_claim` / `fire_claim` = Paid
  Claims with no Investigation Result → P(Fraud) + Fraud/Legitimate at the stored cutoff.
  Ended-policy quotations, investigated claims and CNC rows get none ("—" in Phase 3).
  Now: 617 Motor (Low 390 / Medium 206 / High 21), 411 Fire (244 / 142 / 25), 23 claims
  (2 Fraud).
- **API** (`app/routers/ml.py`, prefix `/ml`, router-wide login, read-only, no train
  endpoint): `GET /ml/models` (per model: available, version, trained_at, data_as_of, rows,
  thresholds, test scores, CV mean ± SD, report file name, latest failure; + `refresh`
  status), `GET /ml/models/{name}` (+ full metrics + attempt history; 404 unknown),
  `GET /ml/predictions/quotations?line=` and `GET /ml/predictions/claims?line=`
  (`line` = "Motor Car" | "Fire & Property", the frontend's labels; else 422). Schemas
  `MLModelsOverview`, `MLModelSummary`, `MLModelDetail`, `QuotationPrediction`,
  `ClaimPrediction` (+ helpers) in `schemas.py`.
- **Deterministic rows**: `features.py` queries now `ORDER BY` id. Motor rows used to come
  back in join order, so its 75/25 split depended on MySQL's plan (Fire/claims were already
  in id order). Moved Motor slightly (below).
- **One-time retrain (user decision)** through the real refresh path, because v1/v2 had no
  fingerprint: Motor **v2** (ml_models id 93), Fire **v2** (id 94), fraud **v3** (id 95),
  all active (ids 29–92 were used up by rolled-back test runs);
  a second refresh right after retrained nothing (9.5s vs 5.6s).
  Motor v2: test acc 63.0% / prec 29.3% / rec 55.8% / F1 38.4% / AUC 0.614; CV acc
  63.6 ± 2.0%, prec 28.5 ± 2.6%, rec 50.6 ± 7.2%, AUC 0.622 ± 0.045; loss rate Low 15.1% /
  Medium 28.9% / High 33.3% (6 rows); color −0.23…+0.40. Fire v2 and fraud v3 = identical
  to Fire v1 / fraud v2 (same rows, same order).
- **Tests**: 51 pass (33 Phase 1 + 18 new: `test_predict.py`, `test_jobs.py`,
  `test_ml_api.py`). API tests use `TestClient(app)` WITHOUT `with` (no startup refresh) and
  an autouse fixture that stops a background refresh from opening a real session. Needs
  `httpx==0.28.1` (added to `requirements-dev.txt`; Starlette warns it will want `httpx2`
  later — harmless).
- **Regression**: snapshot identical except `ml_models` 4 → 7 and `ml_predictions` 0 → 1,051;
  the 4 `/ml` endpoints return 401 without a token.

## Models Phase 3 — frontend (predictions, accuracy cards, auto-refresh) — DONE
2026-09-27, branch `claims-frontend`. No DB change.
- **New** `lib/ml.js` (fetch quotation/claim predictions and `/ml/models`, never throw —
  failures just mean "—" / "Not trained yet"; `waitForModelRefresh()`; % and date
  formatting) and `components/ModelShared.jsx` (`RiskLevelCell` Low gray / Medium amber /
  High red, `ClaimPossibilityCell`, `ModelAccuracyCard`).
- **Proposal**: Risk Assessment + Claim Possibility are the LR predictions, merged by
  `line-id` in the page only (`fetchAllQuotations()` is unchanged, so Policy Holder Info's
  Quotation tab doesn't show them). "—" = no prediction (quotation whose policy has
  ended). Risk filter = All / Low / Medium / High ("All" keeps "—" rows). March Policy
  Forecast REMOVED (+ its mock data, `RoundedBar`, `BarValueLabel`). "Average Quotation
  Claiming Rate" → **"Average Claim Possibility"** = mean probability over the table's
  current rows with a prediction (follows period/month and every filter; both lines mixed
  when the line filter is All), caption "Based on N quotations · All lines | <line>".
- **Accuracy cards** ("Model accuracy (Logistic Regression)" on Proposal with Motor Car +
  Fire & Property; "Fraud model accuracy (Naive Bayes)" on Claims under Fraud Rate): show
  the **5-fold cross-validation MEANS** (user decision — the single 25% test sets are small,
  fraud has ~12 cases), labelled "5-fold average (cross-validation)": "X% accurate",
  "catches Y% of losses / fraud", "vN · trained <date>". Reports keep both.
- **Fraud Warning** (Claims page + Policy Holder Info → Claims tab): `fetchAllClaims()` merges
  the NB predictions: `fraud_warning` = "Suspicious · 56%" / "Not suspicious · 6%" (% =
  P(Fraud); flagged above the stored cutoff 0.3), `fraud_flag` drives red vs gray; kept as
  TEXT because the Claims tab search stringifies every field. "—" for CNC, investigated
  claims, or no prediction. Hover note: a prediction, not an investigation result.
- **Auto-refresh** (user decision): only Policy Holder Info has upload UI (one Upload modal
  for all tabs + Needs Review resolve). After an upload/resolve → `refreshAllData()` as
  before, then `waitForModelRefresh()` polls `GET /ml/models` every 2s (stop when it was
  seen running and has stopped; 4s grace if it never starts; 120s timeout), then refetches
  the claims; "Updating fraud predictions…" shows on the Claims tab meanwhile. Proposal and
  Claims pages: if a retrain is running when they open, they show "Updating…", wait, then
  refetch predictions/claims + scores.
- **Backend tweak** (`app/ml/jobs.py`): `status.running` now stays True across a coalesced
  extra run (was briefly False between the two runs, which could stop a poller early);
  test added. `tests/ml/test_jobs.py` got a `forget_fingerprints` fixture — 3 tests had
  assumed the dev DB's active models had no fingerprint (true only before Phase 2's
  one-time retrain).
- Claims page chart now grows with the taller right-hand column (min 270px) — the new card
  had left a white gap.
- **Verified**: 51 backend tests pass; `npm run build` ok; lint = pre-change baseline on
  every changed file (the "fetch in useEffect" rule, same as before). Browser (fresh loads,
  no console errors): Proposal Past 6 Months = 372 / "Based on 372 quotations · All lines" /
  15%, Low 216 (10%), Medium 140 (21%), High 16 (28%), Motor 198 / 20%, Fire 174 / 9% — all
  = SQL; August 2025 = 66 quotations, 14 predicted / 52 "—", avg 15% = SQL; cards Motor 64% /
  51%, Fire 60% / 68%, fraud 85% / 39% (= CV means). Claims page, all 441 claims: 23
  warnings = exactly the uninvestigated Paid Claims, 2 Suspicious (56%, 39%) in red, none on
  CNC/investigated. Claims tab both lines + search "suspicious" ok. Auto-refresh with real
  ZZTEST uploads (1 row, unknown policy → Needs Review; nothing retrained): Claims tab polled
  running=true until 18.5s then refetched; Proposal and Claims pages opened mid-retrain
  waited and refetched. The 3 ZZTEST import_records (6579–6581) were deleted by exact id
  after a marker check; counts back to baseline. Regression snapshot: ALL IDENTICAL.
- **Found, not fixed**: while a retrain runs (~15–20s after a learning-data upload), other
  backend requests get slow (a `/ml/models` call took ~8s) — training and the web requests
  share one Python process. Harmless (everything completes) but noticeable; a fix would be
  running the refresh in a separate process.

## Policy Forecast (Proposal page card) — DONE
2026-09-27, branch `policy-forecast`. **Plain statistics, NOT one of the ML models** (and
not based on Claim Possibility). No DB change — no new table, no schema change, so the v3
presentation backup stays valid. Replaces the mock "March Policy Forecast" removed in
Models Phase 3.
- **Question**: how many new policies should Maagap expect next month?
- **Waiting period W** = 95th percentile of days from quotation_date to the policy's
  issue_date, rounded up, per line, computed from the data every time (not hardcoded).
  Current data: every conversion takes 1–7 days (median 4, p90/p95/p99/max all 7) on both
  lines → **W = 7**. A quotation converting later than W counts as not converted (none do).
- **Next month (the headline)** = quotations sent per month (average of the past 365 days)
  × conversion rate, per line, then summed. Conversion rate = quotations that became a
  policy within W ÷ quotations old enough to be decided (age ≥ W), age window W..W+364
  days (same idea as Renewal Rate excluding Pending). Now: Motor 302/389 = 77.6% × 388/12
  = 25.1; Fire & Property 253/300 = 84.3% × 303/12 = 21.3 → **October 2026 ≈ 46**. Rates
  are stable across windows (Motor 75–79%, Fire 83–87% for 3/6/12/24 months/all time).
- **Why not "open quotations × rate" for next month** (the first idea): quotations decide
  within 7 days, so today's open quotations are almost all decided before the month starts
  (only ~1.2 of them land in October). That number would say ≈ 6 when ≈ 46 happen.
- **Open quotations** (separate line, NOT added to the monthly number): no policy yet and
  younger than W (age 0..W−1; age = days from quotation_date to today; archived quotations
  are in `deleted_*`, so not counted). No validity/expiry field exists (Fire's
  `period_cover` is "One (1) Year" on every row — coverage length, not quote validity).
  **Age-aware**: each counts with P(becomes a policy | still unconverted at its age) =
  share that converted after that age ÷ share still unconverted at that age, from the same
  past quotations (e.g. Motor 78% at day 0–1 → 50% at day 6). Now: 9 open (Motor 6, Fire 3)
  → ≈ 5.6 policies within 7 days. The simple rate over-forecast in the backtest.
- **"Known on a day"** = dated on or before that day (end of day). Everything is computed
  from (quotation_date, issue_date) pairs + an as-of date, so the backtest runs the same code.
- **Backtest** (last 12 complete months; on the 1st of the month before, forecast the month
  with only that day's data; actual = policies issued in the month): average monthly error
  **Motor 14.0%, Fire & Property 24.2%, total 10.7%**; 12-month total error −1.9% / −5.1% /
  −3.3%; total within ±20% in 10 of 12 months (worst: Sep 2025, 45.3 vs 61). Open-quotation
  forecast, 12-month total error: Motor −9.1%, Fire −8.1% (monthly counts 0–6, noisy).
  Honest caveat for the defense: the synthetic data has steady volume and no seasonality, so
  a plain average of past monthly policies is about as accurate; the volume × rate split is
  kept because it shows the two levers (quotation volume, conversion rate).
  Report: `model_reports/2026-09-27_policy_forecast_backtest.md` (gitignored; regenerate
  with `python -m app.services.policy_forecast` from `Backend/`).
- **Code**: `app/services/policy_forecast.py` (method + backtest + report writer);
  `GET /stats/policy-forecast` in `stats.py` (read-only, login required, ~0.4s) →
  `schemas.PolicyForecast` (+ `PolicyForecastLine`, `PolicyForecastBacktestRow`,
  `PolicyForecastBacktestLine`): target month, per-line W / decided / converted / rate /
  volume / expected / open / expected-from-open / backtest errors, and the 12-row backtest.
- **Card** (`proposal.jsx` `PolicyForecastCard`, right column between Average Claim
  Possibility and Model accuracy): "October Policy Forecast" (month name from the API's
  target month, never hardcoded) · "≈ 46 new policies" · "Motor 25 · Fire & Property 21" ·
  "Based on ≈ 58 quotations a month and past conversion rates (Motor 78% · Fire & Property
  84%), past 12 months" · "Open now: 9 quotations → ≈ 6 policies within 7 days" · "Backtest,
  last 12 months: off by 11% on average". Always both lines; NOT affected by the period,
  month, line or other filters (forward-looking, states its own basis). The card itself does
  not say "statistics, not ML" (user decision) — this section and the report do.
- **Verified**: 12 new tests (`tests/test_policy_forecast.py`: W, decided/open boundaries,
  age-aware formula by hand, later data never changes a past forecast, Dec→Jan, backtest
  months/actuals, error measures, 401, endpoint = independent SQL) + all 51 existing = 63
  pass. Live endpoint = a separate SELECT calculation on every per-line field incl. the
  age-aware open expectation and August 2026 actuals. Browser: card text exact, unchanged
  under Policy Line = Motor Car (Average Claim Possibility followed it: 198) and Past 3
  Months (KPI 187); rest of page = Phase 3 values; no console errors. `npm run build` ok;
  lint = pre-change baseline (3 existing errors). Regression snapshot: ALL IDENTICAL.
- **Found, not fixed**: the extra card makes the right column taller (372 → 615 px), and the
  table panel stretches with it — the page now scrolls ~220 px at 1568×957 with white space
  under the table's 5 rows.
- **Fixed (2026-09-28)**: an empty `risk_predictions` table had come back (created 2026-09-27
  21:24:13 when `main` was briefly checked out at the pre-Models commit `5bdcb0f` while
  `uvicorn --reload` ran — that old `models.py` still has `RiskPrediction`, so
  `create_all()` recreated it). On user instruction it was dropped again: confirmed 0 rows
  and no FK pointing at it, `DROP TABLE risk_predictions`. Afterwards 25 tables, and every
  other table's row count was identical before and after. It is not in the v3 backup or the
  reset script, and no current code uses it. Lesson: checking out an old commit with the
  backend running can recreate dropped tables — stop uvicorn before switching to an old commit.

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

## ⚠️ Importer-wide: cells containing None / NA / N/A / null are read as BLANK
pandas' default NA list (`None`, `NA`, `N/A`, `n/a`, `null`, `NULL`, `nan`,
`NaN`, `#N/A`, ... — confirmed on pandas 3.0.5) converts those exact cell texts
to NaN in EVERY importer, including the ones reading with `dtype=str`
(Customer Info, Claims). Such a cell is stored as NULL, not as the text. Only
exception: the Survey "Protection Facilities" column (see Change 2). Data
generators / real exports must never use these words as meaningful values
(e.g. write Loss Record "No loss record", not "None").

## Known Remaining Issues (not yet fixed)
- No delete endpoint exists yet for `insurance_cases` (quotations got one
  in a later session — see Frontend Status's Delete buttons bullet; the
  original gap was surfaced when a leftover test quotation, `FP-Q-3`, had
  to be removed via raw SQL instead of through the API).

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

**Second cleanup (2026-09-10)**: discovered the table had drifted to 17
rows (an untracked `new1` test row, id 33, had been added since the last
cleanup above). Investigated all rows with the user and did a broader
pass this time — removed `new1` plus every other obviously-test-named
leftover still sitting in the table from earlier sessions (`more`,
`newaccount`, `admin_test`, `admin_test2`, `admin_test3`, `testing1`,
`test2`, `test3`, `test4`, `test5`, `ttry`, `admin12` — 13 rows total).
**4 real users remain: `james` (id 3), `aldrin` (id 5), `manager` (id 8),
`Aaron James` (id 10, role `manager`).** No FK anywhere in `models.py`
references `users.id`, so this was safe — but note `users` has no
delete-archive table (unlike `deleted_policyholders` etc.), so this
cleanup was a hard, unrecoverable delete, done only after explicit user
confirmation of the exact row list.

## Password rules + Change Password — DONE
2026-09-28, branch `password-rules`. No DB change.
- **Rule for a NEW password**: at least 8 characters, at least 2 letters (only A–Z / a–z
  count, so "ñ" doesn't), at most **72 bytes** (bcrypt's limit — bcrypt 5.0 raises above it
  instead of truncating; "é"/"ñ" count as 2 bytes). Messages: "Password must be at least 8
  characters and include at least 2 letters." / "Password must be at most 72 characters
  (accented characters count as 2)."
- **Where enforced**: backend `security.password_rule_error()` (the real check), used by
  `POST /users` and `POST /users/me/password` → 400 with the message. Frontend
  `lib/passwordRule.js` has the same rule/messages (checked before submitting) and the hint
  "At least 8 characters, including 2 letters" under the password field. `POST /users` also
  rejects a blank/whitespace-only username → 400 "Username is required." (the username is
  otherwise stored as typed).
- **Login is unchanged**: `/login` never checks the rule, so passwords set before it (incl.
  Aaron James's) keep working. `verify_password()` now returns False above 72 bytes, so an
  over-long login is a clean 401 (was a raw 500).
- **Change Password**: Settings (sidebar) → "Change Password" link, for every role →
  `ChangePasswordModal.jsx` (Current / New / Confirm new). `POST /users/me/password`
  (login required): wrong current password → 400 "Current password is incorrect." (400, not
  401 — `api.js` logs out on any 401); rule → 400; same as current → 400 "New password must
  be different from the current password."; success → `{"message": "Password changed."}`.
  The user **stays logged in** (JWTs are stateless, 60 min, never revoked — a forced logout
  wouldn't cancel the old token; real revocation would need a token-version column).
  There is still no reset/forgot-password flow (the login page link stays commented out).
- **Tests**: `tests/test_passwords.py` (23) — rule cases (7 chars, 8 digits, 1 letter + 7
  digits, 73 bytes, 37 × "é", "ñé123456"), `POST /users` weak/blank-username/valid, a
  below-rule old password still logs in, 73-byte login = 401, change-password 401 / wrong
  current / weak / same / success. Temporary ZZTEST users only, in the rolled-back `db`
  fixture; the real account is never read or changed.
- **Verified**: 86 tests pass (63 + 23); regression snapshot ALL IDENTICAL (users = 1);
  `npm run build` ok; lint = pre-existing unused-import errors only. Browser (manager session
  via a generated token, the real password never used): Create Account — weak password shows
  the message, valid one creates the account (test user id 63 deleted by exact id);
  Change Password — weak new → rule message, wrong current → "Current password is
  incorrect." (still logged in), then Cancel. The Aaron James password was NOT changed.

## Terms of Service + Privacy Policy (Create Account modal) — DONE
2026-09-28, branch `terms-privacy`. Frontend only.
- **Text lives in `Frontend/src/content/legal.js`** (`TERMS_OF_SERVICE`, `PRIVACY_POLICY`):
  title, effective date, and `sections` (`heading`, optional `text`, optional `bullets`;
  `**bold**` works inside text; sections are numbered automatically). Edit wording there only.
- `components/LegalModal.jsx` shows a document on top (`z-[60]`) of the Create Account
  modal; Close / X / backdrop close only it, so typed values stay. The checkbox links
  ("Terms of Service", "Privacy Policy") are `type="button"` buttons (were dead
  `<Link to="#">`); the checkbox is still required.
- Privacy text adjusted to match the system (user decision): no "date of birth"; system
  users = username, role, hashed password; only business records are archived on delete.
- Verified: browser — typed values kept after opening/closing both documents, checkbox
  untouched and still required, all 10 sections scroll, no console errors; at 794×514 the
  card fits and scrolls. `npm run build` ok; 86 backend tests pass; regression ALL IDENTICAL.
- **Found, not fixed (pre-existing)**: at phone width (<768px) the sidebar — and with it
  Settings and every modal it opens — is hidden, so Create Account isn't reachable on a
  phone.
- **Fixed (same branch): light-mode buttons.** `index.css` had Vite's starter
  `@media (prefers-color-scheme: light)` block (`button { background-color: #f9f9f9 }`,
  `a:hover { color: #747bff }`, `:root { color: #213547 }`). Being unlayered, it beat
  Tailwind 4's layered `bg-*` / `hover:text-*` classes, so on a computer in LIGHT mode the
  yellow buttons (Login, Sign Up, Change Password, filters, pagination, …) turned near-white
  and link hovers purple. The dev browser is in dark mode, so it never showed. The whole
  block was removed (user decision), so light mode now renders exactly like dark mode did.
  Verified with same-origin iframes whose `color-scheme` forces `prefers-color-scheme`
  light/dark: computed background/text colour of every visible button and link on Login,
  Overview, Policy Holder Info, Proposal, Claims, Settings, Create Account and Change
  Password — before the fix light differed on every page (e.g. Sign Up `#f9f9f9`); after,
  light = dark = the pre-fix dark baseline everywhere (Proposal's 5 GIS "View" buttons
  checked separately once loaded: black in both), root text colour identical;
  `npm run build` ok. Don't reintroduce unlayered element rules — put base styles in
  `@layer base` so Tailwind classes still win.

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
  - **Claims tab**: DONE — real data, see "Claims Phase 4 — Frontend".
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
- `pages/overview.jsx`, `pages/distribution.jsx` — all mock dashboard/chart
  data, would need new backend aggregation endpoints (none exist yet)
  before connecting.
- `pages/proposal.jsx` (Quotations/Proposal) — DONE. (History: the March Policy
  Forecast chart, the Average Quotation Claiming Rate indicator and the table's
  Risk Assessment/Claim Possibility "Pending" placeholders were mock until Models
  Phase 3 — all now real or removed; see "Models Phase 3". A real, statistics-based
  "<next month> Policy Forecast" card came back later — see "Policy Forecast".)
  - **Backend**: `GET /stats/quotation-proposal` in `routers/stats.py`,
    `QuotationProposalStats`/`...PieSlice`/`...TrendEntry` schemas — same
    one-endpoint-combines-several-sections shape as `/stats/overview`.
    `Literal[3, 6, 12]` as the `months` query param type does NOT work in
    this FastAPI/pydantic version — a query string like `"3"` fails literal
    validation with no int coercion attempted first (`Input should be 3, 6
    or 12`, got `"3"`) — used a plain `months: int = Query(6)` with a
    manual `if months not in (3, 6, 12): months = 6` instead. "Converted" =
    `quotation.policy is not None`, same check `/stats/overview` already
    uses.
  - **Filter rework (later session)**: KPI cards, both pies, the trend
    chart, AND the table are now ALL scoped to one shared active filter —
    originally only the trend chart was period-scoped, KPI/pies were
    all-time. Two mutually exclusive modes, both computed server-side:
    rolling (`months=3|6|12`, unchanged param, now also scopes KPI/pies —
    range is `_shift_month(today, -(months-1))` through the current
    month's last day, uncapped at today since that's what the pre-existing
    trend bucketing already did for the current-month bucket) and month
    (`year` + `month` together — a partial pair silently falls back to
    rolling, same "invalid → default" convention as `months`; range is
    that calendar month, capped at today if it's the current month, same
    cutoff rule `_range_for_period("mtd", ...)` already uses elsewhere in
    this file — a past month shows in full, a future month is all-zero).
    Response gained `mode` ("rolling"|"month"), `range_start`/`range_end`
    (the exact bounds actually used — lets the frontend filter its
    already-fetched quotations list identically instead of re-deriving
    month math in JS), and `year`/`month` (echoed back only in month mode).
    `months` became `Optional[int]`, null in month mode. In month mode
    `trend` switches to DAY-level granularity (one bucket per day 1..last
    day-in-range, `label = str(day)` — same convention as
    `/stats/policy-distribution`'s MTD `bar_chart`) instead of one bucket
    per month.
  - **Frontend filter rework**: the table's pre-existing `MonthYearPicker`
    (+ "Show All Months" clear button) now drives `fetchStats` directly —
    picking a month sends `{year, month}` instead of `{months}`; clearing
    reverts to `{months: PERIOD_TO_MONTHS[period]}`. The pre-existing
    "Past X Months" dropdown is left in place but visually disabled
    (grayed out, non-interactive) while a month is selected, since it's
    superseded rather than removed. Table rows now filter against
    `stats.range_start`/`stats.range_end` (plain ISO date strings, valid
    to compare lexicographically) instead of the old ad-hoc client-side
    month-only match — same bounds the backend used for KPI/pies/trend, so
    all four sections of the page agree by construction. The 3 KPI cards'
    and both `MiniPie`s' hardcoded "All time" sub-label became a computed
    `periodLabel` (the active month name+year, or the `period` string).
    Trend chart heading switches "Monthly ..." / "Daily ..." based on
    which mode is active. The Policy Line dropdown's existing "All" option
    was deliberately KEPT (not narrowed to Policy Holder Info's
    All-less Fire/Motor-only toggle) — explicit user choice, since removing
    it would drop the table's existing mixed-line view for no requested
    gain. The two still-mock cards (Average Quotation Claiming Rate, March
    Policy Forecast) gained an "As of {current year}" sub-label (computed
    client-side via `new Date().getFullYear()`) to make explicit that
    they're yearly-scoped and deliberately unaffected by either filter —
    labeling only, their content is still mock (Objective 1.2 not started).
  - **Stacked bar double-count bug — FIXED (later session)**: the trend
    chart's stacked bar was stacking `quotation_count` (TOTAL quotations in
    the bucket, per its own schema comment) directly on top of
    `converted_count` (the subset of those that converted) — when most/all
    quotations in a bucket were converted, the bar visually showed roughly
    double the real total (e.g. 9 total/9 converted rendered as an 18-tall
    stack: a 9 segment + another 9 segment). Predated the filter rework
    above, first noticed and flagged (not fixed) while verifying it.
    Backend fields are unchanged/correct (`quotation_count` genuinely means
    total, same as its schema comment always said) — fixed purely in
    `proposal.jsx`'s `trendData` mapping: derives a client-side
    `not_converted_count = Math.max(0, quotation_count - converted_count)`
    and stacks `converted_count` + `not_converted_count` instead of
    `converted_count` + `quotation_count`, so the two segments now sum
    exactly to the real total instead of double-counting the converted
    portion. Legend/tooltip label for that second bar renamed from
    "Quotation" to "Not Yet Converted" to match what it now actually shows.
    Verified against real data in both modes: rolling mode's August bucket
    (real total 9, converted 9) now renders height 9 (was 18); May/Jun/Jul
    (real total 1 each) render height 1 (was 2); Sep (real total 2) renders
    height 2 (was 4). Month mode (August 2026, day-level) verified the same
    way: day 8 (real total 1) renders height 1 (was 2), days 25/27/28/29
    (real total 2 each) render height 2 each (was 4) — KPI cards for that
    month independently confirm 9 total/9 converted/100%. Every quotation
    currently in the dev DB happens to be fully converted, so no bucket
    visually shows a two-color split yet, but the formula sums to the real
    total by construction for a partial-conversion bucket too.
  - **Verified live** (real dev data, no fixtures needed — May-Sep 2026
    already had varying per-month/per-day counts): rolling mode KPI/pies
    now read "Past 6 Months" instead of "All time" and match a direct
    `?months=6` fetch; switching to a specific month (September 2026)
    correctly capped `range_end` at today, showed day-level trend bars
    (bucket for day 2 matching the table's 2 real Sept 2 rows), and
    disabled the Past X Months dropdown; "Show All Months" correctly
    reverted every section back to rolling mode; the Policy Line filter
    (Motor Car) correctly narrowed only the table rows, leaving KPI/pies/
    trend untouched. No console errors.
  - **The table itself gets no new endpoint** — it reuses the exact same
    per-quotation data Policy Holder Info's Quotation tab already fetches,
    extracted into `Frontend/src/lib/quotations.js`'s `fetchAllQuotations()`
    (case→policyholder join, quotation→policy "converted"/policy_no
    lookup) so the logic exists in exactly one place; `policy.jsx`'s own
    `fetchQuotations` was refactored to call it too, no behavior change
    there. "Quote Number" column shows the raw numeric `id` (neither
    quotation type has its own business quote-number field) — same
    no-fake-prefix convention as every other tab.
  - **GIS modal** (`components/FloodRiskModal.jsx`, formerly 100% hardcoded
    mock — fake location, fake "Flood Prone Area"/"Level: Low", fake
    findings list "Low Lying Area"/"Clogged Drain") now takes a real
    `quotation` prop and has 3 real states: no coordinates at all (never
    geocoded / geocoding failed) → "Flood risk not yet available for this
    quotation" with a placeholder box instead of a map; coordinates present
    but outside every mapped hazard zone → real map+pin, "Not Flood-Prone
    / Outside every mapped flood hazard zone"; coordinates + a matched zone
    → real map+pin, real Low/Medium/High category. The fabricated findings
    list is gone entirely — the shapefile only gives a hazard category, not
    specific findings like "clogged drain".
  - **Real design gap found and resolved during planning**: unlike Motor
    Quotation, `FirePropertyQuotation` was never given its own
    latitude/longitude/flood_risk_flag/flood_risk_category columns (only
    Fire Survey and Motor Quotation were in scope for the GIS lookup work
    — see "GIS Flood-Risk Lookup Service" above). Per explicit user
    decision, Fire quotation rows in `fetchAllQuotations()` borrow their
    GIS fields from the Survey sharing the same `insurance_case_id`
    (latest by id if more than one survey exists for a case), falling back
    to the "not yet available" state only if no such Survey exists or the
    Survey's own GIS fields are null. Motor rows use their own stored GIS
    fields directly, no borrowing needed.
  - **Verified end-to-end with real fixtures**: a Fire policyholder/case
    with 1 Survey (real geocoded address, "Medium") + 2 quotations (1 with
    a linked Policy, 1 without), and a Motor policyholder/case with 2
    vehicles + 2 quotations (1 real-address/converted, 1 bad-address/
    unconverted) — `total_quotations`/`converted_accounts`/
    `conversion_rate`/both pies all reconciled exactly against direct SQL
    counts before AND after the fixtures existed, across all 3 `months`
    values, with the fixtures' March 2026 dates landing correctly in the
    trend chart's March bucket (4 quotations, 2 converted). GIS modal
    checked live in the browser for all 3 states: Fire quotation → real
    map/pin/"Medium Risk" via the Survey fallback, Motor quotation → real
    map/pin/"Medium Risk" from its own stored fields, Motor quotation with
    the bad address → the "not yet available" fallback, no broken/empty
    map. All fixtures deleted afterward (matched by exact policyholder
    name, cascaded through cases/surveys/quotations/policies/vehicles in
    FK order) — confirmed the pre-existing "GIS Demo Record" fixture
    (policyholder id 54, survey id 20) was untouched by the cleanup.
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
    (Renewed + Lost) × 100 — Pending excluded (changed in the "Polish pass";
    was Renewed ÷ Expiring). Same-line-only renewal matching (fire only renews
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
  more than once. Reset script: **`Backend/scripts/reset_data.sql`** (see the
  "Reset script" section below — backup first). The old inline version that
  used to live here missed the claims tables and every `deleted_*` table, and
  (unlike the new script) never touched `users`.
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
- Automated tests (pytest, first added in Models Phase 1): from `Backend/`,
  `./venv/Scripts/python -m pip install -r requirements-dev.txt` once, then
  `./venv/Scripts/python -m pytest tests`. The `db` fixture (`tests/conftest.py`)
  runs on the dev DB inside one outer transaction that is always rolled back
  (commits become savepoints), so tests leave no rows — but they DO use up
  auto-increment ids.

## Immediate Next Steps (in order)
1. Models Phases 1–3 are DONE (see those sections). Open follow-ups: backend requests
   slow down while a retrain runs (see "Models Phase 3" → Found); Objective 1.4
   retention still has no dedicated model (Renewal Ratio page is computed, not predicted).

Frontend display of the Motor Quotation GIS fields (latitude/longitude/
flood_risk_flag/flood_risk_category) on the Quotation tab's
`MOTOR_QUOTATION_COLUMNS` — previously listed here as not yet done — was
actually completed; re-confirmed live in a full pre-presentation validation
pass (2026-09-22): the Quotation tab shows real, non-blank Latitude/
Longitude/Flood Risk Flag/Flood Risk Category values for Motor Car rows
that have them, matching Fire/Property's Survey Report tab treatment.