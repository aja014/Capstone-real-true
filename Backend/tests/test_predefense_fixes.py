"""Pre-defense fixes: Claims Open + Closed + Other = Total, the Distribution/Overview pie labels,
and unreadable Quotation/Policy dates failing the row. Read-only against the dev database
(rolled-back `db` fixture). TestClient is used WITHOUT `with`, so no startup model refresh."""
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.routers import import_fire_property, import_motor
from app.security import get_current_user
from main import app

TODAY = "2026-09-28"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="manager")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("months", [3, 6, 12])
def test_claims_open_closed_other_add_up_to_total(client, months):
    s = client.get(f"/stats/claims?months={months}").json()
    assert s["open_claims"] + s["closed_claims"] + s["other_claims"] == s["total_claims"]
    assert s["other_claims"] >= 0


@pytest.mark.parametrize("period", ["mtd", "ytd"])
def test_distribution_pies_say_new_and_renewal(client, period):
    s = client.get(f"/stats/policy-distribution?period={period}&date={TODAY}").json()
    for pie in (s["fire_pie"], s["motor_pie"]):
        assert [slice_["name"] for slice_ in pie] == ["New Policy", "Renewal Policy"]


def test_renewal_ratio_keeps_renewed(client):
    s = client.get(f"/stats/renewal-ratio?period=ytd&date={TODAY}").json()
    assert [slice_["name"] for slice_ in s["fire_pie"]] == ["Renewed Policy", "Lost Policy", "Pending"]


def test_overview_pie_says_not_yet_converted(client):
    s = client.get("/stats/overview").json()
    assert [slice_["name"] for slice_ in s["quotation_pie"]] == ["Converted", "Not Yet Converted"]


PARSERS = [
    (import_fire_property.row_to_fire_quotation_fields, "Date", "quotation_date"),
    (import_motor.row_to_fields, "Date", "quotation_date"),
    (import_fire_property.row_to_fire_policy_fields, "Issue Date", "issue_date"),
    (import_fire_property.row_to_fire_policy_fields, "Period From", "period_from"),
    (import_fire_property.row_to_fire_policy_fields, "Period To", "period_to"),
    (import_motor.row_to_motor_policy_fields, "Issue Date", "issue_date"),
    (import_motor.row_to_motor_policy_fields, "Period From", "period_from"),
    (import_motor.row_to_motor_policy_fields, "Period To", "period_to"),
]


@pytest.mark.parametrize("parser, header, field", PARSERS)
def test_unreadable_date_fails_the_row(parser, header, field):
    with pytest.raises(ValueError, match=f"^{header}: '31/31/2026' is not a valid date$"):
        parser(pd.Series({header: "31/31/2026"}))


@pytest.mark.parametrize("parser, header, field", PARSERS)
def test_blank_and_valid_dates(parser, header, field):
    assert parser(pd.Series({header: None})).get(field) is None
    assert str(parser(pd.Series({header: "2026-09-27"}))[field]) == "2026-09-27"
