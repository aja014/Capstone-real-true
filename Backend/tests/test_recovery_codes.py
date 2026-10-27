"""Forgot password with recovery codes (2026-10-26): code format and hashing, POST /auth/forgot-password,
the recovery code in Settings, the Manager's Reset a Password, the forced password change and
account_events.

Needs scripts/2026-10-26_recovery_codes.sql on the test database. Every user here is a temporary
ZZTEST user inside the rolled-back `db` fixture; the real accounts are never read or changed. All
passwords are made-up test strings, and no code or password is ever printed.
TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
import importlib.util
import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.routers import account_recovery
from app.security import create_access_token, hash_password, password_rule_error, verify_password
from app.services import recovery
from main import app

PASSWORD = "ab123456"
NEW_PASSWORD = "cd654321"
INVALID = "Invalid username or recovery code"
CODE_FORMAT = re.compile(r"^[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{4}(-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{4}){2}$")


def _add_user(db, username, password=PASSWORD, role="admin", code=None, must_change=False):
    user = models.User(username=username, password=hash_password(password), role=role,
                       must_change_password=must_change)
    if code:
        user.recovery_code_hash = recovery.hash_code(code)
    db.add(user)
    db.flush()
    return user


def _auth(username):
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


def _events(db, user):
    return db.query(models.AccountEvent).filter_by(user_id=user.id).order_by(models.AccountEvent.id).all()


def _login(client, username, password):
    return client.post("/login", json={"username": username, "password": password}).status_code


def _forgot(client, username, code, new_password=NEW_PASSWORD):
    return client.post("/auth/forgot-password",
                       json={"username": username, "recovery_code": code, "new_password": new_password})


@pytest.fixture
def client(db):
    """Real login checks (get_current_user runs), on the rolled-back test session."""
    account_recovery.forgot_limiter.clear()
    account_recovery.code_change_limiter.clear()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        account_recovery.forgot_limiter.clear()
        account_recovery.code_change_limiter.clear()


# ---- the code itself ----

def test_code_format_and_alphabet():
    codes = {recovery.new_code() for _ in range(200)}
    assert len(codes) == 200
    assert all(CODE_FORMAT.match(c) for c in codes)
    assert not set("0O1IL") & set(recovery.ALPHABET)


def test_code_is_stored_only_as_a_hash_and_compared_loosely():
    code = recovery.new_code()
    stored = recovery.hash_code(code)
    assert stored.startswith("$2b$") and code not in stored and code.replace("-", "") not in stored
    assert recovery.verify_code(code, stored)
    assert recovery.verify_code(" " + code.replace("-", " ").lower() + " ", stored)  # spaces, case
    assert recovery.verify_code(code.replace("-", ""), stored)
    assert not recovery.verify_code(recovery.new_code(), stored)
    assert not recovery.verify_code("", stored) and not recovery.verify_code(None, stored)
    assert not recovery.verify_code(code, None)


def test_temporary_password_passes_the_rule():
    for _ in range(20):
        password = recovery.temporary_password()
        assert len(password) >= 12 and password_rule_error(password) is None


# ---- POST /auth/forgot-password ----

def test_forgot_password_with_right_code(client, db):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Alpha Forgot", code=code)
    r = _forgot(client, "zztest alpha forgot ", code.lower())   # username and code typed loosely
    assert r.status_code == 200
    new_code = r.json()["recovery_code"]
    assert set(r.json()) == {"recovery_code"} and CODE_FORMAT.match(new_code) and new_code != code
    assert _login(client, "ZZTEST Alpha Forgot", NEW_PASSWORD) == 200
    assert _login(client, "ZZTEST Alpha Forgot", PASSWORD) == 401
    db.refresh(user)
    assert recovery.verify_code(new_code, user.recovery_code_hash)
    assert [e.event for e in _events(db, user)] == [recovery.CODE_USED_RESET]
    assert _events(db, user)[0].ip_address == "testclient"


def test_code_is_single_use(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Bravo Once", code=code)
    new_code = _forgot(client, "ZZTEST Bravo Once", code).json()["recovery_code"]
    r = _forgot(client, "ZZTEST Bravo Once", code, "ef112233")
    assert r.status_code == 400 and r.json()["detail"] == INVALID
    assert _forgot(client, "ZZTEST Bravo Once", new_code, "ef112233").status_code == 200


def test_wrong_code_unknown_user_and_no_code_give_the_same_answer(client, db):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Charlie Wrong", code=code)
    _add_user(db, "ZZTEST Delta NoCode")
    answers = [
        _forgot(client, "ZZTEST Charlie Wrong", recovery.new_code()),
        _forgot(client, "ZZTEST Charlie Wrong", "not a code"),
        _forgot(client, "ZZTEST Nobody Here", code),
        _forgot(client, "ZZTEST Delta NoCode", code),
    ]
    assert {(r.status_code, r.json()["detail"]) for r in answers} == {(400, INVALID)}
    old_hash = user.password
    db.refresh(user)
    assert user.password == old_hash and _events(db, user) == []


def test_weak_new_password_is_refused_and_the_code_still_works(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Echo Weak", code=code)
    r = _forgot(client, "ZZTEST Echo Weak", code, "12345678")
    assert r.status_code == 400 and r.json()["detail"] == password_rule_error("12345678")
    assert _forgot(client, "ZZTEST Echo Weak", code).status_code == 200


def test_429_after_five_failures(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Foxtrot Lock", code=code)
    for _ in range(5):
        assert _forgot(client, "ZZTEST Foxtrot Lock", recovery.new_code()).status_code == 400
    r = _forgot(client, "ZZTEST Foxtrot Lock", code)   # even the right code is refused now
    assert r.status_code == 429
    assert r.json()["detail"] == "Too many attempts. Please try again in 5 minutes."
    assert r.headers["Retry-After"] == "300"
    assert _login(client, "ZZTEST Foxtrot Lock", PASSWORD) == 200   # the login itself is not locked
    # Another username from the same IP is not locked.
    other = recovery.new_code()
    _add_user(db, "ZZTEST Golf Free", code=other)
    assert _forgot(client, "ZZTEST Golf Free", other).status_code == 200


def test_lock_ends_after_five_minutes(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Hotel Wait", code=code)
    limiter = account_recovery.forgot_limiter
    real_now, clock = limiter._now, [1000.0]
    limiter._now = lambda: clock[0]
    try:
        for _ in range(5):
            _forgot(client, "ZZTEST Hotel Wait", recovery.new_code())
        assert _forgot(client, "ZZTEST Hotel Wait", code).status_code == 429
        clock[0] += 301
        assert _forgot(client, "ZZTEST Hotel Wait", code).status_code == 200
    finally:
        limiter._now = real_now


def test_forgot_password_clears_the_temporary_password_flag(client, db):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST India Temp", code=code, must_change=True)
    assert _forgot(client, "ZZTEST India Temp", code).status_code == 200
    db.refresh(user)
    assert user.must_change_password is False


# ---- Settings: recovery code ----

def test_first_code_needs_only_the_password(client, db):
    user = _add_user(db, "ZZTEST Juliet First")
    assert client.get("/users/me/recovery-code", headers=_auth("ZZTEST Juliet First")).json() == \
        {"has_code": False, "set_at": None}
    r = client.post("/users/me/recovery-code", headers=_auth("ZZTEST Juliet First"),
                    json={"current_password": PASSWORD})
    assert r.status_code == 200
    db.refresh(user)
    assert recovery.verify_code(r.json()["recovery_code"], user.recovery_code_hash)
    status = client.get("/users/me/recovery-code", headers=_auth("ZZTEST Juliet First")).json()
    assert status["has_code"] is True and status["set_at"] and set(status) == {"has_code", "set_at"}
    assert [e.event for e in _events(db, user)] == [recovery.CODE_CREATED]


def test_first_code_refuses_a_wrong_password(client, db):
    user = _add_user(db, "ZZTEST Kilo WrongPw")
    r = client.post("/users/me/recovery-code", headers=_auth("ZZTEST Kilo WrongPw"),
                    json={"current_password": "wrong-pass1"})
    assert r.status_code == 400 and r.json()["detail"] == "Current password is incorrect."
    db.refresh(user)
    assert user.recovery_code_hash is None


@pytest.mark.parametrize("password, code_kind, message", [
    (PASSWORD, None, "Current recovery code is incorrect."),        # password alone is not enough
    (PASSWORD, "wrong", "Current recovery code is incorrect."),
    ("wrong-pass1", "right", "Current password is incorrect."),     # code alone is not enough
])
def test_changing_a_code_needs_password_and_old_code(client, db, password, code_kind, message):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Lima Change", code=code)
    body = {"current_password": password}
    if code_kind:
        body["current_code"] = code if code_kind == "right" else recovery.new_code()
    r = client.post("/users/me/recovery-code", headers=_auth("ZZTEST Lima Change"), json=body)
    assert r.status_code == 400 and r.json()["detail"] == message
    db.refresh(user)
    assert recovery.verify_code(code, user.recovery_code_hash)


def test_changing_a_code_with_both(client, db):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Mike Change", code=code)
    r = client.post("/users/me/recovery-code", headers=_auth("ZZTEST Mike Change"),
                    json={"current_password": PASSWORD, "current_code": code})
    assert r.status_code == 200
    db.refresh(user)
    assert recovery.verify_code(r.json()["recovery_code"], user.recovery_code_hash)
    assert not recovery.verify_code(code, user.recovery_code_hash)
    assert [e.event for e in _events(db, user)] == [recovery.CODE_CHANGED]


def test_code_change_is_limited_too(client, db):
    _add_user(db, "ZZTEST November Lock", code=recovery.new_code())
    for _ in range(5):
        client.post("/users/me/recovery-code", headers=_auth("ZZTEST November Lock"),
                    json={"current_password": PASSWORD, "current_code": recovery.new_code()})
    r = client.post("/users/me/recovery-code", headers=_auth("ZZTEST November Lock"),
                    json={"current_password": PASSWORD})
    assert r.status_code == 429


# ---- Create Account gives the first code ----

def test_create_account_returns_a_working_code(client, db):
    _add_user(db, "ZZTEST Oscar Manager", role="manager")
    r = client.post("/users", headers=_auth("ZZTEST Oscar Manager"),
                    json={"username": "ZZTEST Papa Staff", "password": PASSWORD})
    assert r.status_code == 200
    code = r.json()["recovery_code"]
    staff = db.query(models.User).filter_by(username="ZZTEST Papa Staff").one()
    assert CODE_FORMAT.match(code) and recovery.verify_code(code, staff.recovery_code_hash)
    event = _events(db, staff)[0]
    assert (event.event, event.actor_username) == (recovery.CODE_CREATED, "ZZTEST Oscar Manager")
    assert _forgot(client, "ZZTEST Papa Staff", code).status_code == 200


# ---- Reset a Password (Manager) ----

def test_staff_list_has_only_admin_accounts(client, db):
    _add_user(db, "ZZTEST Quebec Manager", role="manager")
    staff = _add_user(db, "ZZTEST Romeo Staff")
    r = client.get("/users/staff", headers=_auth("ZZTEST Quebec Manager"))
    assert r.status_code == 200
    rows = r.json()
    assert {"id": staff.id, "username": "ZZTEST Romeo Staff"} in rows
    assert all(set(row) == {"id", "username"} for row in rows)
    managers = {u.username for u in db.query(models.User).filter_by(role="manager")}
    assert not managers & {row["username"] for row in rows}


def test_staff_cannot_call_manager_routes(client, db):
    _add_user(db, "ZZTEST Sierra Staff")
    other = _add_user(db, "ZZTEST Tango Staff")
    assert client.get("/users/staff", headers=_auth("ZZTEST Sierra Staff")).status_code == 403
    r = client.post(f"/users/{other.id}/reset-password", headers=_auth("ZZTEST Sierra Staff"))
    assert r.status_code == 403 and r.json()["detail"] == "Manager access only."


def test_manager_cannot_reset_a_manager(client, db):
    _add_user(db, "ZZTEST Uniform Manager", role="manager")
    other = _add_user(db, "ZZTEST Victor Manager", role="manager")
    old_hash = other.password
    r = client.post(f"/users/{other.id}/reset-password", headers=_auth("ZZTEST Uniform Manager"))
    assert r.status_code == 403
    db.refresh(other)
    assert other.password == old_hash and other.must_change_password is False


def test_reset_of_a_missing_account_is_404(client, db):
    _add_user(db, "ZZTEST Whiskey Manager", role="manager")
    assert client.post("/users/999999999/reset-password", headers=_auth("ZZTEST Whiskey Manager")).status_code == 404


def test_manager_reset_then_forced_change(client, db):
    _add_user(db, "ZZTEST Xray Manager", role="manager")
    staff = _add_user(db, "ZZTEST Yankee Staff", code=recovery.new_code())
    r = client.post(f"/users/{staff.id}/reset-password", headers=_auth("ZZTEST Xray Manager"))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"username", "temporary_password", "recovery_code"}
    temp = body["temporary_password"]
    assert password_rule_error(temp) is None and _login(client, "ZZTEST Yankee Staff", temp) == 200

    me = _auth("ZZTEST Yankee Staff")
    # Every other route is blocked with 403 (not 401) until the password is changed ...
    for method, path in (("get", "/users/me/recovery-code"), ("get", "/policyholders"),
                         ("get", "/ml/models"), ("post", "/users/me/account-status/seen")):
        r = getattr(client, method)(path, headers=me, **({"json": {"id": 1}} if method == "post" else {}))
        assert (r.status_code, r.json()["detail"]) == (403, "Password change required"), path
    # ... except the account status and the password change.
    status = client.get("/users/me/account-status", headers=me).json()
    assert status["must_change_password"] is True and status["has_recovery_code"] is True
    assert status["notice"]["event"] == recovery.MANAGER_RESET
    r = client.post("/users/me/password", headers=me,
                    json={"current_password": temp, "new_password": NEW_PASSWORD})
    assert r.status_code == 200
    assert client.get("/users/me/recovery-code", headers=me).status_code == 200
    db.refresh(staff)
    assert staff.must_change_password is False
    assert recovery.verify_code(body["recovery_code"], staff.recovery_code_hash)
    events = _events(db, staff)
    assert [e.event for e in events] == [recovery.MANAGER_RESET, recovery.TEMP_PASSWORD_CHANGED]
    assert events[0].actor_username == "ZZTEST Xray Manager"


# ---- account status and the "Not you?" notice ----

def test_account_status_and_notice_seen(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Zulu Notice", code=code)
    me = _auth("ZZTEST Zulu Notice")
    assert client.get("/users/me/account-status", headers=me).json() == \
        {"must_change_password": False, "has_recovery_code": True, "notice": None}
    _forgot(client, "ZZTEST Zulu Notice", code)
    notice = client.get("/users/me/account-status", headers=me).json()["notice"]
    assert notice["event"] == recovery.CODE_USED_RESET and notice["ip_address"] == "testclient"
    assert set(notice) == {"id", "event", "occurred_at", "ip_address"}
    assert client.post("/users/me/account-status/seen", headers=me, json={"id": notice["id"]}).status_code == 200
    assert client.get("/users/me/account-status", headers=me).json()["notice"] is None


def test_code_created_shows_no_notice(client, db):
    _add_user(db, "ZZTEST Amber NoNotice")
    me = _auth("ZZTEST Amber NoNotice")
    client.post("/users/me/recovery-code", headers=me, json={"current_password": PASSWORD})
    assert client.get("/users/me/account-status", headers=me).json()["notice"] is None


def test_account_status_needs_login(client):
    assert client.get("/users/me/account-status").status_code == 401


# ---- nothing secret is stored in events, sent back or logged ----

def test_no_secret_in_events_responses_or_logs(client, db, caplog):
    caplog.set_level(logging.DEBUG)
    _add_user(db, "ZZTEST Basil Manager", role="manager")
    code = recovery.new_code()
    staff = _add_user(db, "ZZTEST Cedar Staff", code=code)
    secrets_seen = [code, PASSWORD, NEW_PASSWORD]
    texts = []

    r = _forgot(client, "ZZTEST Cedar Staff", code)
    secrets_seen.append(r.json()["recovery_code"])
    r2 = client.post(f"/users/{staff.id}/reset-password", headers=_auth("ZZTEST Basil Manager"))
    secrets_seen += [r2.json()["temporary_password"], r2.json()["recovery_code"]]
    texts.append(client.get("/users/me/account-status", headers=_auth("ZZTEST Cedar Staff")).text)
    texts.append(client.get("/users/staff", headers=_auth("ZZTEST Basil Manager")).text)

    db.refresh(staff)
    for e in _events(db, staff):
        texts.append(" ".join(str(v) for v in (e.event, e.actor_username, e.ip_address, e.occurred_at)))
    texts.append(caplog.text)
    blob = "\n".join(texts)
    for secret in secrets_seen:
        assert secret not in blob and secret.replace("-", "") not in blob
    assert staff.password not in blob and staff.recovery_code_hash not in blob


# ---- scripts/reset_password.py (system administrator) ----

class _KeepOpen:
    """The script closes its session; the test's rolled-back session must stay usable."""
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "reset_password.py"
    spec = importlib.util.spec_from_file_location("reset_password_script", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_reset_password_script(db):
    script = _load_script()
    user = _add_user(db, "ZZTEST Dahlia Manager", role="manager")
    answers = iter(["ZZTEST Dahlia Manager", "yes"])
    secrets_in = iter([NEW_PASSWORD, NEW_PASSWORD])
    out = []
    assert script.main(ask=lambda _: next(answers), ask_secret=lambda _: next(secrets_in),
                       out=out.append, session_factory=lambda: _KeepOpen(db)) == 0
    db.refresh(user)
    code = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}", out[-1]).group(0)
    assert recovery.verify_code(code, user.recovery_code_hash)
    assert verify_password(NEW_PASSWORD, user.password)
    assert user.must_change_password is True   # a new password of their own at the next login
    assert NEW_PASSWORD not in "\n".join(out)
    assert [(e.event, e.actor_username) for e in _events(db, user)] == [(recovery.CODE_CHANGED, "system administrator")]


def test_reset_password_script_applies_the_rule(db):
    script = _load_script()
    user = _add_user(db, "ZZTEST Elm Staff")
    old_hash = user.password
    answers = iter(["ZZTEST Elm Staff", "yes"])
    out = []
    assert script.main(ask=lambda _: next(answers), ask_secret=lambda _: "12345678",
                       out=out.append, session_factory=lambda: _KeepOpen(db)) == 1
    db.refresh(user)
    assert user.password == old_hash and user.recovery_code_hash is None
    assert user.must_change_password is False
