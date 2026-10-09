"""Client IP source (branch deploy-ias2): CLIENT_IP_SOURCE picks where the login limiter, login log
and "Last login" read the client IP; DEBUG_CLIENT_IP (temporary) logs one line per login about the
IP headers. Spoofed X-Forwarded-For entries must never be chosen. TestClient WITHOUT `with`."""
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import models
from app.config import settings
from app.database import engine, get_db
from app.security import hash_password
from app.services import login_audit, login_limiter
from app.services.login_limiter import client_ip
from main import app

BACKEND = Path(__file__).resolve().parents[1]
SPOOFED_XFF = "1.2.3.4, 110.54.20.30"  # leftmost typed by the client; the proxy appended the last


def _request(headers=None, peer="10.200.0.5"):
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "headers": raw, "client": (peer, 40000)})


@pytest.fixture
def source(monkeypatch):
    def set_source(value, hops=1):
        monkeypatch.setattr(settings, "CLIENT_IP_SOURCE", value)
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", hops)
    return set_source


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _login(client, username="ZZTEST Nobody Tango", password="zz-wrong-pass1", **headers):
    return client.post("/login", json={"username": username, "password": password}, headers=headers)


# ---- settings ----

def _run(code, **env):
    clean = {k: v for k, v in os.environ.items() if k not in ("CLIENT_IP_SOURCE", "DEBUG_CLIENT_IP")}
    clean.update(env)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=clean,
                          capture_output=True, text=True, timeout=120)


def test_unset_means_xff_hops_and_no_debug_line():
    r = _run("from app.config import settings; print(settings.CLIENT_IP_SOURCE, settings.DEBUG_CLIENT_IP)")
    assert r.returncode == 0 and r.stdout.split() == ["xff_hops", "False"]


def test_an_unknown_source_refuses_to_start():
    r = _run("import app.config", CLIENT_IP_SOURCE="x-real-ip")
    assert r.returncode != 0 and "CLIENT_IP_SOURCE must be" in r.stderr


# ---- the one client_ip() rule ----

def test_xff_hops_takes_the_proxy_entry_not_the_spoofed_one(source):
    source("xff_hops", hops=1)
    assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF})) == "110.54.20.30"
    source("xff_hops", hops=2)
    assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF})) == "1.2.3.4"  # what hops=2 trusts
    source("xff_hops", hops=0)
    assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF})) == "10.200.0.5"  # header ignored


@pytest.mark.parametrize("name", ["cf-connecting-ip", "true-client-ip"])
def test_a_header_source_wins_over_a_spoofed_forwarded_for(source, name):
    source(name)
    headers = {"X-Forwarded-For": SPOOFED_XFF, name: " 110.54.99.1 ", "X-Real-IP": "5.6.7.8"}
    assert client_ip(_request(headers)) == "110.54.99.1"


@pytest.mark.parametrize("name, other", [("cf-connecting-ip", "true-client-ip"),
                                         ("true-client-ip", "cf-connecting-ip")])
def test_a_missing_or_bad_header_falls_back_to_xff_hops(source, name, other):
    source(name, hops=1)
    assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF})) == "110.54.20.30"
    # only the chosen header counts, never the other one or X-Real-IP
    assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF, other: "9.9.9.9",
                               "X-Real-IP": "8.8.8.8"})) == "110.54.20.30"
    for bad in ("", "not-an-ip", "1.2.3.4, 5.6.7.8"):
        assert client_ip(_request({"X-Forwarded-For": SPOOFED_XFF, name: bad})) == "110.54.20.30"


def test_ipv6_is_accepted_and_normalised(source):
    source("cf-connecting-ip")
    assert client_ip(_request({"cf-connecting-ip": "2001:DB8::0001"})) == "2001:db8::1"


def test_the_limiter_and_the_log_use_the_same_function():
    assert login_audit.client_ip is login_limiter.client_ip
    assert login_limiter.key_for(_request(), "X") == (client_ip(_request()), "x")


# ---- the login limiter through the API ----

@pytest.mark.parametrize("name", ["cf-connecting-ip", "true-client-ip"])
def test_changing_the_spoofed_forwarded_for_does_not_escape_the_lock(client, source, name):
    source(name)
    for i in range(5):
        _login(client, **{"X-Forwarded-For": f"1.2.3.{i}, 10.0.0.{i}", name: "203.0.113.7"})
    assert _login(client, **{"X-Forwarded-For": "4.4.4.4", name: "203.0.113.7"}).status_code == 429
    assert _login(client, **{"X-Forwarded-For": "4.4.4.4", name: "203.0.113.8"}).status_code == 401


def test_without_the_header_the_lock_follows_xff_hops(client, source):
    source("cf-connecting-ip", hops=1)
    for i in range(5):
        _login(client, **{"X-Forwarded-For": f"1.2.3.{i}, 203.0.113.7"})
    assert _login(client, **{"X-Forwarded-For": "9.9.9.9, 203.0.113.7"}).status_code == 429


# ---- DEBUG_CLIENT_IP ----

def _debug_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "firemap.login.client_ip"]


def test_debug_line_is_off_by_default(client, source, caplog):
    source("xff_hops")
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client, **{"X-Forwarded-For": SPOOFED_XFF})
    assert _debug_lines(caplog) == []


def test_debug_line_once_per_login_with_only_the_ip_headers(client, source, caplog, monkeypatch):
    source("cf-connecting-ip", hops=1)
    monkeypatch.setattr(settings, "DEBUG_CLIENT_IP", True)
    headers = {"X-Forwarded-For": "1.2.3.4, 110.54.20.30, 10.17.3.4", "CF-Connecting-IP": "110.54.20.30",
               "X-Real-IP": "10.17.3.4", "Authorization": "Bearer zz-token-secret",
               "Cookie": "zz-cookie-secret", "User-Agent": "zz-agent-secret"}
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client, password="zz-password-secret1", **headers)
    lines = _debug_lines(caplog)
    assert len(lines) == 1
    assert lines[0] == ("client-ip debug xff_count=3 "
                        "xff=['1.2.3.4':public, '110.54.20.30':public, '10.17.3.4':private] "
                        "cf-connecting-ip='110.54.20.30' true-client-ip=absent x-real-ip='10.17.3.4' "
                        "peer=testclient source=cf-connecting-ip hops=1 chosen=110.54.20.30")
    assert not any(s in caplog.text for s in ("zz-password-secret1", "zz-token-secret",
                                              "zz-cookie-secret", "zz-agent-secret"))


def test_debug_line_cannot_be_flooded_or_split(client, source, caplog, monkeypatch):
    source("xff_hops", hops=1)
    monkeypatch.setattr(settings, "DEBUG_CLIENT_IP", True)
    xff = ", ".join(f"1.1.1.{i}" for i in range(50)) + ", " + "x" * 500
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client, **{"X-Forwarded-For": xff})
    line = _debug_lines(caplog)[0]
    assert line.startswith("client-ip debug xff_count=51 ") and line.count(":public") == 10
    assert "x" * 65 not in line and "\n" not in line


# ---- login log and "Last login" (login_events table: scratch database only) ----

@pytest.fixture
def audit(monkeypatch):
    if engine.url.database == "insurance_db":
        pytest.skip("login_events tests run on a scratch copy, never on the local insurance_db")
    models.AuditBase.metadata.create_all(bind=engine)
    monkeypatch.setattr(settings, "LOGIN_AUDIT", True)


def test_login_log_and_last_login_use_the_chosen_header(client, db, source, audit, caplog):
    source("true-client-ip", hops=1)
    db.add(models.User(username="ZZTEST Uniform", password=hash_password("zz-uniform-pass1"), role="admin"))
    db.flush()
    ok = {"X-Forwarded-For": "1.2.3.4, 10.17.3.4"}
    with caplog.at_level(logging.INFO, logger="firemap.login"):
        _login(client, "ZZTEST Uniform", "zz-uniform-pass1", **ok, **{"True-Client-IP": "110.54.20.30"})
    assert "ip=110.54.20.30 result=success" in caplog.text
    second = _login(client, "ZZTEST Uniform", "zz-uniform-pass1", **ok, **{"True-Client-IP": "110.54.20.31"})
    assert second.json()["last_login"]["ip"] == "110.54.20.30"
