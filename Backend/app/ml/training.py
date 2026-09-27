"""Trains, evaluates and saves the three models, and writes each one's report file.

    python -m app.ml.training          (run from Backend/) trains all three now

Every training run: fixed-seed stratified 75/25 split -> fit on the 75% -> evaluate on
the held-back 25% (never seen during training) -> 5-fold stratified cross-validation on
all rows (mean ± SD, because the Fire and fraud test sets are small) -> save the model
trained on the 75% (so the stored accuracy belongs to the stored model) -> write
model_reports/<date>_<model>_v<N>.md. A failed run is recorded as status 'failed' and
never touches the active model; train_model() never raises.

retrain_if_changed() (used by the automatic refresh, app/ml/jobs.py) first fingerprints
exactly what a run would learn from (the training rows, their inputs and labels, plus the
settings below) and skips training when that fingerprint equals the latest attempt's:
an identical model would come out, or the identical failure would repeat.
"""
import datetime as dt
import hashlib
import json
import logging
import math
import traceback
from pathlib import Path

import numpy as np

from app import models
from app.ml import features
from app.ml.logistic_regression import LogisticRegression
from app.ml.metrics import mean_sd, roc_auc, scores, stratified_kfold, stratified_split
from app.ml.naive_bayes import DEFAULT_FRAUD_CUTOFF, FRAUD, LEGITIMATE, NaiveBayes
from app.ml.report import write_report

log = logging.getLogger(__name__)

MODEL_NAMES = ("motor_lr", "fire_lr", "fraud_nb")
SEED = 42
TEST_FRACTION = 0.25
CV_FOLDS = 5
LR_SETTINGS = {"learning_rate": 0.5, "max_epochs": 50000, "tolerance": 1e-12, "l2": 0.01}
NB_ALPHA = 1.0
# Stored with each fraud model (thresholds.fraud_cutoff). 0.5 = the documents' rule,
# P(Fraud) > P(Legitimate). Change it here (next training stores the new value) — the
# report's cutoff table shows what 0.5 / 0.4 / 0.3 / 0.2 would do first.
# 0.3 chosen from the v1 cutoff table (5-fold CV): recall 38.9% vs 24.2% at 0.5, with
# precision unchanged (44.6% vs 43.3%).
NB_FRAUD_CUTOFF = 0.3
NB_CUTOFFS_COMPARED = (0.5, 0.4, 0.3, 0.2)
MIN_CLUE_SUPPORT = 5
MIN_ROWS = 30
MIN_PER_CLASS = CV_FOLDS  # every CV fold needs at least one row of each class
REPORT_DIR = Path(__file__).resolve().parents[3] / "model_reports"
# Bump when a code change should force every model to retrain on the next refresh.
MODEL_CODE_VERSION = 1


class NotEnoughData(Exception):
    pass


def _check_counts(y, what):
    positives = int(np.sum(y))
    if len(y) < MIN_ROWS or positives < MIN_PER_CLASS or len(y) - positives < MIN_PER_CLASS:
        raise NotEnoughData(f"{what}: {len(y)} rows, {positives} positive — need at least "
                            f"{MIN_ROWS} rows and {MIN_PER_CLASS} of each class")


# ------------------------------------------------------------ Logistic Regression

def risk_level(probability, thresholds):
    """Low below the training base rate, High from twice the base rate, Medium between."""
    if probability < thresholds["medium_from"]:
        return "Low"
    return "High" if probability >= thresholds["high_from"] else "Medium"


def _fit_lr(frame, spec, train_idx):
    train = frame.iloc[train_idx]
    encoder = features.FeatureEncoder(spec).fit(train)
    model = LogisticRegression(**LR_SETTINGS).fit(encoder.transform(train), train["counted_loss"].to_numpy())
    base = float(train["counted_loss"].mean())
    thresholds = {"medium_from": round(base, 2), "high_from": round(2 * base, 2)}
    return encoder, model, thresholds


def _lr_eval(frame, encoder, model, thresholds, idx):
    rows = frame.iloc[idx]
    y = rows["counted_loss"].to_numpy()
    p = model.predict_proba(encoder.transform(rows))
    # "Predicted loss" = Medium or High (probability >= the training base rate).
    result = scores(y, p >= thresholds["medium_from"])
    result["roc_auc"] = roc_auc(y, p)
    return y, p, result


def _lr_dataset(db, line, today):
    frame_fn = features.motor_quotation_frame if line == "motor" else features.fire_quotation_frame
    return features.ended_policy_rows(frame_fn(db), today)


def train_logistic(db, line, today, frame=None):
    spec = features.MOTOR_SPEC if line == "motor" else features.FIRE_SPEC
    if frame is None:
        frame = _lr_dataset(db, line, today)
    y = frame["counted_loss"].to_numpy()
    _check_counts(y, f"{line} ended policies")

    train_idx, test_idx = stratified_split(y, TEST_FRACTION, SEED)
    encoder, model, thresholds = _fit_lr(frame, spec, train_idx)
    y_test, p_test, test = _lr_eval(frame, encoder, model, thresholds, test_idx)

    folds = []
    for tr, te in stratified_kfold(y, CV_FOLDS, SEED):
        e, m, t = _fit_lr(frame, spec, tr)
        folds.append(_lr_eval(frame, e, m, t, te)[2])

    levels = np.array([risk_level(p, thresholds) for p in p_test])
    by_level = {
        lvl: {"rows": int((levels == lvl).sum()),
              "losses": int(y_test[levels == lvl].sum()),
              "loss_rate": float(y_test[levels == lvl].mean()) if (levels == lvl).any() else None}
        for lvl in ("Low", "Medium", "High")
    }
    names = encoder.feature_names
    weights = sorted(zip(names, model.weights), key=lambda t: -abs(t[1]))
    at_half = scores(y_test, p_test >= 0.5)
    metrics = {
        "decision_rule": f"predicted loss = Medium or High (probability >= {thresholds['medium_from']:.2f})",
        "test": test,
        "test_at_0_5": at_half,
        "baseline_accuracy": float(1 - y_test.mean()),  # always predicting "no loss"
        "cross_validation": {k: mean_sd(folds, k) for k in ("accuracy", "precision", "recall", "roc_auc")},
        "loss_rate_by_level": by_level,
        "top_features": [{"feature": n, "weight": float(w), "odds_ratio": math.exp(w)} for n, w in weights[:10]],
    }
    if line == "motor":
        metrics["control_check"] = [{"feature": n, "weight": float(w)} for n, w in zip(names, model.weights)
                                    if n.startswith("color = ")]
    return {
        "parameters": {"model": model.to_dict(), "encoder": encoder.to_dict(), "feature_names": names},
        "metrics": metrics,
        "thresholds": thresholds,
        "train_rows": len(train_idx), "test_rows": len(test_idx), "positive_rows": int(y.sum()),
        "total_rows": len(y),
        "sources": features.FEATURE_SOURCES[line],
    }


# ------------------------------------------------------------ Naive Bayes

def _nb_rows(frame):
    return frame[list(features.NB_CLUE_VALUES)].to_dict("records")


def _fit_nb(rows, y, idx):
    labels = [FRAUD if y[i] else LEGITIMATE for i in idx]
    return NaiveBayes(NB_ALPHA).fit([rows[i] for i in idx], labels, features.NB_CLUE_VALUES)


def _nb_eval(model, rows, y, idx, cutoff):
    p = np.array([model.fraud_probability(rows[i]) for i in idx])
    result = scores(y[idx], p > cutoff)
    result["roc_auc"] = roc_auc(y[idx], p)
    return result


def _nb_dataset(db):
    frame = features.claim_clue_frame(db)
    return frame[frame["fraud_label"].notna()].reset_index(drop=True)


def train_naive_bayes(db, today, frame=None):
    if frame is None:
        frame = _nb_dataset(db)
    y = frame["fraud_label"].astype(int).to_numpy()
    _check_counts(y, "investigated Paid Claims")
    rows = _nb_rows(frame)

    train_idx, test_idx = stratified_split(y, TEST_FRACTION, SEED)
    model = _fit_nb(rows, y, train_idx)
    test = _nb_eval(model, rows, y, test_idx, NB_FRAUD_CUTOFF)

    fold_models = [(_fit_nb(rows, y, tr), te) for tr, te in stratified_kfold(y, CV_FOLDS, SEED)]
    folds = [_nb_eval(m, rows, y, te, NB_FRAUD_CUTOFF) for m, te in fold_models]
    # Same 5 folds, other cutoffs — to choose the cutoff later without retraining blind.
    cutoff_table = []
    for cutoff in NB_CUTOFFS_COMPARED:
        at = [_nb_eval(m, rows, y, te, cutoff) for m, te in fold_models]
        cutoff_table.append({"cutoff": cutoff, **{k: mean_sd(at, k) for k in ("precision", "recall", "accuracy")},
                             "flagged_share": float(np.mean([(s["confusion"]["tp"] + s["confusion"]["fp"]) / s["rows"]
                                                             for s in at]))})

    # Strongest clues: how many times more likely a clue value is among Fraud than Legitimate
    # (only values seen at least MIN_CLUE_SUPPORT times in training, so rare values don't dominate).
    ratios = []
    for clue, values in model.likelihoods.items():
        for value, p in values.items():
            n = model.counts[clue][value]
            if n[FRAUD] + n[LEGITIMATE] < MIN_CLUE_SUPPORT:
                continue
            ratios.append({"clue": clue, "value": value, "fraud_count": n[FRAUD], "legitimate_count": n[LEGITIMATE],
                           "p_fraud": p[FRAUD], "p_legitimate": p[LEGITIMATE], "ratio": p[FRAUD] / p[LEGITIMATE]})
    ratios.sort(key=lambda r: -r["ratio"])
    rule = ("Fraud when the combined score for Fraud is higher than for Legitimate (P(Fraud) > 0.5)"
            if NB_FRAUD_CUTOFF == DEFAULT_FRAUD_CUTOFF else f"Fraud when P(Fraud) > {NB_FRAUD_CUTOFF}")
    metrics = {
        "decision_rule": rule,
        "test": test,
        "baseline_accuracy": float(1 - y[test_idx].mean()),  # always predicting "Legitimate"
        "cross_validation": {k: mean_sd(folds, k) for k in ("accuracy", "precision", "recall", "roc_auc")},
        "cutoff_table": cutoff_table,
        "top_features": ratios[:10],
        "fraud_share_by_line": {
            line: {"rows": int((frame["line"] == line).sum()), "fraud": int(y[(frame["line"] == line).to_numpy()].sum())}
            for line in ("Motor", "Fire & Property")
        },
    }
    return {
        "parameters": {"model": model.to_dict()},
        "metrics": metrics,
        "thresholds": {"fraud_cutoff": NB_FRAUD_CUTOFF},
        "train_rows": len(train_idx), "test_rows": len(test_idx), "positive_rows": int(y.sum()),
        "total_rows": len(y),
        "sources": features.NB_CLUE_SOURCES,
    }


# ------------------------------------------------------------ fingerprint

def build_dataset(db, name, today):
    if name == "motor_lr":
        return _lr_dataset(db, "motor", today)
    if name == "fire_lr":
        return _lr_dataset(db, "fire", today)
    if name == "fraud_nb":
        return _nb_dataset(db)
    raise ValueError(f"unknown model {name!r}")


def data_signature(name, frame):
    """SHA-256 of the training rows (id, inputs, label) + every setting that shapes the model."""
    if name == "fraud_nb":
        cols = ["line", "claim_id", *features.NB_CLUE_VALUES, "fraud_label"]
        settings = {"alpha": NB_ALPHA, "fraud_cutoff": NB_FRAUD_CUTOFF, "clue_values": features.NB_CLUE_VALUES,
                    "min_clue_support": MIN_CLUE_SUPPORT}
    else:
        spec = features.MOTOR_SPEC if name == "motor_lr" else features.FIRE_SPEC
        cols = ["quotation_id", *spec["categorical"], *spec["numeric"], *spec["binary"], "counted_loss"]
        settings = {"lr": LR_SETTINGS, "spec": spec}
    settings.update(code=MODEL_CODE_VERSION, seed=SEED, test_fraction=TEST_FRACTION, cv_folds=CV_FOLDS)
    digest = hashlib.sha256(frame[cols].to_csv(index=False).encode("utf-8"))
    digest.update(json.dumps(settings, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def active_model(db, name):
    return (db.query(models.MLModel)
            .filter(models.MLModel.model_name == name, models.MLModel.status == "active")
            .order_by(models.MLModel.version.desc()).first())


def latest_attempt(db, name):
    return (db.query(models.MLModel).filter(models.MLModel.model_name == name)
            .order_by(models.MLModel.version.desc()).first())


# ------------------------------------------------------------ save + entry points

def _next_version(db, name):
    last = (db.query(models.MLModel.version).filter(models.MLModel.model_name == name)
            .order_by(models.MLModel.version.desc()).first())
    return (last[0] if last else 0) + 1


def _finish(db, commit):
    if commit:
        db.commit()
    else:
        db.flush()


def train_model(db, name, today=None, report_dir=None, commit=True, dataset=None):
    """Train one model; returns the saved MLModel row, or None if training failed.
    On failure the session is rolled back, so pass a session with no other pending work.
    `dataset` = an already-built build_dataset() frame (saves reading it twice)."""
    today = today or dt.date.today()
    report_dir = Path(report_dir) if report_dir else REPORT_DIR
    signature = None
    try:
        frame = dataset if dataset is not None else build_dataset(db, name, today)
        signature = data_signature(name, frame)
        if name == "motor_lr":
            result = train_logistic(db, "motor", today, frame)
        elif name == "fire_lr":
            result = train_logistic(db, "fire", today, frame)
        else:
            result = train_naive_bayes(db, today, frame)
        result["parameters"]["data_signature"] = signature

        row = models.MLModel(
            model_name=name, version=_next_version(db, name), status="active",
            trained_at=dt.datetime.now(), data_as_of=today,
            train_rows=result["train_rows"], test_rows=result["test_rows"],
            positive_rows=result["positive_rows"],
            parameters=result["parameters"], metrics=result["metrics"], thresholds=result["thresholds"],
        )
        (db.query(models.MLModel)
           .filter(models.MLModel.model_name == name, models.MLModel.status == "active")
           .update({"status": "superseded"}, synchronize_session=False))
        db.add(row)
        db.flush()
        row.report_path = str(write_report(row, result, report_dir))
        _finish(db, commit)
        return row
    except Exception as exc:  # training must never break the caller (e.g. an upload)
        db.rollback()
        log.exception("Training %s failed", name)
        failed = models.MLModel(
            model_name=name, version=_next_version(db, name), status="failed",
            trained_at=dt.datetime.now(), data_as_of=today,
            parameters={"data_signature": signature} if signature else None,
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}",
        )
        db.add(failed)
        _finish(db, commit)
        return None


def retrain_if_changed(db, name, today=None, report_dir=None, commit=True):
    """Train `name` unless its fingerprint equals the latest attempt's (active or failed).
    Returns (active MLModel row or None, retrained: bool). Never raises."""
    today = today or dt.date.today()
    try:
        frame = build_dataset(db, name, today)
        signature = data_signature(name, frame)
    except Exception:
        log.exception("Could not build the %s dataset", name)
        frame, signature = None, None
    latest = latest_attempt(db, name)
    if (signature is not None and latest is not None and latest.status in ("active", "failed")
            and (latest.parameters or {}).get("data_signature") == signature):
        return active_model(db, name), False
    return train_model(db, name, today, report_dir, commit, dataset=frame), True


def train_all(db, today=None, report_dir=None, commit=True):
    return {name: train_model(db, name, today, report_dir, commit) for name in MODEL_NAMES}


if __name__ == "__main__":
    from app.database import SessionLocal

    logging.basicConfig(level=logging.INFO)
    session = SessionLocal()
    try:
        for model_name, saved in train_all(session).items():
            if saved is None:
                print(f"{model_name}: FAILED (see ml_models.error)")
            else:
                t = saved.metrics["test"]
                print(f"{model_name} v{saved.version}: {saved.train_rows}+{saved.test_rows} rows, "
                      f"accuracy {t['accuracy']:.1%}, precision {t['precision']:.1%}, "
                      f"recall {t['recall']:.1%}, ROC AUC {t['roc_auc']:.3f} -> {saved.report_path}")
    finally:
        session.close()
