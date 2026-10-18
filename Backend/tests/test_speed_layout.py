"""Speed fix round: /stats/renewal-ratio and /stats/quotation-proposal load their related
rows up front (selectinload) instead of one lazy query per row. The query count must stay
small and the values must be the same as the plain SQL joins. Read-only against the dev
database (rolled-back `db` fixture). TestClient is used WITHOUT `with`."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.database import engine, get_db
from app.security import get_current_user
from main import app

TODAY = "2026-10-04"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="manager")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@contextmanager
def count_queries():
    counter = {"n": 0}

    def _count(*args, **kwargs):
        counter["n"] += 1

    event.listen(engine, "before_cursor_execute", _count)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _count)


@pytest.mark.parametrize("period", ["daily", "mtd", "ytd"])
def test_renewal_ratio_query_count_does_not_grow_with_policies(client, period):
    # Was 1,628 queries for YTD on the v4 data (3 lazy loads per policy row).
    with count_queries() as q:
        r = client.get(f"/stats/renewal-ratio?period={period}&date={TODAY}")
    assert r.status_code == 200
    # selectinload sends its IN-lists in batches of 500 ids, so the count rises by one query per
    # 500 rows (21 on the v5 data: 2,842 fire policies -> 6 quotation queries). Per-row lazy
    # loading would be thousands, so < 40 still catches that regression.
    assert q["n"] < 40


def test_renewal_ratio_client_names_match_the_sql_join(client, db):
    rows = client.get(f"/stats/renewal-ratio?period=ytd&date={TODAY}").json()["policies"]
    assert rows
    for line, policy_table, quotation_table in [
        ("Fire & Property", "fire_property_policies", "fire_property_quotations"),
        ("Motor Car", "motor_policies", "motor_quotations"),
    ]:
        expected = {
            pid: " ".join(part for part in (first, middle, last) if part) or "—"
            for pid, first, middle, last in db.execute(text(f"""
                SELECT p.id, ph.first_name, ph.middle_name, ph.last_name
                FROM {policy_table} p
                LEFT JOIN {quotation_table} q ON q.id = p.quotation_id
                LEFT JOIN insurance_cases ic ON ic.id = q.insurance_case_id
                LEFT JOIN policyholders ph ON ph.id = ic.policyholder_id"""))
        }
        for row in (r for r in rows if r["line"] == line):
            assert row["client_name"] == expected[row["id"]]


@pytest.mark.parametrize("months", [3, 6, 12])
def test_quotation_proposal_query_count_and_converted_count(client, db, months):
    # Was 304 queries for 6 months on the v4 data (one lazy q.policy per quotation).
    with count_queries() as q:
        s = client.get(f"/stats/quotation-proposal?months={months}").json()
    assert q["n"] < 15
    converted = sum(
        db.execute(text(f"""
            SELECT COUNT(*) FROM {quotation_table} q JOIN {policy_table} p ON p.quotation_id = q.id
            WHERE q.quotation_date BETWEEN :start AND :end"""),
            {"start": s["range_start"], "end": s["range_end"]}).scalar()
        for quotation_table, policy_table in [("fire_property_quotations", "fire_property_policies"),
                                              ("motor_quotations", "motor_policies")]
    )
    assert s["converted_accounts"] == converted
