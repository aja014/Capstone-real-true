"""Automatic retraining (retrain_if_changed) and the refresh job's safety rules."""
import datetime as dt
import threading

from app import models
from app.ml import jobs, training

TODAY = dt.date(2026, 9, 27)


def test_retrains_only_when_the_training_data_or_settings_change(db, tmp_path, monkeypatch):
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


def test_identical_failure_is_not_retried(db, tmp_path, monkeypatch):
    active_before = training.active_model(db, "fire_lr")  # may be None on an empty database
    monkeypatch.setattr(training, "MIN_ROWS", 10_000)
    assert training.retrain_if_changed(db, "fire_lr", TODAY, tmp_path) == (None, True)
    # Same data, same failure: not retried, and any older active version is still the one in use
    assert training.retrain_if_changed(db, "fire_lr", TODAY, tmp_path) == (active_before, False)
    assert training.active_model(db, "fire_lr") is active_before
    assert db.query(models.MLModel).filter_by(model_name="fire_lr", status="failed").count() == 1


def test_run_refresh_upload_and_startup(db, tmp_path, monkeypatch):
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
    started, release, reasons = threading.Event(), threading.Event(), []

    def slow(db, reason, today=None, report_dir=None):
        reasons.append(reason)
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
    assert jobs._running is False
