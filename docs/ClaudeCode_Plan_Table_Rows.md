# Claude Code plan: tables fill the page (rows per page fit the screen)

Branch: `ui-rows`, created from `main` AFTER the v5d-tests branch is merged.
Frontend only. Do not change anything in `Backend/`. Do not commit; Aj commits.

## Problem
The tables use a fixed page size, so on a 1920×1080 screen they stop halfway and leave empty space:
- `pages/proposal.jsx` PAGE_SIZE = 5
- `pages/policy.jsx` PAGE_SIZE = 8
- `pages/claims.jsx` PAGE_SIZE = 8
- `components/PolicyDistributionShared.jsx` PAGE_SIZE = 8 (used by Policy Distribution AND Renewal Ratio)

## Goal
Each table shows as many rows as fit in its white card, down to the pagination line, on any screen
size. On a smaller screen it shows fewer rows. The page itself should not start scrolling because of it.

## Approach (one shared hook)
1. Add `src/lib/useFitRows.js`: a hook that takes a ref to the table's scroll area and returns
   `rowsPerPage`. Use a ResizeObserver plus a window resize listener:
   rows = floor((available height of the table area - header row height) / body row height).
   Measure a real rendered row when one exists; otherwise use a sensible default row height.
   Clamp it to a minimum of 5 and a maximum of 50. Debounce resize events.
2. Replace the PAGE_SIZE constant in the 4 files with the hook's value.
3. When rowsPerPage changes, keep the current page valid (clamp it like `safePage` already does),
   so the table never shows an empty page.
4. Keep everything else the same: search, filters, month pickers, Expiry Date sorting, the
   "N results" count, "No records found.", Updating predictions…, and the sticky Geospatial column.
5. Proposal: the right-hand column (Average Claim Possibility, Policy Forecast, Model accuracy) sets the
   height of that row. The table card should fill the same height and show as many rows as fit.

## Must not break
- The 1280×720 fit from fix round 3 (IT test case): at 1280×720 the pages must still fit without a
  horizontal page scroll; fewer rows per page is expected and fine.
- No re-render loop. Remember the old "Maximum update depth exceeded" crash on the Proposal page: do not
  let the measurement re-render the Recharts charts. Keep the memoized charts as they are, and only
  update rowsPerPage when the number actually changes.

## Check (live, in the browser, backend running on insurance_db; look only, no uploads or deletes)
1. 1920×1080 at 100% zoom: Policy Holder Information (all 6 types), Proposal (Motor and Fire),
   Claims, Policy Distribution (Daily/MTD/YTD), Renewal Ratio (Daily/MTD/YTD). The last row sits just
   above the pagination; no big empty space; no page scrollbar caused by the table.
2. 1280×720: the same pages still fit (fewer rows).
3. Resize the window: the rows adjust, and the page number stays valid.
4. Type fast in a search box on Proposal and Claims for 5 seconds: no crash, no blank page.
5. Run `npm run lint` (stays at baseline) and the frontend tests (all pass).
6. Report: files changed, rows per page measured at 1920×1080 and 1280×720 for each page, and test results.

## Outcome (Oct 20, 2026)
Applied to Proposal, Policy Holder Information, Policy Distribution and Renewal Ratio (useFitRows.js).
Claims was left at a fixed PAGE_SIZE = 8: its table starts below the charts, so fitting to the window gave only the 5-row minimum.
Checks: lint 45 (baseline), npm test 22/22, fast typing on Proposal and Claims with no errors, no horizontal page scroll.
