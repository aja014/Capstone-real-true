"""Read-only regression snapshot: table counts, spot-check endpoint hashes, 401 checks,
auto-detect results. Writes JSON to the given path; with --compare OLD.json it also
diffs against an earlier snapshot.

Run from Backend/ (dev server up on :8000):
    ./venv/Scripts/python ../data_prep/regression_snapshot.py OUT.json [--compare OLD.json]
"""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Backend"))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.security import create_access_token  # noqa: E402
from app.routers import import_batch  # noqa: E402

API = "http://127.0.0.1:8000"
UPLOADS = HERE / "synthetic" / "firemap_synthetic_data" / "upload_files"
SPOT = ["/policyholders", "/insurance-cases", "/fire-property/surveys", "/fire-property/quotations",
        "/fire-property/policies", "/motor/vehicles", "/motor/quotations", "/motor/policies",
        "/motor/claims", "/fire-property/claims", "/stats/overview",
        "/stats/renewal-ratio?period=ytd&date=2026-09-26"]
AUTH_401 = ["/policyholders", "/insurance-cases", "/fire-property/surveys", "/motor/quotations",
            "/motor/claims", "/stats/overview", "/import/policyholders/needs-review",
            "/deleted-fire-property-surveys", "/deleted-policyholders", "/fire-property/claims"]


def minimal_header_sets():
    """Per import type: its first 3 real headers (normalized keys) -- a 'minimal file'."""
    sets = {}
    for e in import_batch.IMPORT_TYPE_REGISTRY:
        sets[f"minimal:{e['key'].value}"] = list(e["column_map"].keys())[:3]
    return sets


def detection():
    out = {}
    header_sets = {f.name: list(pd.read_excel(f, nrows=0).columns) for f in sorted(UPLOADS.glob("*.xlsx"))}
    header_sets.update(minimal_header_sets())
    for name, headers in header_sets.items():
        c = import_batch.detect_headers(headers)
        gap = c[0]["score"] - c[1]["score"]
        auto = c[0]["score"] >= import_batch.DETECT_CONFIDENT_SCORE and gap >= import_batch.AMBIGUITY_MARGIN
        out[name] = {"detected": c[0]["import_type"].value if auto else None,
                     "top": [c[0]["import_type"].value, c[0]["score"]],
                     "runner_up": [c[1]["import_type"].value, c[1]["score"]]}
    return out


def snapshot():
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE() "
            "AND table_type = 'BASE TABLE' ORDER BY 1")).scalars().all()
        counts = {t: conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar() for t in tables}
    h = {"Authorization": f"Bearer {create_access_token({'sub': 'Aaron James'})}"}
    hashes = {p: hashlib.sha256(requests.get(API + p, headers=h).content).hexdigest() for p in SPOT}
    unauth = {p: requests.get(API + p).status_code for p in AUTH_401}
    return {"counts": counts, "hashes": hashes, "unauth": unauth, "detection": detection()}


if __name__ == "__main__":
    snap = snapshot()
    Path(sys.argv[1]).write_text(json.dumps(snap, indent=1))
    print(f"tables {len(snap['counts'])}, 401s: {sorted(set(snap['unauth'].values()))}")
    if "--compare" in sys.argv:
        old = json.loads(Path(sys.argv[sys.argv.index("--compare") + 1]).read_text())
        ok = True
        for section in ("counts", "hashes", "unauth", "detection"):
            diffs = {k: (old[section].get(k), snap[section].get(k))
                     for k in set(old[section]) | set(snap[section]) if old[section].get(k) != snap[section].get(k)}
            print(f"{section}: {'identical' if not diffs else diffs}")
            ok &= not diffs
        print("ALL IDENTICAL" if ok else "DIFFERENCES FOUND")
