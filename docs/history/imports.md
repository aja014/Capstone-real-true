# Bulk import, matching and Needs Review

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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

## ⚠️ Importer-wide: cells containing None / NA / N/A / null are read as BLANK
pandas' default NA list (`None`, `NA`, `N/A`, `n/a`, `null`, `NULL`, `nan`,
`NaN`, `#N/A`, ... — confirmed on pandas 3.0.5) converts those exact cell texts
to NaN in EVERY importer, including the ones reading with `dtype=str`
(Customer Info, Claims). Such a cell is stored as NULL, not as the text. Only
exception: the Survey "Protection Facilities" column (see Change 2). Data
generators / real exports must never use these words as meaningful values
(e.g. write Loss Record "No loss record", not "None").
