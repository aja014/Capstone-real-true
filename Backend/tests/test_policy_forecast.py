"""Policy Forecast (app/services/policy_forecast.py): the statistics on small hand-made rows, and
GET /stats/policy-forecast against independent SQL counts on the dev database.
TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
import datetime as dt
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import get_db
from app.ml import jobs
from app.security import get_current_user
from app.services import policy_forecast as pf
from main import app

D = dt.date
AS_OF = D(2026, 6, 30)


def days(n):
    return dt.timedelta(days=n)


# (quotation_date, issue_date or None). Known lags 2, 1, 2 -> W = 2.
ROWS = [
    (AS_OF - days(10), AS_OF - days(8)),  # decided, converted (lag 2)
    (AS_OF - days(9), AS_OF - days(8)),   # decided, converted (lag 1)
    (AS_OF - days(8), None),              # decided, not converted
    (AS_OF - days(3), AS_OF + days(1)),   # policy issued AFTER as_of: not known yet -> decided, not converted
    (AS_OF - days(2), None),              # age 2 = W: decided (lost), not open
    (AS_OF - days(1), None),              # open, age 1
    (AS_OF, None),                        # open, age 0 (sent today)
    (AS_OF - days(400), AS_OF - days(398)),  # outside the 12-month windows
    (AS_OF + days(1), None),              # sent after as_of: not known yet
]


def test_wait_days_is_95th_percentile_rounded_up():
    q = D(2026, 1, 1)
    rows = [(q, q + days(lag)) for lag in range(1, 21)] + [(q, None)]
    assert pf.wait_days(rows, D(2026, 6, 1)) == 20  # percentile of 1..20 = 19.05
    # a policy issued after as_of is not known yet
    assert pf.wait_days(rows + [(q, D(2026, 7, 1))], D(2026, 6, 1)) == 20
    assert pf.wait_days([(q, None)], D(2026, 6, 1)) == 0


def test_line_forecast_on_hand_made_rows():
    fc = pf.line_forecast(ROWS, AS_OF)
    assert fc["wait_days"] == 2
    assert fc["decided_quotations"] == 5  # ages 10, 9, 8, 3, 2
    assert fc["converted_quotations"] == 2
    assert fc["conversion_rate"] == pytest.approx(0.4)
    assert fc["quotations_past_12_months"] == 7  # ages 0..10
    assert fc["expected_policies"] == pytest.approx(7 / 12 * 0.4)
    assert fc["open_quotations"] == 2
    # lag shares {1: 0.5, 2: 0.5}; age 0 -> 0.4; age 1 -> 0.4*0.5 / (1 - 0.4*0.5) = 0.25
    assert fc["expected_from_open"] == pytest.approx(0.65)


def test_open_probability_hand_example():
    share = {0: 0.0, 1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
    assert pf.open_probability(0.8, share, 4, 0) == pytest.approx(0.8)
    assert pf.open_probability(0.8, share, 4, 1) == pytest.approx(0.8 * 0.75 / 0.8)
    assert pf.open_probability(0.8, share, 4, 3) == pytest.approx(0.8 * 0.25 / 0.4)
    assert pf.open_probability(0.8, share, 4, 4) == 0.0


def test_later_data_does_not_change_a_past_forecast():
    later = ROWS + [(AS_OF + days(3), AS_OF + days(4))]  # a quotation sent after as_of
    later[2] = (AS_OF - days(8), AS_OF + days(5))  # a policy issued after as_of
    assert pf.line_forecast(later, AS_OF) == pf.line_forecast(ROWS, AS_OF)


def test_no_data_gives_no_forecast():
    fc = pf.line_forecast([], AS_OF)
    assert fc["conversion_rate"] is None and fc["expected_policies"] is None
    assert fc["expected_from_open"] is None and fc["open_quotations"] == 0


def test_next_month_rolls_over_the_year():
    assert pf.next_month(2026, 12) == (2027, 1)
    assert pf.next_month(2026, 9) == (2026, 10)


def test_backtest_months_and_actuals():
    rows = {"Motor Car": ROWS, "Fire & Property": []}
    table, errors = pf.backtest(rows, D(2026, 9, 27))
    assert [(r["target_year"], r["target_month"]) for r in table][0] == (2025, 9)
    assert [(r["target_year"], r["target_month"]) for r in table][-1] == (2026, 8)
    assert table[0]["as_of"] == D(2025, 8, 1) and table[-1]["as_of"] == D(2026, 7, 1)
    jan = next(r for r in table if r["target_month"] == 1)
    assert jan["as_of"] == D(2025, 12, 1)
    june = next(r for r in table if r["target_month"] == 6)
    assert june["lines"][0]["actual"] == 2  # ROWS issued in June 2026: 06-22 twice
    assert june["total_forecast"] is None  # Fire & Property has no data -> no total


def test_error_measures():
    assert pf.error_pct([(12, 10), (8, 10), (5, 0)]) == pytest.approx(20.0)  # actual 0 left out
    assert pf.total_error_pct([(12, 10), (9, 10)]) == pytest.approx(5.0)


# ---------------------------------------------------------------- API

class _NoDbSession:
    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture(autouse=True)
def no_real_refresh_session(monkeypatch):
    monkeypatch.setattr(jobs, "SessionLocal", _NoDbSession)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="manager")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_endpoint_requires_login():
    assert TestClient(app).get("/stats/policy-forecast").status_code == 401


@pytest.mark.parametrize("line, quotations, policies", [
    ("Motor Car", "motor_quotations", "motor_policies"),
    ("Fire & Property", "fire_property_quotations", "fire_property_policies"),
])
def test_endpoint_matches_independent_sql(client, db, line, quotations, policies):
    body = client.get("/stats/policy-forecast").json()
    ln = next(x for x in body["lines"] if x["line"] == line)
    issued = "COALESCE(p.issue_date, q.quotation_date)"
    age = "DATEDIFF(CURDATE(), q.quotation_date)"

    lags = [r[0] for r in db.execute(text(
        f"SELECT DATEDIFF({issued}, q.quotation_date) FROM {quotations} q JOIN {policies} p "
        f"ON p.quotation_id = q.id WHERE q.quotation_date <= CURDATE() AND {issued} <= CURDATE()"))]
    w = int(np.ceil(np.percentile(lags, 95)))
    assert ln["wait_days"] == w

    def count(sql):
        return db.execute(text(sql), {"w": w}).scalar()

    decided = count(f"SELECT COUNT(*) FROM {quotations} q WHERE {age} BETWEEN :w AND :w + 364")
    converted = count(
        f"SELECT COUNT(*) FROM {quotations} q JOIN {policies} p ON p.quotation_id = q.id "
        f"WHERE {age} BETWEEN :w AND :w + 364 AND {issued} <= CURDATE() "
        f"AND DATEDIFF({issued}, q.quotation_date) <= :w")
    volume = count(f"SELECT COUNT(*) FROM {quotations} q WHERE {age} BETWEEN 0 AND 364")
    open_ = count(
        f"SELECT COUNT(*) FROM {quotations} q WHERE {age} BETWEEN 0 AND :w - 1 AND NOT EXISTS "
        f"(SELECT 1 FROM {policies} p WHERE p.quotation_id = q.id AND {issued} <= CURDATE())")
    assert (ln["decided_quotations"], ln["converted_quotations"]) == (decided, converted)
    assert ln["quotations_past_12_months"] == volume
    assert ln["open_quotations"] == open_
    assert ln["conversion_rate"] == pytest.approx(converted / decided)
    assert ln["expected_policies"] == pytest.approx(volume / 12 * converted / decided)

    last = body["backtest"][-1]
    y, m = last["target_year"], last["target_month"]
    actual = count(f"SELECT COUNT(*) FROM {policies} WHERE YEAR(issue_date) = {y} AND MONTH(issue_date) = {m}")
    assert next(x for x in last["lines"] if x["line"] == line)["actual"] == actual


def test_endpoint_totals_and_target_month(client):
    body = client.get("/stats/policy-forecast").json()
    today = dt.date.today()
    assert (body["target_year"], body["target_month"]) == pf.next_month(today.year, today.month)
    assert body["expected_policies"] == pytest.approx(sum(x["expected_policies"] for x in body["lines"]))
    assert body["open_quotations"] == sum(x["open_quotations"] for x in body["lines"])
    assert len(body["backtest"]) == pf.BACKTEST_MONTHS
