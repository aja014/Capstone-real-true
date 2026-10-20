"""A text longer than its database column is a 422 naming the field, not a 500 (F1, 2026-10-10).

Before the fix MySQL's "Data too long" became a 500 "Internal Server Error" (e.g. gender > 20,
plate_no > 30, risk_class > 1). Every record is a ZZTEST record inside the rolled-back `db`
fixture. TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import models, schemas
from app.database import get_db
from app.security import get_current_user
from main import app

LIMITED = [(cls, name, limit)
           for cls in vars(schemas).values()
           if isinstance(cls, type) and issubclass(cls, schemas.ColumnLimited)
           and (cls.__name__.endswith("Create") or cls.__name__.endswith("Update"))
           for name, limit in cls.__column_limits__.items() if name in cls.model_fields]


def _too_long_errors(cls, name, value):
    try:
        cls.model_validate({name: value})
    except Exception as exc:  # other fields are missing: only this field's length error counts
        return [e for e in exc.errors() if e["loc"] == (name,) and e["type"] == "string_too_long"]
    return []


def test_the_list_covers_every_create_and_update_schema():
    names = {cls.__name__ for cls, _, _ in LIMITED}
    assert names == {
        "UserCreate", "PolicyholderCreate", "InsuranceCaseCreate", "FirePropertySurveyCreate",
        "FirePropertyQuotationCreate", "FirePropertyPolicyCreate", "VehicleCreate", "MotorQuotationCreate",
        "MotorPolicyCreate", "MotorClaimCreate", "FirePropertyClaimCreate", "MotorClaimUpdate",
        "FirePropertyClaimUpdate"}


@pytest.mark.parametrize("cls,name,limit", LIMITED, ids=[f"{c.__name__}.{n}" for c, n, _ in LIMITED])
def test_one_character_too_long_is_refused_and_the_exact_length_is_not(cls, name, limit):
    errors = _too_long_errors(cls, name, "W" * (limit + 1))
    assert errors and errors[0]["msg"] == f"String should have at most {limit} characters"
    assert _too_long_errors(cls, name, "W" * limit) == []


def test_limits_are_the_column_lengths():
    assert schemas.PolicyholderCreate.__column_limits__["gender"] == models.Policyholder.gender.type.length == 20
    assert schemas.VehicleCreate.__column_limits__["plate_no"] == models.Vehicle.plate_no.type.length == 30
    assert schemas.FirePropertySurveyCreate.__column_limits__["risk_class"] == 1
    assert schemas.UserCreate.__column_limits__ == {"username": 255}  # the password has its own rule


# ---- through the API ----

@pytest.fixture
def client(db):
    manager = SimpleNamespace(id=0, username="ZZTEST Kilo Manager", role="manager")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _assert_422(response, field, limit):
    assert response.status_code == 422, response.text[:200]
    errors = [e for e in response.json()["detail"] if e["loc"][-1] == field]
    assert errors and errors[0]["msg"] == f"String should have at most {limit} characters"


def _case(client, line_type):
    holder = client.post("/policyholders", json={"last_name": "ZZTEST Lima"})
    assert holder.status_code == 200
    case = client.post("/insurance-cases", json={"policyholder_id": holder.json()["id"], "line_type": line_type})
    assert case.status_code == 200
    return case.json()["id"]


def test_policyholder_gender(client):
    _assert_422(client.post("/policyholders", json={"last_name": "ZZTEST Mike", "gender": "G" * 21}), "gender", 20)
    r = client.post("/policyholders", json={"last_name": "ZZTEST Mike", "gender": "G" * 20})
    assert r.status_code == 200
    assert client.get(f"/policyholders/{r.json()['id']}").json()["gender"] == "G" * 20


def test_vehicle_plate_no(client):
    case_id = _case(client, "motor_car")
    _assert_422(client.post("/motor/vehicles", json={"insurance_case_id": case_id, "plate_no": "P" * 31}),
                "plate_no", 30)
    r = client.post("/motor/vehicles", json={"insurance_case_id": case_id, "plate_no": "P" * 30})
    assert r.status_code == 200
    assert client.get(f"/motor/vehicles/{r.json()['id']}").json()["plate_no"] == "P" * 30


def test_survey_risk_class(client):
    case_id = _case(client, "fire_property")
    _assert_422(client.post("/fire-property/surveys", json={"insurance_case_id": case_id, "risk_class": "ab"}),
                "risk_class", 1)
    r = client.post("/fire-property/surveys", json={"insurance_case_id": case_id, "risk_class": "a"})
    assert r.status_code == 200
    assert client.get(f"/fire-property/surveys/{r.json()['id']}").json()["risk_class"] == "a"


def test_claim_update(client, db):
    claim = db.query(models.MotorClaim).first()
    if claim is None:
        pytest.skip("no motor claim in this database")
    limit = schemas.MotorClaimUpdate.__column_limits__["accuterm_claim_no"]
    _assert_422(client.patch(f"/motor/claims/{claim.id}", json={"accuterm_claim_no": "C" * (limit + 1)}),
                "accuterm_claim_no", limit)
    r = client.patch(f"/motor/claims/{claim.id}", json={"accuterm_claim_no": "C" * limit})
    assert r.status_code == 200
    assert r.json()["accuterm_claim_no"] == "C" * limit


def test_username(client, db):
    _assert_422(client.post("/users", json={"username": "ZZTEST " + "N" * 249, "password": "ab123456"}),
                "username", 255)
    name = "ZZTEST " + "N" * 248
    assert client.post("/users", json={"username": name, "password": "ab123456"}).status_code == 200
    assert db.query(models.User).filter_by(username=name).count() == 1
