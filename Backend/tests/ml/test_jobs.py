"""Automatic retraining (retrain_if_changed) and the refresh job's safety rules."""
import datetime as dt
import threading

import pytest
from sqlalchemy import func

from app import models
from app.ml import jobs, training

TODAY = dt.date(2026, 9, 27)


@pytest.fixture
def forget_fingerprints(db):
    """Clear every stored data fingerprint (inside the rolled-back test transaction), so
    the first retrain_if_changed() really trains, whatever models the dev DB already has
    — a model already trained on today's data would otherwise make it a no-op."""
    for row in db.query(models.MLModel):
        row.parameters = {**(row.parameters or {}), "data_signature": None}
    db.flush()


def test_retrains_only_when_the_training_data_or_settings_change(db, tmp_path, monkeypatch, forget_fingerprints):
    first, retrained = training.retrain_if_changed(db, "fraud_nb", TODAY, tmp_path)
    assert retrained and first.parameters["data_signature"]
    same, retrained = training.retrain_if_changed(db, "fraud_nb", TODAY, tmp_path)
    assert not retrained and same.id == first.id

    # A new label on an investigated claim changes the training data -> retrain
    claim = db.query(models.MotorClaim).filter(models.MotorClaim.claim_investigation_result == "Legitimate").first()
    claim.claim_investigation_result = "Suspected Fraud"
    db.flush()
    changed, retrained = training.retrain_if_changed(db, "fraud_nb", TODAY, tmp_path)
    assert retrained and changed.version == first.version + 1

    # A changed setting (e.g. the fraud cutoff) also retrains, even with the same data
    monkeypatch.setattr(training, "NB_FRAUD_CUTOFF", 0.25)
    again, retrained = training.retrain_if_changed(db, "fraud_nb", TODAY, tmp_path)
    assert retrained and again.thresholds == {"fraud_cutoff": 0.25}


def test_a_new_open_quotation_does_not_retrain_the_lr_model(db, tmp_path):
    """Only ENDED policies are training rows; a new open quotation changes predictions, not the model."""
    first, _ = training.retrain_if_changed(db, "motor_lr", TODAY, tmp_path)
    q = db.query(models.MotorQuotation).first()
    db.add(models.MotorQuotation(insurance_case_id=q.insurance_case_id, vehicle_id=q.vehicle_id,
                                 quotation_date=TODAY, classification="Private", sum_insured=500000, deductible=5000))
    db.flush()
    _, retrained = training.retrain_if_changed(db, "motor_lr", TODAY, tmp_path)
    assert not retrained


def test_identical_failure_is_not_retried(db, tmp_path, monkeypatch, forget_fingerprints):
    active_before = training.active_model(db, "fire_lr")  # may be None on an empty database
    before = db.query(func.max(models.MLModel.id)).scalar() or 0  # loaded data may hold failed runs
    monkeypatch.setattr(training, "MIN_ROWS", 10_000)
    assert training.retrain_if_changed(db, "fire_lr", TODAY, tmp_path) == (None, True)
    # Same data, same failure: not retried, and any older active version is still the one in use
    assert training.retrain_if_changed(db, "fire_lr", TODAY, tmp_path) == (active_before, False)
    assert training.active_model(db, "fire_lr") is active_before
    assert (db.query(models.MLModel).filter_by(model_name="fire_lr", status="failed")
            .filter(models.MLModel.id > before).count()) == 1


def test_run_refresh_upload_and_startup(db, tmp_path, monkeypatch, forget_fingerprints):
    monkeypatch.setattr(training, "REPORT_DIR", tmp_path)
    retrained, counts = jobs.run_refresh(db, "upload", TODAY, tmp_path)
    assert sorted(retrained) == sorted(training.MODEL_NAMES) and sum(counts.values()) > 1000
    # startup: every model already has an active version -> nothing trained, predictions rewritten
    retrained, counts2 = jobs.run_refresh(db, "startup", TODAY, tmp_path)
    assert retrained == [] and counts2 == counts


class _FakeSession:
    def __init__(self):
        self.closed = self.rolled_back = False

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_refresh_never_raises_and_records_the_error(monkeypatch):
    def boom(db, reason, today=None, report_dir=None):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(jobs, "run_refresh", boom)
    session = _FakeSession()
    jobs.refresh_now("upload", session_factory=lambda: session)  # must not raise
    assert "database unavailable" in jobs.status["last_error"]
    assert session.rolled_back and session.closed and not jobs.status["running"]
    assert jobs._running is False  # next request can run


def test_requests_during_a_run_are_coalesced_into_one_more_run(monkeypatch):
    started, release, reasons, running_seen = threading.Event(), threading.Event(), [], []

    def slow(db, reason, today=None, report_dir=None):
        reasons.append(reason)
        running_seen.append(jobs.status["running"])
        if len(reasons) == 1:
            started.set()
            release.wait(5)
        return [], {}

    monkeypatch.setattr(jobs, "run_refresh", slow)
    t = threading.Thread(target=jobs.refresh_now, args=("startup",), kwargs={"session_factory": _FakeSession})
    t.start()
    assert started.wait(5)
    for _ in range(3):  # three uploads finish while the startup refresh is still running
        jobs.refresh_now("upload", session_factory=_FakeSession)
    release.set()
    t.join(5)
    assert reasons == ["startup", "upload"]  # exactly one extra run, not three
    assert running_seen == [True, True]  # "running" never dropped between the two runs
    assert jobs._running is False and jobs.status["running"] is False


def test_the_l2_grid_is_part_of_the_lr_fingerprint_only(db, monkeypatch):
    """Fix round A3: changing the λ grid retrains the Logistic Regression models, not Naive Bayes."""
    frames = {n: training.build_dataset(db, n, TODAY) for n in ("motor_lr", "fraud_nb")}
    before = {n: training.data_signature(n, f) for n, f in frames.items()}
    monkeypatch.setattr(training, "LR_L2_CHOICES", (0.01, 0.1))
    after = {n: training.data_signature(n, f) for n, f in frames.items()}
    assert before["motor_lr"] != after["motor_lr"]
    assert before["fraud_nb"] == after["fraud_nb"]
