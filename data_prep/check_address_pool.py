"""Data Prep Step 3 -- check every address-pool candidate through the REAL GIS system.

Run from Backend/ with the Backend venv:
    ./venv/Scripts/python ../data_prep/check_address_pool.py            # check (resumable)
    ./venv/Scripts/python ../data_prep/check_address_pool.py --summary  # summary only

Per candidate:
  1. Town check: one Nominatim request with the system's exact params + addressdetails=1
     (same User-Agent, same process-wide 1 req/s throttle as flood_risk.py).
  2. GIS: kept candidates go through app.services.flood_risk.lookup_flood_risk()
     (which also fills geocode_cache -- the only table this script writes to, indirectly).
  3. Coordinates from step 1 and step 2 must be identical.

Resumable: rows are appended to address_pool_verified.csv as they finish; candidates
already in that file are skipped. Transient errors (network/429/5xx/bad JSON) are
logged to check_errors.log and NOT written, so a re-run retries them.
"""

import csv
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Backend"))

import requests  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.services import flood_risk  # noqa: E402

CANDIDATES = HERE / "address_pool_candidates.csv"
OUTPUT = HERE / "address_pool_verified.csv"
ERROR_LOG = HERE / "check_errors.log"

COLUMNS = [
    "candidate_id", "barangay", "town", "address", "status", "drop_reason",
    "nominatim_display_name", "latitude", "longitude", "flood_risk_flag",
    "flood_risk_category", "river_flood_category", "storm_surge_category", "note",
]

BARANGAY_MATCH_THRESHOLD = 85
TOWN_LEVEL_TYPES = {"city", "town", "municipality", "county", "state", "province", "region", "country"}
BARANGAY_FIELDS = ["village", "quarter", "suburb", "hamlet", "neighbourhood", "city_district", "residential", "isolated_dwelling"]
TOWN_FIELDS = ["city", "town", "municipality", "county"]
PROVINCE_FIELDS = ["province", "state", "county", "state_district"]

# Spelling variants treated as the same town (only logged when actually used).
TOWN_ALIASES = {"baliuag": "baliwag", "bulacan": "bulakan", "sta maria": "santa maria"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str) -> str:
    s = strip_accents(s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_town(s: str) -> str:
    s = norm(s)
    s = re.sub(r"^(city of|municipality of) ", "", s)
    s = re.sub(r" (city|municipality)$", "", s)
    return TOWN_ALIASES.get(s, s)


def norm_barangay(s: str) -> str:
    return re.sub(r"^(barangay|brgy|bgy) ", "", norm(s))


# ---------------------------------------------------------------- step 1


def nominatim_with_details(address: str):
    """Returns ("found", result) / ("not_found", None) / ("error", message)."""
    flood_risk._throttle()
    try:
        r = requests.get(
            flood_risk.NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1, "countrycodes": "ph", "addressdetails": 1},
            headers={"User-Agent": flood_risk.USER_AGENT},
            timeout=10,
        )
        if r.status_code != 200:
            return "error", f"HTTP {r.status_code}"
        results = r.json()
        if not results:
            return "not_found", None
        return "found", results[0]
    except Exception as e:  # noqa: BLE001
        return "error", f"{type(e).__name__}: {e}"


def town_check(cand: dict, res: dict):
    """Returns (drop_reason or None, note or None)."""
    addr = res.get("address", {}) or {}
    display = res.get("display_name", "") or ""
    display_parts = [p.strip() for p in display.split(",")]

    province_vals = [addr.get(k, "") for k in PROVINCE_FIELDS] + display_parts
    if not any(norm(v) == "bulacan" for v in province_vals):
        return "outside Bulacan", None

    want = norm_town(cand["town"])
    town_vals = [addr[k] for k in TOWN_FIELDS if addr.get(k)]
    if not town_vals:
        town_vals = display_parts
    matched_town = next((v for v in town_vals if norm_town(v) == want), None)
    if matched_town is None:
        return f"wrong town (result: {' / '.join(town_vals)})", None

    notes = []
    if matched_town != cand["town"]:
        notes.append(f"town variant: '{cand['town']}' ~ '{matched_town}'")

    if res.get("addresstype") in TOWN_LEVEL_TYPES:
        return "town-level only", None
    want_b = norm_barangay(cand["barangay"])
    field_vals = [addr[k] for k in BARANGAY_FIELDS if addr.get(k)]
    best, best_val = 0.0, None
    for v in field_vals + display_parts:
        sc = fuzz.token_sort_ratio(want_b, norm_barangay(v))
        if sc > best:
            best, best_val = sc, v
    if best < BARANGAY_MATCH_THRESHOLD:
        return "town-level only", None
    if best < 100:
        notes.append(f"barangay fuzzy: '{cand['barangay']}' ~ '{best_val}' ({best:.1f})")
    return None, "; ".join(notes) or None


# ---------------------------------------------------------------- main loop


def load_done() -> set:
    if not OUTPUT.exists():
        return set()
    with OUTPUT.open(encoding="utf-8", newline="") as f:
        return {r["candidate_id"] for r in csv.DictReader(f)}


def log_error(msg: str):
    with ERROR_LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def run():
    with CANDIDATES.open(encoding="utf-8-sig", newline="") as f:
        candidates = list(csv.DictReader(f))
    done = load_done()
    todo = [c for c in candidates if c["candidate_id"] not in done]
    print(f"{len(candidates)} candidates, {len(done)} already done, {len(todo)} to check", flush=True)

    new_file = not OUTPUT.exists()
    out = OUTPUT.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(out, fieldnames=COLUMNS)
    if new_file:
        writer.writeheader()

    consecutive_errors, backoffs = 0, 0
    start = time.monotonic()
    for i, cand in enumerate(todo, 1):
        row = {k: "" for k in COLUMNS}
        row.update({k: cand[k] for k in ("candidate_id", "barangay", "town", "address")})

        status, res = nominatim_with_details(cand["address"])
        if status == "error":
            log_error(f"{cand['candidate_id']} step1 {res}")
            consecutive_errors += 1
            if consecutive_errors >= 5:
                backoffs += 1
                if backoffs > 3:
                    print("Too many consecutive errors -- stopping; re-run to resume.", flush=True)
                    break
                print(f"{consecutive_errors} consecutive errors, backing off 60s", flush=True)
                time.sleep(60)
                consecutive_errors = 0
            continue
        consecutive_errors = 0

        if status == "not_found":
            row.update(status="dropped", drop_reason="not found")
        else:
            row["nominatim_display_name"] = res.get("display_name", "")
            reason, note = town_check(cand, res)
            if note:
                print(f"  NOTE {cand['candidate_id']}: {note}", flush=True)
            if reason:
                row.update(status="dropped", drop_reason=reason,
                           latitude=res.get("lat", ""), longitude=res.get("lon", ""))
            else:
                lat1, lng1 = float(res["lat"]), float(res["lon"])
                gis = flood_risk.lookup_flood_risk(cand["address"])
                if gis["latitude"] is None:
                    # Either a transient error (not cached -> retry later) or a real disagreement.
                    if flood_risk._cache_get(flood_risk._normalize_address(cand["address"])) is None:
                        log_error(f"{cand['candidate_id']} lookup_flood_risk returned no coords (not cached) -- will retry")
                        continue
                    row.update(status="dropped", latitude=lat1, longitude=lng1,
                               drop_reason="coordinate mismatch (lookup_flood_risk found nothing)")
                elif (gis["latitude"], gis["longitude"]) != (lat1, lng1):
                    row.update(status="dropped", latitude=gis["latitude"], longitude=gis["longitude"],
                               drop_reason=f"coordinate mismatch (step1 {lat1},{lng1} vs lookup {gis['latitude']},{gis['longitude']})")
                else:
                    row.update(status="kept", drop_reason="")
                    for k in ("latitude", "longitude", "flood_risk_flag", "flood_risk_category",
                              "river_flood_category", "storm_surge_category"):
                        row[k] = "" if gis[k] is None else gis[k]

        writer.writerow(row)
        out.flush()
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}] {time.monotonic() - start:.0f}s elapsed", flush=True)
    out.close()


# ---------------------------------------------------------------- summary


def summary():
    with CANDIDATES.open(encoding="utf-8-sig", newline="") as f:
        order = [r["candidate_id"] for r in csv.DictReader(f)]
    with OUTPUT.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    # Rewrite sorted in candidate order (dedup by candidate_id, last wins).
    by_id = {r["candidate_id"]: r for r in rows}
    rows = [by_id[c] for c in order if c in by_id]
    with OUTPUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    kept = [r for r in rows if r["status"] == "kept"]
    dropped = [r for r in rows if r["status"] == "dropped"]
    print(f"\n=== SUMMARY ({len(rows)} of {len(order)} candidates processed) ===")
    print(f"kept {len(kept)}, dropped {len(dropped)}")
    missing = [c for c in order if c not in by_id]
    if missing:
        print(f"NOT YET PROCESSED ({len(missing)}): {', '.join(missing)}")

    print("\nDrop reasons:")
    reasons = Counter(re.sub(r" \(.*", "", r["drop_reason"]) for r in dropped)
    for k, v in reasons.most_common():
        print(f"  {k}: {v}")

    print("\nKept per town:")
    towns = sorted({r["town"] for r in rows})
    per_town = Counter(r["town"] for r in kept)
    cand_town = Counter(r["town"] for r in rows)
    for t in towns:
        print(f"  {t}: {per_town[t]} / {cand_town[t]}")

    print("\nKept per combined category:")
    cats = Counter(r["flood_risk_category"] or "none" for r in kept)
    for k in ("High", "Medium", "Low", "none"):
        print(f"  {k}: {cats[k]}")
    sev = {"": 0, "Low": 1, "Medium": 2, "High": 3}
    high_ss = [r for r in kept if r["flood_risk_category"] == "High"
               and sev[r["storm_surge_category"]] > sev[r["river_flood_category"]]]
    print(f"  High because of storm surge (storm surge High, river lower): {len(high_ss)}")

    low_towns = [t for t in towns if per_town[t] < 5]
    print(f"\nTowns with < 5 kept: {', '.join(f'{t} ({per_town[t]})' for t in low_towns) or 'none'}")

    groups = defaultdict(list)
    for r in kept:
        groups[(r["latitude"], r["longitude"])].append(r)
    shared = [g for g in groups.values() if len(g) > 1]
    print(f"\nKept candidates sharing identical coordinates: {sum(len(g) for g in shared)} in {len(shared)} group(s)")
    for g in shared:
        print(f"  ({g[0]['latitude']}, {g[0]['longitude']}): "
              + "; ".join(f"{r['candidate_id']} {r['barangay']}, {r['town']}" for r in g))

    with engine.connect() as conn:
        counts = conn.execute(text("SELECT status, COUNT(*) FROM geocode_cache GROUP BY status")).all()
    total = sum(c for _, c in counts)
    print(f"\ngeocode_cache rows: {total} ({', '.join(f'{s} {c}' for s, c in counts)})")


# ---------------------------------------------------------------- revision + second pass
# Decisions made after reviewing pass 1 (Data Prep Step 3, second round).

OTHER_BARANGAY_HALL = ["C028", "C033", "C036", "C126", "C129", "C165", "C167", "C172", "C179", "C258",
                       "C273", "C277", "C290", "C295", "C378", "C445", "C465", "C474", "C496"]
AMBIGUOUS_SUB_BARANGAY = ["C092", "C098", "C101", "C105", "C106"]
MISSPELLED = ["C176"]
SHARED_COORDINATES = ["C007", "C033", "C028", "C030", "C126", "C129", "C139", "C140", "C258", "C274",
                      "C273", "C277", "C294", "C295", "C376", "C378", "C403", "C421", "C458", "C465",
                      "C463", "C474"]
GIS_KEYS = ("latitude", "longitude", "flood_risk_flag", "flood_risk_category",
            "river_flood_category", "storm_surge_category")


def read_rows():
    with OUTPUT.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows):
    tmp = OUTPUT.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) or "" for k in COLUMNS})
    tmp.replace(OUTPUT)


def meters_between(lat1, lng1, lat2, lng2) -> float:
    dy = (lat1 - lat2) * flood_risk._METERS_PER_DEGREE_LAT
    dx = (lng1 - lng2) * flood_risk._METERS_PER_DEGREE_LON
    return (dx * dx + dy * dy) ** 0.5


def fill_gis(row, gis):
    for k in GIS_KEYS:
        row[k] = "" if gis[k] is None else gis[k]


def revise():
    rows = read_rows()
    by_id = {r["candidate_id"]: r for r in rows}

    def drop(ids, reason):
        for c in ids:
            r = by_id[c]
            if r["status"] == "kept":
                r.update(status="dropped", drop_reason=reason)
                for k in GIS_KEYS[2:]:
                    r[k] = ""

    drop(OTHER_BARANGAY_HALL, "other barangay hall")
    drop(AMBIGUOUS_SUB_BARANGAY, "ambiguous sub-barangay")
    drop(MISSPELLED, "misspelled candidate")
    drop(SHARED_COORDINATES, "shared coordinates")

    for r in rows:
        m = re.match(r"coordinate mismatch \(step1 ([-\d.]+),([-\d.]+) vs lookup", r["drop_reason"])
        if not m:
            continue
        gis = flood_risk.lookup_flood_risk(r["address"])  # cached -> no network request
        if gis["latitude"] is None:
            print(f"{r['candidate_id']}: no cached lookup result, left dropped", flush=True)
            continue
        d = meters_between(float(m.group(1)), float(m.group(2)), gis["latitude"], gis["longitude"])
        r.update(status="kept", drop_reason="", note=f"rescued: check point differed by {d:.1f} m")
        fill_gis(r, gis)
    write_rows(rows)


def second_pass():
    """Retry 'not found' / 'town-level only' rows once, without the word 'Barangay'.
    Resumable: a row whose note already starts with 'second pass' is skipped."""
    rows = read_rows()
    todo = [r for r in rows if r["status"] == "dropped"
            and r["drop_reason"] in ("not found", "town-level only")
            and not (r.get("note") or "").startswith("second pass")]
    print(f"second pass: {len(todo)} to retry", flush=True)
    consecutive_errors, backoffs = 0, 0
    for i, r in enumerate(todo, 1):
        addr2 = re.sub(r"^Barangay\s+", "", r["address"])
        status, res = nominatim_with_details(addr2)
        if status == "error":
            log_error(f"{r['candidate_id']} second-pass step1 {res}")
            consecutive_errors += 1
            if consecutive_errors >= 5:
                backoffs += 1
                if backoffs > 3:
                    print("Too many consecutive errors -- stopping; re-run to resume.", flush=True)
                    break
                time.sleep(60)
                consecutive_errors = 0
            continue
        consecutive_errors = 0

        if status == "not_found":
            r["note"] = "second pass: not found"
        else:
            reason, note = town_check(r, res)
            if note:
                print(f"  NOTE {r['candidate_id']}: {note}", flush=True)
            if reason:
                r["note"] = f"second pass: {reason}"
            else:
                lat1, lng1 = float(res["lat"]), float(res["lon"])
                gis = flood_risk.lookup_flood_risk(addr2)
                if gis["latitude"] is None:
                    if flood_risk._cache_get(flood_risk._normalize_address(addr2)) is None:
                        log_error(f"{r['candidate_id']} second-pass lookup returned no coords (not cached) -- will retry")
                        continue
                    r["note"] = "second pass: coordinate mismatch (lookup_flood_risk found nothing)"
                else:
                    note_txt = "second pass format"
                    d = meters_between(lat1, lng1, gis["latitude"], gis["longitude"])
                    if d > 0:
                        note_txt += f"; rescued: check point differed by {d:.1f} m"
                    r.update(status="kept", drop_reason="", address=addr2,
                             nominatim_display_name=res.get("display_name", ""), note=note_txt)
                    fill_gis(r, gis)
        write_rows(rows)
        if i % 25 == 0 or i == len(todo):
            print(f"[{i}/{len(todo)}]", flush=True)


if __name__ == "__main__":
    if "--revise" in sys.argv:
        revise()
    elif "--second-pass" in sys.argv:
        second_pass()
    elif "--summary" not in sys.argv:
        run()
    summary()
