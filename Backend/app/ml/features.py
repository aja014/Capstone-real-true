"""Steps 1–2 of both algorithms (input collection + feature encoding).

Leakage rule: a Logistic Regression feature may only use information that existed on the
QUOTATION date. So every feature comes from the quotation itself, its vehicle (Motor) or
the case's survey (Fire) — never from the policy (construction, renewing_policy_no, issue
date, premium) — and "renews a policy with a counted loss" only counts claims REPORTED
BEFORE the quotation date. One training row = one ended policy, described by the
quotation it came from; a new quotation is described the same way at prediction time.

Naive Bayes clues are all known when a claim is filed; nothing decided later (final
status, LOA, net liability, the investigation result itself) is ever a clue.
"""
import json
import math

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from app import schemas

# A policy "has a counted loss" when it has >= 1 Paid Claim in one of these final statuses.
COUNTED_LOSS_FINAL_STATUSES = ("Closed Claim", "Waiting for LOA", "Waiting for Billing", "Waiting for Claim Check")
FRAUD_RESULTS = ("Suspected Fraud", "Confirmed Fraud")
PAID_CLAIM = "Paid Claim"
assert set(COUNTED_LOSS_FINAL_STATUSES) <= set(schemas.CLAIM_FINAL_STATUS_OPTIONS)

# The 8 fire-protection items of the Survey's Protection Facilities checklist
# (keys from schemas.PROTECTION_FACILITY_OPTIONS).
FIRE_PROTECTION_KEYS = (
    "fire_extinguisher", "smoke_detector", "heat_detector", "fire_alarm",
    "sprinklers", "internal_hydrants", "external_hydrants", "fire_breaks_doors",
)
assert set(FIRE_PROTECTION_KEYS) <= set(schemas.PROTECTION_FACILITY_OPTIONS.values())

MOTOR_SPEC = {
    "categorical": ["flood_category", "classification", "make", "body_type", "color"],
    "numeric": ["vehicle_age", "log_sum_insured", "deductible"],
    "binary": ["prior_counted_loss"],
}
FIRE_SPEC = {
    "categorical": ["flood_category", "occupancy", "overall_risk_assessment"],
    "numeric": ["log_total_sum_insured", "fire_protection_count"],
    "binary": ["construction_class_b", "has_loss_record", "prior_counted_loss"],
}

# Where each feature comes from — printed in the report (Step 1: input collection).
FEATURE_SOURCES = {
    "motor": {
        "flood_category": "motor_quotations.flood_risk_category (GIS lookup of the quotation address)",
        "classification": "motor_quotations.classification",
        "make": "vehicles.make (via motor_quotations.vehicle_id)",
        "body_type": "vehicles.body_type",
        "color": "motor_quotations.color (control: expected to carry ~no weight)",
        "vehicle_age": "year of motor_quotations.quotation_date − vehicles.model (model year)",
        "log_sum_insured": "log of motor_quotations.sum_insured",
        "deductible": "motor_quotations.deductible",
        "prior_counted_loss": "the vehicle's previous policy had a counted loss reported before this quotation date",
    },
    "fire": {
        "flood_category": "fire_property_surveys.flood_risk_category (worst of river flood / storm surge)",
        "occupancy": "fire_property_quotations.occupancy",
        "overall_risk_assessment": "fire_property_surveys.overall_risk_assessment (surveyor)",
        "log_total_sum_insured": "log of fire_property_quotations.total_sum_insured",
        "fire_protection_count": "number of the 8 fire-protection items ticked in the Survey's protection_facilities",
        "construction_class_b": "fire_property_surveys.risk_class = 'b' (concrete & wood/light materials)",
        "has_loss_record": "fire_property_surveys.loss_record starts with 'With loss history'",
        "prior_counted_loss": "the property's previous policy had a counted loss reported before this quotation date",
    },
}


def _read(db, sql, **params):
    stmt = text(sql)
    for name, value in params.items():
        if isinstance(value, (tuple, list)):
            stmt = stmt.bindparams(bindparam(name, expanding=True))
    return pd.read_sql(stmt, db.connection(), params=params)


def _flood_category(latitude, category):
    # NULL category with coordinates = geocoded but outside every mapped zone ("None").
    # No coordinates at all = the address was never located ("Unknown").
    if latitude is None or (isinstance(latitude, float) and math.isnan(latitude)):
        return "Unknown"
    return category if isinstance(category, str) and category else "None"


def _counted_claims(db, claims_table, policy_fk):
    df = _read(
        db,
        f"SELECT {policy_fk} AS policy_id, date_reported FROM {claims_table} "
        "WHERE claim_type = :paid AND final_status IN :statuses",
        paid=PAID_CLAIM, statuses=COUNTED_LOSS_FINAL_STATUSES,
    )
    df["date_reported"] = pd.to_datetime(df["date_reported"])
    return df


def _add_label_and_prior_loss(frame, counted, group_col):
    """counted_loss: this row's own policy has a counted loss (the training label).
    prior_counted_loss: the most recent EARLIER policy for the same vehicle/property had a
    counted loss whose claim was reported before this row's quotation date."""
    frame = frame.copy()
    frame["quotation_date"] = pd.to_datetime(frame["quotation_date"])
    frame["period_to"] = pd.to_datetime(frame["period_to"])
    frame["counted_loss"] = frame["policy_id"].isin(counted["policy_id"]).astype(int)
    first_report = counted.groupby("policy_id")["date_reported"].min()

    prior = pd.Series(0, index=frame.index)
    for _, group in frame.sort_values(["quotation_date", "quotation_id"]).groupby(group_col):
        issued = group[group["policy_id"].notna()]
        for idx, row in group.iterrows():
            earlier = issued[issued["quotation_date"] < row["quotation_date"]]
            if earlier.empty:
                continue
            prev_policy = earlier.iloc[-1]["policy_id"]
            reported = first_report.get(prev_policy)
            if reported is not None and reported < row["quotation_date"]:
                prior.at[idx] = 1
    frame["prior_counted_loss"] = prior
    return frame


def motor_quotation_frame(db):
    """Every Motor quotation with its encoded-ready inputs, its policy (if issued) and label."""
    df = _read(db, """
        SELECT q.id AS quotation_id, q.quotation_date, q.vehicle_id, q.latitude,
               q.flood_risk_category, q.classification, q.color, q.sum_insured, q.deductible,
               v.make, v.body_type, v.model AS model_year,
               p.id AS policy_id, p.period_to
        FROM motor_quotations q
        JOIN vehicles v ON v.id = q.vehicle_id
        LEFT JOIN motor_policies p ON p.quotation_id = q.id
        ORDER BY q.id
    """)
    df["flood_category"] = [_flood_category(la, c) for la, c in zip(df["latitude"], df["flood_risk_category"])]
    model_year = pd.to_numeric(df["model_year"], errors="coerce")
    df["vehicle_age"] = (pd.to_datetime(df["quotation_date"]).dt.year - model_year).clip(lower=0)
    df["log_sum_insured"] = np.log(pd.to_numeric(df["sum_insured"], errors="coerce").where(lambda s: s > 0))
    df["deductible"] = pd.to_numeric(df["deductible"], errors="coerce")
    counted = _counted_claims(db, "motor_claims", "motor_policy_id")
    return _add_label_and_prior_loss(df, counted, "vehicle_id")


def _fire_protection_count(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan
    data = json.loads(value) if isinstance(value, str) else value
    return sum(1 for k in FIRE_PROTECTION_KEYS if data.get(k) is True)


def fire_quotation_frame(db):
    """Every Fire quotation with its case's (latest) Survey, its policy (if issued) and label."""
    df = _read(db, """
        SELECT q.id AS quotation_id, q.quotation_date, q.insurance_case_id, q.occupancy,
               q.total_sum_insured, s.latitude, s.flood_risk_category, s.risk_class,
               s.protection_facilities, s.loss_record, s.overall_risk_assessment,
               p.id AS policy_id, p.period_to
        FROM fire_property_quotations q
        LEFT JOIN fire_property_surveys s ON s.id = (
            SELECT MAX(s2.id) FROM fire_property_surveys s2 WHERE s2.insurance_case_id = q.insurance_case_id)
        LEFT JOIN fire_property_policies p ON p.quotation_id = q.id
        ORDER BY q.id
    """)
    df["flood_category"] = [_flood_category(la, c) for la, c in zip(df["latitude"], df["flood_risk_category"])]
    df["log_total_sum_insured"] = np.log(pd.to_numeric(df["total_sum_insured"], errors="coerce").where(lambda s: s > 0))
    df["fire_protection_count"] = df["protection_facilities"].map(_fire_protection_count)
    df["construction_class_b"] = (df["risk_class"] == "b").astype(int)
    df["has_loss_record"] = df["loss_record"].fillna("").str.startswith("With loss history").astype(int)
    return _add_label_and_prior_loss(df, _counted_claims(db, "fire_property_claims", "fire_property_policy_id"),
                                     "insurance_case_id")


def ended_policy_rows(frame, today):
    """Training rows: issued policies whose coverage has ended (period_to < today)."""
    return frame[frame["policy_id"].notna() & (frame["period_to"] < pd.Timestamp(today))].reset_index(drop=True)


class FeatureEncoder:
    """Step 2 for Logistic Regression. Categories -> one-hot (one 0/1 column per category
    seen in the training rows); numbers -> scaled to mean 0 / SD 1 using the training rows
    only; yes/no inputs stay 0/1. A missing number takes the training mean (0 after
    scaling); a category never seen in training gets all-zero columns."""

    def __init__(self, spec):
        self.spec = spec
        self.categories = {}
        self.means = {}
        self.sds = {}

    def fit(self, frame):
        for c in self.spec["categorical"]:
            self.categories[c] = sorted(frame[c].fillna("Unknown").astype(str).unique().tolist())
        for c in self.spec["numeric"]:
            x = frame[c].astype(float)
            self.means[c] = float(x.mean())
            sd = float(x.std(ddof=0))
            self.sds[c] = sd if sd > 0 else 1.0
        return self

    @property
    def feature_names(self):
        names = [f"{c} = {v}" for c in self.spec["categorical"] for v in self.categories[c]]
        return names + list(self.spec["numeric"]) + list(self.spec["binary"])

    def transform(self, frame):
        cols = []
        for c in self.spec["categorical"]:
            values = frame[c].fillna("Unknown").astype(str)
            cols += [(values == v).astype(float).to_numpy() for v in self.categories[c]]
        for c in self.spec["numeric"]:
            x = frame[c].astype(float).fillna(self.means[c])
            cols.append(((x - self.means[c]) / self.sds[c]).to_numpy())
        for c in self.spec["binary"]:
            cols.append(frame[c].fillna(0).astype(float).to_numpy())
        return np.column_stack(cols)

    def to_dict(self):
        return {"spec": self.spec, "categories": self.categories, "means": self.means, "sds": self.sds}

    @classmethod
    def from_dict(cls, d):
        e = cls(d["spec"])
        e.categories, e.means, e.sds = d["categories"], d["means"], d["sds"]
        return e


# ---------------------------------------------------------------- Naive Bayes clues

def _dedupe(seq):
    return list(dict.fromkeys(seq))


NB_CLUE_VALUES = {
    "days_coverage_start_to_loss": ["0–15 days", "16–30 days", "Over 30 days", "Unknown"],
    "days_loss_to_report": ["0–7 days", "8–30 days", "Over 30 days", "Unknown"],
    "estimate_to_sum_insured": ["Below 0.50", "0.50–0.69", "0.70 or more", "Unknown"],
    "earlier_claims_12_months": ["0", "1", "2 or more"],
    "days_loss_to_expiry": ["30 days or less", "Over 30 days", "Unknown"],
    "nature_of_loss": _dedupe(list(schemas.MOTOR_NATURE_OF_LOSS_OPTIONS) + list(schemas.FIRE_NATURE_OF_LOSS_OPTIONS) + ["Unknown"]),
    "coverage_type": list(schemas.MOTOR_COVERAGE_TYPE_OPTIONS) + ["N/A (Fire)", "Unknown"],
    "policy_type": ["New", "Renewal"],
    "days_report_to_documents": ["30 days or less", "Over 30 days", "Not yet submitted"],
    "line": ["Motor", "Fire & Property"],
}

NB_CLUE_SOURCES = {
    "days_coverage_start_to_loss": "date_of_loss − policy.period_from",
    "days_loss_to_report": "date_reported − date_of_loss",
    "estimate_to_sum_insured": "repair_estimate_amount ÷ policy.sum_insured",
    "earlier_claims_12_months": "Paid Claims of the same policyholder (both lines) reported in the 365 days before this claim's report date",
    "days_loss_to_expiry": "policy.period_to − date_of_loss",
    "nature_of_loss": "nature_of_loss",
    "coverage_type": "motor_claims.coverage_type ('N/A (Fire)' for Fire claims)",
    "policy_type": "policy.renewing_policy_no blank (New) or filled (Renewal)",
    "days_report_to_documents": "date_docs_submitted − date_reported",
    "line": "Motor or Fire & Property claims table",
}


def _days(a, b):
    return (pd.to_datetime(a) - pd.to_datetime(b)).dt.days


def _bin(days, edges, labels, missing="Unknown"):
    out = []
    for d in days:
        if pd.isna(d):
            out.append(missing)
            continue
        for edge, label in zip(edges, labels):
            if d <= edge:
                out.append(label)
                break
        else:
            out.append(labels[-1])
    return out


def claim_clue_frame(db):
    """Every Paid Claim (CNC Issuance rows are never classified) with its 10 clues and its
    human label: 1 = Fraud (Suspected or Confirmed), 0 = Legitimate, None = not yet investigated."""
    common = """c.id AS claim_id, c.date_of_loss, c.date_reported, c.date_docs_submitted,
                c.nature_of_loss, c.repair_estimate_amount, c.claim_investigation_result,
                p.period_from, p.period_to, p.sum_insured, p.renewing_policy_no, ic.policyholder_id"""
    motor = _read(db, f"""
        SELECT 'Motor' AS line, c.coverage_type, {common}
        FROM motor_claims c
        JOIN motor_policies p ON p.id = c.motor_policy_id
        JOIN motor_quotations q ON q.id = p.quotation_id
        JOIN insurance_cases ic ON ic.id = q.insurance_case_id
        WHERE c.claim_type = :paid ORDER BY c.id""", paid=PAID_CLAIM)
    fire = _read(db, f"""
        SELECT 'Fire & Property' AS line, 'N/A (Fire)' AS coverage_type, {common}
        FROM fire_property_claims c
        JOIN fire_property_policies p ON p.id = c.fire_property_policy_id
        JOIN fire_property_quotations q ON q.id = p.quotation_id
        JOIN insurance_cases ic ON ic.id = q.insurance_case_id
        WHERE c.claim_type = :paid ORDER BY c.id""", paid=PAID_CLAIM)
    df = pd.concat([motor, fire], ignore_index=True)
    df["date_reported"] = pd.to_datetime(df["date_reported"])

    df["days_coverage_start_to_loss"] = _bin(_days(df["date_of_loss"], df["period_from"]), [15, 30], ["0–15 days", "16–30 days", "Over 30 days"])
    df["days_loss_to_report"] = _bin(_days(df["date_reported"], df["date_of_loss"]), [7, 30], ["0–7 days", "8–30 days", "Over 30 days"])
    ratio = pd.to_numeric(df["repair_estimate_amount"], errors="coerce") / pd.to_numeric(df["sum_insured"], errors="coerce")
    df["estimate_to_sum_insured"] = [
        "Unknown" if pd.isna(r) else "Below 0.50" if r < 0.5 else "0.50–0.69" if r < 0.7 else "0.70 or more"
        for r in ratio
    ]
    df["days_loss_to_expiry"] = _bin(_days(df["period_to"], df["date_of_loss"]), [30], ["30 days or less", "Over 30 days"])
    df["days_report_to_documents"] = _bin(_days(df["date_docs_submitted"], df["date_reported"]), [30],
                                          ["30 days or less", "Over 30 days"], missing="Not yet submitted")
    df["nature_of_loss"] = df["nature_of_loss"].fillna("Unknown")
    df["coverage_type"] = df["coverage_type"].fillna("Unknown")
    df["policy_type"] = np.where(df["renewing_policy_no"].fillna("").str.strip() != "", "Renewal", "New")

    # Earlier claims by the same person: only claims REPORTED BEFORE this one, within 365 days.
    earlier = []
    by_person = df.groupby("policyholder_id")["date_reported"].apply(list).to_dict()
    for person, reported in zip(df["policyholder_id"], df["date_reported"]):
        n = sum(1 for d in by_person.get(person, []) if d < reported and (reported - d).days <= 365)
        earlier.append("0" if n == 0 else "1" if n == 1 else "2 or more")
    df["earlier_claims_12_months"] = earlier

    result = df["claim_investigation_result"]
    df["fraud_label"] = [None if pd.isna(r) else int(r in FRAUD_RESULTS) for r in result]
    return df
