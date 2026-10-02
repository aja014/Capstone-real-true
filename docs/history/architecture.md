# Architecture, schema and backend structure

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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
