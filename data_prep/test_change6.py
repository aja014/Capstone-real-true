"""Data Prep Change 6 tests -- Occupancy Breakdown / Boundaries survey upload columns.
Creates ZZTEST rows only, through the real endpoints; ids are saved to
test_change6_ids.json (scratch location given as argv[1]) for exact-id cleanup.

Run from Backend/ (dev server up on :8000):
    ./venv/Scripts/python ../data_prep/test_change6.py <scratch_dir>
"""

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Backend"))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.routers import import_batch, import_fire_property as fp  # noqa: E402
from app.security import create_access_token  # noqa: E402

API = "http://127.0.0.1:8000"
H = {"Authorization": f"Bearer {create_access_token({'sub': 'Aaron James'})}"}
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SCRATCH = Path(sys.argv[1])
ADDR = ["Atlag, Malolos City, Bulacan, Philippines", "Paco, Obando, Bulacan, Philippines",
        "Caniogan, Malolos City, Bulacan, Philippines", "Poblacion, Pulilan, Bulacan, Philippines"]

OCC = ["Occupancy - Building", "Occupancy - Main Occupancy", "Occupancy - Stocks", "Occupancy - M/E",
       "Occupancy - FFF", "Occupancy - BI/LOP", "Occupancy - Others", "Occupancy - Total"]
BND = ["Boundary - Front", "Boundary - Right", "Boundary - Left", "Boundary - Rear", "Boundary - Sketch"]

results, ids = [], {"import_records": [], "surveys": [], "cases": [], "policyholders": []}


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""), flush=True)


def base(name, addr):
    return {"Name of Insured": name, "Location of Risk": addr, "Risk Class": "a",
            "Description": "ZZTEST change 6", "Maximum Amount Subject": "1,000,000"}


def xlsx(rows, columns):
    buf = io.BytesIO()
    pd.DataFrame(rows, columns=columns).to_excel(buf, index=False)
    return buf.getvalue()


def upload(content, filename, url="/import/fire-property/surveys/upload"):
    r = requests.post(API + url, headers=H, files={"file": (filename, content, MIME)})
    r.raise_for_status()
    return r.json()


def track(summary):
    ids["import_records"] += summary["import_record_ids"]


def survey_for(record_id):
    with engine.connect() as c:
        rec = c.execute(text("SELECT matched_case_id, matched_policyholder_id FROM import_records WHERE id=:i"),
                        {"i": record_id}).first()
        s = c.execute(text("SELECT id, occupancy_breakdown, boundaries, flood_risk_category FROM fire_property_surveys "
                           "WHERE insurance_case_id=:c"), {"c": rec.matched_case_id}).first()
    ids["cases"].append(rec.matched_case_id)
    ids["policyholders"].append(rec.matched_policyholder_id)
    ids["surveys"].append(s.id)
    load = lambda v: json.loads(v) if isinstance(v, str) else v  # noqa: E731
    return s.id, load(s.occupancy_breakdown), load(s.boundaries), s.flood_risk_category


FULL_OCC = {"Occupancy - Building": "₱1,000,000.00", "Occupancy - Main Occupancy": "500,000",
            "Occupancy - Stocks": "Php 250,000.50", "Occupancy - M/E": 150000, "Occupancy - FFF": "50,000",
            "Occupancy - BI/LOP": "25,000", "Occupancy - Others": "10,000", "Occupancy - Total": "1,985,000.50"}
FULL_BND = {"Boundary - Front": "MacArthur Highway", "Boundary - Right": "Residential house (2-storey, concrete)",
            "Boundary - Left": "Vacant lot", "Boundary - Rear": "Irrigation canal",
            "Boundary - Sketch": "See attached sketch no. 12"}
EXP_OCC = {"building": 1000000, "main_occupancy": 500000, "stocks": 250000.5, "me": 150000, "fff": 50000,
           "bi_lop": 25000, "others": 10000, "total": 1985000.5}
EXP_BND = {"front": "MacArthur Highway", "right": "Residential house (2-storey, concrete)", "left": "Vacant lot",
           "rear": "Irrigation canal", "sketch": "See attached sketch no. 12"}

cols = list(base("x", "x")) + OCC + BND

# ---- File 1: rows A (all filled), B (partial), C (all new columns blank), D (bad amount), E (total mismatch)
rowA = {**base("ZZTESTALPHA Holdings", ADDR[0]), **FULL_OCC, **FULL_BND}
rowB = {**base("ZZTESTBRAVO Mills", ADDR[1]), "Occupancy - Building": "2,000,000", "Occupancy - Total": "2,000,000",
        "Boundary - Front": "Provincial road", "Boundary - Sketch": "Sketch on file"}
rowC = {**base("ZZTESTCHARLIE Bakery", ADDR[2])}
rowD = {**base("ZZTESTDELTA Foundry", ADDR[3]), "Occupancy - Building": "1,000,000", "Occupancy - Stocks": "abc"}
rowE = {**base("ZZTESTECHO Warehouse", ADDR[0]), "Occupancy - Building": "1,000,000",
        "Occupancy - Stocks": "200,000", "Occupancy - Total": "1,500,000"}
s1 = upload(xlsx([rowA, rowB, rowC, rowD, rowE], cols), "zztest_change6_main.xlsx")
track(s1)
print("summary 1:", {k: s1[k] for k in ("total_rows", "unmatched_created", "matched", "needs_review", "failed")},
      "errors:", s1["errors"], "warnings:", s1["warnings"], flush=True)
check("file 1: 4 created, 1 failed, 0 needs review",
      (s1["unmatched_created"], s1["failed"], s1["needs_review"]) == (4, 1, 0))
recA, recB, recC, recE = s1["import_record_ids"]

sid, occ, bnd, cat = survey_for(recA)
check("A all 13 filled: occupancy_breakdown exact", occ == EXP_OCC, str(occ))
check("A all 13 filled: boundaries exact", bnd == EXP_BND, str(bnd))
check("A: GIS still filled (cached address)", cat == "High", str(cat))
check("A: no warning for a matching total", not any(w["source_row"] == 2 for w in s1["warnings"]))

sid, occ, bnd, _ = survey_for(recB)
check("B partial: only filled keys", occ == {"building": 2000000, "total": 2000000}
      and bnd == {"front": "Provincial road", "sketch": "Sketch on file"}, f"{occ} {bnd}")

sid, occ, bnd, _ = survey_for(recC)
check("C new columns present but blank: both NULL", occ is None and bnd is None, f"{occ} {bnd}")

err = [e for e in s1["errors"] if e["source_row"] == 5]
check("D bad amount fails with clear message",
      len(err) == 1 and err[0]["error"] == 'Occupancy - Stocks: "abc" is not a valid amount', str(err))

sid, occ, bnd, _ = survey_for(recE)
warn = [w for w in s1["warnings"] if w["source_row"] == 6]
check("E total mismatch: imported, total stored as given",
      occ == {"building": 1000000, "stocks": 200000, "total": 1500000}, str(occ))
check("E total mismatch: warning reported",
      len(warn) == 1 and "1,500,000.00 differs from the sum of the other parts 1,200,000.00" in warn[0]["warning"],
      str(warn))
check("only one warning in file 1", len(s1["warnings"]) == 1)

# ---- File 2: no new columns at all (exactly today's format)
rowF = base("ZZTESTFOXTROT Depot", ADDR[1])
s2 = upload(xlsx([rowF], list(rowF)), "zztest_change6_nocolumns.xlsx")
track(s2)
check("F no new columns: 1 created, warnings []",
      (s2["unmatched_created"], s2["failed"], s2["warnings"]) == (1, 0, []), str(s2))
sid, occ, bnd, _ = survey_for(s2["import_record_ids"][0])
check("F no new columns: both NULL", occ is None and bnd is None)

# ---- File 3: folder upload (/import/batch/detect + /import/batch/upload), same data as A
rowG = {**base("ZZTESTGOLF Printing", ADDR[2]), **FULL_OCC, **FULL_BND}
content = xlsx([rowG], cols)
det = requests.post(API + "/import/batch/detect", headers=H,
                    files=[("files", ("zztest_change6_folder.xlsx", content, MIME))]).json()
f = det["files"][0]
check("folder: file with new columns auto-detects as Fire Survey",
      f["best_guess"] == "fire_property" and not f["ambiguous"], f"{f['best_guess']} {f['candidates'][0]['score']}")
r = requests.post(API + "/import/batch/upload", headers=H,
                  files=[("files", ("zztest_change6_folder.xlsx", content, MIME))],
                  data={"import_types": "fire_property"})
r.raise_for_status()
s3 = r.json()["files"][0]["summary"]
track(s3)
check("folder: 1 created, no failures/warnings", (s3["unmatched_created"], s3["failed"], s3["warnings"]) == (1, 0, []),
      str(s3))
sid, occ, bnd, _ = survey_for(s3["import_record_ids"][0])
check("folder: same JSON as single-file A", occ == EXP_OCC and bnd == EXP_BND)

# ---- Resolve path: same parsing via raw_data (rolled back, nothing kept)
db = SessionLocal()
try:
    raw = {k: fp.clean_cell_value(v) for k, v in pd.Series(rowA).items()}
    record = models.ImportRecord(source_file="zztest_resolve", source_row=2, import_type=models.ImportType.fire_property,
                                 match_status=models.MatchStatus.needs_review, raw_data=raw)
    ph_id = ids["policyholders"][0]
    # ZZTESTALPHA already has an Atlag survey -> use a different address so a new survey is created
    raw["Location of Risk"] = ADDR[3]
    case_id, status = fp.resolve_for_policyholder(db, record, ph_id)
    s = db.query(models.FirePropertySurvey).filter_by(insurance_case_id=case_id).one()
    check("resolve path: same occupancy_breakdown/boundaries", s.occupancy_breakdown == EXP_OCC
          and s.boundaries == EXP_BND, f"{status} {s.occupancy_breakdown}")
finally:
    db.rollback()
    db.close()

# ---- Detection: new headers don't disturb anything
cand = import_batch.detect_headers(cols)
check("detect (file-1 headers): fire_property top, clear margin",
      cand[0]["import_type"].value == "fire_property" and cand[0]["score"] - cand[1]["score"] >= 12,
      f"{cand[0]['score']} vs {cand[1]['import_type'].value} {cand[1]['score']}")

(SCRATCH / "test_change6_ids.json").write_text(json.dumps(ids, indent=1))
print("ids:", ids)
print(f"\n{sum(results)}/{len(results)} checks passed")
