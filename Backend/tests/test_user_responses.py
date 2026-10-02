"""No endpoint that handles a user may send the password hash back (IT test, 2026-10-03).

Covers POST /users, POST /login and POST /users/me/password; there is no user list or "me"
endpoint. Every user is a temporary ZZTEST user inside the rolled-back `db` fixture; the hash
values are compared in memory and never printed.
TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
import pytest
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.security import create_access_token, get_current_user, hash_password
from main import app

PASSWORD = "ab123456"


def _add_user(db, username, password, role="admin"):
    user = models.User(username=username, password=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user


def _assert_no_secret(response, *hashes):
    assert "password" not in response.text
    for h in hashes:
        assert h not in response.text


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def manager_client(db):
    manager = _add_user(db, "ZZTEST Hotel Manager", "zz-manager-pass", role="manager")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_user_returns_only_safe_fields(manager_client, db):
    r = manager_client.post("/users", json={"username": "ZZTEST India New", "password": PASSWORD})
    assert r.status_code == 200
    stored = db.query(models.User).filter_by(username="ZZTEST India New").one()
    body = r.json()
    assert body["message"] == "User created!"
    assert body["user"] == {"id": stored.id, "username": "ZZTEST India New", "role": "admin"}
    _assert_no_secret(r, stored.password)


def test_login_returns_no_hash(client, db):
    user = _add_user(db, "ZZTEST Juliet Login", PASSWORD)
    r = client.post("/login", json={"username": "ZZTEST Juliet Login", "password": PASSWORD})
    assert r.status_code == 200
    assert set(r.json()) == {"access_token", "token_type", "role"}
    _assert_no_secret(r, user.password)


def test_change_password_returns_no_hash(client, db):
    user = _add_user(db, "ZZTEST Kilo Changer", PASSWORD)
    old_hash = user.password
    r = client.post("/users/me/password",
                    headers={"Authorization": f"Bearer {create_access_token({'sub': 'ZZTEST Kilo Changer'})}"},
                    json={"current_password": PASSWORD, "new_password": "cd654321"})
    assert r.status_code == 200
    assert r.json() == {"message": "Password changed."}
    db.refresh(user)
    _assert_no_secret(r, old_hash, user.password)
