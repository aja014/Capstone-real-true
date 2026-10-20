# FIREMAP — System Reference (for the User Manual)

Inventory of every page, element, formula and rule, taken from the code on branch
`docs-reference` (= `main` at `d133650`). **Live values are as of 2026-09-28** on the v4
presentation dataset (1,129 clients). Nothing here is from memory: every number was read
from the running API or with a `SELECT` on that day. A live value will drift as days pass
(anything tied to "today", "this month" or "past N months").

**Conventions used throughout the app**
- "—" (grey dash) = the value is empty/not on file, or there is nothing to show (e.g. no prediction).
- Money = `₱1,234.56` (Philippine locale, always 2 decimals). An empty money field shows "—";
  an aggregate total with nothing to add up shows `₱0.00`. On a stat card a long value (a ₱
  amount in the millions) is drawn in a smaller font so the full amount fits the card — it is
  never shortened or cut off (since 2026-10-04).
- Dates in tables = `MM/DD/YYYY`.
- Percentages on cards are rounded to whole numbers unless stated (Renewal Rate: 2 decimals,
  Fraud Rate: 1 decimal; model accuracy cards: 1 decimal, AUC 3 decimals — the same as the
  report files).
- A model's **prediction** percentage (Claim Possibility on the Proposal table, the "% fraud
  chance" on claims) shows **1 decimal, rounded down** (since 2026-10-04): the level thresholds
  are whole hundredths (e.g. Medium from 0.21), so a value just under one never shows as
  reaching it (0.20985 → "20.9%" Low, never "21.0%").
- "…" = still loading.
- Two insurance lines everywhere: **Fire & Property** and **Motor Car** (also written
  "Motor & Car" on some charts).
- Tables show 8 rows per page (Proposal table: 5), with `«  N / M  »` paging at the bottom right.

---

## Contents
1. Roles and access
2. Login, session, Settings, passwords, Terms and Privacy
3. Page: Overview
4. Page: Quotations / Proposal
5. Page: Policy Distribution
6. Page: Renewal Ratio Monitoring
7. Page: Claims
8. Page: Policy Holder Information (6 tabs)
9. Shared parts (Upload modal, Needs Review modal, GIS popup, JSON "View" popup, accuracy cards, pickers)
10. Bulk import (file types, detection, order, matching, Needs Review, rollback)
11. Delete and archive
12. GIS (flood-risk lookup)
13. The three models
14. Policy Forecast (method)
15. Renewal Ratio (method)
16. Policy Distribution (method)
17. Glossary
18. Found while inventorying (unclear / inconsistent / possibly wrong)

---

## 1. Roles and access

There are two roles: **manager** and **admin**. The live database has 1 user (role manager).

| | Manager | Admin ("Admin & Finance") |
|---|---|---|
| Overview, Quotations/Proposal, Policy Distribution, Renewal Ratio Monitoring, Claims pages | ✅ | ❌ (sidebar item greyed out; typing the URL redirects to Policy Holder Information) |
| Policy Holder Information page (all 6 tabs, Upload, Needs Review, every Delete) | ✅ | ✅ |
| Settings → **Create an Account** | ✅ | ❌ (link hidden; the API also returns 403 "Only managers can create admin accounts.") |
| Settings → Change Password, Log out | ✅ | ✅ |
| Page after login | Overview | Policy Holder Information |

- An account created in the app is **always role admin**. No screen or endpoint can create
  another manager.
- The page restrictions are enforced **in the browser** (`App.jsx` ProtectedRoute + sidebar)
  **and on the server** (fixed 2026-09-28). With an admin login the server answers **403
  "Manager access only."** on:
  - every `/stats/*` endpoint (the five manager pages);
  - `GET /ml/models/{model_name}`, `GET /ml/predictions/quotations` and
    `GET /ml/inputs/quotations` (since 2026-10-16);
  - `POST /users` (403 "Only managers can create admin accounts.").
- Everything Policy Holder Information uses stays open to both roles: all lists, uploads,
  Needs Review, deletes, `GET /ml/models` (upload refresh status),
  `GET /ml/predictions/claims` (Fraud Warning on the Claims tab) and `GET /ml/inputs/claims`.

## 2. Login, session, Settings, passwords, Terms and Privacy

### Login page (`/`)
- Left: MAAGAP logo, "Be Ready. Be Protected.", "Protect your vehicle and your future with
  coverage designed for real life."; fields **Username**, **Password** (eye icon shows/hides);
  **Login** button ("Logging in..." while waiting). Right: photo.
- Wrong username or password → **"Invalid username or password"**.
- Backend not reachable (off, or no network) → **"Can't reach the server. Please try
  again."**; any other server error (e.g. 500) → **"Something went wrong on the server.
  Please try again."** (fix round 2026-10-02).
- These three appear as a red message in the form, between Password and the Login button
  (since 2026-10-05, polish-4; before: a browser alert), and clear at the next Login click.
- Spaces before/after the username are ignored (" Aaron James " logs in as "Aaron James").
- Success stores the token, role and username in the browser (the username as **stored**, read
  from the token's `sub` — "aaron james" typed shows "Aaron James" in Settings; since 2026-10-05) and opens Overview (manager) or
  Policy Holder Information (admin).
- No "Forgot password" / reset: the link exists in the code but is commented out.

### Session
- The login token lasts **60 minutes** from login (not extended by activity).
- After it expires (or if the stored login is invalid), the server rejects every request with
  401. On **any** such 401, from any page, the app clears the login and opens the Login page,
  which shows **"Your session has expired. Please log in again."** (one shared handler in
  `Frontend/src/api/api.js`, fixed 2026-09-28).
  - Not triggered by a wrong password on the Login page itself (that still shows "Invalid
    username or password").
  - Not triggered by a wrong current password on Change Password (that is a 400).
- **Log out** (Settings) clears everything stored in the browser and returns to Login.

### Settings panel (sidebar → Settings, bottom left)
Slides in from the left: MAAGAP logo, **"Malolos Branch"** (fixed text), avatar, the
**username**, the role ("Manager" or "Admin & Finance"), **Change Password** (everyone),
**Create an Account** (manager only), **Log out**. Close with X or by clicking outside.

### Password rule (every new password)
- At least **8 characters**, at least **2 letters** (only A–Z / a–z count, so "ñ" doesn't),
  at most **72 bytes** (accented letters count as 2).
- Messages: "Password must be at least 8 characters and include at least 2 letters." /
  "Password must be at most 72 characters (accented characters count as 2)."
- Checked in the browser before sending (hint under the field: "At least 8 characters,
  including 2 letters") **and** on the server (the real check).
- Existing passwords are never re-checked at login, so older passwords keep working.
- Passwords are stored only as bcrypt hashes.

### Create Account (manager; Settings → Create an Account)
- Fields: **Username** (required: "Username is required"), **Password** (with the hint),
  **Confirm Password** ("Passwords do not match"), checkbox "I agree to the **Terms of
  Service** and **Privacy Policy**" (required: "You must agree to the terms"), **Sign Up**
  (disabled and reads "Creating…" while the request runs, so a double click sends one request).
- Server errors shown in a red box: "Username is required.", the password rule, "User already
  exists" (usernames are unique, case-insensitive; spaces before/after the name are removed
  before saving and before the check, so "X " and " x" both count as "X").
- Success → "Account Created! Your account has been successfully created." → **Continue**.
- The new account is role admin.
- The server reply contains only the new account's id, username and role — never the
  password or its hash (`UserOut` schema, since 2026-10-03). Login returns only the token,
  token type and role; Change Password only a message.
- The two links open the document on top of the form (typed values are kept). Each shows the
  title, "Effective: September 2026", 10 numbered sections, and **Close**. Clicking outside
  closes only the document. The wording lives in `Frontend/src/content/legal.js`.

### Change Password (everyone; Settings → Change Password)
- Fields: **Current Password**, **New Password** (with hint), **Confirm New Password**;
  buttons **Change Password** ("Saving…") and **Cancel**. The header shows the username.
- Messages: "Current password is required", the rule, "New password must be different from
  the current password.", "Passwords do not match", and from the server "Current password is
  incorrect." (this does **not** log you out).
- Success → "Password Changed — Use your new password the next time you log in." →
  **Continue**. You stay logged in.
- The server reply is only `{"message": "Password changed."}` — no password or hash.

---

## 3. Page: Overview (`/overview`) — manager only

One API call: `GET /stats/overview`. No filters on this page. "This month" = the current
calendar month (1st through the last day of the month).

| Element (where) | What it shows | Source → exact formula | Live value (2026-09-28) |
|---|---|---|---|
| Card 1 "**Gross Premium Written**", caption "This Month (September 2026)" (top row; all four cards use this caption since 2026-09-28) | Premium of policies issued this month | Σ `total_amount_due` of `fire_property_policies` + `motor_policies` with `issue_date` in the current month | **₱1,092,348.33** |
| Card 2 "**Policies Made**", "This Month (September 2026)" | Policies issued this month | count of both policy tables, `issue_date` in current month | **50** |
| Card 3 "**Total Quotation Offered**", "This Month (September 2026)" | Quotations made this month | count of both quotation tables, `quotation_date` in current month | **66** |
| Card 4 "**Filed Claims**", "This Month (September 2026)" | Claims filed this month | count of `motor_claims` + `fire_property_claims`, `date_reported` in current month (includes CNC Issuance rows) | **8** |
| Bar chart "**Policy Made (Past 4 Years)**" (middle left) | Policies per calendar year, stacked Fire & Property (lilac) / Motor & Car (blue) | count by `issue_date` year, current year + 3 before; current year is partial | 2023: 197 + 308 · 2024: 239 + 305 · 2025: 243 + 303 · 2026: 196 + 221 |
| Pie "**Quotation vs. Converted Accounts**" (middle right), caption "Past 3 Months (Jul-Sep 2026)" | Quotations of the last 3 calendar months split into converted / not converted | quotations with `quotation_date` from the 1st of the month 2 months ago to the end of this month; **Converted** (yellow) = has a policy; **Not Yet Converted** (pale; was "Quotation" before 2026-09-28) = no policy yet | Converted **143**, Not Yet Converted **44** (of 187) |
| Line chart "**Policy Line (Past 6 Months)**" (bottom) | Policies per month for the last 6 months (this month included), one line per line (Motor & Car indigo, Fire & Prop. red) | count by `issue_date` month | Apr 15/37 · May 32/20 · Jun 21/25 · Jul 28/23 · Aug 24/23 · Sep 26/24 (Fire/Motor) |

- Pie with nothing in it shows a grey circle "No data yet".
- A failed load shows "Failed to load Overview data." in red.

---

## 4. Page: Quotations / Proposal (`/proposal`) — manager only

APIs: `GET /stats/quotation-proposal` (cards, pies, chart), the quotation/policy/case/client/
survey lists (table, joined in `lib/quotations.js`), `GET /ml/predictions/quotations` (Risk
Assessment, Claim Possibility), `GET /ml/inputs/quotations?line=` (the model-input columns, one
line per call — see §13.10), `GET /stats/policy-forecast`, `GET /ml/models`.

**The page filter.** Two mutually exclusive modes:
- **Rolling** (default): the "**Past 6 Months**" dropdown on the chart (options Past 3/6/12
  Months) = from the 1st of the month (N−1) months ago through the **last day of the current
  month**. Live: Past 6 Months = 2026-04-01 … 2026-09-30.
- **Month**: the **Select Month** picker above the table. That calendar month; if it's the
  current month, it stops at today. While a month is picked the Past-X dropdown is greyed out
  (tooltip "Overridden by the selected month below") and a violet **Show All Months** button
  appears to go back.
- Cards, both pies, the chart **and** the table all use the same date range (by
  `quotation_date`). Line / Risk / Status / search filters affect **only the table and the
  Average Claim Possibility card**.

| Element | What it shows | Source → formula | Follows | Live (Past 6 Months) |
|---|---|---|---|---|
| Card "**Total Quotations**" (caption = period, e.g. "Past 6 Months") | Quotations in the range | count of both quotation tables, `quotation_date` in range | period/month | **372** |
| Card "**Converted Accounts**" | Of those, how many became a policy | quotation has a linked policy (`policies.quotation_id`) | period/month | **291** |
| Card "**Conversion Rate**" | Share converted | Converted ÷ Total × 100, rounded to a whole % (0 if no quotations) | period/month | **78%** |
| Chart "**Monthly Quotation Conversion Trend**" (month mode: "**Daily …**") | Per month (per day in month mode), stacked **Converted** (indigo) + **Not Yet Converted** (light indigo); each segment labelled with its own count; the bar height = total | same counts, grouped by `quotation_date` month/day | period/month | Apr 53+18 · May 46+8 · Jun 49+11 · Jul 52+16 · Aug 46+7 · Sep 45+21 |
| Pie "**Fire & Property**" (right of chart) | Not Yet Converted vs Converted Account, Fire quotations in range; a grey "No data yet" circle when the range has none (since 2026-10-02) | as above, Fire only | period/month | 30 / 144 |
| Pie "**Motor & Car**" | same for Motor | as above | period/month | 51 / 147 |
| Card "**Average Claim Possibility**" (right, below pies), caption "Based on N quotations · Motor Car" (the chosen line; since 2026-10-16 there is no "All lines") | Mean predicted claim probability of the rows the table currently lists that have a prediction | mean of `claim_probability` over the filtered table rows (all pages), rounded to whole % | period/month **and** every table filter + search | **15%**, based on 372 (Motor alone 20.5% → "21%"; Fire alone 9.2% → "9%") |
| Card "**<Month> Policy Forecast**" | Next month's expected new policies (statistics, see §14) | `GET /stats/policy-forecast` | **nothing** (fixed) | Example **as of 2026-09-28** (recomputed every day, so today's card differs): "October Policy Forecast ≈ 46 new policies · Motor 25 · Fire & Property 21 · Based on ≈ 57 quotations a month and past conversion rates (Motor 77% · Fire & Property 84%), past 12 months · Open now: 8 quotations → ≈ 5 policies within 7 days · Backtest, last 12 months: off by 11% on average" |
| Card "**Model accuracy (Logistic Regression)**", "5-fold average (cross-validation)" | Per line: "X% accurate", "catches Y% of losses", "AUC 0.NN (0.5 = guessing)", "vN · trained <date>" | `GET /ml/models`: CV mean accuracy and recall to 1 decimal, CV mean ROC AUC to 3 decimals — the same rounding as the report file (see §13) | nothing | Motor Car **63.6%** accurate, catches **50.6%** of losses, AUC **0.622**, v2 · trained Sep 27, 2026 · Fire & Property **59.7%**, **68.5%**, AUC **0.660**, v2 · Sep 27, 2026 |

**Table** (bottom left). Toolbar: **Select Month**, **Risk Assessment: All** (All/Low/Medium/High),
**Policy Line** (Motor Car / Fire & Property, default **Motor Car**; one line at a time since
2026-10-16, because each line has its own model-input columns), **Status: All** (All/Converted/Not Yet
Converted — the filter stays although the Status column was removed), search box "Search Quotation..." (every typed word must appear in some field of the
row — words may be in different fields and in any order — including fields not shown such as
address and middle name; dates also match as shown, MM/DD/YYYY; empty
fields never match words like "null" — same search as §8, `lib/search.js`); "N results" appears while searching; "Updating
predictions…" (violet) while a model refresh runs.

Since 2026-10-16 the table shows **IDs → only the variables the model uses → the prediction**
(Client Name, Insurance Line, Quotation Date and Status columns removed). The input values come
from `GET /ml/inputs/quotations`, built from the same frames the model trains and predicts on
(§13.10), so they are exactly what the model saw. Missing = "—"; money as ₱1,234.56.

- **Motor Car**: Quote No. · Case ID · Vehicle ID · Flood Risk Category · Classification · Make ·
  Body Type · Color · Vehicle Age ("N yrs") · Sum Insured · Deductible · Prior Claim (Yes/No) ·
  Risk Assessment · Claim Possibility · Geospatial Information.
- **Fire & Property**: Quote No. · Case ID · Survey ID · Flood Risk Category · Occupancy · Overall
  Risk Assessment · Total Sum Insured · Fire Protection Count ("N of 8") · Construction Class B
  (Yes/No) · Loss Record (Yes/No) · Prior Claim (Yes/No) · Risk Assessment · Claim Possibility ·
  Geospatial Information.

| Column | Meaning / source |
|---|---|
| Quote No. | The Quotation ID: **FQ-<id>** for Fire & Property, **MQ-<id>** for Motor Car (display only, since 2026-09-28 — the ids of the two lines overlap; the database/API id is unchanged). The search also matches this form, e.g. "fq-1002" |
| Case ID / Vehicle ID / Survey ID | `insurance_case_id`; Motor `vehicle_id`; Fire: the case's latest survey (highest id — the same survey the model uses), "—" if the case has no survey. (In the current data every survey's id equals its case id, so the two columns show the same number.) |
| Model-input columns | See §13.2 for each one's source. A Fire quotation without a survey shows "—" for Overall Risk Assessment, Fire Protection Count, Construction Class B and Loss Record (the model itself uses Unknown / the training mean / 0 there) and "Unknown" as Flood Risk Category |
| Risk Assessment | Logistic Regression risk level: Low (grey), **Medium (amber)**, **High (red)**; "—" = no prediction (the quotation's policy has already ended) |
| Claim Possibility | Predicted probability of a counted loss, 1 decimal rounded down (e.g. "20.9%"); "—" = no prediction |
| Geospatial Information | Black **View** button → GIS popup (§9.3). The column is pinned to the table's right edge, so View stays visible when the table scrolls sideways on a small screen |

- Live, Past 6 Months: Low **216** rows (avg 10%), Medium **140** (21%), High **16** (28%);
  every one of the 372 has a prediction. Status: Converted 291, Not Yet Converted 81.
- Order: all Fire rows (by id) then all Motor rows (by id), i.e. oldest first per line —
  search by name to find a new quotation.
- "Loading quotations…", "No records found.", "Failed to load quotations."
- If a model refresh is running when the page opens, it waits and reloads the predictions and
  scores by itself.

---

## 5. Page: Policy Distribution (`/distribution`) — manager only

Top-left dropdown: **Daily / MTD / YTD** (default Daily). Source: `GET
/stats/policy-distribution?period=…&date=…` for cards/charts; the table uses the full policy
lists (joined to the client) filtered to the same range by **`issue_date`**. "Policies" = rows
of `fire_property_policies` + `motor_policies`. Method details in §16.

### Daily (range = today)
- Cards (caption "As of September 28 2026"): **Total Policies Today** 0 · **Fire & Property
  Policies** 0 · **Motor & Car Policies** 0 · **Total Amount Due** ₱0.00 (Σ `total_amount_due`).
- Table only (no charts). Live: "No records found." (no policy issued on 2026-09-28).

### MTD (range = 1st of the month → today; a past month = the whole month)
- Cards (caption "As of September 2026"): **Total Policies Made 50** · **Fire & Property
  Policies 26** · **Motor & Car Policies 24** · **Total Amount Due ₱1,092,348.33**.
- Chart "**Policy Type: Motor & Car vs. Fire & Property** (As of September 2026)": policies
  per day of the month, stacked Fire & Property (lilac) / Motor & Car (red).
- Pies "Fire & Property" and "Motor & Car": **New Policy** vs **Renewal Policy** (was "Renewed Policy" before 2026-09-28). Live: Fire
  5 / 21, Motor 8 / 16.
- Month picker (table toolbar, January … current month) + **Clear**: re-scopes the **whole**
  view (cards, chart, pies, table) to that month.

### YTD (range = Jan 1 → today)
- Cards (caption "As of 2026"): **Total Policies Made 417** · **Fire & Property 196** · **Motor
  & Car 221** · **Total Amount Due ₱11,379,453.04**.
- Chart: policies per month Jan … current month (live Jan 20+22 … Sep 26+24, Fire+Motor).
- Pies: Fire New **54** / Renewed **142**; Motor New **78** / Renewed **143**.
- Month picker + **Clear**: filters **only the table** to policies issued in that one month;
  cards/charts stay year-to-date.

### Table (all three views)
- Toolbar: **Policy Line: All**, **Status: All** (All / New / Renewal), search "Search Policy
  Number" (every typed word must appear in the policy number or the client name; since
  2026-10-05, before: the whole text in one of them).
- Columns: **Policy Number** · **Client Name** · **Policy Line** · **Issued Date** ·
  **Expiry Date** (click to sort ▲ ascending / ▼ descending / off; blanks last) · **Total
  Amount Due** · **Sum Insured** (from the policy, both lines; Motor was always "—" before 2026-09-28) ·
  **Status** (New = no Renewing Policy No.; **Renewal** = has one, i.e. the policy itself renews an earlier one).
- Pies with all-zero data show "No data yet".

---

## 6. Page: Renewal Ratio Monitoring (`/renewal`) — manager only

Dropdown **Daily / MTD / YTD** (default Daily). Source: `GET /stats/renewal-ratio`. Every
policy whose **expiry date (`period_to`)** falls in the range is listed with one status
(Renewed / Lost / Pending, judged against **today**; rules in §15).

Ranges: Daily = today · MTD = the **whole** current month (future days included) · YTD = the
whole year Jan 1 – Dec 31.

| Element | Daily | MTD | YTD |
|---|---|---|---|
| Card "**Expiring Policy**" (= Renewed + Lost + Pending) | **2** | **63** | **548** |
| Card "**Renewed Policy**" | 0 | 44 | 286 |
| Card "**Lost Policy**" | 0 | 16 | 125 |
| Card "**Pending**" | 2 | 3 | 137 |
| Chart "**MTD/YTD Policy Retention: Renewed vs. Lost** (Stacked by Day/Month, As of …)" — Renewed (indigo), Lost (red), Pending (grey) by expiry day/month | — | ✔ | ✔ |
| Pies "Fire & Property" / "Motor & Car" (Renewed Policy / Lost Policy / Pending) | — | Fire 26/5/0 · Motor 18/11/3 | Fire 143/42/58 · Motor 143/83/79 |
| Card "**Current Renewal Rate (YTD)**" (label says YTD since 2026-10-04) — "Renewal Rate = Renewed ÷ (Renewed + Lost) × 100 · Pending excluded" | **always the YTD figure on all 3 tabs: 69.59%** (286 ÷ 411) | same | same |

- Card captions: "As of September 28 2026" (Daily), "As of September 2026" (MTD), "As of 2026" (YTD).
- MTD's own rate (44 ÷ 60 = 73.33%) is calculated by the server but not shown anywhere.
- Table (same component as Distribution): **Policy Line**, **Status** (All/Renewed/Lost/
  Pending), search (every word in the policy number or client, as on Distribution), columns Policy Number · Client Name · Policy
  Line · Issued Date · Expiry Date (sortable) · **Total Amount Due** (header was "Premium" before 2026-10-05) · Sum
  Insured (both lines from the policy) · Status. Rows: Daily 2, MTD 63, YTD 548.
- Extra filter per tab:
  - **Daily**: "Filter by Date" calendar + Clear — shows only rows expiring on that exact
    day; table only. Note that the Daily table only holds today's rows.
  - **MTD**: month picker + Clear — re-scopes the whole MTD view to that month.
  - **YTD**: month picker + Clear — table only.

---

## 7. Page: Claims (`/claims`) — manager only

APIs: `GET /stats/claims?months=3|6|12` (cards, chart, pie, Fraud Rate); the claims + policies +
quotations + cases + clients lists and `GET /ml/predictions/claims` (table, joined in
`lib/claims.js`); `GET /ml/inputs/claims` (the clue columns, §13.10); `GET /ml/models`.

**Period** dropdown on the chart: Past 3 / 6 / 12 Months (default 6) = from the 1st of the
month N−1 months ago to the end of the current month, by **Date Reported** (`date_reported`).
It drives the 5 cards, the chart, the pie and Fraud Rate — **not the table**.

| Element | What / formula | Live 3 m | Live 6 m | Live 12 m |
|---|---|---|---|---|
| Card "**Total Claims**" ("Filed Past N Months") | claims (both lines, all claim types) with Date Reported in range | 36 | **67** | 133 |
| Card "**Open Claims**" | Final Status is one of: No Docs. Submitted, Waiting for Evaluation, Waiting for LOA, Waiting for Billing, Waiting for Claim Check, With Lacking Docs, Hold per Client | 29 | **32** | 37 |
| Card "**Closed Claims**" | Final Status = "Closed Claim" only | 4 | **22** | 74 |
| Card "**Other Finished**", small caption "Denied, CNC Only, Not Push Through" (added 2026-09-28) | Total − Open − Closed: Final Status Denied Claim, CNC Only or Not Push Through (or none). **Open + Closed + Other Finished = Total** | 3 | **13** | 22 |
| Card "**Total Net Liability**" | Σ `net_liability` of those claims (any status) | ₱5,457,281.94 | **₱13,272,613.23** | ₱30,284,192.49 |
| Chart "**Filed Claims per Month** (by Date Reported)" | bars stacked **Motor & Car** (indigo) + **Fire & Property** (light) with each segment's own count; red line "**Investigated as Fraud (human label)**" = Suspected + Confirmed Fraud (CNC rows excluded) per month | — | Apr 12+1 (3) · May 3+2 (1) · Jun 9+4 (2) · Jul 10+8 (1) · Aug 7+3 (0) · Sep 5+3 (0) | — |
| Pie "**Claim Investigation Result**" (Legitimate indigo, Suspected Fraud amber, Confirmed Fraud red, Not Yet Investigated grey), note "CNC Issuance rows are excluded (N in this period)." | human label counts of non-CNC claims in range; blank label = Not Yet Investigated | 23/0/1/10, CNC 2 | **44/2/5/11**, CNC **5** | 97/3/7/15, CNC 11 |
| Card "**Fraud Rate**" ("Filed Past N Months · investigated claims, CNC excluded"; footnote "(Suspected + Confirmed Fraud) ÷ investigated × 100") | investigated = Legitimate + Suspected + Confirmed; 1 decimal; "—" if none investigated | 4.2% | **13.7%** (7 ÷ 51) | 9.3% |
| Card "**Fraud model accuracy (Naive Bayes)**", "5-fold average (cross-validation)", row "Motor Car and Fire & Property" | CV mean accuracy / recall ("catches X% of fraud"), AUC, version, trained date | **85.2%** accurate, catches **38.9%** of fraud, AUC **0.759**, v3 · trained Sep 27, 2026 | | |

**Table** ("All claims, both lines — not limited by the period above."), newest Date
Reported first, 8 per page.
- Toolbar: **Select Month** (by Date Reported) + **Show All Months** · **Policy Line: All**
  · **Final Status: All** (the 11 statuses) · **Investigation Result: All** (Legitimate /
  Suspected Fraud / Confirmed Fraud / Not yet investigated — the last never includes CNC rows)
  · search "Search policy, client, claim no." (Policy No., Client Name, Assured, Accuterm
  Claim No. only; every typed word must appear in one of them, since 2026-10-05).
- "N results · reported in <Month Year>" appears while any filter is on; "Updating fraud
  predictions…" while a model refresh runs.
- Columns (since 2026-10-16: IDs → the Naive Bayes clues → the result): Claim ID · Policy No. ·
  Days from Coverage Start to Loss · Days from Loss to Report · Estimate to Sum Insured ·
  Earlier Claims (12 Months) · Days from Loss to Expiry · Nature of Loss · Coverage Type ·
  Policy Type · Days from Report to Documents · Line · **Claim Investigation Result** ·
  **Fraud Warning**. The clue columns show the clue GROUP exactly as the model uses it (e.g.
  "16–30 days", "Below 0.50", "2 or more", "Not yet submitted"; §13.2), from
  `GET /ml/inputs/claims`, matched by line + claim id. CNC Issuance rows have no clues ("—").
  Accuterm Claim No., Client Name, Date of Loss, Date Reported, Claim Type, Net Liability and
  Final Status are no longer columns, but the Final Status filter and the search (which still
  looks at Client Name, Assured and Accuterm Claim No.) work as before.
- **Claim Investigation Result** = the human label. Legitimate grey, **Suspected Fraud
  amber**, **Confirmed Fraud red**; CNC Issuance rows show "Not applicable (CNC)"
  (light grey); blank = "—".
- **Fraud Warning** = the Naive Bayes prediction. "**Suspicious · 56.2% fraud chance**" (red) when
  P(Fraud) > 0.3, "Not suspicious · 5.6% fraud chance" (grey, e.g. fire claim #90 at 0.05620) otherwise (wording since 2026-09-28; 1 decimal rounded down since 2026-10-04); the % is always P(Fraud). Hover text
  "Naive Bayes P(Fraud) — a prediction, not an investigation result". "—" for CNC rows, claims
  already investigated, or no model.
- Live: 441 claims (Motor 351, Fire 90); Fraud Warning on **23** (the uninvestigated Paid
  Claims), **2 Suspicious**: Fire claim **#83** Rosa Robles Padilla, Accuterm MS2602030016,
  policy MS-02-25-MS-000133, **56%**; Motor claim **#248** Sonia Francisco Magbanua,
  MS2501030071, policy MS-01-24-MS-000193, **39%**. Filter counts: Closed Claim 306,
  Legitimate 336, Suspected Fraud 26, Confirmed Fraud 23, Not yet investigated 23.

---

## 8. Page: Policy Holder Information (`/policy`) — every role

### Cards (top row; click one to open that tab; the active one has a black border)
Counts of **all** records, both lines (no filters):

| Card | Source | Live |
|---|---|---|
| Total Policies | fire + motor policies | **2015** (876 + 1,139) |
| Total Quotation | fire + motor quotations | **2482** (1,032 + 1,450) |
| Total Claims | fire + motor claims | **441** |
| Total Client Information | policyholders | **1129** |
| Total Survey Report | fire surveys | **481** |
| Total Vehicle Information | vehicles | **743** |

### Toolbar
- **Upload** icon → Upload modal (§9.1). Its manual type list starts at the tab's importer.
- **Needs Review** button, with a red count badge when > 0 (live **0**) → Needs Review modal (§9.2).
- **Type** dropdown: Policy / Quotation / Claims / Client Information / Survey Report /
  Vehicle Information. Switching clears search, date and resets the line to Fire & Property.
- **Insurance Line** dropdown (Policy, Quotation and Claims tabs only): Fire & Property
  (default) / Motor Car — switches between the two column sets.
- **Filter by Date** calendar (not on Client Information / Vehicle Information): keeps rows
  whose date equals the **exact day** picked (Policy: Issue Date; Quotation: Quotation Date;
  Claims: **Date of Loss**; Survey Report: the import timestamp `created_at` — all 481 surveys
  = 09/27/2026). Once a day is picked, rows with an **empty** date are hidden; clearing the
  date shows them again (since 2026-10-05; before, they always stayed — §18). The day is read as written
  (local date): before 2026-10-02 a survey imported before 08:00 landed on the previous day.
- Search "Search <Type>..." — the text is split into words; a row matches when **every** word
  appears in some field of the row (words may be in different fields, any order; since
  2026-10-05 — "Antonio Gonzales Umali" now finds client #1 on Client Information, before 0).
  One word works as before. It matches any field (including hidden fields) as it is
  **shown**: dates also as MM/DD/YYYY, money also as ₱1,234.56 / 1,234.56 / 1234.56, the JSON
  fields (View popups) by their keys and text values (e.g. "sprinklers"); empty fields never
  match "null"/"undefined" and JSON fields never match "object" (`lib/search.js`, since
  2026-10-02); "N results".
- Messages: "Loading <type>...", "No records found.", "Failed to load …".
- "Updating fraud predictions…" (Claims tab) after an upload/resolve while the model refresh runs.
- Every row ends with a trash icon (**Actions**) → confirm "Delete … ? This moves the record
  to the deleted archive." (browser confirm, rules in §11). A refused or failed delete shows
  an in-app box **"Not deleted"** with the server's reason (e.g. "Cannot delete: this
  policyholder has N insurance case(s) on file. …") and an **OK** button (since 2026-10-05;
  before: a browser alert).

### Tab: Policy (Fire & Property 22 columns / Motor Car 21 columns)
- Common: Policy ID · Policy No. · Quotation ID · **Client Name** (resolved client via
  quotation → case → policyholder) · **Insured Name & Address** (the literal text on the
  policy; may differ from Client Name) · Line of Insurance · Issue Date · Period From ·
  Period To · Renewing Policy No. · TIN · Agency Code · Total Amount Due ·
  Replacing Cover Note No. · Premium Invoice No. · Official Receipt No.
- Fire only: Coverage Description · Sum Insured · **Premium** (₱; the policy's Total Premium
  before taxes — see §10.1) · Property Insured · Construction · Occupancy.
- Motor only: Sum Insured · COC No. · COI No. · Endorsement No. · Deductible.
- **Motor screen order** (21): Policy ID · Policy No. · Quotation ID · Client Name · Insured
  Name & Address · Line of Insurance · Issue Date · Period From · Period To · Renewing Policy
  No. · TIN · Agency Code · **Sum Insured** · Total Amount Due · Replacing Cover Note No. ·
  Premium Invoice No. · Official Receipt No. · COC No. · COI No. · Endorsement No. ·
  Deductible (Sum Insured sits between Agency Code and Total Amount Due).
- Delete: archive; blocked (409) if the policy has claims.

### Tab: Quotation (Fire 19 / Motor 19 columns)
- **Fire**: Quotation ID · Case ID · Client Name · Insured Name · **Converted Policy No.**
  ("—" if no policy yet) · Quotation Date · Location of Risk · Period Cover · Property Sums
  Insured · Total Sum Insured · Basis of Evaluation · Deductibles · Subjective · Occupancy ·
  Mortgagee · Perils Covered · Line of Insurance · Total Premium · **Conditions** (View
  button, or "—").
- **Motor**: Quotation ID · Case ID · Vehicle ID · Client Name · Quotation Date · Insured
  Name · Converted Policy No. · Address · Unit · Classification · Color · Deductible · Plate
  No. · Sum Insured · Total Amount Due · Latitude · Longitude · **Flood Risk Flag**
  (Yes/No/—) · **Flood Risk Category** (Low/Medium/High/—).
- No Risk Assessment / Claim Possibility here (only on the Proposal page).
- Delete: archive; blocked (409) if a policy exists for the quotation.

### Tab: Claims (Fire 25 / Motor 27 columns)
- Columns: Claim ID · Policy No. · Client Name · Accuterm Claim No. · Assured · Claimant
  Name · [Motor: Plate No.] · Date Reported · Date of Loss · Date Docs Submitted · Nature of
  Loss · [Motor: Coverage Type] · Claim Type · Updates · Date Updated · Agent · Repair
  Estimate · LOA Received Date · LOA No. · LOA Amount · Net Liability · [Motor: Shop/Casa |
  Fire: Adjuster] · Status · Billing Date / Remarks · Final Status · Claim Investigation
  Result · Fraud Warning (same colours and meaning as on the Claims page).
- Delete: archive, always allowed.

### Tab: Client Information (18 columns + Actions)
- Columns: Client ID · Last Name · First Name · Middle Name · Sex · Nationality · Marital
  Status · Spouse Name · Present Address · Permanent Address · Residence Phone · Mobile
  Number · Email Address (blue) · Zip Code · Occupation · Employer · TIN · SSS No.
- A business client has the whole business name in Last Name, First Name "—".
- Delete: archive; blocked (409) if the client has any insurance case.

### Tab: Survey Report (28 columns)
- Columns: Survey ID · Case ID · **Quotation ID(s)** (all Fire quotations of the same case) ·
  Client Name · Name of Insured · Contact Person · Owner Business Description · Location of
  Risk · District/Block No. · Tel/Fax No. · Current Block Accumulation · Zone · T.I. · Risk
  Class (a = concrete, b = concrete & wood/light materials) · Maximum Amount Subject · Loss
  Record · Description.
- **View** popups (§9.4): Occupancy Breakdown · Boundaries · Protection Facilities (all 32
  items ✓/✗) · Perils Assessment (18 perils, Low/Moderate/High) · Hazard Assessment (6
  items, Good/Fair/Poor).
- Then Overall Risk Assessment · Surveyor Risk Acceptability · Latitude · Longitude · Flood
  Risk Flag · Flood Risk Category.
- Delete: archive, always allowed.

### Tab: Vehicle Information (12 columns + Actions)
- Columns: Vehicle ID · **Policyholder ID** · Quotation ID(s) (Motor quotations of this
  vehicle) · Client Name · Make · Model (model year) · Body Type · Color · Plate No. · Engine
  No. · Chassis No. · Authorized Capacity.
- Delete: archive; blocked (409) if the vehicle has Motor quotations.

---

## 9. Shared parts

### 9.1 Upload modal (Policy Holder Information → Upload icon)
Two modes (top-left toggle): **Single file** / **Folder**. Files: `.xlsx`, `.xls`, `.csv`.
- **Single file**: "Upload Files — Drag files here to upload / or click anywhere to browse" →
  "Detecting file type..." →
  - confident: "**Detected as: <type>**" + **Confirm** / "Not right? Choose type manually"
  - unsure: "**Select the file type**" + "Couldn't confidently tell which type this is —
    could be A or B." + dropdown "Select type..." + **Confirm** / Start over
  → "Uploading..." → "**Import complete** — N rows — X matched, Y new, Z needs review, W
  failed", then **every** failed row in red ("Row n: reason") and every warning in amber
  (e.g. a Survey's occupancy total, a reused vehicle's conflicting identifier); more than 10
  lines collapse with "**Show all (N)**" / "Show less" (since 2026-10-02) / "Upload failed" +
  reason + Try again.
- **Folder**: "Upload a Folder — Click to choose a folder of Excel/CSV files · Each file's type
  is detected automatically from its columns" → "Reading files..." → "**Confirm file types**"
  (one row per file with a type dropdown; **amber** = couldn't be detected confidently,
  "Could be A or B" — pick manually; a file that can't be opened shows "**Can't be read:
  <reason> · will be skipped**") → **Import All (N)** (N = readable files; enabled once each of
  them has a type) → "Import complete" with the same per-file line, the same list of failed
  rows / warnings per file, and a grey "**Skipped — can't be read: <reason>**" row for each
  unreadable file → "Upload another folder".
  Drag-and-drop of a folder is not supported ("Drag-and-drop isn't supported for folders yet
  — click to browse instead."); an empty folder → "This folder is empty — please select a
  folder that contains files."; a folder with files but none `.xlsx` / `.xls` / `.csv` →
  "**No spreadsheet files (.xlsx, .xls or .csv) were found in this folder.**" (since
  2026-10-05; before: nothing happened).
- "**Processing — this may take longer for larger files due to flood-risk lookups.**" shows
  while importing when a file is a Fire & Property Survey or Motor Quotation (the two types
  that geocode addresses). It waits for the whole import request (all rows of all files); it
  does **not** wait for the model refresh that follows.
- Result words: **matched** = the row was already on file (no new record); **new** = created;
  **needs review** = parked for a person (§10.5); **failed** = rejected, nothing saved for that
  row (§10.6).

### 9.2 Needs Review modal
Title "Needs Review (N)"; "Nothing needs review right now." when empty. Each row shows
"<file> — row n" and every non-empty cell of the original row, then one of three control sets:
1. **Client decision** (Customer Info, Survey, Fire/Motor Quotation, Vehicle rows; Policy rows
   whose client is unknown): dropdown "Link to existing client..." (Last, First (#id)) →
   **Link**; **Create as new** (yellow); trash (discard).
2. **Quotation pick** (Fire/Motor Policy rows whose client is known): dropdown "Select
   quotation..." listing that client's quotations without a policy ("₱amount — date (case
   #id)", newest first) → **Confirm**; if none: "No unattached quotation found for this
   policyholder — import the quotation first."
3. **Policy pick** (Claims rows): dropdown "Select policy..." with **every** policy of that
   line, closest Policy No. first ("No. — insured name (from to to)") → **Confirm**; if the
   line has no policies: "No policies on file for this line — import the policy first."

- Trash = "Discard this import row? It moves to the deleted archive."
- Errors from the server appear in red under the row.
- Resolving triggers a model refresh.

### 9.3 GIS popup ("View" in the Proposal table)
Left: satellite map (Esri World Imagery via Leaflet, loaded from the internet) with a red pin,
or the text "No coordinates on file for this quotation yet". Right: the address (Fire =
Location of Risk — or, if the quotation has none, its survey's Location of Risk (since
2026-10-02); Motor = Address; "Address not on file"), "Flood Risk Assessment", then one
of:

| State | Headline | Line under it |
|---|---|---|
| No coordinates (never geocoded / address not found) | "Flood risk not yet available for this quotation." | — |
| Coordinates, outside every hazard zone | **Not Flood-Prone** (green) | "Outside every mapped flood hazard zone" |
| Category from river flood only | **Low / Medium / High Risk** (colour by level) | "Rated from the 100-year river flood map" |
| Category from storm surge only | same | "Rated from the storm surge map (coastal flooding)" |
| Both maps give the same category | same | "Rated from both the 100-year river flood map and the storm surge map" |
| Breakdown missing | same | "Within a mapped flood hazard zone" |

- Fire quotations borrow the GIS result of the **latest survey of the same insurance case**.
  Motor quotations use their own stored result.
- Close with X or by clicking outside.

### 9.4 JSON "View" popup (Quotation → Conditions; Survey → the 5 checklist fields)
A white box titled with the column name, showing the stored values as a labelled list (since
2026-10-05; before: raw JSON). Display only — nothing stored changes. Labels are the Survey
Report form wording (upload headers / `schemas.PROTECTION_FACILITY_OPTIONS`), an abbreviation
followed by its meaning, e.g. "FFF (Furniture, Fixtures & Fittings)"; one map in
`Frontend/src/lib/viewFormat.js`. Empty values show "—"; every form item is listed in form
order, and a stored key the form doesn't list is still shown at the end.
- **Occupancy Breakdown**: item | amount as ₱1,234.56; **Total** last, bold.
- **Boundaries**: Front / Right / Left / Rear / Sketch.
- **Perils Assessment** / **Hazard Assessment**: table **Peril** (or **Hazard**) | **Rating** |
  **Remarks**; ratings in title case, Low/Good green, Moderate/Fair amber, High/Poor red
  (same colours as the GIS popup).
- **Protection Facilities**: two-column checklist, ✓ (green) = true, ✗ (grey) = false.
- **Conditions** (and any other shape): labelled list ("general_conditions" → "General
  Conditions"), nested parts indented, true/false as ✓/✗. Empty for every v4 quotation.

Close with X or outside.

### 9.5 Model accuracy cards
Per model: "X.X% accurate", "catches Y.Y% of …", "**AUC 0.NNN (0.5 = guessing)**" (AUC since
2026-10-02; 1 decimal / 3 decimals since 2026-10-04, the same rounding as the report file),
"vN · trained <date>". See §13.8.

### 9.6 Pickers
- "**Select Month**" (month + year; Proposal, Claims, Distribution YTD, Renewal YTD).
- MTD month picker (January … current month; Distribution MTD, Renewal MTD).
- "**Filter by Date**" (a single day; Policy Holder Information, Renewal Daily).

---

## 10. Bulk import

### 10.1 File types and headers
Headers are matched ignoring case, spaces and punctuation ("Plate No." = "plateno"). Only
known headers are read; others are ignored. `*` = the row needs it to do anything useful.

| Type (label in the app) | Headers the importer reads |
|---|---|
| **Customer / Policyholder Information** | Last Name*, First Name, Middle Name, Nationality, Marital Status, Complete Name of Spouse, Gender, Present Address, Permanent Address, Residence Phone Number, Mobile Number, Email Address, Zip Code, Occupation, TIN, SSS No., Employer (*a name is required: Last or First) |
| **Fire & Property Survey** | Name of Insured*, Contact Person, Brief Description of Owner's Business, Location of Risk (geocoded), District No./Block No., Tel/Fax No., Current Block Accumulation, Zone, T.I., Risk Class (a/b), Description, Maximum Amount Subject, Loss Record; 18 perils (Fire, Earthquake, Typhoon, Flood, Landslide/Subsidence, Smoke/Aircraft/Vehicle Impact/Explosion, RSMD, Burglary/Robbery, Volcanic Eruption, Tsunami, Terrorist Attack, Spontaneous Combustion, Machinery Breakdown, General Liability, Money, Fidelity Guarantee, Goods Transit, Others → Low/Moderate/High); 6 hazards (Maintenance, Housekeeping, Storage Arrangement, Safety/Security, Block Condition, Surrounding Community → Good/Fair/Poor); Overall Risk Assessment; Surveyor Risk Acceptability; Protection Facilities (comma list of the 32 names or "None"); Occupancy - Building / Main Occupancy / Stocks / M/E / FFF / BI/LOP / Others / Total; Boundary - Front / Right / Left / Rear / Sketch |
| **Fire & Property Quotation** | Date, Name of Insured*, Location of Risk, Period of Cover (or Period Cover), Property Sums Insured, Basis of Evaluation, Deductibles, Subjective, Occupancy, Total Sum Insured, Mortgagee, Perils Covered, Line of Insurance, Total Premium |
| **Fire & Property Policy** | Issue Date, Insured Name & Address* ("NAME, ADDRESS" — split at the first comma), Line of Insurance, Policy No., Renewing Policy No., Period From, Period To, TIN, Total Amount Due, Agency Code, Coverage Description, Sum Insured, Premium, Replacing Cover Note No., Premium Invoice No., Official Receipt No., Property Insured, Construction, Occupancy |
| **Motor Quotation** | Date, Insured Name*, Address (geocoded), Unit, Classification, Color, Deductible, Plate No., Bank, Total Amount Due, Sum Insured, Model, Make, Body Type, Motor/Engine No., Serial/Chassis No. (or Serial/Chasis No.), Authorized Capacity |
| **Motor Policy** | Issue Date, Insured Name & Address*, Line of Insurance, Policy No., Renewing Policy No., Period From, Period To, TIN, Agency Code, COC No., COI No., Endorsement No., Total Amount Due, Sum Insured, Replacing Cover Note No., Premium Invoice No., Official Receipt No., Deductible |
| **Vehicle Information** | Insured Name*, Make, Model, Body Type, Color, Plate No., Motor/Engine No., Serial/Chassis No., Authorized Capacity |
| **Motor Claims** | Accuterm Claim No., Assured, Claimant Name (optional), Policy No.* (links the claim; not stored), PLA Date (Date Reported) or PLA Date, Date of Loss, Date of Docs Submission, Nature of Loss, Claim Type, Updates, Date Updated, Agent Name, Amount of Repair Estimate, Date of LOA Received, LOA No., LOA Amount, Net Liability, Status, Billing Date and Remarks, Final Status, Claim Investigation Result, **Plate No., Coverage Type, Shop/Casa** |
| **Fire & Property Claims** | same common claims headers + **Adjuster** |

- Claims files may also contain SN, No. of Days (As of Today), Turn-Around-Time, a second
  Date of Loss, Assureds Name. These are recognised but not stored; Assureds Name is used as
  Assured only if there is no Assured column.
- ⚠️ In every importer the cell texts None, NA, N/A, null, nan … are read as **blank** (pandas
  default). The only exception is Protection Facilities, where "None" means "no facilities".
- **Fire Policy "Premium"** (since 2026-10-05) = the policy's **Total Premium in pesos, before
  taxes**, read as money like Total Amount Due (₱ and commas allowed). On Maagap's real fire
  policy the taxes are a percentage of the Total Premium — Doc. Stamps 12.5%, FST 2%, VAT 12%,
  Local Gov't Tax 0.5% — so **Total Amount Due = Premium × 1.27** (their example: Total Premium
  12,900.00 → Total Amount Due 16,383.00). Coverage rows (Fire/Lightning, Earthquake, Typhoon,
  Flood, Extended Cover, RSMD), Qty and Unit Cost are not stored (Qty is always 1). The old
  header "Unit Cost Premium" (a made-up rate per ₱1,000 in the synthetic data) is **ignored**,
  like any unknown column. Rows loaded before the change got Premium = Total Amount Due ÷ 1.27
  (`Backend/scripts/2026-10-05_premium_field.sql`). Fire **quotation** "Total Premium" is
  unchanged: the full amount with taxes, as on Maagap's quotation form.

### 10.2 Auto-detect (folder mode and single-file mode)
- For each type: score = (file headers that belong to that type ÷ all headers in the file) ×
  100. If only **one** header matches (and the file has more than one), the score × 0.6.
- A Claims file that has the other line's own headers scores 0 for that line: Adjuster ⇒ not
  Motor; Plate No./Coverage Type/Shop/Casa ⇒ not Fire.
- Decision:
  - top score ≥ **55** and ≥ **12** points above the runner-up → detected ("high", normal row).
  - top ≥ 55 but runner-up within 12 → **ambiguous** (amber, pick manually).
  - top < 55 → not detected (amber). An unreadable file shows its error.
- Known ambiguous cases: a Vehicle Information file (all its headers are also Motor Quotation
  headers → 100 vs 100); a minimal policy file with only the shared policy columns; a minimal
  claims file with only the shared claims columns.

### 10.3 Processing order (folder upload)
Customer Info (0) → Survey, Motor Quotation, Vehicle (1) → Fire Quotation (2) → Fire Policy,
Motor Policy (3) → Motor Claims, Fire Claims (4). Ties keep folder order. Results are listed
in the original order. One folder upload = **one** model refresh afterwards.

### 10.4 Matching (fuzzy, `rapidfuzz.token_sort_ratio`, 0–100)
Names are compared as "first middle last", lower case, without periods and extra spaces.
Thresholds everywhere: **≥ 90 = same client (matched)**, **70–89 = Needs Review**, **< 70 =
new client**.

| Importer | Score |
|---|---|
| Customer Info | exact same name + (exact same Present Address **or** same mobile) → 100; exact same name alone → **70** (always reviewed, never silently duplicated); otherwise name × 0.6 + address × 0.25 + (same mobile ? 100 : 0) × 0.15. Mobile numbers are compared after dropping +63/0 and formatting. |
| Survey | exact same name → 100; otherwise name × 0.8 + (same Tel/Fax as the client's mobile ? 100 : 0) × 0.2. Location of Risk is **not** used for the client. |
| Fire Quotation, Fire Policy | same as Survey, name only (no phone). |
| Motor Quotation, Motor Policy, Vehicle | plain name score. |

- Rows sent to review earlier in the same file are remembered, so a second copy of the same
  unknown name in that file also goes to review.
- Then, per record type:
  - **Survey**: if the matched client already has a Fire survey whose Location of Risk scores
    ≥ **85** → "matched" (same property, nothing new). Otherwise a new insurance case + survey
    (+ GIS lookup).
  - **Fire Quotation**:
    - 0 Fire cases → new case (no survey, so no GIS).
    - 1 case → that case.
    - 2+ cases → the case whose latest survey's Location of Risk scores ≥ 85 **and** leads the
      runner-up by ≥ **8**; otherwise a new case.
    - Same quotation date + same Total Premium already in that case → "matched" (duplicate).
    - Write the Location of Risk exactly like the survey's.
  - **Motor Quotation / Vehicle**:
    - The vehicle is "the same" if Plate No. **or** Engine No. **or** Chassis No. matches
      exactly.
    - Known vehicle → its case is reused (a re-quote); same date + same Total Amount Due →
      "matched".
    - A reused vehicle gets any **empty** Plate / Engine / Chassis No. filled in from the
      quotation row (so a later re-quote found by any of them reaches it). A different
      non-empty value never overwrites the stored one, and a number already used by another
      vehicle is not copied — both give a warning in the import result (since 2026-10-02).
    - Vehicle file: a known vehicle → "matched", nothing created. A new vehicle → case +
      vehicle, **no quotation**.
  - **Policy (Fire / Motor)**:
    - Same Policy No. already on that client → "matched".
    - Otherwise the client's quotations **without a policy** are scored: amount score × 0.7 +
      date score × 0.3.
    - Amount score: 100 − 200 × relative difference (Fire compares with Total Premium, Motor
      with Total Amount Due).
    - Date score, days between the policy's Issue Date (or Period From) and the quotation
      date: ≤ 7 → 100, ≤ 30 → 85, ≤ 90 → 65, ≤ 180 → 40, else 15.
    - Best ≥ **75** and ≥ **15** ahead of the next → the policy is created on it. Otherwise →
      Needs Review (quotation pick).
  - **Claims**:
    - Linked **only** by Policy No. (trimmed, case-insensitive) within the line; exactly one
      policy must match.
    - The Date of Loss must fall within the policy's Period From–Period To (inclusive, when
      all three are known), otherwise the row fails with "Date of loss X is outside the
      policy's coverage period (A to B)."
    - Duplicate re-upload (same policy + same Accuterm No., Assured, Claimant Name, Date of
      Loss, Nature of Loss, Claim Type [+ Coverage Type, Plate No. for Motor]) → "matched".
      Changed progress fields are **not** applied.

### 10.5 Every reason a row goes to Needs Review, and how it's resolved
| Reason | Import types | Resolve |
|---|---|---|
| Client name scores 70–89 against an existing client (or an earlier review row in the same file) | Customer Info, Survey, Fire Quotation, Fire Policy, Motor Quotation, Motor Policy, Vehicle | **Link** to a client, or **Create as new**. The row is then processed exactly like an automatic match (survey/case/quotation/vehicle/policy creation, duplicate checks, GIS). |
| Exact same name but no matching address or mobile (Customer Info) | Customer Info | same |
| Policy: client known but 0 open quotations, or no clear best (score < 75 or lead < 15) | Fire Policy, Motor Policy | Pick the quotation → **Confirm** (the policy is created on it; 409 if it already has a policy) |
| Claim: Policy No. blank, unknown, or matching more than one policy | Motor Claims, Fire Claims | Pick the policy → **Confirm** (the same coverage-period and duplicate checks run; a failure shows in red) |

Discarding (trash) archives the import row (§11).

### 10.6 Rollback and failed rows
- Each row is saved on its own: everything a row creates is committed together, or undone
  together if anything fails. The error goes to the summary ("W failed", "Row n: message"),
  and the next row continues.
- Examples of failed rows:
  - a blank name when a new client must be created;
  - Risk Class not a/b;
  - a peril/hazard rating outside its list;
  - an unknown Protection Facilities name, or "None" mixed with names;
  - an Occupancy amount that isn't a number;
  - a Claims date/amount that isn't valid, a fixed-list value outside its list (the message
    lists the allowed values), or a date of loss outside coverage;
  - an unreadable date in a Quotation or Policy file (Date, Issue Date, Period From, Period
    To), e.g. "Date: '31/31/2026' is not a valid date" (since 2026-09-28; a blank date cell
    is still allowed and stays empty).
- Non-blocking warning (API only, not shown in the UI): Occupancy - Total differs from the
  sum of the parts by more than ₱1.
- A file that can't be read at all → "Could not read file: …".

### 10.7 The "no quotation, no policy" rule
- A policy must always point to the quotation it came from.
- A Policy row is never created without one: with no clear quotation it waits in Needs Review
  until a person picks one ("import the quotation first" if the client has none).
- Likewise a claim needs exactly one policy.

---

## 11. Delete and archive

| Record | Where | What happens | Blocked (409) when |
|---|---|---|---|
| Client (policyholder) | Client Information | archived (`deleted_policyholders`), import rows pointing at it are unlinked | the client has any insurance case: "Cannot delete: this policyholder has N insurance case(s) on file. …" |
| Fire / Motor quotation | Quotation | archived | a policy exists for it: "Cannot delete: this quotation has a policy on file. …" |
| Fire / Motor policy | Policy | archived | it has claims: "Cannot delete: this policy has N claim(s) on file. …" |
| Vehicle | Vehicle Information | archived | it has Motor quotations: "Cannot delete: this vehicle has N motor quotation(s) on file. …" |
| Fire survey | Survey Report | archived | never |
| Fire / Motor claim | Claims tab | archived | never |
| Import row (Needs Review) | Needs Review trash | archived (`deleted_import_records`) | never |
| Insurance case | — | no delete exists | — |
| User account | — | no delete in the app (only by SQL, permanent — no archive) | — |

- "Archived" = a full copy is saved in the matching `deleted_*` table first, then the live
  row is removed. The archive row's `deleted_by` holds the **username** of the user who
  deleted it (since 2026-10-02; older archive rows have it empty). Creating and changing
  records do not record a user.
- Archives can be read back through `GET /deleted-…` endpoints, but there is no screen for
  them.
- Deleting doesn't trigger a model refresh; the next refresh drops predictions of deleted
  rows.

---

## 12. GIS (flood-risk lookup)

- **When**: while creating a Fire & Property **Survey** (its Location of Risk) and a
  **Motor Quotation** (its Address) — by upload, by the manual API, or when a Needs Review row
  is resolved. Fire quotations have no GIS of their own; they show their case's survey.
- **Geocoding**:
  - Service: OpenStreetMap Nominatim, restricted to the Philippines, 1 result, 10-second
    timeout, User-Agent "MaagapCapstoneFloodRiskLookup/1.0 (student capstone project,
    non-commercial)". Only the address is sent.
  - Rate limit: at least 1 second between requests, shared by the whole server.
  - Cache (`geocode_cache`, **500** addresses live): the key is the address in lower case
    with single spaces. Both "found" and "not found" answers are cached. Errors, timeouts,
    non-200 answers and bad JSON are never cached. A cached address needs no network and no
    wait.
- **Datasets** (Bulacan, Project NOAH via Hugging Face, point-in-polygon with shapely/pyogrio):
  - **River flood, 100-year** (`gis_data/flood_hazard/bulacan_100yr/.../Bulacan_Flood_100year.shp`,
    field `Var` 1/2/3 = Low/Medium/High).
  - **Storm surge, advisory level SSA3** (4.01–5 m peak storm tide;
    `gis_data/storm_surge/bulacan/extracted/SSA3/Bulacan_StormSurge_SSA3.shp`, field `HAZ`
    1/2/3 = Low/Medium/High).
- **50 m buffer**: a point counts as inside a zone if it is inside it **or within 50 m of its
  edge**. Where zones overlap, the worst category wins within each dataset.
- **Combined rating** (`flood_risk_category`) = the more severe of river flood and storm surge
  (Low < Medium < High; outside every zone is the lowest). On a tie the river-flood value is
  used.
  - `flood_risk_flag` = Yes if there is any category, No if outside every zone, blank if
    never located.
  - The two separate results are stored in `river_flood_category` / `storm_surge_category`
    (not shown as table columns; used by the popup text and the Fire model).
- **Soft-fail**: a blank address, an address not found, a network error or a shapefile
  problem never blocks the record. The GIS fields are simply left blank (one dataset failing
  doesn't blank the other).
- **Where the columns live**: `fire_property_surveys` (Fire) and `motor_quotations` (Motor):
  latitude, longitude, flood_risk_flag, flood_risk_category, river_flood_category,
  storm_surge_category.
- **Live distribution**:
  - Surveys (481, all with coordinates): outside every zone 133 · Medium 118 (river) · High
    110 (river) · Low 85 (river) · High from storm surge only 12 · High from both / mixed
    20 · Medium mixed 3.
  - Motor quotations (1,450): High 442 · none 409 · Medium 390 · Low 209.

---

## 13. The three models

All are written by the team in numpy (`Backend/app/ml/`); scikit-learn is used only in the
tests to cross-check them. Predictions are stored in `ml_predictions`, never in the business
tables.

### 13.1 Label rules
- **Motor / Fire Logistic Regression (Predictive Risk)**:
  - One training row = one **issued policy whose coverage has ended** (`period_to` before
    today), described by **its quotation**.
  - Label 1 = "counted loss": the policy has ≥ 1 **Paid Claim** whose Final Status is Closed
    Claim, Waiting for LOA, Waiting for Billing or Waiting for Claim Check. Otherwise 0.
- **Fraud Naive Bayes**:
  - One row = one **Paid Claim** (never CNC Issuance) that has a Claim Investigation Result.
  - Fraud = Suspected Fraud or Confirmed Fraud; Legitimate = Legitimate.

### 13.2 Features (inputs)
**Motor** (from the quotation and its vehicle only — nothing from the policy):

| Feature | Source | Encoding |
|---|---|---|
| flood_category | `motor_quotations.flood_risk_category` | category; blank with coordinates = "None", no coordinates = "Unknown" |
| classification | `motor_quotations.classification` | category |
| make | `vehicles.make` | category |
| body_type | `vehicles.body_type` | category |
| color | `motor_quotations.color` (a control: should carry ~no weight) | category |
| vehicle_age | year of quotation date − `vehicles.model` (model year), at least 0 | number |
| log_sum_insured | log of `motor_quotations.sum_insured` | number |
| deductible | `motor_quotations.deductible` | number |
| prior_counted_loss | the vehicle's most recent earlier policy had a **Paid Claim reported before** this quotation date — whatever its outcome (not used: it may only be decided after the quote; since 2026-10-02, before: only claims that became a counted loss) | 0/1 |

**Fire** (from the quotation and the **latest survey** of its case):

| Feature | Source | Encoding |
|---|---|---|
| flood_category | survey `flood_risk_category` (worst of river / storm surge) | category, as above |
| occupancy | `fire_property_quotations.occupancy` | category |
| overall_risk_assessment | survey (surveyor's rating) | category |
| log_total_sum_insured | log of quotation `total_sum_insured` | number |
| fire_protection_count | how many of 8 fire items are ticked in the survey's Protection Facilities (fire extinguisher, smoke detector, heat detector, fire alarm, sprinklers, internal hydrants, external hydrants, fire breaks/doors) | number 0–8 |
| construction_class_b | survey `risk_class` = b | 0/1 |
| has_loss_record | survey `loss_record` starts with "With loss history" | 0/1 |
| prior_counted_loss | same property's (insurance case's) earlier policy had a Paid Claim reported before this quotation date, whatever its outcome (as for Motor) | 0/1 |

- Encoding: each category becomes a 0/1 column for every value seen in the training rows (an
  unseen value → all 0). Numbers are scaled to mean 0 / SD 1 using the training rows (missing
  → the training mean). Yes/no stays 0/1.

**Fraud** (10 "clues", all known **by the time the claim is investigated**: 8 are known when
the claim is filed; the documents date (days_report_to_documents) and the repair estimate
(estimate_to_sum_insured) arrive shortly after):

| Clue | Source | Values |
|---|---|---|
| days_coverage_start_to_loss | date of loss − policy Period From | 0–15 / 16–30 / Over 30 days / Unknown |
| days_loss_to_report | date reported − date of loss | 0–7 / 8–30 / Over 30 days / Unknown |
| estimate_to_sum_insured | repair estimate ÷ policy Sum Insured | Below 0.50 / 0.50–0.69 / 0.70 or more / Unknown |
| earlier_claims_12_months | Paid Claims of the same client (both lines) reported in the 365 days before this one | 0 / 1 / 2 or more |
| days_loss_to_expiry | policy Period To − date of loss | 30 days or less / Over 30 days / Unknown |
| nature_of_loss | claim | the Motor + Fire lists / Unknown |
| coverage_type | Motor claim | Own Damage / Third Party Property Damage / Third Party Bodily Injury/Death / "N/A (Fire)" / Unknown |
| policy_type | policy Renewing Policy No. blank or filled | New / Renewal |
| days_report_to_documents | date docs submitted − date reported | 30 days or less / Over 30 days / Not yet submitted |
| line | which claims table | Motor / Fire & Property |

Never used as inputs: Final Status, LOA, Net Liability, the investigation result itself.

### 13.3 Training rows and split
- Stratified **75 % / 25 %** train/test split (each class split separately), fixed seed 42.
  The model is fitted on the 75 % and scored on the unseen 25 %.
- Then **5-fold stratified cross-validation** on all rows (every row is tested once).
- The **stored** model is the one trained on the 75 %.
- Minimum to train: 30 rows and 5 of each class, otherwise the attempt is recorded as
  "failed" and the previous model stays active.
- Live training rows (v2/v3, data as of 2026-09-27):

  | Model | Rows (train + test) | Positives |
  |---|---|---|
  | Motor | 833 (625 + 208) | 172 losses |
  | Fire | 621 (466 + 155) | 57 losses |
  | Fraud | 385 (289 + 96) | 49 fraud |

### 13.4 Settings
- **Logistic Regression**:
  - z = Σ weight × input + bias → sigmoid.
  - Full-batch gradient descent on log-loss, learning rate **0.5** (min(0.5, 1/λ), so 0.1
    at λ = 10 — a larger step makes gradient descent diverge there), stops when the loss
    changes by less than **1e-12**, at most **50,000** epochs.
  - **L2** penalty λ/2 × Σw² (weights only, not the bias). **λ is chosen on every training
    run by 5-fold cross-validation** from **0.0001, 0.001, 0.01, 0.1, 1, 10**: the best mean ROC AUC
    on the same stratified folds (seed 42) wins, ties → the larger λ. The chosen λ and the
    whole table are stored with the model (`parameters.model.l2`, `metrics.l2_selection`)
    and printed in the report. The CV scores shown are the chosen λ's (slightly optimistic,
    since the same folds chose it). Until 2026-10-02 λ was fixed at 0.01.
  - λ table on 2026-10-02 data (CV ROC AUC, λ = 0.0001 … 10): Motor 0.619 / 0.624 /
    **0.637** / 0.628 / 0.601 / 0.592 → **0.01**; Fire 0.680 / **0.681** / 0.673 / 0.662 /
    0.652 / 0.651 → **0.001**. Both choices are inside the grid. The λ = 0.0001 fits stop at
    the 50,000-epoch cap (not fully converged; every other λ stops by the tolerance). The v2
    models (trained 2026-09-27) used λ = 0.01.
- **Naive Bayes**:
  - prior × product of the per-clue likelihoods for each class.
  - **Laplace smoothing α = 1**: (count + 1) ÷ (claims in class + K), K = number of possible
    values of that clue.
  - **Unseen-value rule**: a clue value that never appeared in any training claim is left
    out of the product (no evidence either way).
  - P(Fraud) = score(Fraud) ÷ (score(Fraud) + score(Legitimate)).

### 13.5 Risk Level thresholds (Logistic Regression)
- Base rate = the training rows' loss rate (the 75 %).
- **medium_from** = base rate rounded to 2 decimals; **high_from** = 2 × base rate rounded
  to 2 decimals.
- Low = probability < medium_from; Medium = medium_from ≤ p < high_from; High = p ≥ high_from.
- Live: **Motor 0.21 / 0.41**, **Fire 0.09 / 0.18**.

### 13.6 Fraud cutoff
Suspicious = P(Fraud) **> 0.3** (stored per model as `thresholds.fraud_cutoff`; chosen from
the v1 cutoff table: at 0.3 cross-validated recall 38.9 % vs 24.2 % at 0.5, precision about
the same).

### 13.7 Who gets a prediction
- **Quotations** (Proposal "Risk Assessment" / "Claim Possibility"): every quotation that is
  still **open** (no policy) or whose policy is **in force** (Period To ≥ today). A quotation
  whose policy has **ended** → "—".
  - Live: Motor **615** (311 open + 304 in force: Low 390 / Medium 204 / High 21).
  - Live: Fire **411** (156 + 255: Low 244 / Medium 142 / High 25).
- **Claims** ("Fraud Warning"): Paid Claims with **no** investigation result. CNC rows and
  investigated claims → "—".
  - Live: **23** (17 Motor + 6 Fire), 2 flagged Suspicious.
- Predictions are recomputed for the whole table on every refresh (after an upload/resolve
  and at every backend start).

### 13.8 Metrics (cards and report files)
- On the test data, with 1 = loss / fraud:
  - **Accuracy** = (TP + TN) ÷ all.
  - **Precision** = TP ÷ (TP + FP).
  - **Recall** ("catches X %") = TP ÷ (TP + FN).
  - **F1** = 2PR ÷ (P + R).
  - **ROC AUC** = the chance a random positive gets a higher probability than a random
    negative (ties count ½; independent of any cutoff).
- "Predicted positive" = Medium or High for Logistic Regression (p ≥ medium_from); p > 0.3
  for Naive Bayes.
- **5-fold CV**: the mean ± SD over the 5 folds (SD with n−1).
- The **cards show the CV means** of accuracy, recall and ROC AUC ("AUC 0.622 (0.5 =
  guessing)"; AUC since 2026-10-02; since 2026-10-04 percentages with 1 decimal and AUC with 3,
  exactly as the report file — accuracy alone is below the "always predict no"
  baseline for these rare-event models, see the reports).
- Reports also show: the 25 % test scores + confusion matrix; the score at a 0.5 cutoff; the
  "always predict no" baseline; loss rate per risk level; the λ table (Logistic Regression);
  top weights and odds ratios; the Motor colour control check; the Naive Bayes cutoff table (0.5 / 0.4 / 0.3 / 0.2) and its
  strongest clues.

**Current active versions (live)**

| Model | Version (trained) | Test acc / prec / rec / F1 / AUC | CV mean ± SD: acc / prec / rec / AUC | Card |
|---|---|---|---|---|
| motor_lr | v2 (2026-09-27 16:53:21) | 63.0 / 29.3 / 55.8 / 38.4 / 0.614 | 63.6 ± 2.0 / 28.5 ± 2.6 / 50.6 ± 7.2 / 0.622 ± 0.045 | 64 % · 51 % |
| fire_lr | v2 (2026-09-27 16:53:24) | 65.2 / 13.0 / 50.0 / 20.6 / 0.612 | 59.7 ± 3.8 / 14.4 ± 1.6 / 68.5 ± 9.6 / 0.660 ± 0.067 | 60 % · 68 % |
| fraud_nb | v3 (2026-09-27 16:53:24) | 90.6 / 61.5 / 66.7 / 64.0 / 0.877 | 85.2 ± 4.6 / 44.6 ± 16.5 / 38.9 ± 8.9 / 0.759 ± 0.064 | 85 % · 39 % |

### 13.9 Retraining, fingerprint, warm-up
- **Triggers** (a background job after a successful response):
  - Survey, Fire Quotation, Fire Policy, Motor Quotation, Motor Policy, Motor Claims and Fire
    Claims uploads;
  - the **folder** upload (once per folder);
  - **resolving** a Needs Review row.
- Customer Info and Vehicle uploads, deletes and manual edits do **not** trigger it.
- Refreshes requested while one is running are merged into one more run.
- **Fingerprint**: SHA-256 of the training rows (ids, inputs, labels) + all settings,
  including the λ grid (the chosen λ follows from data + grid) (+ a code version number).
  The fix round (2026-10-02) changed both LR fingerprints (new λ grid, new prior rule), not
  the fraud one. Same as the last attempt → no retrain, only the predictions are rewritten.
  Different → train a new version (the old one becomes "superseded").
- Because training uses "policies ended **before today**", the fingerprint changes as days
  pass:
  - Live check: Motor already differs (835 rows on 2026-09-28 vs 833).
  - Fire from about 2026-10-05.
  - Fraud unchanged.
  - The first refresh after that retrains.
- **At startup** the backend trains only a model with no active version, then rewrites all
  predictions (about 10 s; the old predictions stay visible meanwhile).
- **Warm-up** (defense morning, from `Backend/`):
  `./venv/Scripts/python -c "from app.ml import jobs; jobs.refresh_now('pre-demo warm-up'); print(jobs.status)"`
  runs that retrain before the demo, so the live upload only rewrites predictions (rehearsal
  2026-09-28: warm-up 28.6 s; later upload refresh 40.8 s, no retrain). Since the λ search the
  warm-up takes ≈ 3 min (2026-10-02: 3 min 2 s) — start it early.
- While a refresh runs, other requests are slower (training shares the web server's process).
  Since the λ search (2026-10-02, 31 fits per Logistic Regression instead of 6; the six
  λ = 0.0001 fits each run the full 50,000 epochs) a refresh that retrains Motor + Fire takes
  ≈ **3 min** (warm-up measured 2026-10-02: 3 min 2 s, backend otherwise idle).
- **Report files**: `model_reports/<data date>_<model>_v<N>.md` at the repository root
  (gitignored), one per training (e.g. `2026-09-27_motor_lr_v2.md`), plus
  `2026-09-27_policy_forecast_backtest.md`.

---

### 13.10 Model inputs on screen (`GET /ml/inputs/...`, since 2026-10-16)
Read-only; nothing is trained, predicted or stored. Both endpoints call the SAME frame functions
training and prediction use (`features.motor_quotation_frame`, `fire_quotation_frame`,
`claim_clue_frame`), so the fingerprint and the models cannot change.
- `GET /ml/inputs/quotations?line=Motor Car|Fire & Property` (line required; manager only) —
  every quotation of that line. Motor: `quotation_id, flood_category, classification, make,
  body_type, color, vehicle_age, sum_insured, deductible, prior_claim`. Fire: `quotation_id,
  survey_id, flood_category, occupancy, overall_risk_assessment, total_sum_insured,
  fire_protection_count, construction_class_b, has_loss_record, prior_claim`. `prior_claim` =
  the frame's `prior_counted_loss`; `survey_id` = MAX(survey id) of the case (same rule as the
  frame's join, read by a separate query). No survey → `null` survey fields (not false/0).
  Raw sums insured are returned (the model uses their log). Missing values → `null`.
- `GET /ml/inputs/claims?line=` (line optional; every role) — every Paid Claim with its 9 clue
  groups (`line` as "Motor Car" / "Fire & Property", `claim_id`, then the clues). CNC Issuance
  rows are not returned.
- Speed: the Motor call takes ≈ 5 s (the frame's prior-claim loop over ≈ 1,500 quotations);
  Fire ≈ 3 s; claims < 1 s.

## 14. Policy Forecast (method) — Proposal card, statistics not ML

Per line (Motor Car, Fire & Property), from (quotation date, policy issue date) pairs. The
numbers below are **examples as of 2026-09-28**; the card recomputes them every day, so
today's card shows different values (the method is the same).

- **W (waiting period)** = 95th percentile of days from quotation to policy, rounded up.
  Example (2026-09-28): **7** days both lines.
- **Conversion rate**:
  - Numerator: quotations that became a policy within W days.
  - Denominator: quotations old enough to be decided (age W … W + 364 days).
  - Example (2026-09-28): Motor 302 ÷ 390 = **77.4 %**, Fire 254 ÷ 301 = **84.4 %**.
- **Quotations per month** = quotations of the past 365 days ÷ 12. Example (2026-09-28): Motor 386 ÷ 12 =
  32.2, Fire 302 ÷ 12 = 25.2 (total **57.3**).
- **Next month's expected new policies** = per month × rate. Example (2026-09-28): Motor 24.9, Fire 21.2 →
  **October 2026 ≈ 46**.
- **Open now**:
  - Quotations without a policy and younger than W (example 2026-09-28: **8**: Motor 5, Fire 3).
  - Each counts with P(converts | still open at its age) = (share of past quotations that
    converted after that age) ÷ (share still unconverted at that age).
  - Example (2026-09-28) ≈ **4.6 → "≈ 5 policies within 7 days"**. Not added to the monthly number.
- **Backtest**:
  - For each of the last 12 complete months, forecast it on the 1st of the month before,
    using only data known that day, and compare with the policies actually issued.
  - Average monthly error = mean of |forecast − actual| ÷ actual.
  - Example (2026-09-28): total **10.7 %** ("off by 11%"), Motor 14.0 %, Fire 24.2 %.
  - 12-month total error: −3.3 % (Motor −1.9 %, Fire −5.1 %).
- Not affected by any page filter. Quotations with no date are left out. A policy with no
  issue date counts as issued on its quotation date.

## 15. Renewal Ratio (method)

- Each policy is judged on its own, **against today**, within its own line only (Fire only
  renews Fire, Motor only Motor).
- **Renewed**: some *other* policy of the same line has `renewing_policy_no` equal to this
  policy's `policy_no` (trimmed). Checked against all policies, not just those in view.
- **Lost**: not renewed, and today is after its Period To.
- **Pending**: not renewed, and Period To is today or later (no day limit).
- Which policies are shown: `period_to` inside the tab's range (Daily = today; MTD = the whole
  month; YTD = Jan 1 – Dec 31 of the current year). A past month can only have Renewed/Lost.
- **Expiring** = Renewed + Lost + Pending.
- **Renewal Rate** = Renewed ÷ (Renewed + Lost) × 100 (0 if none decided); the card always
  shows YTD.
- Live links: 766 Motor and 615 Fire policies carry a Renewing Policy No.

## 16. Policy Distribution (method)

- Counts policies by **issue date** (`issue_date`).
- Daily = today only.
- MTD = 1st of the month → today (a past month: → its last day).
- YTD = Jan 1 → today.
- **New** vs **Renewal** (pies and Status): Renewal = the policy itself has a Renewing
  Policy No. (it is a renewal of an earlier policy); New = blank.
- **Total Amount Due** = Σ policy `total_amount_due` (premium due) in the range. Same number
  as Overview's "Gross Premium Written" for the current month.

---

## 17. Glossary (as used on screen)

| Term | Meaning in FIREMAP |
|---|---|
| Accuterm Claim No. | Maagap's claim reference number; OD and TP rows of one accident share it, CNC rows may have none |
| Adjuster | Fire claims: the loss adjuster handling the claim |
| Agency Code | Code of the agency that sold the policy |
| Assured / Claimant Name | Name written on the claim sheet (may include "– TP: NAME" markers); Claimant = the person claiming |
| Case / Insurance Case | Internal grouping: one client + one line (Fire property or Motor vehicle); holds its survey or vehicle, quotations and policies |
| Claim Investigation Result | The human fraud decision: Legitimate, Suspected Fraud, Confirmed Fraud (blank = not yet investigated) |
| Claim Possibility | The model's predicted probability that the quotation's policy will have a counted loss |
| Claim Type | Paid Claim or CNC Issuance |
| Client Name | The resolved client record (not the literal name text on the document) |
| CNC / CNC Issuance | Certificate of No Claim issuance — not a paid loss; never investigated for fraud or predicted |
| COC No. / COI No. | Motor: Certificate of Cover / Certificate of Insurance numbers |
| Conversion Rate | Converted ÷ total quotations in the period |
| Converted (Account) | A quotation that has a policy |
| Counted loss | Paid Claim with Final Status Closed Claim / Waiting for LOA / Waiting for Billing / Waiting for Claim Check (the Logistic Regression label) |
| Coverage Type | Motor claim: Own Damage, Third Party Property Damage, Third Party Bodily Injury/Death |
| Deductible | Amount the insured pays first on a claim (Motor: a peso amount; Fire quotation: text rules) |
| Endorsement No. | Motor: number of a change made to the policy |
| Expiring Policy | Policy whose Period To falls in the view's range |
| Final Status | Claim stage: No Docs. Submitted, Waiting for Evaluation, Waiting for LOA, Waiting for Billing, Waiting for Claim Check, Closed Claim, Denied Claim, CNC Only, Not Push Through, With Lacking Docs, Hold per Client |
| Flood Risk Category / Flag | Combined river-flood/storm-surge rating (Low/Medium/High, blank = outside all zones); Flag Yes/No |
| Fraud Rate | (Suspected + Confirmed) ÷ investigated claims, CNC excluded |
| Fraud Warning | The Naive Bayes prediction (Suspicious / Not suspicious · P(Fraud)) |
| Gross Premium Written | Premium (Total Amount Due) of policies issued this month |
| Insured Name & Address | Policy's literal "NAME, ADDRESS" text |
| Line of Insurance | The document's line text (e.g. Fire) |
| LOA / LOA No. / LOA Amount | Letter of Authority (approval to repair/pay), its number and amount |
| Location of Risk | Address of the insured property (geocoded on surveys) |
| Lost Policy | Expired, not renewed |
| Maximum Amount Subject | Survey: the largest amount exposed at the property |
| Nature of Loss | Motor: Collision, Flood, Theft/Carnapping, Fire, Vandalism, Other; Fire: Fire, Flood, Typhoon, Earthquake, Lightning, Other |
| Needs Review | Import rows the system could not decide safely; a person links/creates/picks |
| Net Liability | Amount Maagap owes on the claim |
| New / Renewal Policy (Distribution) | Policy without / with a Renewing Policy No. (a Renewal renews an earlier policy) |
| Renewed Policy (Renewal Ratio) | A policy that another, later policy renews |
| Occupancy | Use of the property (e.g. Dwelling, Store with Dwelling, Office, Warehouse, Restaurant, Small Factory) |
| Open Claims | Final Status still in progress (not Closed/Denied/CNC Only/Not Push Through) |
| Pending | Not renewed yet and not yet expired |
| Period From / Period To (Period Cover) | Coverage start / end |
| PLA Date (Date Reported) | Date the claim was reported/filed |
| Policy No. / Renewing Policy No. | The policy's number / the number of the earlier policy this one renews |
| Premium / Total Premium / Total Amount Due | What the client pays (Fire quotation: Total Premium; Motor quotation and all policies: Total Amount Due) |
| Quotation | Price offer before a policy; a case can have several |
| Renewal Rate | Renewed ÷ (Renewed + Lost) |
| Repair Estimate | Amount of repair estimate on the claim |
| Risk Assessment / Risk Level | Model risk band Low / Medium / High (§13.5) |
| Risk Class | Survey construction: a = concrete, b = concrete & wood/light materials |
| RSMD | Riot, Strike, Malicious Damage (a peril) |
| Shop/Casa | Motor claims: repair shop / dealer service centre |
| Storm surge (SSA3) | Coastal flooding hazard, advisory level 3 (4.01–5 m storm tide) |
| Sum Insured / Total Sum Insured / Property Sums Insured | Maximum amount covered |
| Surveyor Risk Acceptability | Accept / Key Consideration / Decline |
| T.I. | Tariff item / occupancy code on the survey (e.g. TI-112 Store with Dwelling) |
| Unit | Motor quotation: number of vehicle units |
| Zone / District/Block No. / Current Block Accumulation | Survey location and block exposure fields |
| 100-year river flood | River flooding hazard map for a flood expected once in 100 years |

---

## 18. Found while inventorying — unclear, inconsistent or possibly wrong

Items marked **Fixed 2026-09-28** were fixed on branch `predefense-fixes`, items marked
**Fixed 2026-10-02** on branch `fix-round` (validation Phases 0–8, see
`docs/validation/VALIDATION_LOG.md`); the others are still open (left as is on purpose).

1. **"Renewed" means two different things.**
   - Policy Distribution: a policy that **has** a Renewing Policy No. (it is itself a
     renewal).
   - Renewal Ratio: a policy that **another** policy renews.
   - The same word points in opposite directions on two pages.
   - **Fixed 2026-09-28**: Policy Distribution now says **New / Renewal** (pies, Status filter, column);
     Renewal Ratio keeps "Renewed".
2. **Claims page: Open + Closed ≠ Total.**
   - "Closed Claims" counts only "Closed Claim". Denied Claim, CNC Only and Not Push Through
     are in neither card.
   - Past 6 Months: 32 + 22 = 54 of 67.
   - **Fixed 2026-09-28**: fifth card **Other Finished** ("Denied, CNC Only, Not Push Through"); Open +
     Closed + Other = Total (3 m 29+4+3 = 36 · 6 m 32+22+13 = 67 · 12 m 37+74+22 = 133).
3. **Claims date basis differs.**
   - The Claims page (cards, chart, month filter) uses **Date Reported**.
   - The Claims tab's date filter on Policy Holder Information uses **Date of Loss**.
4. **Overview wording.**
   - The pie's not-converted slice is named "Quotation" (Proposal calls it "Not Yet
     Converted").
   - Cards 1–2 say "As of September 2026" while cards 3–4 say "This Month (September 2026)"
     for the same basis.
   - "Gross Premium Written" (Overview) and "Total Amount Due" (Distribution MTD) are the
     same number (₱1,092,348.33) under different names.
   - **Fixed 2026-09-28**: the slice is now "Not Yet Converted" and all four cards say "This Month
     (September 2026)". The Gross Premium Written / Total Amount Due naming is unchanged.
5. **Rolling windows run to the end of the current month** (Overview pie, Proposal, Claims),
   not to today. Policy Distribution MTD stops at today. The results are only the same while
   there are no future-dated records.
6. **Distribution table: Motor "Sum Insured" is hard-coded "—"**, although all 1,139 Motor
   policies have one. The Renewal table does show it.
   - **Fixed 2026-09-28**: the real `motor_policies.sum_insured` is shown.
7. **Distribution pie colours are per line, not per status.** On YTD, "New Policy" is lilac
   in the Fire pie and red in the Motor pie. Easy to misread.
8. **Proposal "Quote Number" is the internal id**, and Fire and Motor ids overlap (all 1,032
   Fire ids also exist as Motor ids), so two rows can show the same number.
   - **Fixed 2026-09-28**: shown as **FQ-<id>** / **MQ-<id>** (display only); search matches it.
9. **Searches behave differently.** (Since 2026-10-05 every search box uses the multi-word
   rule — every typed word must appear; the field sets below still differ.)
   - Proposal and Policy Holder Information match **every** field, including hidden ones
     (searching "Pelayo" returns 9 rows, some only by middle name).
   - The Claims page searches 4 fields.
   - The Distribution/Renewal tables search the policy number and client only.
   - **Fixed 2026-10-02** (Proposal + Policy Holder Information): the search now matches what
     is shown (dates MM/DD/YYYY, ₱ amounts, JSON popup text) and never "null"/"object". The
     field sets still differ between pages.
10. **Policy Holder Information "Filter by Date"**:
    - It picks one exact day (not a month).
    - Rows with an **empty** date are never filtered out. **Fixed 2026-10-05**: once a day is
      picked they are hidden; clearing the date shows them again.
    - On Survey Report it uses the import timestamp (all 481 surveys = 09/27/2026), so it
      doesn't reflect any survey date.
    - **Fixed 2026-10-02**: the Survey timestamp was read in UTC, so a survey imported before
      08:00 showed on the previous day (Sep 27 → 0 rows); it now uses the date as written.
11. **Manager-only pages are enforced only in the browser.** `/stats/*`, `/ml/*` and every
    CRUD/delete/import endpoint accept any logged-in user, so an admin token can call them
    directly. The only server-side role check is Create Account.
    - **Fixed 2026-09-28**: `/stats/*`, `/ml/models/{name}` and `/ml/predictions/quotations` return 403
      for admins (see §1); everything Policy Holder Information uses stays open to both roles.
12. **Expired session**: only the Create Account and Change Password forms send the user back
    to Login on a 401. Every other page just shows "Failed to load …" after 60 minutes, with
    no hint to log in again.
    - **Fixed 2026-09-28**: one shared 401 handler (plain axios + the `api` instance) sends every page
      to Login with "Your session has expired. Please log in again." (§2).
13. **Quotation and Policy importers turn an unreadable date into a blank** (Claims fail the
    row instead). A quotation with no date is left out of the Proposal cards/table, the
    forecast and the date filter, without any warning.
    - **Fixed 2026-09-28**: an unreadable date now fails the row with a clear message (§10.6); a blank
      date is still allowed.
14. **Leftover clients from uploads that didn't finish.**
    - A Policy row whose name scores < 70 first creates a brand-new client, then finds no
      quotation and goes to Needs Review. The new, almost empty client stays even if the row
      is later discarded.
    - Quotation/Survey/Vehicle rows with an unknown name also create clients with only the
      Last Name = full name.
15. **Customer Info "matched" rows don't update anything.** A new phone or address in the file
    is ignored for an existing client.
16. **Renewal Rate card is always YTD.**
    - MTD's own rate (73.33 % today) is computed but never shown.
    - If the YTD request fails, the card shows "…" forever.
17. **"X% accurate" on the model cards is below the "always predict no loss" baseline.**
    - Motor ≈ 79 % and Fire ≈ 91 % of rows have no loss. The Logistic Regression cards say
      64 % / 60 % because they count Medium/High as "predicted loss" (to catch more losses).
    - Correct as designed, but likely to be questioned; the recall line is the meaningful one.
    - **Fixed 2026-10-02**: the cards add "AUC 0.NN (0.5 = guessing)", which doesn't depend on
      the cutoff.
18. **Average Claim Possibility mixes lines when Policy Line = All.** Fire's base rate is about
    9 % and Motor's about 21 %, so the "15 %" average depends on the line mix.
19. **Fraud Warning shows P(Fraud) on both labels.** "Not suspicious · 29 %" is possible
    (cutoff 0.3), and a reader may take the % as confidence.
    - **Fixed 2026-09-28**: the text is now "Suspicious · 56% fraud chance" / "Not suspicious · 6% fraud
      chance".
20. **Total Net Liability sums every claim filed in the window**, including Denied / Not Push
    Through.
21. **Orphan report file.**
    - `model_reports/2026-09-28_motor_lr_v3.md` is left over from the demo-warm-up rehearsal;
      the database (v4) has no Motor v3.
    - The next Motor retrain will also be called v3 (a different date in the file name).
    - **Fixed 2026-09-28**: the orphan file was deleted (after the pre-defense rehearsal and v4 restore).
22. **No password reset.** "Forgot your password?" is commented out, and a manager cannot
    reset an admin's password from the app.
23. **Settings shows "Malolos Branch" for every user** (fixed text).
24. **Customer Info header matching is stricter than detection.** Its importer only strips
    spaces, "." and "/", so a header like "E-mail Address" is detected as Customer Info but
    that column is not imported. The other importers strip all punctuation.
25. **Vehicle Information shows "Policyholder ID"** where the other tabs show Case ID.
26. **Vehicle Information files can never be auto-detected** (their headers are a subset of
    Motor Quotation's), so a manual type pick is always needed.
27. **Fix round 2026-10-02 — other items fixed** (details in the sections named):
    - `deleted_by` is filled with the deleting user's username on every archive (§11).
    - A reused vehicle gets its empty Plate/Engine/Chassis No. from the quotation row (§10.4).
    - Usernames: surrounding spaces removed on create and ignored at login (§2).
    - Upload results list every failed row and warning; an unreadable file in a folder is
      skipped instead of blocking Import All (§9.1).
    - Sign Up can't be double-clicked; Login says "Can't reach the server" when the backend is
      off (§2).
    - GIS popup: a Fire quotation without its own Location of Risk shows its survey's (§9.3).
    - Proposal pies show "No data yet" (§4).
    - Models: prior_counted_loss counts any earlier Paid Claim reported before the quote,
      whatever its outcome; λ chosen by 5-fold CV; fraud clue wording (§13).
    - Terms 7/8 and Privacy 7 reworded to match the system (Terms 8 heading "Account removal.").
28. **λ = 0.0001 does not converge within 50,000 epochs.** It was added so Fire's choice
    (0.001) isn't at the edge of the grid; its fits stop at the epoch cap (CV AUC 0.680 vs
    0.681 at 0.001, so it is not chosen) and make each LR training slower.
29. **The Motor colour control weight is still not near 0** (Black ≈ +0.37 at the chosen
    λ = 0.01). Larger λ shrinks it (+0.12 at 0.1) but lowers the CV AUC at every step, so the
    CV keeps 0.01; the weight is the noise level of ~840 rows (validation P6.28, "Addressed").
