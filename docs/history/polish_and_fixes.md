# Polish, pre-defense fixes, accounts/passwords, legal pages, known issues

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

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

## Pre-defense fixes (SYSTEM_REFERENCE §18) — DONE
2026-09-28, branch `predefense-fixes`. No DB change, no ML code/number change. Fixed §18 items
1, 2, 4, 6, 8, 11, 12, 13, 19, 21; the rest are left as is on purpose.
- **Claims page (#2)**: fifth card **Other Finished** (caption "Denied, CNC Only, Not Push
  Through") = Total − Open − Closed (`/stats/claims` `other_claims`, schema `ClaimsStats`), so the
  cards add up: 3 m 29+4+3 = 36 · 6 m 32+22+13 = 67 · 12 m 37+74+22 = 133. `StatCard` gained an
  optional `note` caption.
- **Distribution (#1, #6)**: New / **Renewal** (pies from the API "Renewal Policy", Status filter,
  column — a policy that itself renews an earlier one); Renewal Ratio keeps "Renewed". Motor rows
  show the real Sum Insured.
- **Server-side roles (#11)**: `security.require_manager` (401 without login, 403 "Manager access
  only." for non-managers) on the whole `/stats` router + `GET /ml/models/{name}` +
  `GET /ml/predictions/quotations`. `GET /ml/models` and `GET /ml/predictions/claims` stay open
  to both roles (Policy Holder Information polls the refresh status and shows Fraud Warning to
  admins); every CRUD/import/Needs Review endpoint stays open to both roles. Tests that stub
  `get_current_user` must return a manager-like object (`SimpleNamespace(role="manager")`).
- **Expired session (#12)**: one 401 handler in `Frontend/src/api/api.js`, registered on plain
  `axios` and on the `api` instance, installed by `import './api/api'` in `main.jsx`: clears the
  login, sets `sessionStorage.sessionExpired`, goes to `/`; Login shows "Your session has
  expired. Please log in again." The `/login` request itself is excluded.
- **Proposal (#8)**: Quote Number shown as **FQ-<id>** / **MQ-<id>** (display + search only).
- **Overview (#4)**: pie slice "Not Yet Converted" (API), all four card captions "This Month (…)".
- **Fraud Warning (#19)**: "Suspicious · 56% fraud chance" / "Not suspicious · 6% fraud chance".
- **Unreadable dates (#13)**: `import_shared.parse_import_date` — Fire/Motor Quotation (Date) and
  Policy (Issue Date / Period From / Period To) rows with an unreadable date now FAIL with e.g.
  "Date: '31/31/2026' is not a valid date" (blank dates still allowed). v2 synthetic files (1,032 +
  1,450 quotation, 876 + 1,139 policy rows) and the demo folder: 0 parser failures.
- **Orphan report (#21)**: `model_reports/2026-09-28_motor_lr_v3.md` deleted.
- **Verified**: 155 backend tests (86 + `tests/test_roles.py` + `tests/test_predefense_fixes.py`);
  `npm run build` ok; lint = baseline (19 pre-existing). Regression: counts, 401s, detection
  identical; only `/stats/overview` differs, and hashing it with "Quotation" put back matches the
  baseline exactly. Browser as manager (all changed places) and as a temporary admin (ZZTEST
  Admin, created via Create Account): admin 403 on stats/manager ML, 200 on everything Policy
  Holder Information uses, `/overview` redirects to `/policy`, Claims tab Fraud Warning shown;
  invalid token → Login with the session message; wrong password still "Invalid username or
  password". Demo rehearsal (warm-up 26.9 s, retrained motor_lr → Import All 0 review / 0 failed
  → Proposal FQ-1033 Medium 12% / MQ-1460 Low 16%, GIS High storm surge / Medium river → Claims
  new cards) passed; then v4 restored (25 counts = v4, users 1, no ZZTEST user, no demo client).

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
- **Security note — SECRET_KEY rotated 2026-10-01** (the old key was in pushed git history via
  the initial-commit `Backend/.env`): new `secrets.token_urlsafe(64)` in `Backend/.env` only, never
  committed; all earlier JWTs are invalid (401). `--reload` doesn't watch `.env` — restart uvicorn
  after changing it.

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
