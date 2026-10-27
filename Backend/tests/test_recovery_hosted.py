"""Forgot password with recovery codes on the hosted copy (branch deploy-ias2): the recovery routes
follow the IAS2 switches exactly like the login and Change Password.

2  client IP: the forgot-password / code-change limit and account_events.ip_address use
   login_limiter.client_ip() (TRUSTED_PROXY_HOPS / CLIENT_IP_SOURCE), so Render's proxy is not one IP
3  password rule: forgot password, the forced "Set a new password", scripts/reset_password.py and the
   Manager's temporary password follow PASSWORD_MIN_LENGTH / PASSWORD_BLOCK_COMMON + the username check
6  sessions (SESSION_ENDS_ON_PASSWORD_CHANGE): the forced step keeps its own user logged in; a
   forgot-password reset or a Manager reset ends that user's older tokens
7  the login response: must_change_password and the "Not you?" notice, next to "Last login"

Needs scripts/2026-10-26_recovery_codes.sql on the test database. ZZTEST users inside the rolled-back
`db` fixture, made-up passwords, TestClient WITHOUT `with`; no code or password is ever printed."""
import importlib.util
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import models
from app.config import settings
from app.database import engine, get_db
from app.routers import account_recovery
from app.security import (PASSWORD_COMMON_MESSAGE, PASSWORD_HAS_USERNAME_MESSAGE, SESSION_ENDED_MESSAGE,
                          hash_password, password_rule_error, token_for_user, verify_password)
from app.services import attempt_limiter, common_passwords, login_limiter, recovery
from main import app

PASSWORD = "zz-kilo-pass1"
GOOD_NEW = "violet-harbor-58"          # 16 characters, no username, not on the (patched) list
HOSTED_LENGTH_MESSAGE = "Password must be at least 12 characters and include at least 2 letters."
CODE = re.compile(r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}")


def _add_user(db, username, password=PASSWORD, role="admin", code=None, must_change=False):
    user = models.User(username=username, password=hash_password(password), role=role,
                       must_change_password=must_change)
    if code:
        user.recovery_code_hash = recovery.hash_code(code)
    db.add(user)
    db.flush()
    return user


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _login(client, username, password=PASSWORD, **headers):
    return client.post("/login", json={"username": username, "password": password}, headers=headers)


def _forgot(client, username, code, new_password=GOOD_NEW, **headers):
    return client.post("/auth/forgot-password", headers=headers,
                       json={"username": username, "recovery_code": code, "new_password": new_password})


def _events(db, user):
    return db.query(models.AccountEvent).filter_by(user_id=user.id).order_by(models.AccountEvent.id).all()


@pytest.fixture
def client(db):
    account_recovery.forgot_limiter.clear()
    account_recovery.code_change_limiter.clear()
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        account_recovery.forgot_limiter.clear()
        account_recovery.code_change_limiter.clear()


@pytest.fixture
def behind_proxy(monkeypatch):
    """Render: TRUSTED_PROXY_HOPS=1 (the last X-Forwarded-For entry is the client)."""
    monkeypatch.setattr(settings, "CLIENT_IP_SOURCE", "xff_hops")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)


@pytest.fixture
def hosted_rule(monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_MIN_LENGTH", 12)
    monkeypatch.setattr(settings, "PASSWORD_BLOCK_COMMON", True)
    monkeypatch.setattr(common_passwords, "_common", lambda: frozenset({"sunflower-1234"}))


@pytest.fixture
def session_switch(monkeypatch):
    monkeypatch.setattr(settings, "SESSION_ENDS_ON_PASSWORD_CHANGE", True)


def _xff(ip):
    return {"X-Forwarded-For": f"10.9.9.9, {ip}"}  # leftmost is client-made; Render appends the last


# ---- 2 client IP ----

def _request(xff):
    return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())], "client": ("10.0.0.1", 50000)})


def test_attempt_limiter_uses_the_login_client_ip_rule(behind_proxy, monkeypatch):
    request = _request("10.9.9.9, 203.0.113.7")
    assert attempt_limiter.client_ip(request) == login_limiter.client_ip(request) == "203.0.113.7"
    assert attempt_limiter.key_for(request, " ZZTEST Kilo ") == ("203.0.113.7", "zztest kilo")
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 0)  # unset = the laptop: the connection's address
    assert attempt_limiter.client_ip(request) == "10.0.0.1"


def test_one_person_behind_the_proxy_cannot_lock_everyone_out(client, db, behind_proxy):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Kilo Lock", code=code)
    for _ in range(5):
        assert _forgot(client, "ZZTEST Kilo Lock", recovery.new_code(), **_xff("198.51.100.1")).status_code == 400
    assert _forgot(client, "ZZTEST Kilo Lock", code, **_xff("198.51.100.1")).status_code == 429
    # Same username from another client IP (same proxy connection): not locked.
    assert _forgot(client, "ZZTEST Kilo Lock", code, **_xff("198.51.100.2")).status_code == 200


def test_account_events_store_the_proxied_client_ip(client, db, behind_proxy):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Lima Event", code=code)
    assert _forgot(client, "ZZTEST Lima Event", code, **_xff("198.51.100.20")).status_code == 200
    manager = _add_user(db, "ZZTEST Lima Manager", role="manager")
    r = client.post(f"/users/{user.id}/reset-password", headers={**_bearer(token_for_user(manager)),
                                                                 **_xff("198.51.100.21")})
    assert r.status_code == 200
    assert [(e.event, e.ip_address) for e in _events(db, user)] == [
        (recovery.CODE_USED_RESET, "198.51.100.20"), (recovery.MANAGER_RESET, "198.51.100.21")]


# ---- 3 password rule ----

@pytest.mark.parametrize("new_password, message", [
    ("zq-river-77", HOSTED_LENGTH_MESSAGE),                 # 11 characters
    ("Sunflower-1234", PASSWORD_COMMON_MESSAGE),
    ("mike-garden-77", PASSWORD_HAS_USERNAME_MESSAGE),      # "mike" is a word of the username
])
def test_forgot_password_follows_the_hosted_rule(client, db, hosted_rule, new_password, message):
    code = recovery.new_code()
    user = _add_user(db, "ZZTEST Mike Forgot", code=code)
    old_hash = user.password
    r = _forgot(client, "ZZTEST Mike Forgot", code, new_password)
    assert (r.status_code, r.json()["detail"]) == (400, message)
    db.refresh(user)
    assert user.password == old_hash and recovery.verify_code(code, user.recovery_code_hash)
    assert _forgot(client, "ZZTEST Mike Forgot", code).status_code == 200


def test_forgot_password_default_rule_is_unchanged(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Mike Default", code=code)
    assert _forgot(client, "ZZTEST Mike Default", code, "mike1234").status_code == 200  # 8 chars, username ok


def test_forced_new_password_follows_the_hosted_rule(client, db, hosted_rule):
    temp = recovery.temporary_password("ZZTEST November Temp")
    _add_user(db, "ZZTEST November Temp", password=temp, must_change=True)
    token = _login(client, "ZZTEST November Temp", temp).json()["access_token"]
    for bad, message in (("november-77-xy", PASSWORD_HAS_USERNAME_MESSAGE), ("short-pw1", HOSTED_LENGTH_MESSAGE),
                         ("Sunflower-1234", PASSWORD_COMMON_MESSAGE)):
        r = client.post("/users/me/password", headers=_bearer(token),
                        json={"current_password": temp, "new_password": bad})
        assert (r.status_code, r.json()["detail"]) == (400, message), bad
    r = client.post("/users/me/password", headers=_bearer(token),
                    json={"current_password": temp, "new_password": GOOD_NEW})
    assert r.status_code == 200


class _KeepOpen:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        pass


def _run_script(db, username, password):
    path = Path(__file__).resolve().parents[1] / "scripts" / "reset_password.py"
    spec = importlib.util.spec_from_file_location("reset_password_script_hosted", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    answers = iter([username, "yes"])
    out = []
    result = script.main(ask=lambda _: next(answers), ask_secret=lambda _: password,
                         out=out.append, session_factory=lambda: _KeepOpen(db))
    return result, out


def test_reset_password_script_follows_the_hosted_rule(db, hosted_rule):
    user = _add_user(db, "ZZTEST Oscar Script")
    old_hash = user.password
    result, out = _run_script(db, "ZZTEST Oscar Script", "oscar-garden-77")
    assert result == 1 and out[-1].startswith(PASSWORD_HAS_USERNAME_MESSAGE)
    db.refresh(user)
    assert user.password == old_hash and user.recovery_code_hash is None
    result, out = _run_script(db, "ZZTEST Oscar Script", GOOD_NEW)
    assert result == 0 and CODE.search(out[-1])
    db.refresh(user)
    assert verify_password(GOOD_NEW, user.password)


@pytest.mark.parametrize("min_length", [12, 20])
def test_temporary_password_passes_the_hosted_rule(monkeypatch, hosted_rule, min_length):
    monkeypatch.setattr(settings, "PASSWORD_MIN_LENGTH", min_length)
    for _ in range(20):
        temp = recovery.temporary_password("ZZTEST Papa Temp")
        assert len(temp) == max(12, min_length)
        assert password_rule_error(temp, "ZZTEST Papa Temp") is None


def test_temporary_password_never_contains_the_username(monkeypatch, hosted_rule):
    # The first draw spells the username word "papa" (blocked), the second is clean: the second is used.
    draws = iter("papapapapapa" + "xk7mxk7mxk7m")
    monkeypatch.setattr(recovery.secrets, "choice", lambda _alphabet: next(draws))
    assert recovery.temporary_password("ZZTEST Papa Temp") == "xk7mxk7mxk7m"


def test_manager_reset_temporary_password_passes_the_hosted_rule(client, db, hosted_rule, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_MIN_LENGTH", 16)
    manager = _add_user(db, "ZZTEST Quebec Manager", role="manager")
    staff = _add_user(db, "ZZTEST Quebec Staff")
    r = client.post(f"/users/{staff.id}/reset-password", headers=_bearer(token_for_user(manager)))
    temp = r.json()["temporary_password"]
    assert r.status_code == 200 and len(temp) == 16
    assert password_rule_error(temp, "ZZTEST Quebec Staff") is None


# ---- 6 sessions end on password change ----

def test_forced_step_keeps_its_own_user_logged_in(client, db, session_switch):
    manager = _add_user(db, "ZZTEST Romeo Manager", role="manager")
    staff = _add_user(db, "ZZTEST Romeo Staff")
    temp = client.post(f"/users/{staff.id}/reset-password",
                       headers=_bearer(token_for_user(manager))).json()["temporary_password"]
    login = _login(client, "ZZTEST Romeo Staff", temp).json()
    assert login["must_change_password"] is True
    old = _bearer(login["access_token"])
    assert client.get("/users/me/account-status", headers=old).status_code == 200
    assert client.get("/users/me/recovery-code", headers=old).status_code == 403  # change required

    r = client.post("/users/me/password", headers=old, json={"current_password": temp, "new_password": GOOD_NEW})
    assert r.status_code == 200
    new = _bearer(r.json()["access_token"])                      # AccountGuards stores this one
    assert client.get("/users/me/recovery-code", headers=new).status_code == 200
    assert client.get("/users/me/account-status", headers=new).json()["must_change_password"] is False
    r = client.get("/users/me/recovery-code", headers=old)        # the temporary-password token ended
    assert (r.status_code, r.json()["detail"]) == (401, SESSION_ENDED_MESSAGE)


def test_forgot_password_reset_ends_older_tokens(client, db, session_switch):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Sierra Forgot", code=code)
    old = _bearer(_login(client, "ZZTEST Sierra Forgot").json()["access_token"])
    assert client.get("/users/me/recovery-code", headers=old).status_code == 200
    assert _forgot(client, "ZZTEST Sierra Forgot", code).status_code == 200
    r = client.get("/users/me/recovery-code", headers=old)
    assert (r.status_code, r.json()["detail"]) == (401, SESSION_ENDED_MESSAGE)
    new = _bearer(_login(client, "ZZTEST Sierra Forgot", GOOD_NEW).json()["access_token"])
    assert client.get("/users/me/recovery-code", headers=new).status_code == 200


def test_manager_reset_ends_the_users_older_tokens_not_the_managers(client, db, session_switch):
    manager = _add_user(db, "ZZTEST Tango Manager", role="manager")
    staff = _add_user(db, "ZZTEST Tango Staff")
    manager_token = _bearer(_login(client, "ZZTEST Tango Manager").json()["access_token"])
    old = _bearer(_login(client, "ZZTEST Tango Staff").json()["access_token"])
    assert client.post(f"/users/{staff.id}/reset-password", headers=manager_token).status_code == 200
    r = client.get("/users/me/account-status", headers=old)
    assert (r.status_code, r.json()["detail"]) == (401, SESSION_ENDED_MESSAGE)
    assert client.get("/users/staff", headers=manager_token).status_code == 200


def test_without_the_switch_older_tokens_keep_working(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Uniform Laptop", code=code)
    old = _bearer(_login(client, "ZZTEST Uniform Laptop").json()["access_token"])
    assert _forgot(client, "ZZTEST Uniform Laptop", code).status_code == 200
    assert client.get("/users/me/recovery-code", headers=old).status_code == 200  # laptop behaviour


# ---- 7 the login response ----

def test_login_returns_must_change_password_and_the_notice(client, db):
    code = recovery.new_code()
    _add_user(db, "ZZTEST Victor Login", code=code)
    body = _login(client, "ZZTEST Victor Login").json()
    assert body["must_change_password"] is False and body["notice"] is None
    assert _forgot(client, "ZZTEST Victor Login", code).status_code == 200
    body = _login(client, "ZZTEST Victor Login", GOOD_NEW).json()
    assert set(body["notice"]) == {"id", "event", "occurred_at", "ip_address"}
    assert body["notice"]["event"] == recovery.CODE_USED_RESET
    status = client.get("/users/me/account-status", headers=_bearer(body["access_token"])).json()
    assert status["notice"] == body["notice"]


def test_login_keeps_last_login_next_to_the_new_fields(client, db, monkeypatch):
    if engine.url.database == "insurance_db":
        pytest.skip("login_events tests run on a scratch copy, never on the local insurance_db")
    models.AuditBase.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "LOGIN_AUDIT", True)
    _add_user(db, "ZZTEST Whiskey Audit", must_change=True)
    assert _login(client, "ZZTEST Whiskey Audit").json()["last_login"] is None
    body = _login(client, "ZZTEST Whiskey Audit").json()
    assert body["last_login"] is not None and body["must_change_password"] is True
    assert {"access_token", "token_type", "role", "must_change_password", "notice", "last_login"} == set(body)
