"""GET /ml/inputs/quotations and /ml/inputs/claims: the values shown on the Proposal and
Claims tables must be exactly the frame values the models use (app/ml/features.py).
Runs in the rolled-back `db` fixture; seeded rows use the ZZTEST prefix."""
import datetime as dt
import math
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app import models
from app.database import get_db
from app.ml import features, training
from app.security import get_current_user
from main import app

TODAY = dt.date(2026, 9, 27)


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="manager")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def seeded(db):
    """One Motor quotation (vehicle, no GIS) and one Fire quotation whose case has NO survey."""
    person = models.Policyholder(last_name="ZZTEST Inputs Alpha", first_name="Juan")
    db.add(person)
    db.flush()
    motor_case = models.InsuranceCase(policyholder_id=person.id, line_type=models.LineType.motor_car)
    fire_case = models.InsuranceCase(policyholder_id=person.id, line_type=models.LineType.fire_property)
    db.add_all([motor_case, fire_case])
    db.flush()
    vehicle = models.Vehicle(insurance_case_id=motor_case.id, model="2019", make="ZZTEST Make",
                             body_type="Sedan", plate_no="ZZT 0001")
    db.add(vehicle)
    db.flush()
    motor_q = models.MotorQuotation(insurance_case_id=motor_case.id, vehicle_id=vehicle.id,
                                    quotation_date=dt.date(2026, 9, 1), classification="Private",
                                    color="Red", sum_insured=850000, deductible=4250)
    fire_q = models.FirePropertyQuotation(insurance_case_id=fire_case.id, quotation_date=dt.date(2026, 9, 1),
                                          occupancy="Dwelling", total_sum_insured=2000000)
    db.add_all([motor_q, fire_q])
    db.flush()
    return SimpleNamespace(motor_q=motor_q, fire_q=fire_q)


def _same(api_value, frame_value):
    if frame_value is None or (isinstance(frame_value, float) and math.isnan(frame_value)):
        return api_value is None
    if isinstance(api_value, bool):
        return api_value == bool(frame_value)
    if isinstance(api_value, (int, float)):
        return math.isclose(float(api_value), float(frame_value))
    return api_value == frame_value


def test_motor_inputs_equal_the_frame(client, db, seeded):
    body = client.get("/ml/inputs/quotations", params={"line": "Motor Car"}).json()
    frame = features.motor_quotation_frame(db)
    assert [r["quotation_id"] for r in body] == frame["quotation_id"].tolist()
    pairs = {"flood_category": "flood_category", "classification": "classification", "make": "make",
             "body_type": "body_type", "color": "color", "vehicle_age": "vehicle_age",
             "sum_insured": "sum_insured", "deductible": "deductible", "prior_claim": "prior_counted_loss"}
    for item, row in zip(body, frame.to_dict("records")):
        for api_key, frame_key in pairs.items():
            assert _same(item[api_key], row[frame_key]), (item["quotation_id"], api_key)

    mine = next(r for r in body if r["quotation_id"] == seeded.motor_q.id)
    assert mine == {"quotation_id": seeded.motor_q.id, "flood_category": "Unknown", "classification": "Private",
                    "make": "ZZTEST Make", "body_type": "Sedan", "color": "Red", "vehicle_age": 7,
                    "sum_insured": 850000.0, "deductible": 4250.0, "prior_claim": False}


def test_fire_inputs_equal_the_frame(client, db, seeded):
    body = client.get("/ml/inputs/quotations", params={"line": "Fire & Property"}).json()
    frame = features.fire_quotation_frame(db)
    assert [r["quotation_id"] for r in body] == frame["quotation_id"].tolist()
    latest_survey = dict(db.query(models.FirePropertySurvey.insurance_case_id, func.max(models.FirePropertySurvey.id))
                         .group_by(models.FirePropertySurvey.insurance_case_id).all())
    pairs = {"flood_category": "flood_category", "occupancy": "occupancy",
             "overall_risk_assessment": "overall_risk_assessment", "total_sum_insured": "total_sum_insured",
             "fire_protection_count": "fire_protection_count", "construction_class_b": "construction_class_b",
             "has_loss_record": "has_loss_record", "prior_claim": "prior_counted_loss"}
    for item, row in zip(body, frame.to_dict("records")):
        assert item["survey_id"] == latest_survey.get(row["insurance_case_id"])
        for api_key, frame_key in pairs.items():
            if item["survey_id"] is None and api_key in ("construction_class_b", "has_loss_record"):
                continue  # null on screen; checked below
            assert _same(item[api_key], row[frame_key]), (item["quotation_id"], api_key)


def test_fire_quotation_without_survey_has_null_survey_fields(client, seeded):
    body = client.get("/ml/inputs/quotations", params={"line": "Fire & Property"}).json()
    mine = next(r for r in body if r["quotation_id"] == seeded.fire_q.id)
    assert mine["survey_id"] is None
    for key in ("overall_risk_assessment", "fire_protection_count", "construction_class_b", "has_loss_record"):
        assert mine[key] is None, key
    assert mine["flood_category"] == "Unknown"  # what the model sees for an unlocated property
    assert mine["occupancy"] == "Dwelling" and mine["total_sum_insured"] == 2000000.0
    assert mine["prior_claim"] is False


def test_claim_inputs_equal_the_frame(client, db):
    body = client.get("/ml/inputs/claims").json()
    frame = features.claim_clue_frame(db)
    assert len(body) == len(frame)
    by_key = {(r["line"], r["claim_id"]): r for r in body}
    for row in frame.to_dict("records"):
        item = by_key[("Motor Car" if row["line"] == "Motor" else row["line"], row["claim_id"])]
        for clue in ("days_coverage_start_to_loss", "days_loss_to_report", "estimate_to_sum_insured",
                     "earlier_claims_12_months", "days_loss_to_expiry", "nature_of_loss", "coverage_type",
                     "policy_type", "days_report_to_documents"):
            assert item[clue] == row[clue], (item["line"], item["claim_id"], clue)
            assert item[clue] in features.NB_CLUE_VALUES[clue]

    fire_only = client.get("/ml/inputs/claims", params={"line": "Fire & Property"}).json()
    assert fire_only == [r for r in body if r["line"] == "Fire & Property"]


def test_quotation_inputs_need_a_line_and_a_manager(client):
    assert client.get("/ml/inputs/quotations").status_code == 422
    assert client.get("/ml/inputs/quotations", params={"line": "Boat"}).status_code == 422
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role="admin")
    assert client.get("/ml/inputs/quotations", params={"line": "Motor Car"}).status_code == 403
    assert client.get("/ml/inputs/claims").status_code == 200  # claims inputs: every role


def test_inputs_require_login():
    raw = TestClient(app)
    assert raw.get("/ml/inputs/quotations", params={"line": "Motor Car"}).status_code == 401
    assert raw.get("/ml/inputs/claims").status_code == 401


def test_reading_inputs_changes_no_fingerprint_model_or_prediction(client, db):
    before = {n: training.data_signature(n, training.build_dataset(db, n, TODAY)) for n in training.MODEL_NAMES}
    models_before = db.query(models.MLModel.id, models.MLModel.status).order_by(models.MLModel.id).all()
    predictions_before = db.query(models.MLPrediction.id, models.MLPrediction.probability).order_by(
        models.MLPrediction.id).all()

    for line in ("Motor Car", "Fire & Property"):
        assert client.get("/ml/inputs/quotations", params={"line": line}).status_code == 200
    assert client.get("/ml/inputs/claims").status_code == 200

    after = {n: training.data_signature(n, training.build_dataset(db, n, TODAY)) for n in training.MODEL_NAMES}
    assert after == before
    assert db.query(models.MLModel.id, models.MLModel.status).order_by(models.MLModel.id).all() == models_before
    assert db.query(models.MLPrediction.id, models.MLPrediction.probability).order_by(
        models.MLPrediction.id).all() == predictions_before
