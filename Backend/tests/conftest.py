"""Shared test setup. Run from Backend/:   ./venv/Scripts/python -m pytest tests

The `db` fixture runs against the dev database inside ONE outer transaction that is always
rolled back: code under test may commit() or rollback() freely (those become savepoints),
and nothing it writes survives the test."""
import sys
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import engine  # noqa: E402
from app.services import login_limiter  # noqa: E402


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def clear_login_limiter():
    """Failed logins of one test must never lock a later test out (the limiter is in memory)."""
    login_limiter.clear()
    yield
    login_limiter.clear()
