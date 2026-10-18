"""Full training runs against the dev database. Everything written (ml_models rows) is
rolled back by the `db` fixture; reports go to a temporary folder."""
import datetime as dt

from sqlalchemy import func

from app import models
from app.ml import training

TODAY = dt.date(2026, 9, 27)


def _active(db, name):
    return db.query(models.MLModel).filter_by(model_name=name, status="active").all()


def _max_model_id(db):
    # The loaded data may already hold failed runs; tests count only the rows they create.
    return db.query(func.max(models.MLModel.id)).scalar() or 0


def test_train_all_saves_models_and_reports(db, tmp_path):
    saved = training.train_all(db, TODAY, tmp_path)
    for name in training.MODEL_NAMES:
        row = saved[name]
        assert row is not None, name
        assert [r.id for r in _active(db, name)] == [row.id]
        assert row.data_as_of == TODAY and row.train_rows + row.test_rows > 0
        test = row.metrics["test"]
        assert 0 <= test["accuracy"] <= 1 and 0.5 < test["roc_auc"] <= 1
        cv = row.metrics["cross_validation"]
        assert set(cv) == {"accuracy", "precision", "recall", "roc_auc"}
        assert len(cv["accuracy"]["per_fold"]) == 5
        text = open(row.report_path, encoding="utf-8").read()
        for heading in ("## Results on held-back test data", "## 5-fold stratified cross-validation",
                        "ROC AUC", "## Note on the data"):
            assert heading in text, (name, heading)

    motor, fire, nb = saved["motor_lr"], saved["fire_lr"], saved["fraud_nb"]
    assert (motor.train_rows, motor.test_rows, motor.positive_rows) == (678, 227, 294)
    assert (fire.train_rows, fire.test_rows, fire.positive_rows) == (1389, 463, 51)
    assert (nb.train_rows, nb.test_rows, nb.positive_rows) == (523, 175, 31)
    assert set(motor.thresholds) == {"medium_from", "high_from"}
    assert len(motor.metrics["control_check"]) == 9
    assert "Control check" in open(motor.report_path, encoding="utf-8").read()
    for lr in (motor, fire):  # Fix round A3: λ chosen by 5-fold CV
        sel = lr.metrics["l2_selection"]
        assert [r["l2"] for r in sel["table"]] == list(training.LR_L2_CHOICES)
        best = max(sel["table"], key=lambda r: (round(r["roc_auc"]["mean"], 4), r["l2"]))
        assert sel["chosen"] == best["l2"] == lr.parameters["model"]["l2"]
        assert lr.parameters["model"]["learning_rate"] == min(0.5, 1 / best["l2"])
        assert lr.metrics["cross_validation"]["roc_auc"]["mean"] == best["roc_auc"]["mean"]
        assert "Choosing the L2 strength" in open(lr.report_path, encoding="utf-8").read()
    assert nb.thresholds == {"fraud_cutoff": training.NB_FRAUD_CUTOFF}
    assert [r["cutoff"] for r in nb.metrics["cutoff_table"]] == [0.5, 0.4, 0.3, 0.2]
    recalls = [r["recall"]["mean"] for r in nb.metrics["cutoff_table"]]
    assert recalls == sorted(recalls)  # a lower cutoff never catches less fraud
    assert "Choosing the fraud cutoff" in open(nb.report_path, encoding="utf-8").read()


def test_retraining_supersedes_and_is_deterministic(db, tmp_path):
    first = training.train_model(db, "motor_lr", TODAY, tmp_path)
    second = training.train_model(db, "motor_lr", TODAY, tmp_path)
    assert second.version == first.version + 1
    db.refresh(first)
    assert first.status == "superseded" and second.status == "active"
    assert first.parameters["model"]["weights"] == second.parameters["model"]["weights"]
    assert first.metrics == second.metrics


def test_failed_training_keeps_the_active_model_and_does_not_raise(db, tmp_path, monkeypatch):
    before = _max_model_id(db)
    good = training.train_model(db, "fire_lr", TODAY, tmp_path)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(training, "train_logistic", boom)
    assert training.train_model(db, "fire_lr", TODAY, tmp_path) is None
    failed = (db.query(models.MLModel).filter_by(model_name="fire_lr", status="failed")
              .filter(models.MLModel.id > before).one())
    assert "simulated failure" in failed.error and failed.version == good.version + 1
    assert [r.id for r in _active(db, "fire_lr")] == [good.id]


def test_not_enough_data_is_a_failed_run(db, tmp_path, monkeypatch):
    monkeypatch.setattr(training, "MIN_ROWS", 10_000)
    before = _max_model_id(db)
    assert training.train_model(db, "fraud_nb", TODAY, tmp_path) is None
    failed = (db.query(models.MLModel).filter_by(model_name="fraud_nb", status="failed")
              .filter(models.MLModel.id > before).one())
    assert "NotEnoughData" in failed.error


def test_l2_tie_goes_to_the_larger_lambda(db, monkeypatch):
    """Equal mean AUC (to 4 decimals) for every λ -> the largest λ (the simpler model)."""
    frame = training.build_dataset(db, "fire_lr", TODAY)
    monkeypatch.setattr(training, "_fit_lr", lambda *a: (None, None, None))
    monkeypatch.setattr(training, "_lr_eval", lambda *a: (None, None, {"roc_auc": 0.61234, "accuracy": 0.5, "recall": 0.5}))
    chosen, table, folds = training.choose_l2(frame, None, frame["counted_loss"].to_numpy())
    assert chosen == max(training.LR_L2_CHOICES) and len(table) == len(training.LR_L2_CHOICES)
