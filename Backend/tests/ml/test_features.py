"""Data and leakage rules, checked against the dev database (read-only)."""
import datetime as dt

import pandas as pd
import pytest
from sqlalchemy import bindparam, text

from app.ml import features

TODAY = dt.date(2026, 9, 27)
# Counts in the loaded v5d dataset as of TODAY — update if the data changes.
EXPECTED = {"motor": (898, 284), "fire": (1832, 132)}
# Nothing may be read from a policy table, or from these policy-stage columns.
# (Fire's construction class is read from the SURVEY's risk_class, not policies.construction.)
POLICY_STAGE_SOURCES = ("_policies.", "renewing_policy_no", "issue_date", "total_amount_due",
                        "period_from", "premium")


def _frame(db, line):
    return features.motor_quotation_frame(db) if line == "motor" else features.fire_quotation_frame(db)


@pytest.mark.parametrize("line", ["motor", "fire"])
def test_training_rows_and_labels(db, line):
    rows = features.ended_policy_rows(_frame(db, line), TODAY)
    assert (len(rows), int(rows["counted_loss"].sum())) == EXPECTED[line]
    assert (rows["period_to"] < pd.Timestamp(TODAY)).all()
    assert rows["policy_id"].notna().all()


@pytest.mark.parametrize("line,table,fk,group", [
    ("motor", "motor", "motor_policy_id", "vehicle_id"),
    ("fire", "fire_property", "fire_property_policy_id", "insurance_case_id"),
])
def test_prior_counted_loss_matches_independent_sql(db, line, table, fk, group):
    """Most recent earlier policy on the same vehicle / case had a Paid Claim REPORTED BEFORE the
    quotation date (any outcome)."""
    sql = text(f"""
        SELECT q.id AS quotation_id, COALESCE((
            SELECT EXISTS (SELECT 1 FROM {table}_claims c
                           WHERE c.{fk} = p2.id AND c.claim_type = 'Paid Claim'
                             AND c.date_reported < q.quotation_date)
            FROM {table}_policies p2 JOIN {table}_quotations q2 ON q2.id = p2.quotation_id
            WHERE q2.{group} = q.{group} AND q2.quotation_date < q.quotation_date
            ORDER BY q2.quotation_date DESC, q2.id DESC LIMIT 1), 0) AS expected
        FROM {table}_quotations q""")
    expected = pd.read_sql(sql, db.connection())
    frame = _frame(db, line).merge(expected, on="quotation_id")
    assert len(frame) == len(expected)
    assert (frame["prior_counted_loss"] == frame["expected"]).all()


def test_prior_loss_reported_after_the_quotation_is_not_used(db):
    """Renewal quotations whose previous policy DID have a Paid Claim, but only reported on/after
    the quotation date: the feature must be 0 (that claim wasn't known when quoting)."""
    sql = text("""
        SELECT q.id AS quotation_id FROM motor_quotations q
        JOIN motor_quotations q2 ON q2.vehicle_id = q.vehicle_id AND q2.quotation_date < q.quotation_date
        JOIN motor_policies p2 ON p2.quotation_id = q2.id
        WHERE q2.id = (SELECT q3.id FROM motor_quotations q3 JOIN motor_policies p3 ON p3.quotation_id = q3.id
                       WHERE q3.vehicle_id = q.vehicle_id AND q3.quotation_date < q.quotation_date
                       ORDER BY q3.quotation_date DESC, q3.id DESC LIMIT 1)
          AND EXISTS (SELECT 1 FROM motor_claims c WHERE c.motor_policy_id = p2.id AND c.claim_type = 'Paid Claim'
                      AND c.date_reported >= q.quotation_date)
          AND NOT EXISTS (SELECT 1 FROM motor_claims c WHERE c.motor_policy_id = p2.id AND c.claim_type = 'Paid Claim'
                          AND c.date_reported < q.quotation_date)
    """)
    late = pd.read_sql(sql, db.connection())["quotation_id"]
    assert len(late) > 0, "the dataset should contain at least one such case"
    frame = features.motor_quotation_frame(db).set_index("quotation_id")
    assert (frame.loc[late, "prior_counted_loss"] == 0).all()


@pytest.mark.parametrize("line,table,fk,group", [
    ("motor", "motor", "motor_policy_id", "vehicle_id"),
    ("fire", "fire_property", "fire_property_policy_id", "insurance_case_id"),
])
def test_prior_claim_counts_whatever_its_outcome(db, line, table, fk, group):
    """Fix round A2 (P6.11): an earlier Paid Claim that never became a counted loss (Denied,
    Not Push Through, still open...) still sets the feature — its outcome is not used, since
    it may only have been decided after the quotation."""
    sql = text(f"""
        SELECT q.id AS quotation_id FROM {table}_quotations q
        JOIN {table}_quotations q2 ON q2.{group} = q.{group} AND q2.quotation_date < q.quotation_date
        JOIN {table}_policies p2 ON p2.quotation_id = q2.id
        WHERE q2.id = (SELECT q3.id FROM {table}_quotations q3 JOIN {table}_policies p3 ON p3.quotation_id = q3.id
                       WHERE q3.{group} = q.{group} AND q3.quotation_date < q.quotation_date
                       ORDER BY q3.quotation_date DESC, q3.id DESC LIMIT 1)
          AND EXISTS (SELECT 1 FROM {table}_claims c WHERE c.{fk} = p2.id AND c.claim_type = 'Paid Claim'
                      AND c.date_reported < q.quotation_date)
          AND NOT EXISTS (SELECT 1 FROM {table}_claims c WHERE c.{fk} = p2.id AND c.claim_type = 'Paid Claim'
                          AND c.final_status IN :s AND c.date_reported < q.quotation_date)
    """).bindparams(bindparam("s", expanding=True))
    outcome_open = pd.read_sql(sql, db.connection(), params={"s": features.COUNTED_LOSS_FINAL_STATUSES})["quotation_id"]
    assert len(outcome_open) > 0, "the dataset should contain at least one such case"
    frame = _frame(db, line).set_index("quotation_id")
    assert (frame.loc[outcome_open, "prior_counted_loss"] == 1).all()


@pytest.mark.parametrize("line", ["motor", "fire"])
def test_no_policy_stage_inputs(line):
    spec = features.MOTOR_SPEC if line == "motor" else features.FIRE_SPEC
    names = spec["categorical"] + spec["numeric"] + spec["binary"]
    assert set(names) == set(features.FEATURE_SOURCES[line])
    for name in names:
        source = features.FEATURE_SOURCES[line][name]
        assert not any(w in source for w in POLICY_STAGE_SOURCES), (name, source)
    assert "color" in names if line == "motor" else "prior_counted_loss" in names


def test_fire_feature_values(db):
    frame = features.fire_quotation_frame(db)
    assert frame["fire_protection_count"].between(0, 8).all()
    assert set(frame["flood_category"]) <= {"High", "Medium", "Low", "None", "Unknown"}
    assert frame["has_loss_record"].isin([0, 1]).all() and frame["construction_class_b"].isin([0, 1]).all()


def test_motor_feature_values(db):
    frame = features.motor_quotation_frame(db)
    assert (frame["vehicle_age"] >= 0).all()
    assert frame["log_sum_insured"].notna().all()


def test_naive_bayes_rows_and_clues(db):
    frame = features.claim_clue_frame(db)
    trained = frame[frame["fraud_label"].notna()]
    assert (len(trained), int(trained["fraud_label"].sum())) == (827, 56)
    assert frame["fraud_label"].isna().sum() > 0             # not yet investigated -> predicted in Phase 2
    for clue, values in features.NB_CLUE_VALUES.items():
        assert set(frame[clue]) <= set(values), clue
    forbidden = ("final_status", "net_liability", "loa_", "claim_investigation_result", "billing", "status")
    for clue, source in features.NB_CLUE_SOURCES.items():
        assert not any(w in clue or w in source for w in forbidden), clue


def test_earlier_claims_only_counts_claims_reported_before(db):
    frame = features.claim_clue_frame(db)
    raw = frame[["policyholder_id", "date_reported"]]
    for i in range(0, len(frame), 7):  # every 7th claim, recomputed from scratch
        person, reported = raw.iloc[i]
        same = raw[(raw["policyholder_id"] == person) & (raw["date_reported"] < reported)
                   & ((reported - raw["date_reported"]).dt.days <= 365)]
        n = len(same)
        assert frame.iloc[i]["earlier_claims_12_months"] == ("0" if n == 0 else "1" if n == 1 else "2 or more")
