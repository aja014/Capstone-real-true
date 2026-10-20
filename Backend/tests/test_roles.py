"""Server-side role checks: manager-only endpoints (the 5 manager pages' /stats/* and the two
manager-only /ml endpoints) give an admin 403, while everything Policy Holder Information uses
stays open to admins. Real login tokens for two temporary ZZTEST users inside the rolled-back
`db` fixture; nothing is changed (mutating calls target ids that don't exist or files that
aren't Excel/CSV). TestClient is used WITHOUT `with`, so the startup model refresh never runs."""
import io

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.ml import jobs
from app.security import create_access_token, hash_password
from main import app

TODAY = "2026-09-28"
NO_ID = 999999999

MANAGER_ONLY = [
    "/stats/overview",
    f"/stats/policy-distribution?period=daily&date={TODAY}",
    f"/stats/renewal-ratio?period=daily&date={TODAY}",
    "/stats/quotation-proposal?months=3",
    "/stats/policy-forecast",
    "/stats/claims?months=3",
    "/ml/models/motor_lr",
    "/ml/predictions/quotations",
]

# Everything the Policy Holder Information page (open to admins) reads.
ADMIN_READS = [
    "/policyholders", "/insurance-cases",
    "/fire-property/surveys", "/fire-property/quotations", "/fire-property/policies", "/fire-property/claims",
    "/motor/vehicles", "/motor/quotations", "/motor/policies", "/motor/claims",
    "/import/policyholders/needs-review", "/import/policyholders/deleted-records", "/deleted-policyholders",
    "/ml/models", "/ml/predictions/claims",
]

ADMIN_NOT_FOUND = [
    ("delete", f"/policyholders/{NO_ID}"),
    ("delete", f"/fire-property/surveys/{NO_ID}"),
    ("delete", f"/fire-property/quotations/{NO_ID}"),
    ("delete", f"/fire-property/policies/{NO_ID}"),
    ("delete", f"/fire-property/claims/{NO_ID}"),
    ("delete", f"/motor/vehicles/{NO_ID}"),
    ("delete", f"/motor/quotations/{NO_ID}"),
    ("delete", f"/motor/policies/{NO_ID}"),
    ("delete", f"/motor/claims/{NO_ID}"),
    ("delete", f"/import/policyholders/records/{NO_ID}"),
    ("get", f"/import/policyholders/records/{NO_ID}/quotation-candidates"),
    ("get", f"/import/policyholders/records/{NO_ID}/policy-candidates"),
]

UPLOADS = [
    "/import/policyholders/upload", "/import/fire-property/surveys/upload",
    "/import/fire-property/quotations/upload", "/import/fire-property/policies/upload",
    "/import/motor/quotations/upload", "/import/motor/policies/upload", "/import/vehicles/upload",
    "/import/claims/motor/upload", "/import/claims/fire-property/upload",
]


class _NoDbSession:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def no_real_refresh(monkeypatch):
    monkeypatch.setattr(jobs, "SessionLocal", _NoDbSession)
    monkeypatch.setattr(jobs, "refresh_now", lambda reason, session_factory=None: None)


@pytest.fixture
def client(db):
    for username, role in (("ZZTEST Role Manager", "manager"), ("ZZTEST Role Admin", "admin")):
        db.add(models.User(username=username, password=hash_password("zz-role-pass1"), role=role))
    db.flush()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth(username):
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


# Tokens are made inside each test, not when the file loads: they expire after 60 min, and a
# full run of the suite can take longer than that before these tests are reached.
def _manager():
    return _auth("ZZTEST Role Manager")


def _admin():
    return _auth("ZZTEST Role Admin")


@pytest.mark.parametrize("path", MANAGER_ONLY)
def test_manager_only_endpoints(client, path):
    no_token = client.get(path)
    assert no_token.status_code == 401
    admin = client.get(path, headers=_admin())
    assert admin.status_code == 403
    assert admin.json()["detail"] == "Manager access only."
    assert client.get(path, headers=_manager()).status_code == 200


@pytest.mark.parametrize("path", ADMIN_READS)
def test_admin_can_read_policy_holder_information_data(client, path):
    assert client.get(path, headers=_admin()).status_code == 200


@pytest.mark.parametrize("method, path", ADMIN_NOT_FOUND)
def test_admin_can_reach_delete_and_needs_review_endpoints(client, method, path):
    # 404 = the role check let the admin through to the real lookup.
    assert getattr(client, method)(path, headers=_admin()).status_code == 404


def test_admin_can_reach_resolve(client):
    r = client.patch(f"/import/policyholders/records/{NO_ID}/resolve", headers=_admin(), json={"create_new": True})
    assert r.status_code == 404


def _txt():
    return {"file": ("notes.txt", io.BytesIO(b"not a spreadsheet"), "text/plain")}


@pytest.mark.parametrize("path", UPLOADS)
def test_admin_can_reach_every_upload(client, path):
    r = client.post(path, headers=_admin(), files=_txt())
    assert r.status_code == 400
    assert "Only .xlsx" in r.json()["detail"]


def test_admin_can_use_folder_upload(client):
    files = [("files", ("notes.txt", io.BytesIO(b"x"), "text/plain"))]
    detect = client.post("/import/batch/detect", headers=_admin(), files=files)
    assert detect.status_code == 200 and detect.json()["files"][0]["error"]
    files = [("files", ("notes.txt", io.BytesIO(b"x"), "text/plain"))]
    upload = client.post("/import/batch/upload", headers=_admin(), files=files, data={"import_types": ["policyholder"]})
    assert upload.status_code == 200 and "Only .xlsx" in upload.json()["files"][0]["error"]
