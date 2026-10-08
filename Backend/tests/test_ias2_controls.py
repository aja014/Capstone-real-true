"""IAS2 security controls (branch deploy-ias2): /health, security headers, security.txt, the
failed-login limit, the dummy bcrypt check, the 10 MB upload limit and SQL-free row errors.

API tests run inside the rolled-back `db` fixture with ZZTEST records, TestClient WITHOUT `with`
(no startup model refresh). Uploads go to endpoints/functions that don't schedule a retrain."""
import datetime as dt
import io
import logging

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app import models
from app.config import settings
from app.database import get_db
from app.http_security import DATABASE_ROW_ERROR, FILE_TOO_LARGE, MAX_UPLOAD_BYTES, check_upload_size, row_error_text
from app.routers import auth, import_batch, import_motor
from app.security import DUMMY_PASSWORD_HASH, get_current_user, hash_password
from app.services import login_limiter
from main import app

SECRET_SQL = "INSERT INTO motor_quotations (zz_secret_column) VALUES (%(zz)s)"
LOCK_MESSAGE = "Too many failed login attempts. Please try again in 5 minutes."
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _add(db, obj):
    db.add(obj)
    db.flush()
    return obj


def _db_error():
    return OperationalError(SECRET_SQL, {"zz": 1}, Exception("(1054, \"Unknown column 'zz_secret_column'\")"))


@pytest.fixture
def client(db):
    """Real login (no get_current_user stub) on the rolled-back session."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def manager_client(db):
    manager = _add(db, models.User(username="ZZTEST Kilo Manager", password=hash_password("zz-kilo-pass1"),
                                   role="manager"))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


class _BrokenSession:
    def execute(self, *a, **k):
        raise _db_error()


@pytest.fixture
def broken_db_client():
    app.dependency_overrides[get_db] = lambda: _BrokenSession()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- 1. /health ----

def test_health_get_and_head_run_select_1(client, db, monkeypatch):
    calls = []
    real_execute = db.execute
    monkeypatch.setattr(db, "execute", lambda stmt, *a, **k: calls.append(str(stmt)) or real_execute(stmt, *a, **k))

    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
    r = client.head("/health")
    assert r.status_code == 200
    assert calls == ["SELECT 1", "SELECT 1"]  # HEAD touches the database too


def test_health_needs_no_login():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/health").status_code in (200, 503)  # never 401


def test_health_get_503_without_details(broken_db_client, caplog):
    with caplog.at_level(logging.ERROR):
        r = broken_db_client.get("/health")
    assert r.status_code == 503
    assert r.json() == {"status": "unavailable"}
    assert "zz_secret_column" not in r.text
    assert "zz_secret_column" in caplog.text  # the detail goes to the server log


def test_health_head_503(broken_db_client):
    r = broken_db_client.head("/health")
    assert r.status_code == 503
    assert r.content == b""


# ---- 3. security headers ----

BASE_HEADERS = {"x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer"}


def _assert_headers(response, hsts):
    for k, v in BASE_HEADERS.items():
        assert response.headers.get(k) == v, (response.status_code, k)
    if hsts:
        assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    else:
        assert "strict-transport-security" not in response.headers


def test_headers_on_success_and_error_responses(client):
    _assert_headers(client.get("/health"), hsts=False)                      # 200
    _assert_headers(client.get("/policyholders"), hsts=False)               # 401, no login
    _assert_headers(client.get("/zz-no-such-page"), hsts=False)             # 404
    _assert_headers(client.post("/login", json={}), hsts=False)             # 422
    _assert_headers(client.options("/login", headers={                      # CORS preflight
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}), hsts=False)


def test_headers_on_an_unhandled_500(manager_client):
    def boom():
        raise RuntimeError("zz boom")
    app.dependency_overrides[get_db] = boom
    r = TestClient(app, raise_server_exceptions=False).get("/policyholders")
    assert r.status_code == 500 and r.text == "Internal Server Error"
    _assert_headers(r, hsts=False)


def test_hsts_only_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    _assert_headers(client.get("/health"), hsts=True)
    _assert_headers(client.get("/zz-no-such-page"), hsts=True)


# ---- 4. security.txt ----

def test_security_txt(client):
    r = client.get("/.well-known/security.txt")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == ("Contact: mailto:gaj@firemap.local\n"
                      "Expires: 2027-10-08T00:00:00.000Z\n"
                      "Preferred-Languages: en\n")


# ---- 5. failed-login limit ----

@pytest.fixture
def zz_user(db):
    return _add(db, models.User(username="ZZTEST Lima", password=hash_password("zz-lima-pass1"), role="admin"))


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(login_limiter, "_now", lambda: now[0])
    return now


def _login(client, password, username="ZZTEST Lima", **headers):
    return client.post("/login", json={"username": username, "password": password}, headers=headers)


def test_five_failures_then_429_even_with_the_right_password(client, zz_user, clock):
    for _ in range(5):
        assert _login(client, "wrong-pass1").status_code == 401
    r = _login(client, "wrong-pass1")
    assert r.status_code == 429
    assert r.json() == {"detail": LOCK_MESSAGE}
    assert r.headers["retry-after"] == "300"
    assert _login(client, "zz-lima-pass1").status_code == 429


def test_lock_ends_after_5_minutes_and_lock_attempts_do_not_extend_it(client, zz_user, clock):
    for _ in range(5):
        _login(client, "wrong-pass1")
    clock[0] += 299
    assert _login(client, "zz-lima-pass1").status_code == 429
    clock[0] += 1
    assert _login(client, "zz-lima-pass1").status_code == 200


def test_failures_older_than_5_minutes_do_not_count(client, zz_user, clock):
    for _ in range(4):
        _login(client, "wrong-pass1")
    clock[0] += 300
    for _ in range(4):
        assert _login(client, "wrong-pass1").status_code == 401


def test_success_resets_the_count(client, zz_user, clock):
    for _ in range(4):
        _login(client, "wrong-pass1")
    assert _login(client, "zz-lima-pass1").status_code == 200
    for _ in range(4):
        assert _login(client, "wrong-pass1").status_code == 401
    assert _login(client, "zz-lima-pass1").status_code == 200


def test_unknown_usernames_are_limited_too_and_case_does_not_matter(client, clock):
    for name in ["ZZTEST Nobody", "zztest nobody", " ZZTEST NOBODY ", "ZZTEST Nobody", "zztest nobody"]:
        assert _login(client, "wrong-pass1", username=name).status_code == 401
    assert _login(client, "wrong-pass1", username="ZZTEST Nobody").status_code == 429


def test_key_is_ip_plus_username(client, zz_user, clock, monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    for _ in range(5):
        _login(client, "wrong-pass1", **{"X-Forwarded-For": "203.0.113.7"})
    assert _login(client, "zz-lima-pass1", **{"X-Forwarded-For": "203.0.113.7"}).status_code == 429
    # another client IP, same user: not locked
    assert _login(client, "zz-lima-pass1", **{"X-Forwarded-For": "198.51.100.9"}).status_code == 200
    # same IP, another username: not locked
    assert _login(client, "wrong-pass1", username="ZZTEST Mike",
                  **{"X-Forwarded-For": "203.0.113.7"}).status_code == 401


def test_a_faked_leftmost_forwarded_for_does_not_escape_the_lock(client, zz_user, clock, monkeypatch):
    """Render appends the real address on the right; whatever the client sends stays on the left."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    for i in range(5):
        _login(client, "wrong-pass1", **{"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"})
    r = _login(client, "zz-lima-pass1", **{"X-Forwarded-For": "10.9.9.9, 203.0.113.7"})
    assert r.status_code == 429


def test_forwarded_for_is_ignored_locally(client, zz_user, clock):
    """TRUSTED_PROXY_HOPS unset (0): the header can't be used to dodge the limit."""
    for i in range(5):
        _login(client, "wrong-pass1", **{"X-Forwarded-For": f"10.0.0.{i}"})
    assert _login(client, "zz-lima-pass1", **{"X-Forwarded-For": "10.9.9.9"}).status_code == 429


# ---- 6. same work for unknown usernames ----

def test_unknown_username_runs_one_dummy_bcrypt_check(client, zz_user, monkeypatch):
    checked = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda pw, h: checked.append(h) or real(pw, h))

    assert _login(client, "wrong-pass1", username="ZZTEST Nobody").status_code == 401
    assert checked == [DUMMY_PASSWORD_HASH]
    assert _login(client, "wrong-pass1").status_code == 401
    assert checked[-1] == zz_user.password and len(checked) == 2


def test_dummy_hash_is_a_real_bcrypt_hash_with_the_normal_cost():
    assert DUMMY_PASSWORD_HASH.startswith("$2b$12$")
    assert DUMMY_PASSWORD_HASH[:7] == hash_password("x")[:7]


# ---- 7. upload size ----

def _upload(content, filename="zztest_big.xlsx"):
    return UploadFile(file=io.BytesIO(content), filename=filename)


def test_size_limit_boundary():
    check_upload_size(_upload(b"0" * MAX_UPLOAD_BYTES))  # exactly 10 MB is allowed
    with pytest.raises(HTTPException) as e:
        check_upload_size(_upload(b"0" * (MAX_UPLOAD_BYTES + 1)))
    assert e.value.status_code == 413 and e.value.detail == FILE_TOO_LARGE == "File is too large (max 10 MB)."


def test_single_file_upload_over_10_mb_is_413(manager_client):
    r = manager_client.post("/import/policyholders/upload",
                            files={"file": ("zztest_big.xlsx", b"0" * (MAX_UPLOAD_BYTES + 1), XLSX)})
    assert r.status_code == 413
    assert r.json() == {"detail": FILE_TOO_LARGE}


@pytest.mark.parametrize("upload_fn", [
    "import_policyholders.upload_policyholders", "import_fire_property.upload_surveys",
    "import_fire_property.upload_fire_property_quotations", "import_fire_property.upload_fire_property_policies",
    "import_motor.upload_motor_quotations", "import_motor.upload_motor_policies",
    "import_vehicle.upload_vehicles", "import_claims.upload_motor_claims",
    "import_claims.upload_fire_property_claims",
])
def test_every_single_file_importer_checks_the_size(upload_fn, db):
    module, name = upload_fn.split(".")
    fn = getattr(getattr(__import__("app.routers", fromlist=[module]), module), name)
    with pytest.raises(HTTPException) as e:
        fn(file=_upload(b"0" * (MAX_UPLOAD_BYTES + 1)), db=db)
    assert e.value.status_code == 413


def test_folder_detect_reports_too_large_without_the_read_prefix():
    result = import_batch.detect_batch(files=[_upload(b"0" * (MAX_UPLOAD_BYTES + 1))])
    assert result.files[0].error == FILE_TOO_LARGE


def test_folder_upload_rejects_only_the_big_file(db):
    buf = io.BytesIO()
    pd.DataFrame([{"Last Name": "ZZTEST November", "First Name": "Folder"}]).to_excel(buf, index=False)
    small = UploadFile(file=io.BytesIO(buf.getvalue()), filename="zztest_small.xlsx")

    result = import_batch.upload_batch(
        files=[_upload(b"0" * (MAX_UPLOAD_BYTES + 1)), small],
        import_types=["policyholder", "policyholder"], db=db)

    assert result.files[0].error == FILE_TOO_LARGE and result.files[0].summary is None
    assert result.files[1].error is None and result.files[1].summary.failed == 0
    assert db.query(models.Policyholder).filter(models.Policyholder.last_name == "ZZTEST November").count() == 1


# ---- 8. no SQL in row errors ----

def test_row_error_text_hides_database_errors_only(caplog):
    with caplog.at_level(logging.ERROR):
        assert row_error_text(_db_error(), 7) == DATABASE_ROW_ERROR == "could not be saved (database error)"
    assert "zz_secret_column" in caplog.text
    assert row_error_text(ValueError("Date: 'soon' is not a valid date"), 7) == "Date: 'soon' is not a valid date"


def _motor_quote_file(date_value, plate):
    buf = io.BytesIO()
    pd.DataFrame([{"Date": date_value, "Insured Name": "ZZTEST Oscar Rowerr", "Address": "Malolos, Bulacan",
                   "Plate No.": plate, "Motor/Engine No.": "", "Serial/Chasis No.": "",
                   "Total Amount Due": 15000, "Sum Insured": 500000, "Make": "Toyota", "Model": "2020"}]
                 ).to_excel(buf, index=False)
    buf.seek(0)
    return UploadFile(file=buf, filename="zztest_row_errors.xlsx")


def test_database_error_in_a_row_shows_no_sql(db, monkeypatch):
    owner = _add(db, models.Policyholder(last_name="ZZTEST Oscar", first_name="Rowerr"))
    case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.motor_car))
    _add(db, models.Vehicle(insurance_case_id=case.id, plate_no="ZZROW01"))

    def failing_lookup(address):
        raise _db_error()
    monkeypatch.setattr(import_motor, "lookup_flood_risk", failing_lookup)

    summary = import_motor.upload_motor_quotations(file=_motor_quote_file(dt.date(2026, 10, 5), "ZZROW01"), db=db)

    assert summary.failed == 1
    assert [e.error for e in summary.errors] == [DATABASE_ROW_ERROR]
    assert "zz_secret_column" not in summary.model_dump_json() and "INSERT" not in summary.model_dump_json()


def test_validation_messages_are_unchanged(db, monkeypatch):
    monkeypatch.setattr(import_motor, "lookup_flood_risk", lambda address: {})
    summary = import_motor.upload_motor_quotations(file=_motor_quote_file("not-a-date", "ZZROW02"), db=db)
    assert [e.error for e in summary.errors] == ["Date: 'not-a-date' is not a valid date"]


def test_folder_file_level_database_error_shows_no_sql(db, monkeypatch):
    def failing_upload(file, db):
        raise _db_error()
    monkeypatch.setattr(import_batch, "IMPORT_TYPE_REGISTRY",
                        [{**e, "upload_fn": failing_upload} for e in import_batch.IMPORT_TYPE_REGISTRY])
    result = import_batch.upload_batch(files=[_upload(b"x", "zztest.xlsx")], import_types=["policyholder"], db=db)
    assert result.files[0].error == DATABASE_ROW_ERROR
