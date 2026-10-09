"""IAS2 round 2 (branch deploy-ias2): controls against a stolen password (no MFA).

1a sessions end when the password changes (SESSION_ENDS_ON_PASSWORD_CHANGE)
1c token lifetime (TOKEN_MINUTES)
1d/2 login attempt log + "Last login" (LOGIN_AUDIT, table login_events)
3  stronger password rule (PASSWORD_MIN_LENGTH, PASSWORD_BLOCK_COMMON)
(1b, the idle logout, is frontend only: Frontend/src/lib/idleTimeout.test.js.)

Every switch at its default keeps today's behaviour; the first tests prove it. API tests run inside
the rolled-back `db` fixture with ZZTEST users and made-up passwords, TestClient WITHOUT `with`.
The login_events tests need the table, which is created only on a database that is NOT the local
insurance_db (run them on the scratch copy; on insurance_db they skip)."""
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import inspect

from app import models
from app.config import settings
from app.database import engine, get_db
from app.security import (PASSWORD_COMMON_MESSAGE, PASSWORD_HAS_USERNAME_MESSAGE, PASSWORD_RULE_MESSAGE,
                          SESSION_ENDED_MESSAGE, create_access_token, hash_password, password_fingerprint,
                          password_rule_error, token_for_user)
from app.services import common_passwords, login_audit
from main import app

BACKEND = Path(__file__).resolve().parents[1]
ROUND2_SWITCHES = ("TOKEN_MINUTES", "SESSION_ENDS_ON_PASSWORD_CHANGE", "LOGIN_AUDIT",
                   "PASSWORD_MIN_LENGTH", "PASSWORD_BLOCK_COMMON")
OLD_PW, NEW_PW = "zz-oscar-pass1", "zz-oscar-newpass2"


def _run(code, **env):
    clean = {k: v for k, v in os.environ.items() if k not in ROUND2_SWITCHES}
    clean.update(env)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=clean,
                          capture_output=True, text=True, timeout=300)


def _add_user(db, username="ZZTEST Oscar", password=OLD_PW, role="admin"):
    user = models.User(username=username, password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db):
    """Real login and real get_current_user, on the rolled-back session."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _login(client, username="ZZTEST Oscar", password=OLD_PW, **headers):
    return client.post("/login", json={"username": username, "password": password}, headers=headers)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _claims(token):
    return jwt.get_unverified_claims(token)


@pytest.fixture
def session_switch(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_ENDS_ON_PASSWORD_CHANGE", True)


@pytest.fixture
def hosted_rule(monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_MIN_LENGTH", 12)
    monkeypatch.setattr(settings, "PASSWORD_BLOCK_COMMON", True)


@pytest.fixture
def audit(monkeypatch):
    """LOGIN_AUDIT on, with the login_events table (scratch database only)."""
    if engine.url.database == "insurance_db":
        pytest.skip("login_events tests run on a scratch copy, never on the local insurance_db")
    models.AuditBase.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "LOGIN_AUDIT", True)


def _events(db, username):
    return (db.query(models.LoginEvent).filter(models.LoginEvent.username == username)
            .order_by(models.LoginEvent.id).all())


# ---- defaults = today's behaviour ----

def test_unset_round2_switches_keep_todays_behaviour():
    code = ("import json; from app.config import settings as s; print(json.dumps([s.TOKEN_MINUTES, "
            "s.SESSION_ENDS_ON_PASSWORD_CHANGE, s.LOGIN_AUDIT, s.PASSWORD_MIN_LENGTH, s.PASSWORD_BLOCK_COMMON]))")
    out = _run(code)
    assert out.returncode == 0, out.stderr[-2000:]
    assert json.loads(out.stdout.strip().splitlines()[-1]) == [60, False, False, 8, False]
    out = _run(code, TOKEN_MINUTES="30", SESSION_ENDS_ON_PASSWORD_CHANGE="true", LOGIN_AUDIT="TRUE",
               PASSWORD_MIN_LENGTH="12", PASSWORD_BLOCK_COMMON="true")
    assert json.loads(out.stdout.strip().splitlines()[-1]) == [30, True, True, 12, True]


@pytest.mark.parametrize("value", ["7", "65"])
def test_password_min_length_outside_8_to_64_refuses_to_start(value):
    out = _run("import app.config", PASSWORD_MIN_LENGTH=value)
    assert out.returncode != 0 and "PASSWORD_MIN_LENGTH must be between 8 and 64" in out.stderr


def test_login_table_is_not_created_while_the_login_log_is_off():
    """main.py creates login_events only with LOGIN_AUDIT=true: a local database keeps 25 tables."""
    assert "login_events" not in models.Base.metadata.tables
    code = ("from app import models; "
            "calls = []; models.AuditBase.metadata.create_all = lambda **k: calls.append(1); "
            "import main; print(len(calls))")
    assert _run(code).stdout.strip().splitlines()[-1] == "0"
    assert _run(code, LOGIN_AUDIT="true").stdout.strip().splitlines()[-1] == "1"


def test_defaults_login_response_and_token_are_unchanged(client, db):
    _add_user(db)
    r = _login(client)
    assert r.status_code == 200
    assert set(r.json()) == {"access_token", "token_type", "role"}  # no last_login
    claims = _claims(r.json()["access_token"])
    assert set(claims) == {"sub", "role", "exp"}  # no password fingerprint
    lifetime = datetime.fromtimestamp(claims["exp"], timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(minutes=59) < lifetime <= timedelta(minutes=60)


def test_defaults_password_change_keeps_old_tokens_and_returns_no_token(client, db):
    _add_user(db)
    old = _login(client).json()["access_token"]
    r = client.post("/users/me/password", headers=_bearer(old),
                    json={"current_password": OLD_PW, "new_password": NEW_PW})
    assert r.status_code == 200 and r.json() == {"message": "Password changed."}
    assert client.get("/ml/models", headers=_bearer(old)).status_code == 200  # today: still valid


def test_defaults_password_rule_is_todays(db):
    assert password_rule_error("ab345678") is None
    assert password_rule_error("ab34567") == PASSWORD_RULE_MESSAGE
    assert password_rule_error("password1") is None            # common: allowed by default
    assert password_rule_error("zztestoscar1", "ZZTEST Oscar") is None  # has the username: allowed


def test_defaults_log_no_login_line(client, db, caplog):
    _add_user(db)
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client)
        _login(client, password="wrong-pass1")
    assert [r for r in caplog.records if r.name == "firemap.login"] == []


# ---- 1c token lifetime ----

def test_token_minutes_sets_the_lifetime(client, db, monkeypatch):
    monkeypatch.setattr(settings, "TOKEN_MINUTES", 30)
    _add_user(db)
    exp = _claims(_login(client).json()["access_token"])["exp"]
    lifetime = datetime.fromtimestamp(exp, timezone.utc) - datetime.now(timezone.utc)
    assert timedelta(minutes=29) < lifetime <= timedelta(minutes=30)


def test_an_expired_token_is_refused(client, db, monkeypatch):
    _add_user(db)
    expired = jwt.encode({"sub": "ZZTEST Oscar", "exp": datetime.now(timezone.utc) - timedelta(seconds=1)},
                         settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert client.get("/ml/models", headers=_bearer(expired)).status_code == 401


# ---- 1a sessions end when the password changes ----

def test_password_change_ends_every_other_session_and_keeps_the_changer_logged_in(client, db, session_switch):
    _add_user(db)
    device_a = _login(client).json()["access_token"]
    device_b = _login(client).json()["access_token"]
    assert client.get("/ml/models", headers=_bearer(device_b)).status_code == 200

    r = client.post("/users/me/password", headers=_bearer(device_a),
                    json={"current_password": OLD_PW, "new_password": NEW_PW})
    assert r.status_code == 200
    new_token = r.json()["access_token"]

    for old in (device_a, device_b):
        r = client.get("/ml/models", headers=_bearer(old))
        assert r.status_code == 401
        assert r.json()["detail"] == SESSION_ENDED_MESSAGE  # the Login page shows this text
    assert SESSION_ENDED_MESSAGE == "Your password was changed. Please log in again."
    assert client.get("/ml/models", headers=_bearer(new_token)).status_code == 200


def test_a_password_reset_in_the_database_also_ends_sessions(client, db, session_switch):
    """There is no admin-reset endpoint; an administrator's SQL reset is covered all the same."""
    user = _add_user(db)
    token = _login(client).json()["access_token"]
    user.password = hash_password("zz-reset-by-admin1")
    db.flush()
    assert client.get("/ml/models", headers=_bearer(token)).status_code == 401


def test_a_token_without_or_with_a_forged_fingerprint_is_refused(client, db, session_switch):
    user = _add_user(db)
    no_claim = create_access_token({"sub": user.username, "role": user.role})  # e.g. issued before the switch
    forged = create_access_token({"sub": user.username, "role": user.role, "pwf": "0" * 32})
    for token in (no_claim, forged):
        r = client.get("/ml/models", headers=_bearer(token))
        assert r.status_code == 401 and r.json()["detail"] == SESSION_ENDED_MESSAGE
    assert client.get("/ml/models", headers=_bearer(token_for_user(user))).status_code == 200


def test_the_fingerprint_reveals_nothing_about_the_hash(db, session_switch):
    user = _add_user(db)
    claim = _claims(token_for_user(user))["pwf"]
    assert len(claim) == 32 and claim not in user.password
    assert claim == password_fingerprint(user.password)
    assert claim != password_fingerprint(hash_password(OLD_PW))  # new salt, new hash: different


# ---- 3 password rule ----

def test_common_password_list_is_bundled_and_loaded():
    assert common_passwords.LIST_PATH.name == "common_passwords.txt"
    assert len(common_passwords._common()) >= 9900
    assert common_passwords.is_common("PASSWORD") and common_passwords.is_common("qwerty")
    assert not common_passwords.is_common("zz-oscar-newpass2")


def test_hosted_rule_minimum_length(hosted_rule):
    message = "Password must be at least 12 characters and include at least 2 letters."
    assert password_rule_error("zq-river-77") == message          # 11 characters
    assert password_rule_error("zq-river-779") is None             # 12 characters


@pytest.mark.parametrize("password", ["baseball1234", "Passwordxx99", "1qaz2wsx3edc", "PASSWORD1234"])
def test_hosted_rule_blocks_common_passwords(hosted_rule, monkeypatch, password):
    monkeypatch.setattr(common_passwords, "_common", lambda: frozenset({"baseball1234", "passwordxx99",
                                                                       "1qaz2wsx3edc", "password1234"}))
    assert password_rule_error(password, "ZZTEST Oscar") == PASSWORD_COMMON_MESSAGE


def test_real_list_entries_of_12_or_more_characters_are_blocked(hosted_rule):
    long_common = sorted(p for p in common_passwords._common() if len(p) >= 12
                         and sum(c.isalpha() for c in p) >= 2)
    assert long_common, "the list has no 12+ character entries with 2 letters"
    for p in long_common:
        assert password_rule_error(p) == PASSWORD_COMMON_MESSAGE, p


@pytest.mark.parametrize("password", ["myZZTESTOscar-77", "zztest oscar 77!", "oscar-garden-77"])
def test_hosted_rule_blocks_the_username(hosted_rule, password):
    assert password_rule_error(password, "ZZTEST Oscar") == PASSWORD_HAS_USERNAME_MESSAGE


def test_hosted_rule_applies_on_create_and_change_but_not_login(client, db, hosted_rule, monkeypatch):
    manager = _add_user(db, "ZZTEST Papa Manager", "zz-papa-pass1", role="manager")
    r = client.post("/users", headers=_bearer(token_for_user(manager)),
                    json={"username": "ZZTEST Quebec", "password": "quebec-garden-77"})
    assert r.status_code == 400 and r.json()["detail"] == PASSWORD_HAS_USERNAME_MESSAGE
    r = client.post("/users", headers=_bearer(token_for_user(manager)),
                    json={"username": "ZZTEST Quebec", "password": "short-pw1"})
    assert r.json()["detail"] == "Password must be at least 12 characters and include at least 2 letters."

    _add_user(db, "ZZTEST Oscar", "ab123456")  # old 8-character password still logs in
    token = _login(client, password="ab123456").json()["access_token"]
    monkeypatch.setattr(common_passwords, "_common", lambda: frozenset({"sunflower-1234"}))
    r = client.post("/users/me/password", headers=_bearer(token),
                    json={"current_password": "ab123456", "new_password": "Sunflower-1234"})
    assert r.status_code == 400 and r.json()["detail"] == PASSWORD_COMMON_MESSAGE
    r = client.post("/users/me/password", headers=_bearer(token),
                    json={"current_password": "ab123456", "new_password": "violet-harbor-58"})
    assert r.status_code == 200


# ---- 2 + 1d login attempt log and "Last login" ----

def test_every_result_is_logged_once_without_the_password(client, db, audit, caplog, monkeypatch):
    from app.services import login_limiter
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    user = _add_user(db)
    xff = {"X-Forwarded-For": "10.1.1.1, 203.0.113.9"}  # leftmost is client-made; Render adds the last
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        assert _login(client, **xff).status_code == 200
        assert _login(client, password="zz-secret-typo1", **xff).status_code == 401
        assert _login(client, username="ZZTEST Nobody Romeo", password="zz-secret-typo2", **xff).status_code == 401
        monkeypatch.setattr(login_limiter, "is_locked", lambda key: True)
        assert _login(client, password="zz-secret-typo3", **xff).status_code == 429

    lines = [r.getMessage() for r in caplog.records if r.name == "firemap.login"]
    assert len(lines) == 4
    for line, result, name in zip(lines, ["success", "wrong_password", "unknown_user", "locked"],
                                  ["ZZTEST Oscar", "ZZTEST Oscar", "ZZTEST Nobody Romeo", "ZZTEST Oscar"]):
        assert line.startswith("login time=") and line.endswith(f"user='{name}' ip=203.0.113.9 result={result}")
    assert not any(pw in caplog.text for pw in (OLD_PW, "zz-secret-typo1", "zz-secret-typo2", "zz-secret-typo3"))

    rows = _events(db, "ZZTEST Oscar") + _events(db, "ZZTEST Nobody Romeo")
    assert sorted((e.result, e.user_id, e.ip_address) for e in rows) == sorted([
        ("success", user.id, "203.0.113.9"), ("wrong_password", user.id, "203.0.113.9"),
        ("unknown_user", None, "203.0.113.9"), ("locked", None, "203.0.113.9")])
    assert {c["name"] for c in inspect(engine).get_columns("login_events")} == {
        "id", "occurred_at", "user_id", "username", "ip_address", "result"}  # nothing else stored


def test_a_newline_in_the_username_cannot_fake_a_log_line(client, db, audit, caplog):
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client, username="ZZTEST Sierra\nINFO: login user='admin' result=success", password="x")
    lines = [r.getMessage() for r in caplog.records if r.name == "firemap.login"]
    assert len(lines) == 1 and "\n" not in lines[0] and "\\n" in lines[0]


def test_last_login_is_the_previous_success_not_this_one(client, db, audit, monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    _add_user(db)
    first = _login(client, **{"X-Forwarded-For": "198.51.100.1"})
    assert first.json()["last_login"] is None  # first recorded login
    _login(client, password="wrong-pass1", **{"X-Forwarded-For": "198.51.100.66"})  # failures don't count
    second = _login(client, **{"X-Forwarded-For": "198.51.100.2"})
    last = second.json()["last_login"]
    assert last["ip"] == "198.51.100.1"
    first_row = [e for e in _events(db, "ZZTEST Oscar") if e.result == "success"][0]
    assert last["at"] == first_row.occurred_at.isoformat(timespec="seconds") + "Z"
    assert _login(client, **{"X-Forwarded-For": "198.51.100.3"}).json()["last_login"]["ip"] == "198.51.100.2"


def test_rows_older_than_90_days_are_removed(client, db, audit):
    user = _add_user(db)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for days in (91, 89):
        db.add(models.LoginEvent(occurred_at=now - timedelta(days=days), user_id=user.id,
                                 username="ZZTEST Oscar", ip_address="192.0.2.1", result="success"))
    db.flush()
    _login(client)
    ages = sorted(round((now - e.occurred_at).total_seconds() / 86400) for e in _events(db, "ZZTEST Oscar"))
    assert ages == [0, 89]
    assert login_audit.RETENTION_DAYS == 90


def test_a_broken_login_log_never_blocks_the_login(client, db, audit, monkeypatch, caplog):
    _add_user(db)
    monkeypatch.setattr(models, "LoginEvent", None)  # any use of the table now fails
    with caplog.at_level(logging.ERROR, logger="firemap.login"):
        r = _login(client)
    assert r.status_code == 200 and r.json()["last_login"] is None
    assert "could not" in caplog.text
