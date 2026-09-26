"""Data Prep Step 4, Part B -- upload the 8 synthetic files one at a time through the
real single-file import endpoints (same ones the Upload modal uses), in order.
Stops before the next file if a file has any needs_review or failed rows.

Run from Backend/ (dev server must be up on :8000):
    ./venv/Scripts/python -u ../data_prep/load_step4.py
"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "Backend"))

import requests  # noqa: E402

from app.security import create_access_token  # noqa: E402

API = "http://127.0.0.1:8000"
UPLOADS = HERE / "synthetic" / "firemap_synthetic_data" / "upload_files"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ORDER = [
    ("1_customer_information.xlsx", "/import/policyholders/upload"),
    ("2_fire_surveys.xlsx", "/import/fire-property/surveys/upload"),
    ("3_motor_quotations.xlsx", "/import/motor/quotations/upload"),
    ("4_fire_quotations.xlsx", "/import/fire-property/quotations/upload"),
    ("5_fire_policies.xlsx", "/import/fire-property/policies/upload"),
    ("6_motor_policies.xlsx", "/import/motor/policies/upload"),
    ("7_motor_claims.xlsx", "/import/claims/motor/upload"),
    ("8_fire_property_claims.xlsx", "/import/claims/fire-property/upload"),
]

# Allows resuming after a stop: python load_step4.py 3  -> starts at file 3.
start_at = int(sys.argv[1]) if len(sys.argv) > 1 else 1

for n, (name, endpoint) in enumerate(ORDER, 1):
    if n < start_at:
        continue
    headers = {"Authorization": f"Bearer {create_access_token({'sub': 'Aaron James'})}"}
    print(f"--- {name} -> POST {endpoint}", flush=True)
    t0 = time.monotonic()
    with open(UPLOADS / name, "rb") as f:
        r = requests.post(API + endpoint, headers=headers, files={"file": (name, f, MIME)}, timeout=None)
    secs = time.monotonic() - t0
    if r.status_code != 200:
        print(f"HTTP {r.status_code}: {r.text[:1000]}\nSTOPPED.", flush=True)
        sys.exit(1)
    s = r.json()
    print(f"    {secs:.0f}s  rows {s['total_rows']}  new {s['unmatched_created']}  matched {s['matched']}  "
          f"needs_review {s['needs_review']}  failed {s['failed']}", flush=True)
    if s["needs_review"] or s["failed"]:
        for e in s["errors"][:10]:
            print(f"    FAILED row {e['source_row']}: {e['error']}", flush=True)
        if s["needs_review"]:
            nr = requests.get(API + "/import/policyholders/needs-review", headers=headers).json()
            for rec in [x for x in nr if x["source_file"] == name][:10]:
                print(f"    NEEDS REVIEW row {rec['source_row']}: {rec.get('raw_data')}", flush=True)
        print(f"STOPPED after {name}. Resume later with: load_step4.py {n + 1}", flush=True)
        sys.exit(2)

print("ALL FILES LOADED", flush=True)
