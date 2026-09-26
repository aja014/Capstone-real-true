"""Checks every rule in the FIREMAP Synthetic Data Rules document against the generated data.
Run after generate.py. Writes output/validation_report.md and exits non-zero on any failure."""
import sys, math, datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
import openpyxl
from rapidfuzz import fuzz
import generate as G

OUT = G.OUT
checks = []
def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))

TODAY = G.TODAY
TERMS, QUOTES, PEOPLE, PROPS, VEH = G.TERMS, G.QUOTES, G.PEOPLE, G.PROPERTIES, G.VEHICLES
LIVE = G.LIVE
paid = [e for e in LIVE if not e["cnc"]]

# ---- files as written
files = {}
for f in sorted(OUT.glob("*.xlsx")):
    ws = openpyxl.load_workbook(f, read_only=True).active
    rows = list(ws.iter_rows(values_only=True))
    files[f.stem] = (list(rows[0]), rows[1:])

EXPECTED_HEADERS = {
 "1_customer_information": ["Last Name", "First Name", "Middle Name", "Gender", "Marital Status", "Complete Name of Spouse",
     "Nationality", "Present Address", "Permanent Address", "Residence Phone Number", "Mobile Number", "Email Address",
     "Zip Code", "Occupation", "Employer", "TIN", "SSS No."],
 "2_fire_surveys": ["Name of Insured", "Contact Person", "Brief Description of Owner's Business", "Location of Risk",
     "Tel/Fax No.", "Risk Class", "Description", "Maximum Amount Subject", "Loss Record", "Fire", "Earthquake",
     "Typhoon", "Flood", "Burglary/Robbery", "RSMD", "Landslide/Subsidence", "Smoke/Aircraft/Vehicle Impact/Explosion",
     "Volcanic Eruption", "Tsunami", "Terrorist Attack", "Spontaneous Combustion", "Machinery Breakdown",
     "General Liability", "Money", "Fidelity Guarantee", "Goods Transit", "Others", "Maintenance", "Housekeeping",
     "Storage Arrangement", "Safety/Security", "Block Condition", "Surrounding Community", "Overall Risk Assessment",
     "Surveyor Risk Acceptability", "Protection Facilities", "District No./Block No.", "Current Block Accumulation",
     "Zone", "T.I.", "Occupancy - Building", "Occupancy - Main Occupancy", "Occupancy - Stocks", "Occupancy - M/E",
     "Occupancy - FFF", "Occupancy - BI/LOP", "Occupancy - Others", "Occupancy - Total", "Boundary - Front",
     "Boundary - Right", "Boundary - Left", "Boundary - Rear", "Boundary - Sketch"],
 "3_motor_quotations": ["Date", "Insured Name", "Address", "Unit", "Classification", "Color", "Deductible", "Plate No.",
     "Total Amount Due", "Sum Insured", "Model", "Make", "Body Type", "Motor/Engine No.", "Serial/Chassis No.",
     "Authorized Capacity", "Bank"],
 "4_fire_quotations": ["Date", "Name of Insured", "Location of Risk", "Period of Cover", "Property Sums Insured",
     "Total Sum Insured", "Total Premium", "Deductibles", "Occupancy", "Basis of Evaluation", "Perils Covered",
     "Line of Insurance"],
 "5_fire_policies": ["Issue Date", "Insured Name & Address", "Line of Insurance", "Policy No.", "Renewing Policy No.",
     "Period From", "Period To", "Total Amount Due", "Sum Insured", "Agency Code", "Property Insured", "Construction", "Occupancy"],
 "6_motor_policies": ["Issue Date", "Insured Name & Address", "Line of Insurance", "Policy No.", "Renewing Policy No.",
     "Period From", "Period To", "Total Amount Due", "Sum Insured", "Agency Code", "Deductible"],
 "7_motor_claims": G.MOTOR_CLAIM_COLS, "8_fire_property_claims": G.FIRE_CLAIM_COLS,
}
for k, exp in EXPECTED_HEADERS.items():
    check(f"Headers exactly as the importer expects: {k}", files[k][0] == exp, "" if files[k][0] == exp else str(files[k][0]))

# ---- forbidden blank-words anywhere except Protection Facilities
bad = []
for k, (hdr, rows) in files.items():
    for r in rows:
        for c, v in zip(hdr, r):
            if isinstance(v, str) and v.strip().lower() in ("none", "na", "n/a", "null", "nan") and c != "Protection Facilities":
                bad.append((k, c, v))
check("No None/NA/N/A/null cell outside Protection Facilities", not bad, str(bad[:5]))

# ---- survey occupancy breakdown adds up
occ_ok = all(abs(sum(pr["occ_parts"].values()) - pr["tsi"]) < 1 for pr in PROPS)
check("Survey Occupancy parts add up exactly to Occupancy - Total (= sum insured)", occ_ok)
spouse_ok = all((p["spouse"] is not None) == (p["marital"] == "Married") for p in PEOPLE)
check("Spouse name filled for married clients only", spouse_ok)

# ---- counts and rates
cnt = {k: len(v[1]) for k, v in files.items()}
ended = [t for t in TERMS if t["pto"] < TODAY]
def rate(xs): return sum(xs) / len(xs) if xs else 0
m_rate = rate([t["counted_loss"] for t in ended if t["line"] == "motor"])
f_rate = rate([t["counted_loss"] for t in ended if t["line"] == "fire"])
inv = [e for e in paid if e["label"]]
fraud = [e for e in inv if e["label"] != "Legitimate"]
fr_rate = len(fraud) / len(inv)
expired = [t for t in TERMS if t["pto"] < TODAY - dt.timedelta(days=30)]
renewed_nos = {t["renewing_no"] for t in TERMS if t["renewing_no"]}
ren_rate = rate([t["policy_no"] in renewed_nos for t in expired])
cnc_share = sum(1 for e in LIVE if e["cnc"]) / cnt["7_motor_claims"]
unlabeled = sum(1 for e in paid if not e["label"]) / len(paid)
check("Motor policies with a counted loss about 20% (17-24%)", 0.17 <= m_rate <= 0.24, f"{m_rate:.1%} of {sum(1 for t in ended if t['line']=='motor')} ended motor policies")
check("Fire policies with a counted loss about 9% (7-12%)", 0.07 <= f_rate <= 0.12, f"{f_rate:.1%} of {sum(1 for t in ended if t['line']=='fire')} ended fire policies")
check("Fraud about 12% of investigated paid claims (10-15%)", 0.10 <= fr_rate <= 0.15, f"{fr_rate:.1%} ({len(fraud)} of {len(inv)})")
check("Renewal rate about 70% (62-78%)", 0.62 <= ren_rate <= 0.78, f"{ren_rate:.1%}")
check("CNC share of motor claim rows about 10% (7-16%)", 0.07 <= cnc_share <= 0.16, f"{cnc_share:.1%}")
check("Claims without a label yet about 8% or less", unlabeled <= 0.10, f"{unlabeled:.1%}")

# ---- dates
errs = []
for t in TERMS:
    q = t["quote"]
    if not (1 <= (t["issue"] - q["date"]).days <= 14): errs.append(("quote->issue", t["policy_no"]))
    if not (0 <= (t["pfrom"] - t["issue"]).days <= 7): errs.append(("issue->from", t["policy_no"]))
    if t["pto"] != G.add_years(t["pfrom"]): errs.append(("one year", t["policy_no"]))
    if t["issue"] > TODAY or q["date"] > TODAY: errs.append(("future", t["policy_no"]))
    if t["prev"] is not None and t["pfrom"] != t["prev"]["pto"]: errs.append(("renewal start", t["policy_no"]))
for q in QUOTES:
    if q["date"] > TODAY: errs.append(("future quote", q["date"]))
for e in LIVE:
    t = e["term"]
    if not (t["pfrom"] <= e["loss"] <= t["pto"]): errs.append(("loss outside coverage", e["accuterm"]))
    if not (e["loss"] <= e["reported"] <= TODAY): errs.append(("reported", e["accuterm"]))
    if not e["cnc"]:
        chain = [e["loss"], e["reported"], e.get("docs"), e.get("loa_date"), e.get("billing"), e.get("updated")]
        chain = [x for x in chain if x]
        if chain != sorted(chain) or max(chain) > TODAY: errs.append(("claim date order", e["accuterm"]))
check("All date rules hold (quote/issue/period, renewals, claim chain, nothing after today)", not errs, str(errs[:5]))

# ---- uniqueness and references
pol_nos = [t["policy_no"] for t in TERMS]
check("Policy numbers unique", len(pol_nos) == len(set(pol_nos)))
acc = Counter(r[0] for r in files["7_motor_claims"][1] + files["8_fire_property_claims"][1])
acc_events = Counter(e["accuterm"] for e in LIVE)
check("Accuterm numbers unique per accident (third party rows share their accident's number)", all(v == 1 for v in acc_events.values()))
loas = [e["loa_no"] for e in LIVE if e.get("loa_no")]
check("LOA numbers unique", len(loas) == len(set(loas)))
for attr in ("plate", "engine", "chassis"):
    vals = [v[attr] for v in VEH]
    check(f"Vehicle {attr} numbers unique and contain letters", len(vals) == len(set(vals)) and all(any(ch.isalpha() for ch in x) for x in vals))
known = set(pol_nos)
claim_pols = [r[3] for r in files["7_motor_claims"][1]] + [r[3] for r in files["8_fire_property_claims"][1]]
check("Every claim points to an existing policy", all(p in known for p in claim_pols))
check("Every policy has its quotation", all(t["quote"] in QUOTES for t in TERMS))
ren_ok = all((t["prev"] is None) or (t["prev"]["subject"] is t["subject"] and t["renewing_no"] == t["prev"]["policy_no"]) for t in TERMS)
check("Every renewal points to the same person's earlier policy on the same vehicle/property", ren_ok)
check("Importer linking simulation: every policy links to its own quotation", not G.LINK_PROBLEMS, f"{len(G.LINK_PROBLEMS)} problems")

# ---- names
names = [G.norm_name(p["full"]) for p in PEOPLE]
check("Client full names unique", len(names) == len(set(names)))
worst = 0
for i in range(len(names)):
    for j in range(i + 1, len(names)):
        s = fuzz.token_sort_ratio(names[i], names[j])
        if s > worst: worst = s
check("No two clients look alike to the importers (name similarity below 70)", worst < 70, f"highest pair = {worst:.1f}")
two = defaultdict(list)
for pr in PROPS:
    two[pr["owner"]["id"]].append(pr["addr"]["address"].lower())
loc_worst = max([fuzz.token_sort_ratio(a[0], a[1]) for a in two.values() if len(a) == 2] or [0])
check("Owners with two properties: the two locations are clearly different (below 85)", loc_worst < 85, f"highest = {loc_worst:.1f}; owners with 2 properties = {sum(1 for a in two.values() if len(a)==2)}")

# ---- addresses
pool = {a["address"] for a in G.POOL}
all_addr = [p["addr"]["address"] for p in PEOPLE] + [pr["addr"]["address"] for pr in PROPS]
check("Every address comes from the verified pool", all(a in pool for a in all_addr))

# ---- amounts
amt_err = []
for e in paid:
    t = e["term"]
    if e["loa_amt"] is not None:
        total = e["line"] == "motor" and e["nature"] == "Theft/Carnapping"
        if not total and e["loa_amt"] > e["estimate"] + 0.01: amt_err.append(("LOA>est", e["accuterm"]))
        exp_net = e["loa_amt"] - (t["deductible"] if e["line"] == "motor" else G.fire_deductible(e["nature"], t["si"], e["loa_amt"]))
        if abs(max(0, exp_net) - e["net"]) > 0.02: amt_err.append(("net", e["accuterm"]))
        if e["net"] <= 0: amt_err.append(("net<=0", e["accuterm"], e["nature"]))
    if e["estimate"] < 0: amt_err.append(("neg", e["accuterm"]))
check("Claim amounts: LOA within estimate, Net = LOA - deductible, all positive", not amt_err, str(amt_err[:6]))
check("Policy amount equals its quotation amount", all(abs(t["amount"] - t["quote"]["amount"]) < 0.01 for t in TERMS))

# ---- status vs label
OK = {"Legitimate": {"Closed Claim", "Waiting for LOA", "Waiting for Billing", "Waiting for Claim Check", "Not Push Through"},
      "Suspected Fraud": {"Denied Claim", "Not Push Through", "Hold per Client"},
      "Confirmed Fraud": {"Denied Claim"},
      None: {"No Docs. Submitted", "Waiting for Evaluation", "With Lacking Docs"}}
mis = [(e["accuterm"], e["label"], e["final"]) for e in paid if e["final"] not in OK[e["label"]]]
check("Final Status always agrees with Claim Investigation Result", not mis, str(mis[:5]))

# ---- planted patterns show up (ended policies)
def grp_rate(line, keyf):
    g = defaultdict(list)
    for t in ended:
        if t["line"] == line: g[keyf(t)].append(t["counted_loss"])
    return {k: (round(rate(v) * 100, 1), len(v)) for k, v in sorted(g.items(), key=lambda x: str(x[0]))}
pat = {
 "Motor by flood category": grp_rate("motor", lambda t: t["person"]["addr"]["cat"]),
 "Motor by classification": grp_rate("motor", lambda t: "Commercial" if t["subject"]["obj"]["commercial"] else "Private"),
 "Motor by color (should be flat)": grp_rate("motor", lambda t: t["subject"]["obj"]["color"]),
 "Motor renews a policy with a loss": grp_rate("motor", lambda t: bool(t["prev"] and t["prev"]["counted_loss"])),
 "Fire by flood category": grp_rate("fire", lambda t: t["subject"]["obj"]["addr"]["cat"]),
 "Fire by construction class": grp_rate("fire", lambda t: t["subject"]["obj"]["risk_class"]),
 "Fire by protection": grp_rate("fire", lambda t: "protected" if t["subject"]["obj"]["protected"] else "not protected"),
}
fl = pat["Motor by flood category"]
check("Pattern: High-flood motor policies claim more than no-hazard ones", fl.get("High", (0,))[0] > fl.get("none", (0,))[0], str(fl))
cl = pat["Motor by classification"]
check("Pattern: Commercial vehicles claim more than Private", cl["Commercial"][0] > cl["Private"][0], str(cl))
ff = pat["Fire by flood category"]
check("Pattern: High-flood fire properties claim more than no-hazard ones", ff.get("High", (0,))[0] > ff.get("none", (0,))[0], str(ff))
fc = pat["Fire by construction class"]
check("Pattern: class b buildings claim more than class a", fc["b"][0] > fc["a"][0], str(fc))
fraud_pts = defaultdict(list)
for e in inv: fraud_pts[min(e["points"], 7)].append(e["label"] != "Legitimate")
fp = {k: (round(rate(v) * 100, 1), len(v)) for k, v in sorted(fraud_pts.items())}
check("Pattern: fraud share rises with red-flag points", fp[max(fp)][0] > fp[0][0], str(fp))

# ---- report
passed = sum(ok for _, ok, _ in checks)
lines = ["# Validation report", "", f"Generated with seed {G.SEED}, today = {TODAY}. **{passed} of {len(checks)} checks passed.**", "",
         "## File row counts", "", "| File | Rows |", "| --- | --- |"]
lines += [f"| {k} | {v} |" for k, v in cnt.items()]
lines += ["", "## Checks", "", "| Check | Result | Detail |", "| --- | --- | --- |"]
lines += [f"| {n} | {'PASS' if ok else 'FAIL'} | {d} |" for n, ok, d in checks]
lines += ["", "## Planted patterns (claim rate %, number of ended policies)", ""]
lines += [f"- **{k}:** {v}" for k, v in pat.items()]
lines += [f"- **Fraud share % by red-flag points (points: %, claims):** {fp}"]
lines += ["", "## Other figures", "",
          f"- Clients {len(PEOPLE)}, vehicles {len(VEH)}, properties {len(PROPS)}",
          f"- Motor claim rows {cnt['7_motor_claims']} (third party rows {G.TP_ROWS}, CNC rows {sum(1 for e in LIVE if e['cnc'])}), fire claim rows {cnt['8_fire_property_claims']}",
          f"- Final status mix (paid claims): {dict(Counter(e['final'] for e in paid))}",
          f"- Labels: {dict(Counter(e['label'] for e in paid))}"]
(OUT / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
sys.exit(0 if passed == len(checks) else 1)
