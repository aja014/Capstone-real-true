"""Data Prep Step 4, Part A -- READ-ONLY pre-flight for the synthetic upload files.

Run from Backend/:  ./venv/Scripts/python ../data_prep/preflight_step4.py
Uses the importers' own code (column maps, header normalizers, detection, matching).
The only DB access is SELECTs on geocode_cache. Nothing is written anywhere.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Backend"))

import pandas as pd  # noqa: E402
from rapidfuzz import fuzz  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.services import flood_risk  # noqa: E402
from app.routers import (  # noqa: E402
    import_batch, import_claims, import_fire_property as fp, import_motor as mo,
    import_policyholders as ph, import_shared,
)

UPLOADS = HERE / "synthetic" / "firemap_synthetic_data" / "upload_files"

FILES = [
    ("1_customer_information.xlsx", "policyholder", ph.COLUMN_MAP, ph.normalize_header, set()),
    ("2_fire_surveys.xlsx", "fire_property", fp.SURVEY_COLUMN_MAP, fp.normalize_header, set()),
    ("3_motor_quotations.xlsx", "motor", mo.COLUMN_MAP, mo.normalize_header, set()),
    ("4_fire_quotations.xlsx", "fire_property_quotation", fp.FIRE_QUOTATION_COLUMN_MAP, fp.normalize_header, set()),
    ("5_fire_policies.xlsx", "fire_property_policy", fp.FIRE_POLICY_COLUMN_MAP, fp.normalize_header, set()),
    ("6_motor_policies.xlsx", "motor_policy", mo.MOTOR_POLICY_COLUMN_MAP, mo.normalize_header, set()),
    ("7_motor_claims.xlsx", "motor_claim", import_claims.MOTOR_CLAIM_COLUMN_MAP,
     import_claims.normalize_header, import_claims.IGNORED_HEADERS),
    ("8_fire_property_claims.xlsx", "fire_property_claim", import_claims.FIRE_CLAIM_COLUMN_MAP,
     import_claims.normalize_header, import_claims.IGNORED_HEADERS),
]


def detect(headers):
    """Same decision rule as import_batch.detect_batch."""
    cands = import_batch.detect_headers(headers)
    top, run = cands[0], cands[1]
    gap = top["score"] - run["score"]
    if top["score"] >= import_batch.DETECT_CONFIDENT_SCORE and gap >= import_batch.AMBIGUITY_MARGIN:
        verdict = f"AUTO-DETECTED {top['import_type'].value}"
    elif top["score"] >= import_batch.DETECT_CONFIDENT_SCORE:
        verdict = "AMBIGUOUS (manual pick)"
    else:
        verdict = "LOW CONFIDENCE (manual pick)"
    return verdict, top, run


def part1():
    print("=== 1. Headers and auto-detect ===")
    for name, expected, cmap, normh, ignored in FILES:
        headers = list(pd.read_excel(UPLOADS / name, nrows=0).columns)
        unmapped = [h for h in headers if normh(h) not in cmap and normh(h) not in ignored]
        ign = [h for h in headers if normh(h) in ignored]
        verdict, top, run = detect(headers)
        ok = "OK" if top["import_type"].value == expected and verdict.startswith("AUTO") else "CHECK"
        print(f"{name}: {len(headers)} headers; unmapped: {unmapped or 'none'}"
              + (f"; recognised-but-ignored: {ign}" if ign else ""))
        print(f"   detect: {verdict}  score {top['score']}  (runner-up {run['import_type'].value} "
              f"{run['score']})  [{ok}]")


def part2():
    print("\n=== 2. Addresses already in geocode_cache ===")
    with engine.connect() as conn:
        cached = {r[0]: r[1] for r in conn.execute(text("SELECT normalized_address, status FROM geocode_cache"))}
    cols = {"1_customer_information.xlsx": ("Present Address", "no geocoding in this importer"),
            "2_fire_surveys.xlsx": ("Location of Risk", "geocoded on import"),
            "3_motor_quotations.xlsx": ("Address", "geocoded on import"),
            "4_fire_quotations.xlsx": ("Location of Risk", "no geocoding in this importer")}
    for name, (col, note) in cols.items():
        df = pd.read_excel(UPLOADS / name, dtype=str)
        match = [c for c in df.columns if fp.normalize_header(c) == fp.normalize_header(col)]
        vals = df[match[0]].dropna().map(str.strip) if match else pd.Series([], dtype=str)
        keys = {flood_risk._normalize_address(v) for v in vals if v}
        missing = sorted(k for k in keys if k not in cached)
        not_found = sorted(k for k in keys if cached.get(k) == "not_found")
        blanks = len(df) - len(vals)
        print(f"{name} [{col}] ({note}): {len(vals)} filled cells, {blanks} blank, {len(keys)} distinct; "
              f"missing from cache {len(missing)}, cached as not_found {len(not_found)}")
        for k in missing[:10]:
            print(f"   missing: {k}")


def part3():
    print("\n=== 3. File 1 row-by-row matching (importer's own match_score, empty DB) ===")
    df = pd.read_excel(UPLOADS / "1_customer_information.xlsx", dtype=str)
    pool, problems, new = [], [], 0
    for idx, row in df.iterrows():
        f = ph.row_to_policyholder_fields(row)
        cn = ph.full_name(f.get("last_name", ""), f.get("first_name", ""), f.get("middle_name", ""))
        ca = (f.get("present_address") or "").lower()
        cp = ph.normalize_phone(f.get("mobile_number"))
        best, be = 0, None
        for e in pool:
            s = ph.match_score(cn, ca, cp, e["name"], e["addr"], e["phone"])
            if s > best:
                best, be = s, e
        if best >= ph.MATCH_THRESHOLD and be["source"] == "db":
            problems.append((idx + 2, cn, "would MERGE into", be["row"], be["name"], best))
        elif best >= ph.REVIEW_THRESHOLD:
            problems.append((idx + 2, cn, "would go to NEEDS REVIEW vs", be["row"], be["name"], best))
            pool.append({"source": "pending", "row": idx + 2, "name": cn, "addr": ca, "phone": cp})
        else:
            new += 1
            pool.append({"source": "db", "row": idx + 2, "name": cn, "addr": ca, "phone": cp})
    top = max((max((ph.match_score(p["name"], p["addr"], p["phone"], q["name"], q["addr"], q["phone"])
                    for q in pool[:i]), default=0) for i, p in enumerate(pool)), default=0)
    print(f"{len(df)} rows -> {new} new, {len(problems)} problem rows; highest score vs an earlier row: {top:.1f}")
    for p in problems[:10]:
        print(f"   row {p[0]} '{p[1]}' {p[2]} row {p[3]} '{p[4]}' (score {p[5]:.1f})")
    return pool


def part3b(people):
    """Bonus: how files 2-6 resolve their person against the 1,129 people from file 1."""
    print("\n=== 3b. Bonus: files 2-6 person matching against file 1 (each importer's own rule) ===")
    db_pool = [{"name": p["name"], "phone": p["phone"]} for p in people]
    phones = {p["name"]: p["phone"] for p in people}  # noqa: F841

    def fire_best(cn, cp):
        best = 0
        for e in db_pool:
            s = fp.match_score(cn, cp, e["name"], e["phone"])
            if s > best:
                best = s
                if best >= 100:
                    break
        return best

    def motor_best(cn):
        return max(fuzz.token_sort_ratio(cn, e["name"]) for e in db_pool)

    specs = [
        ("2_fire_surveys.xlsx", lambda f: (fp.full_name(f.get("name_of_insured", "")),
                                           fp.normalize_phone(f.get("tel_fax_no"))), fp.row_to_survey_fields, "fire"),
        ("3_motor_quotations.xlsx", lambda f: (mo.full_name(f.get("insured_name", "")), ""), mo.row_to_fields, "motor"),
        ("4_fire_quotations.xlsx", lambda f: (fp.full_name(f.get("insured_name", "")), ""),
         fp.row_to_fire_quotation_fields, "fire"),
        ("5_fire_policies.xlsx", lambda f: (fp.full_name(import_shared.split_insured_name_address(
            f.get("insured_name_address"))[0]), ""), fp.row_to_fire_policy_fields, "fire"),
        ("6_motor_policies.xlsx", lambda f: (mo.full_name(import_shared.split_insured_name_address(
            f.get("insured_name_address"))[0]), ""), mo.row_to_motor_policy_fields, "motor"),
    ]
    for name, getname, to_fields, line in specs:
        df = pd.read_excel(UPLOADS / name)
        matched, review, new, errs, examples = 0, 0, 0, 0, []
        for idx, row in df.iterrows():
            try:
                cn, cp = getname(to_fields(row))
            except Exception as e:  # a row the importer itself would fail
                errs += 1
                examples.append((idx + 2, f"row parse error: {e}"))
                continue
            best = fire_best(cn, cp) if line == "fire" else motor_best(cn)
            if best >= 90:
                matched += 1
            elif best >= 70:
                review += 1
                examples.append((idx + 2, f"'{cn}' best {best:.1f} -> needs review"))
            else:
                new += 1
                examples.append((idx + 2, f"'{cn}' best {best:.1f} -> NEW person"))
        print(f"{name}: {len(df)} rows -> person matched {matched}, needs review {review}, "
              f"new person {new}, parse errors {errs}")
        for ex in examples[:5]:
            print(f"   row {ex[0]}: {ex[1]}")


if __name__ == "__main__":
    part1()
    part2()
    people = part3()
    part3b([p for p in people if p["source"] == "db"])
