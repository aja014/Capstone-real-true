# Claims phases 1–4

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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
