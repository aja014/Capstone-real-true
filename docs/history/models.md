# ML models phases 1–3 and Policy Forecast

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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
