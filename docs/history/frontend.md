# Frontend status (page-by-page build history)

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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
