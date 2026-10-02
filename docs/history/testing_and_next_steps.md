# Testing conventions and next steps (as of 2026-10-01)

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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
