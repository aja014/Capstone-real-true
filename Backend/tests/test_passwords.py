"""Password rule (8-72 bytes, 2+ letters), POST /users and POST /users/me/password.

Every user here is a temporary ZZTEST user inside the rolled-back `db` fixture; the real
accounts are never read or changed. All passwords are made-up test strings.
TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.security import (PASSWORD_RULE_MESSAGE, PASSWORD_TOO_LONG_MESSAGE, create_access_token,
                          get_current_user, hash_password, password_rule_error)
from main import app

WEAK = ["abc1234",       # 7 characters
        "12345678",      # 8 digits, no letters
        "a1234567"]      # 1 letter + 7 digits
VALID = "ab123456"       # 2 letters + 6 digits


def _add_user(db, username, password, role="admin"):
    user = models.User(username=username, password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db):
    """Real login checks (get_current_user runs), but on the rolled-back test session."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def manager_client(db):
    manager = _add_user(db, "ZZTEST Manager", "zz-manager-pass", role="manager")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _auth(username):
    return {"Authorization": f"Bearer {create_access_token({'sub': username})}"}


# ---- the rule itself ----

@pytest.mark.parametrize("password", WEAK + ["", "AB"])
def test_rule_rejects_weak(password):
    assert password_rule_error(password) == PASSWORD_RULE_MESSAGE


@pytest.mark.parametrize("password", [VALID, "abcdefgh", "Zz" + "9" * 70])  # last one = 72 bytes
def test_rule_accepts_valid(password):
    assert password_rule_error(password) is None


def test_rule_counts_bytes_not_characters():
    assert password_rule_error("ab" + "1" * 71) == PASSWORD_TOO_LONG_MESSAGE   # 73 bytes
    assert password_rule_error("é" * 37) == PASSWORD_TOO_LONG_MESSAGE          # 37 chars, 74 bytes
    assert password_rule_error("ñé123456") == PASSWORD_RULE_MESSAGE            # only A-Z/a-z count


# ---- POST /users ----

@pytest.mark.parametrize("password", WEAK)
def test_create_user_rejects_weak_password(manager_client, db, password):
    r = manager_client.post("/users", json={"username": "ZZTEST Weak", "password": password})
    assert r.status_code == 400
    assert r.json()["detail"] == PASSWORD_RULE_MESSAGE
    assert db.query(models.User).filter_by(username="ZZTEST Weak").count() == 0


@pytest.mark.parametrize("username", ["", "   "])
def test_create_user_rejects_blank_username(manager_client, db, username):
    count = db.query(models.User).count()
    r = manager_client.post("/users", json={"username": username, "password": VALID})
    assert r.status_code == 400
    assert r.json()["detail"] == "Username is required."
    assert db.query(models.User).count() == count


def test_create_user_accepts_valid_password_and_it_logs_in(manager_client, db):
    r = manager_client.post("/users", json={"username": "ZZTEST Valid", "password": VALID})
    assert r.status_code == 200
    stored = db.query(models.User).filter_by(username="ZZTEST Valid").one()
    assert stored.password.startswith("$2b$") and stored.role == "admin"
    assert manager_client.post("/login", json={"username": "ZZTEST Valid", "password": VALID}).status_code == 200


# ---- existing login ----

def test_existing_password_below_the_rule_still_logs_in(client, db):
    _add_user(db, "ZZTEST Old", "abc")   # set before the rule existed
    assert client.post("/login", json={"username": "ZZTEST Old", "password": "abc"}).status_code == 200
    assert client.post("/login", json={"username": "ZZTEST Old", "password": "abd"}).status_code == 401


def test_over_72_byte_login_is_401_not_500(client, db):
    _add_user(db, "ZZTEST Long", VALID)
    r = client.post("/login", json={"username": "ZZTEST Long", "password": "a" * 73})
    assert r.status_code == 401


# ---- POST /users/me/password ----

def test_change_password_requires_login(client):
    r = client.post("/users/me/password", json={"current_password": "x", "new_password": VALID})
    assert r.status_code == 401


@pytest.mark.parametrize("current, new, message", [
    ("wrong-pass1", "cd654321", "Current password is incorrect."),
    ("zz-old-pass1", "a1234567", PASSWORD_RULE_MESSAGE),
    ("zz-old-pass1", "12345678", PASSWORD_RULE_MESSAGE),
    ("zz-old-pass1", "zz-old-pass1", "New password must be different from the current password."),
])
def test_change_password_rejections(client, db, current, new, message):
    user = _add_user(db, "ZZTEST Changer", "zz-old-pass1")
    old_hash = user.password
    r = client.post("/users/me/password", headers=_auth("ZZTEST Changer"),
                    json={"current_password": current, "new_password": new})
    assert r.status_code == 400
    assert r.json()["detail"] == message
    db.refresh(user)
    assert user.password == old_hash


def test_change_password_success(client, db):
    _add_user(db, "ZZTEST Changer", "zz-old-pass1")
    r = client.post("/users/me/password", headers=_auth("ZZTEST Changer"),
                    json={"current_password": "zz-old-pass1", "new_password": "cd654321"})
    assert r.status_code == 200
    assert client.post("/login", json={"username": "ZZTEST Changer", "password": "cd654321"}).status_code == 200
    assert client.post("/login", json={"username": "ZZTEST Changer", "password": "zz-old-pass1"}).status_code == 401
