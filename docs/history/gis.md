# GIS flood-risk lookup, boundary buffer and storm surge data

> Moved word-for-word from CLAUDE.md on 2026-10-01 (CLAUDE.md was over the size limit). Full original: [CLAUDE_full_2026-10-01.md](CLAUDE_full_2026-10-01.md). Cross-references like "see X above/below" may now point to another file in this folder — see the index in CLAUDE.md.

## GIS Flood-Risk Lookup Service (Objective 2.1) — DONE (now combines river flood + storm surge)
Shared service, not duplicated per line: `Backend/app/services/flood_risk.py`,
one entrypoint `lookup_flood_risk(address: str) -> dict` returning
`{latitude, longitude, flood_risk_flag, flood_risk_category, river_flood_category,
storm_surge_category}`. Called from all 6 creation sites where an address is
known before a policy is issued: Fire/Property Survey (manual endpoint + bulk
import + its needs-review `resolve_for_policyholder`) and Motor Quotation
(manual endpoint + bulk import + its needs-review `resolve_for_policyholder`)
— the needs-review resolve paths weren't explicitly requested but were
included so a manually-resolved row matches what auto-import would've
produced, same principle as the rest of the Needs-Review Resolution section
above. All 6 call sites merge the function's full return dict generically
(`dict.update(...)` or `**lookup_flood_risk(...)`), so the storm-surge
extension below reached every one of them with zero call-site changes —
confirmed, not assumed, via a real end-to-end test through the actual
`/fire-property/surveys` and `/motor/quotations` HTTP endpoints.

**Behavior (extended this session)**: geocode the address via OpenStreetMap
Nominatim (User-Agent `MaagapCapstoneFloodRiskLookup/1.0`, no personal
contact info in it — deliberately not the same as sending someone's real
email to a third-party service; `countrycodes=ph`), then point-in-polygon
against BOTH hazard datasets:
- River flood: `gis_data/flood_hazard/bulacan_100yr/extracted/Bulacan_Flood_100year.shp`
  (`Var` 1/2/3 = Low/Medium/High).
- Storm surge: `gis_data/storm_surge/bulacan/extracted/SSA3/Bulacan_StormSurge_SSA3.shp`
  (`HAZ` 1/2/3 = Low/Medium/High) — SSA3 (the 3rd of the 4 increasingly-severe
  advisory-level shapefiles acquired earlier, see the old "Storm Surge Hazard
  Data" section below) was picked as the one fixed scenario to combine in,
  rather than checking all 4 or exposing a scenario choice — out of scope
  for what this capstone needs.

Each dataset is classified independently (worst zone wins on overlap within
that dataset, same as before); the two results are then combined by taking
whichever is MORE SEVERE (Low < Medium < High, "outside every zone" counts as
lowest/safest) as the headline `flood_risk_flag`/`flood_risk_category` —
this is the repurposed meaning of those 2 existing columns, shown everywhere
they already were (GIS modal, table columns) with no frontend changes needed
since the field name/shape is unchanged. The 2 new columns
`river_flood_category` / `storm_surge_category` store each dataset's
individual result for future ML use — not displayed in the UI.

Every failure mode (blank address, geocode miss, network error, an invalid
polygon tripping a specific `contains()` call) is caught inside the service;
the two hazard checks fail independently of each other (one shapefile
failing to load doesn't blank the other's result or the headline it would
otherwise produce) and total failure (bad geocode) returns all 6 fields
null — never raises, never blocks the Survey/Quotation record from being
created. A caller-supplied manual value for any of the 4 original fields on
the 2 manual endpoints is respected (lookup only fills them in when all 4
are blank), same as Survey's pre-existing manual-entry support — the 2 new
breakdown columns aren't part of that manual-override check, since they're
purely a lookup byproduct, never manually entered.

**Why not geopandas/QGIS API as CLAUDE.md originally said**: geopandas/fiona
have no wheels for this project's Python 3.14 venv. `pyshp` (pure Python) was
tried first and couldn't even finish a raw read of the shapefile in several
minutes — the file is 71MB but only **3 features** (one dissolved multi-
polygon per hazard class), each with an enormous vertex count, which is a
pathological case for pure-Python per-feature parsing. Fixing formal GEOS
validity (`shapely.make_valid()`, since all 3 polygons report `is_valid ==
False` — typical of dissolved/raster-derived hazard polygons) was tried and
also killed after 4+ minutes for the same reason. Switched to `pyogrio`
(GDAL-backed, ships its own binaries, has a wheel for this Python version)
which reads all 3 features in ~2.5s; skipped `make_valid`/`simplify`
entirely and verified `contains()` directly against the raw (formally
invalid) geometries instead — correct results across 8 points spanning all
3 hazard classes plus clearly-outside points, ~0.16s/query average, wrapped
in a per-geometry try/except as the safety net for the rare point that
might trip GEOS on the unfixed geometry. New deps: `shapely`, `pyogrio` (in
`Backend/requirements.txt`, this session also gave that file its first real
content — it was empty before).

**Schema**: `motor_quotations` got the same 4 columns
`FirePropertySurvey` already had (`latitude DECIMAL(10,7)`,
`longitude DECIMAL(10,7)`, `flood_risk_flag BOOLEAN`,
`flood_risk_category VARCHAR(50)`) via a manual `ALTER TABLE` against the
live dev DB — same `create_all()`-doesn't-alter-existing-tables caveat as
everywhere else in this doc. `MotorQuotationCreate` gained the matching 4
`Optional[...]` schema fields (mirrors `FirePropertySurveyCreate`'s
pre-existing ones). Later session: both `fire_property_surveys` and
`motor_quotations` got 2 more columns each, `river_flood_category
VARCHAR(50)` and `storm_surge_category VARCHAR(50)`, same manual-`ALTER
TABLE` caveat; `FirePropertySurveyCreate`/`MotorQuotationCreate` both
gained the matching 2 `Optional[str]` schema fields.

**Progress indicator**: bulk imports of Surveys/Motor Quotations are now
slower (Nominatim's usage policy caps requests at 1/second, enforced
process-wide via a lock in `flood_risk.py`, so N addressed rows take at
least N seconds). Live per-row "Checking address 12 of 50..." progress
would need genuinely new infrastructure (background job + polling endpoint
or SSE/WebSockets — none of that exists anywhere in this codebase today).
Given this project's own "simplest defensible architecture, tight deadline"
framing and that it's a low-concurrency capstone tool, went with the
simple option instead: the Upload modal's existing spinner text swaps to
"Processing — this may take longer for larger files due to flood-risk
lookups" (`UploadFileModal.jsx`, `GEOCODED_BATCH_TYPES`), shown only when
the import type actually triggers geocoding (Fire/Property Survey or Motor
Quotation) — no new backend infrastructure.

**Verified end-to-end with real fixtures** (all 4 required scenarios plus
the needs-review resolve path as a bonus check, since it was newly wired
in): a real, known-good Bulacan address ("Barangay Longos, Malolos City,
Bulacan, Philippines") geocoded consistently to the same coordinates and
"Medium" flood risk across all call sites — manual Survey creation, manual
Motor Quotation creation, bulk Survey import, bulk Motor Quotation import,
and a Motor Quotation created via needs-review resolve. A deliberately
unfindable address left all 4 fields null in every case, with the
Survey/Quotation record still created successfully and no error surfaced
(`failed: 0` in both bulk-import summaries). All test data (9 policyholders,
8 insurance cases, their surveys/quotations/vehicles, 7 import_records) was
identified by exact test name / `zzfloodtest%` source-file match and
deleted afterward — nothing else in the dev DB was touched.

**Storm-surge integration verified (later session)**: Panghulo and Salambao
(the 2 coastal Obando addresses the storm-surge data was originally acquired
to cover, see below) now correctly come back with `river_flood_category:
null` (flood-alone genuinely still finds nothing there — unchanged) but
`storm_surge_category: "High"` and a headline `flood_risk_category: "High"`
— confirmed both via direct `lookup_flood_risk()` calls and via a real
`POST /fire-property/surveys` + `POST /motor/quotations` round trip (JWT
generated through the app's own `create_access_token`, hitting a live
`uvicorn` instance, checked against the DB row afterward, then deleted).
A real inland address (Marilao) came back `river_flood_category: "Medium"`,
`storm_surge_category: null`, headline `"Medium"` — storm surge correctly
contributes nothing inland, headline unchanged from pre-storm-surge
behavior. "Worst of both" was verified against 3 real points found by
intersecting the two shapefiles' geometries directly (river Low/storm High
→ headline High; river High/storm Low → headline High; river Medium/storm
Medium → headline Medium) — forward-geocoding barangay-level addresses
landed near but not exactly inside these small overlap polygons, so the
combine logic itself was checked at the precise overlap coordinates rather
than via a geocoded address for this specific case.

## Hazard Boundary Buffer (50m) — DONE
A wide geographic reliability pass (16 real barangay-level addresses across
8 towns, beyond the original Obando spot-check) surfaced a real problem:
**Calumpit** — a town with a well-documented real-world flood history —
came back with zero risk everywhere, including its town center at the
river confluence near Calumpit Bridge. Investigating rather than accepting
that at face value: every one of 6 tested Calumpit points (Iba, Gatbuca,
Poblacion, San Marcos, Panducot, Sergio Bayan) landed within **1.74m to
25.93m** of a river-flood hazard polygon's edge — i.e. right on the
boundary line, not genuinely outside the mapped floodplain. This is a
structural property of river-adjacent settlements, not bad data: towns
build on the highest available ground right at a floodplain's edge, so a
geocoded barangay point routinely lands within meters of the hazard
boundary in either direction, and a hard yes/no point-in-polygon test is
unstable at that margin.

**Investigation** (data-driven, not a guessed number): measured exact
distances using a local equirectangular projection (meters-per-degree
scaled for Bulacan's ~14.8°N band — no `pyproj` in this venv, but accurate
to well under 1% at this scale).
- **Near-miss group** (Calumpit's 6 points, should flip to at-risk):
  1.74m, 3.14m, 4.98m, 5.83m, 25.75m, 25.93m — max **25.93m** needed to
  close all 6.
- **Confirmed-safe group** (5 successfully-geocoded inland/upland points —
  Niugan/Angat, San Roque/Angat, San Lorenzo/Norzagaray, Bigte/Norzagaray,
  Camachin/DRT): minimum measured distance to the nearest river-flood zone
  was **900m** (Niugan, Angat) — the others ranged 1.36km–8.46km. Storm-
  surge distances for these were all 19–40km, not a constraint.
- **Verdict**: no conflict between the two goals — the gap between "largest
  distance needed to catch a real near-miss" (25.93m) and "smallest margin
  among confirmed-safe points" (900m) is ~35x. Tested candidate sizes
  25/50/100/150/200m against both groups: 25m missed 2 of 6 Calumpit points
  by under 1m; 50m+ caught all 6 with zero false positives among the 5
  inland points at any tested size up to 200m.
- **Chose 50m**: smallest tested size that reliably closes every documented
  near-miss, leaving ~24m of margin over the tightest case (Iba/Gatbuca at
  25.93m) and ~850m of headroom before the nearest genuinely-safe point.

**Bambang, Bulakan caveat (found during investigation, not swept under
the rug)**: Bambang has two very different distances to the two hazard
datasets — 324m from the nearest storm-surge zone (a genuine, different-
scale miss, correctly NOT closed by 50m) but only **14.20m** from the
nearest river-flood zone (the same near-miss phenomenon as Calumpit).
Explicit decision: no per-address exceptions — the buffer applies
uniformly, so Bambang's river-flood result changes (correctly, by the same
logic as Calumpit) while its storm-surge result stays unaffected.

**Implementation**: `Backend/app/services/flood_risk.py`'s `_classify()`
now treats a point as inside a zone if `contains()` OR the point is within
`BOUNDARY_BUFFER_METERS` (50) of the zone's edge. Rather than buffering the
zone polygons directly — which would have hit the same `make_valid()`/
`unary_union()` performance wall documented above (these 3-feature,
huge-vertex, formally-invalid geometries took 4+ minutes and were killed
twice) — the buffer is implemented as `geom.distance(point) <=
BOUNDARY_BUFFER_METERS`, mathematically equivalent but far cheaper since it
never touches the polygon's own geometry. Zone geometries are projected
once (cached, same lazy-load pattern as before) into the same local-meters
frame used for the investigation, via `shapely.transform()` (fast — ~1.1s
one-time cost for the river shapefile, ~0.02s for storm surge, negligible
against the existing ~2.5-4s one-time shapefile read this already paid).
Applies to both datasets uniformly via the same `_classify()` function —
no per-address or per-dataset special-casing.

**Verified with real data**: all 6 Calumpit points now return a real
category — Iba/Gatbuca/Poblacion/Panducot → High, San Marcos → Medium,
Sergio Bayan → Low (higher than the single nearest zone in a few cases,
because the 50m buffer can put a point within range of *multiple* tiers at
once — e.g. Iba is within 50m of both the Medium zone at 25.93m and the
High zone at 46.60m, so worst-wins correctly picks High — an expected
interaction with the tiered classification, not a bug). Bambang confirmed:
river-flood flipped to "Low" (14.20m, within buffer), storm-surge stayed
`None` (324m, outside buffer) — exactly as investigated. All 5 inland/
upland control points stayed `None`/`None`, unaffected. Re-running the same
address twice still gives byte-identical results (determinism unaffected).

**Performance — honest finding, not just "still fast"**: classification-
only cost (excluding geocoding) rose from ~0.1-0.2ms/lookup (contains()
only) to **6-115ms/lookup** depending on how many zones require the new
`distance()` fallback. Root cause, isolated and confirmed: `contains()` on
these huge (millions-of-vertices, formally-invalid) polygons already cost
~2ms/zone for a point near/inside the shape (not sub-millisecond the way a
point far outside the bounding box is) — that part is pre-existing,
unrelated to this change. The new `distance()` call, needed only for zones
where `contains()` returns False, costs roughly **~30ms/call** on these
same huge geometries — meaningfully more expensive than `contains()`, and
the actual driver of the added cost. Still a non-issue in absolute terms:
full `lookup_flood_risk()` calls remain dominated by the >=1000ms Nominatim
throttle (a real request still averages ~1-2s), so this adds roughly a
5-11% overhead per lookup, not a user-visible slowdown. Not optimized
further (e.g. checking zones highest-severity-first and early-exiting once
a hit is confirmed would cut this) since it wasn't needed to meet "still
fast" — flagged here in case a future session wants to tighten it.

## Storm Surge Hazard Data (Bulacan) — ACQUIRED AND INTEGRATED (see GIS Flood-Risk Lookup Service above)
Companion dataset to the 100yr flood data above, for the coastal-flooding gap
the flood-only data misses (surfaced via Obando's Panghulo/Salambao
barangays — see verification below). This section is data acquisition/
verification history — the actual lookup/storage/combine logic lives in the
"GIS Flood-Risk Lookup Service" section above.

**Source**: same Hugging Face mirror as the flood data,
`bettergovph/project-noah-hazard-maps`, but under `Storm Surge/` (not
`Flood/`) — 4 subfolders `StormSurgeAdvisory1`-`4` (one per SSA advisory
level), each containing a per-province `Bulacan.zip`. Downloaded all 4 into
`gis_data/storm_surge/bulacan/` (`SSA1_Bulacan.zip` ...
`SSA4_Bulacan.zip`, extracted under `extracted/SSA1/` ... `extracted/SSA4/`
as `Bulacan_StormSurge_SSA{1-4}.shp` + sidecars), plus
`metadata_stormsurge.txt` and `01ReadMe_StormSurge.pdf` (the authoritative
source for the SSA definitions — see below; the metadata txt's own
"SSA1 up to 2m ... SSA4 exceeding 4m" wording is rounded/imprecise
compared to the PDF's real thresholds, don't rely on the txt for exact
cutoffs).

**Verified properties** (via pyogrio, same tooling as the flood data):
all 4 shapefiles load cleanly, CRS EPSG:4326 (WGS84), each has exactly 3
rows with a single `HAZ` attribute (1.0/2.0/3.0 = Low/Medium/High per
water depth + velocity-depth product) — same one-dissolved-polygon-per-
hazard-class shape as the flood data's `Var` column, different column
name. Real SSA definitions per the README PDF (PAGASA/NIGS, DOST-Project
NOAH, JMA storm surge model + WXTide + FLO-2D, simulated over 721 historical
tropical cyclones 1951-2013): **SSA1 = 2.01-3m, SSA2 = 3.01-4m, SSA3 =
4.01-5m, SSA4 = 5m+ peak storm tide height** — 4 separate, INCREASINGLY
SEVERE scenario shapefiles, not 4 severity levels within one file (unlike
flood's single-file 3-tier `Var`). Bounds are notably narrower than the
flood data's whole-province extent (~120.69-120.96°E, 14.69-14.84°N vs
flood's 120.69-121.35°E, 14.72-15.27°N) — consistent with storm surge only
affecting Bulacan's western coastal strip, not the whole province.
`.xml` sidecar shows the same `CreaDate=20210719` dissolve-tool processing
date as the flood data (likely the same GIS batch), on top of the
1951-2013 simulation base — same "later processing pass on older survey
work" vintage story as flood. License: ODC-ODbL, same as flood.

**Confirmed it fills the real Obando gap**: tested real, verified (via
PhilAtlas) coordinates for Obando's Panghulo (14.6980, 120.9471) and
Salambao (14.7087, 120.9081) against both datasets. The 100yr flood
shapefile MISSES both — nearest polygon edge ~2.8km (Panghulo) / ~2.2km
(Salambao) away, i.e. genuinely outside every flood hazard polygon, not
just coordinate noise. Storm surge HITS both directly at every SSA level:
Panghulo comes back Medium at SSA1, High at SSA2-4; Salambao comes back
High at every level (SSA1-4). Inland/deep-inland controls (Marilao, a
point ~20km from the coast) correctly stayed outside the storm surge
polygons at low SSA levels and only came into range at the most severe
SSA4 scenario (Marilao ~111m from the SSA4 edge) — consistent with a real
coastal-hazard dataset, not an overly permissive one.

**Integrated (later session)**: the open design questions above were
resolved as worst-of-both (river vs. storm surge, whichever is more
severe, becomes the headline `flood_risk_flag`/`flood_risk_category`) with
SSA3 picked as the single fixed storm-surge scenario to check (not all 4,
not configurable) and each hazard's individual result kept in its own new
column (`river_flood_category`, `storm_surge_category`) for future ML use.
See "GIS Flood-Risk Lookup Service" above for the implementation and
verification.
