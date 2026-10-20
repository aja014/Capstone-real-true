# Claude Code plan: update backend tests for the v5d sample data (more fire claims, more fraud spread across months)

Context: the sample data was rebuilt again (v5d). Fire claims were raised to about 8% of ended fire
policies (adviser-approved) and the fire patterns were made stronger. Fraud was raised to about 6.8% and spread so each of the last 18 months has at least one case. The ML code did NOT change.
Only tests that hard-code dataset numbers should fail (the same ones changed for v5).

Rules
- Do not change any code in `Backend/app/`. Only test files.
- `insurance_db` is read-only. Run the tests on `insurance_db_test` as described in CLAUDE.md
  ("How to test"): first REFRESH insurance_db_test from insurance_db with mysqldump (it still holds v5),
  then check engine.url.database = insurance_db_test before running.
- Never print passwords, full URLs or .env values. Do not commit.

Steps
1. Refresh insurance_db_test from insurance_db (now v5d). Check the row counts match below.
2. Run the full suite once and list every failing test.
3. Group (a) old v5 numbers: update the exact training counts (train, test, positive) to the values
   from this run, the same way as last time. Ranges/invariants stay as they are.
   Group (b) anything else: STOP and report to Aj.
4. Rerun the full suite. Expected: 330 passed.
5. Report: tests changed, old value -> new value, final pass count.

v5d reference (generator + real training code, today = 2026-10-19)
- Upload row counts: customers 1845, fire surveys 1193, motor quotations 1574, fire quotations 3005,
  fire policies 2774, motor policies 1193, motor claims 701, fire & property claims 240
- Motor: 906 ended policies, 286 counted losses (31.6%)
- Fire: 1885 ended policies, 137 counted losses (7.3%)
- Fraud: 827 investigated claims, 56 fraud (6.8%)
(The tests use their own date, 2026-09-27, so their exact counts will be a little lower.)
