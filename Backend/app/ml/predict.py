"""Step 6 of both algorithms for the rows that still need a prediction, written to
ml_predictions (never into the business tables):

  - Motor / Fire quotations that are still open (no policy yet) or whose policy is in
    force (period_to >= today): claim probability + Low/Medium/High, from the active
    Logistic Regression model of that line. Quotations whose policy has ended get none.
  - Paid Claims not yet investigated (no Claim Investigation Result): P(Fraud) and
    Fraud/Legitimate at the model's stored fraud cutoff. CNC Issuance rows never get one.

refresh_predictions() replaces the whole table in one transaction, so a quotation that
converted/ended or a claim that got investigated simply drops out on the next refresh.
"""
import datetime as dt
import logging

import pandas as pd

from app import models
from app.ml import features
from app.ml.logistic_regression import LogisticRegression
from app.ml.naive_bayes import FRAUD, LEGITIMATE, NaiveBayes
from app.ml.training import active_model, risk_level

log = logging.getLogger(__name__)

LR_TARGETS = {"motor_lr": ("motor_quotation", features.motor_quotation_frame),
              "fire_lr": ("fire_quotation", features.fire_quotation_frame)}
CLAIM_TARGET_TYPES = {"Motor": "motor_claim", "Fire & Property": "fire_claim"}


def quotations_to_predict(frame, today):
    """Open quotations + quotations whose policy is still in force."""
    in_force = frame["policy_id"].notna() & ~(frame["period_to"] < pd.Timestamp(today))
    return frame[frame["policy_id"].isna() | in_force].reset_index(drop=True)


def _lr_predictions(db, name, today):
    row = active_model(db, name)
    if row is None:
        return []
    target_type, frame_fn = LR_TARGETS[name]
    frame = quotations_to_predict(frame_fn(db), today)
    if frame.empty:
        return []
    encoder = features.FeatureEncoder.from_dict(row.parameters["encoder"])
    model = LogisticRegression.from_dict(row.parameters["model"])
    probabilities = model.predict_proba(encoder.transform(frame))
    return [
        {"model_id": row.id, "target_type": target_type, "target_id": int(qid),
         "probability": round(float(p), 5), "label": risk_level(float(p), row.thresholds)}
        for qid, p in zip(frame["quotation_id"], probabilities)
    ]


def _claim_predictions(db):
    row = active_model(db, "fraud_nb")
    if row is None:
        return []
    frame = features.claim_clue_frame(db)
    frame = frame[frame["fraud_label"].isna()]
    model = NaiveBayes.from_dict(row.parameters["model"])
    cutoff = row.thresholds["fraud_cutoff"]
    out = []
    for claim in frame.to_dict("records"):
        try:
            p = model.fraud_probability({c: claim[c] for c in features.NB_CLUE_VALUES})
        except ValueError:  # a clue value outside the model's lists — skip, never guess
            log.warning("No fraud prediction for %s claim %s", claim["line"], claim["claim_id"])
            continue
        out.append({"model_id": row.id, "target_type": CLAIM_TARGET_TYPES[claim["line"]],
                    "target_id": int(claim["claim_id"]), "probability": round(float(p), 5),
                    "label": FRAUD if p > cutoff else LEGITIMATE})
    return out


def refresh_predictions(db, today=None, commit=True):
    """Recompute every prediction with the active models; returns counts per target type."""
    today = today or dt.date.today()
    rows = _lr_predictions(db, "motor_lr", today) + _lr_predictions(db, "fire_lr", today) + _claim_predictions(db)
    db.query(models.MLPrediction).delete(synchronize_session=False)
    if rows:
        db.bulk_insert_mappings(models.MLPrediction, rows)
    if commit:
        db.commit()
    else:
        db.flush()
    counts = {}
    for r in rows:
        counts[r["target_type"]] = counts.get(r["target_type"], 0) + 1
    return counts
