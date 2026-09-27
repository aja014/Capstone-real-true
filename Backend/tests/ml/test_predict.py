"""Writing predictions (app/ml/predict.py) against the dev database — rolled back after each test."""
import datetime as dt

import pandas as pd
from sqlalchemy import func

from app import models
from app.ml import features, predict, training
from app.ml.logistic_regression import LogisticRegression

TODAY = dt.date(2026, 9, 27)


def _trained(db, tmp_path):
    saved = training.train_all(db, TODAY, tmp_path)
    assert all(saved.values())
    return saved


def test_targets_and_counts(db, tmp_path):
    _trained(db, tmp_path)
    counts = predict.refresh_predictions(db, TODAY)
    motor = features.motor_quotation_frame(db)
    fire = features.fire_quotation_frame(db)

    def expected(frame):
        open_q = frame["policy_id"].isna().sum()
        in_force = (frame["policy_id"].notna() & (frame["period_to"] >= pd.Timestamp(TODAY))).sum()
        return int(open_q + in_force)

    assert counts == {"motor_quotation": expected(motor), "fire_quotation": expected(fire),
                      "motor_claim": 17, "fire_claim": 6}
    assert counts["motor_quotation"] == 311 + 306 and counts["fire_quotation"] == 156 + 255
    assert db.query(func.count(models.MLPrediction.id)).scalar() == sum(counts.values())


def test_no_prediction_for_ended_policies_or_investigated_or_cnc_claims(db, tmp_path):
    _trained(db, tmp_path)
    predict.refresh_predictions(db, TODAY)
    predicted = {(p.target_type, p.target_id) for p in db.query(models.MLPrediction)}
    motor = features.motor_quotation_frame(db)
    ended = motor[motor["policy_id"].notna() & (motor["period_to"] < pd.Timestamp(TODAY))]["quotation_id"]
    assert not any(("motor_quotation", int(q)) in predicted for q in ended)
    claims = features.claim_clue_frame(db)  # Paid Claims only, so CNC rows are never candidates
    investigated = claims[claims["fraud_label"].notna()]
    kinds = {"Motor": "motor_claim", "Fire & Property": "fire_claim"}
    assert not any((kinds[l], int(c)) in predicted for l, c in zip(investigated["line"], investigated["claim_id"]))
    cnc_ids = {r[0] for r in db.query(models.MotorClaim.id).filter(models.MotorClaim.claim_type == "CNC Issuance")}
    assert len(cnc_ids) == 33 and not any(("motor_claim", c) in predicted for c in cnc_ids)


def test_values_match_the_stored_model(db, tmp_path):
    saved = _trained(db, tmp_path)
    predict.refresh_predictions(db, TODAY)
    motor_row = saved["motor_lr"]
    frame = predict.quotations_to_predict(features.motor_quotation_frame(db), TODAY).head(25)
    encoder = features.FeatureEncoder.from_dict(motor_row.parameters["encoder"])
    p = LogisticRegression.from_dict(motor_row.parameters["model"]).predict_proba(encoder.transform(frame))
    stored = {r.target_id: r for r in db.query(models.MLPrediction).filter_by(target_type="motor_quotation")}
    for qid, prob in zip(frame["quotation_id"], p):
        row = stored[int(qid)]
        assert abs(float(row.probability) - prob) < 1e-5
        assert row.label == training.risk_level(prob, motor_row.thresholds)
        assert row.model_id == motor_row.id
    cutoff = saved["fraud_nb"].thresholds["fraud_cutoff"]
    for r in db.query(models.MLPrediction).filter(models.MLPrediction.target_type.in_(["motor_claim", "fire_claim"])):
        assert r.label == ("Fraud" if float(r.probability) > cutoff else "Legitimate")


def test_refresh_replaces_rather_than_duplicates(db, tmp_path):
    _trained(db, tmp_path)
    first = predict.refresh_predictions(db, TODAY)
    second = predict.refresh_predictions(db, TODAY)
    assert first == second
    assert db.query(func.count(models.MLPrediction.id)).scalar() == sum(first.values())


def test_missing_model_means_no_predictions_for_it(db, tmp_path):
    training.train_model(db, "fire_lr", TODAY, tmp_path)
    db.query(models.MLModel).filter(models.MLModel.model_name != "fire_lr").update({"status": "superseded"})
    counts = predict.refresh_predictions(db, TODAY)
    assert set(counts) == {"fire_quotation"}
