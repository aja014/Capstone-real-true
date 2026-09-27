"""HTTP level: the 4 /ml endpoints and which uploads schedule the automatic refresh.
TestClient is used WITHOUT `with`, so the app's startup refresh never runs in tests."""
import datetime as dt
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import get_db
from app.ml import jobs, predict, training
from app.security import get_current_user
from main import app

TODAY = dt.date(2026, 9, 27)
ML_ENDPOINTS = ["/ml/models", "/ml/models/motor_lr", "/ml/predictions/quotations", "/ml/predictions/claims"]
CLAIMS_CSV = ("Policy No.,Assured,Date of Loss,PLA Date (Date Reported),Nature of Loss,Claim Type,"
              "Coverage Type,Final Status\nZZTEST-NO-SUCH-POLICY,ZZTEST ASSURED,2026-09-01,2026-09-03,"
              "Collision,Paid Claim,Own Damage,Waiting for Evaluation\n")


class _NoDbSession:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def no_real_refresh_session(monkeypatch):
    """Safety net: a background refresh in these tests may never open a real session (it would
    commit models to the dev database outside the test's rolled-back transaction)."""
    monkeypatch.setattr(jobs, "SessionLocal", _NoDbSession)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def refresh_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(jobs, "refresh_now", lambda reason, session_factory=None: calls.append(reason))
    return calls


def _csv(name, text):
    return {"file": (name, io.BytesIO(text.encode("utf-8")), "text/csv")}


def test_endpoints_require_login():
    raw = TestClient(app)
    for path in ML_ENDPOINTS:
        assert raw.get(path).status_code == 401, path


def test_models_and_predictions(client, db, tmp_path):
    training.train_all(db, TODAY, tmp_path)
    predict.refresh_predictions(db, TODAY)

    body = client.get("/ml/models").json()
    assert [m["model_name"] for m in body["models"]] == ["motor_lr", "fire_lr", "fraud_nb"]
    for m in body["models"]:
        assert m["available"] and m["test"]["accuracy"] is not None and m["report_file"].endswith(".md")
        assert set(m["cross_validation"]) == {"accuracy", "precision", "recall", "roc_auc"}
    assert body["models"][2]["thresholds"] == {"fraud_cutoff": training.NB_FRAUD_CUTOFF}
    assert "running" in body["refresh"]

    detail = client.get("/ml/models/fraud_nb").json()
    assert detail["metrics"]["cutoff_table"] and detail["history"][0]["status"] == "active"
    assert client.get("/ml/models/no_such_model").status_code == 404

    quotes = client.get("/ml/predictions/quotations").json()
    assert len(quotes) == 617 + 411
    assert {q["risk_level"] for q in quotes} <= {"Low", "Medium", "High"}
    motor_only = client.get("/ml/predictions/quotations", params={"line": "Motor Car"}).json()
    assert len(motor_only) == 617 and {q["line"] for q in motor_only} == {"Motor Car"}
    assert client.get("/ml/predictions/quotations", params={"line": "Boat"}).status_code == 422

    claims = client.get("/ml/predictions/claims").json()
    assert len(claims) == 23 and {c["label"] for c in claims} <= {"Fraud", "Legitimate"}
    assert all(0 <= c["fraud_probability"] <= 1 for c in claims)


def test_learning_data_upload_schedules_exactly_one_refresh(client, refresh_calls):
    r = client.post("/import/claims/motor/upload", files=_csv("zztest_claims.csv", CLAIMS_CSV))
    assert r.status_code == 200 and r.json()["needs_review"] == 1
    assert refresh_calls == ["upload"]


def test_folder_upload_schedules_one_refresh_not_one_per_file(client, refresh_calls):
    files = [("files", ("a.csv", io.BytesIO(CLAIMS_CSV.encode()), "text/csv")),
             ("files", ("b.csv", io.BytesIO(CLAIMS_CSV.encode()), "text/csv"))]
    r = client.post("/import/batch/upload", files=files,
                    data={"import_types": ["motor_claim", "motor_claim"]})
    assert r.status_code == 200 and len(r.json()["files"]) == 2
    assert refresh_calls == ["upload"]


def test_resolve_schedules_a_refresh(client, db, refresh_calls):
    r = client.post("/import/claims/motor/upload", files=_csv("zztest_claims.csv", CLAIMS_CSV))
    record_id = r.json()["import_record_ids"][0]
    policy_id = db.execute(text(
        "SELECT id FROM motor_policies WHERE period_from <= '2026-09-01' AND period_to >= '2026-09-01' LIMIT 1")).scalar()
    r = client.patch(f"/import/policyholders/records/{record_id}/resolve", json={"matched_policy_id": policy_id})
    assert r.status_code == 200
    assert refresh_calls == ["upload", "upload"]


def test_uploads_without_learning_data_or_with_errors_do_not_schedule(client, refresh_calls):
    r = client.post("/import/policyholders/upload",
                    files=_csv("zztest_people.csv", "Last Name,First Name\nZZTEST Alpha,Juan\n"))
    assert r.status_code == 200
    r = client.post("/import/claims/motor/upload", files=_csv("zztest_claims.txt", CLAIMS_CSV))
    assert r.status_code == 400
    assert refresh_calls == []


def test_a_failing_refresh_never_fails_the_upload(client, monkeypatch):
    monkeypatch.setattr(jobs, "run_refresh", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.post("/import/claims/motor/upload", files=_csv("zztest_claims.csv", CLAIMS_CSV))
    assert r.status_code == 200  # the refresh ran after the response and swallowed its error
    assert "boom" in jobs.status["last_error"]
