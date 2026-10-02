"""Fix round (validation Phases 0–8): deleted_by on every archive (B2), a reused vehicle
gets its missing identifiers (B3), usernames trimmed (B4).

Everything runs inside the rolled-back `db` fixture with ZZTEST records. Motor quotation
files are passed straight to the importer function (as the folder upload does), so no
background model refresh is scheduled, and the flood lookup is stubbed (no network).
TestClient is used WITHOUT `with`, so the app's startup model refresh never runs."""
import datetime as dt
import io

import pandas as pd
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app import models
from app.database import get_db
from app.routers import import_motor
from app.security import create_access_token, get_current_user, hash_password
from main import app

DELETER = "ZZTEST Deleter"


def _add_user(db, username, role="admin"):
    user = models.User(username=username, password=hash_password("zz-test-pass1"), role=role)
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def client(db):
    """Real token check (get_current_user runs) on the rolled-back test session."""
    app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---- B2: every delete records who did it ----

def _add(db, obj):
    db.add(obj)
    db.flush()
    return obj


def test_every_archive_records_the_deleting_user(db, client):
    _add_user(db, DELETER)
    headers = {"Authorization": f"Bearer {create_access_token({'sub': DELETER})}"}
    day = dt.date(2026, 1, 5)

    owner = _add(db, models.Policyholder(last_name="ZZTEST Alpha", first_name="Owner"))
    fire_case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.fire_property))
    survey = _add(db, models.FirePropertySurvey(insurance_case_id=fire_case.id, name_of_insured="ZZTEST Alpha"))
    fq = _add(db, models.FirePropertyQuotation(insurance_case_id=fire_case.id, quotation_date=day))
    fp = _add(db, models.FirePropertyPolicy(quotation_id=fq.id, policy_no="ZZTEST-FP-1", issue_date=day,
                                            period_from=day, period_to=day + dt.timedelta(days=365)))
    fc = _add(db, models.FirePropertyClaim(fire_property_policy_id=fp.id, date_of_loss=day, date_reported=day))
    motor_case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.motor_car))
    vehicle = _add(db, models.Vehicle(insurance_case_id=motor_case.id, plate_no="ZZTDEL1"))
    mq = _add(db, models.MotorQuotation(insurance_case_id=motor_case.id, vehicle_id=vehicle.id, quotation_date=day))
    mp = _add(db, models.MotorPolicy(quotation_id=mq.id, policy_no="ZZTEST-MP-1", issue_date=day,
                                     period_from=day, period_to=day + dt.timedelta(days=365)))
    mc = _add(db, models.MotorClaim(motor_policy_id=mp.id, date_of_loss=day, date_reported=day))
    record = _add(db, models.ImportRecord(source_file="zztest.xlsx", source_row=2,
                                          import_type=models.ImportType.policyholder,
                                          match_status=models.MatchStatus.needs_review, raw_data={}))
    lone = _add(db, models.Policyholder(last_name="ZZTEST Bravo", first_name="Lone"))

    deletes = [  # dependency order: nothing deleted here is still referenced
        (f"/motor/claims/{mc.id}", models.DeletedMotorClaim, mc.id),
        (f"/fire-property/claims/{fc.id}", models.DeletedFirePropertyClaim, fc.id),
        (f"/motor/policies/{mp.id}", models.DeletedMotorPolicy, mp.id),
        (f"/fire-property/policies/{fp.id}", models.DeletedFirePropertyPolicy, fp.id),
        (f"/motor/quotations/{mq.id}", models.DeletedMotorQuotation, mq.id),
        (f"/fire-property/quotations/{fq.id}", models.DeletedFirePropertyQuotation, fq.id),
        (f"/fire-property/surveys/{survey.id}", models.DeletedFirePropertySurvey, survey.id),
        (f"/motor/vehicles/{vehicle.id}", models.DeletedVehicle, vehicle.id),
        (f"/import/policyholders/records/{record.id}", models.DeletedImportRecord, record.id),
        (f"/policyholders/{lone.id}", models.DeletedPolicyholder, lone.id),
    ]
    for path, archive, original_id in deletes:
        r = client.delete(path, headers=headers)
        assert r.status_code == 200, (path, r.text)
        row = db.query(archive).filter_by(original_id=original_id).order_by(archive.id.desc()).first()
        assert row is not None and row.deleted_by == DELETER, path


# ---- B3: a reused vehicle gets its missing identifiers ----

@pytest.fixture
def no_geocoding(monkeypatch):
    monkeypatch.setattr(import_motor, "lookup_flood_risk", lambda address: {})


def _upload_quotations(db, rows):
    buf = io.BytesIO()
    pd.DataFrame(rows).to_excel(buf, index=False)
    buf.seek(0)
    return import_motor.upload_motor_quotations(file=UploadFile(file=buf, filename="zztest_mq.xlsx"), db=db)


def _quote(day, amount, plate="", engine="", chassis=""):
    return {"Date": day, "Insured Name": "ZZTEST Charlie Vehicleowner", "Address": "Malolos, Bulacan",
            "Plate No.": plate, "Motor/Engine No.": engine, "Serial/Chasis No.": chassis,
            "Total Amount Due": amount, "Sum Insured": 500000, "Make": "Toyota", "Model": "2020"}


def _plate_only_vehicle(db):
    owner = _add(db, models.Policyholder(last_name="ZZTEST Charlie", first_name="Vehicleowner"))
    case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.motor_car))
    return _add(db, models.Vehicle(insurance_case_id=case.id, plate_no="ZZTP001"))


def test_reused_vehicle_fills_missing_ids_and_is_found_by_them_later(db, no_geocoding):
    vehicle = _plate_only_vehicle(db)
    first = _upload_quotations(db, [_quote("2026-01-10", 15000, plate="ZZTP001", engine="ZZTE001", chassis="ZZTC001")])
    assert first.failed == 0 and first.warnings == []
    db.refresh(vehicle)
    assert (vehicle.motor_engine_no, vehicle.serial_chassis_no) == ("ZZTE001", "ZZTC001")

    vehicles_before = db.query(models.Vehicle).count()
    second = _upload_quotations(db, [_quote("2026-02-10", 16000, plate="ZZTP999", engine="ZZTE001")])
    assert second.failed == 0
    assert db.query(models.Vehicle).count() == vehicles_before  # same vehicle, no new one
    q = db.query(models.MotorQuotation).filter_by(plate_no="ZZTP999").one()
    assert q.vehicle_id == vehicle.id and q.insurance_case_id == vehicle.insurance_case_id
    db.refresh(vehicle)
    assert vehicle.plate_no == "ZZTP001"  # a different plate never overwrites the stored one
    assert len(second.warnings) == 1 and "ZZTP999" in second.warnings[0].warning
    assert second.warnings[0].source_row == 2


def test_identifier_of_another_vehicle_is_not_copied(db, no_geocoding):
    vehicle = _plate_only_vehicle(db)
    other_case = _add(db, models.InsuranceCase(policyholder_id=vehicle.insurance_case.policyholder_id,
                                               line_type=models.LineType.motor_car))
    _add(db, models.Vehicle(insurance_case_id=other_case.id, plate_no="ZZTP002", motor_engine_no="ZZTE777"))
    summary = _upload_quotations(db, [_quote("2026-03-10", 17000, plate="ZZTP001", chassis="ZZTC555")])
    # Found by plate; the chassis is new, so it is filled in.
    db.refresh(vehicle)
    assert vehicle.serial_chassis_no == "ZZTC555" and summary.warnings == []

    vehicle.motor_engine_no = None
    db.flush()
    fill = import_motor.fill_vehicle_ids(db, vehicle, "ZZTP001", "ZZTE777", "")
    assert "belongs to another vehicle" in fill and vehicle.motor_engine_no is None


# ---- B4: usernames ----

@pytest.fixture
def manager_client(db):
    manager = _add_user(db, "ZZTEST Manager", role="manager")
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("again", ["ZZTEST_Admin ", " zztest_admin ", "ZZTEST_ADMIN"])
def test_same_name_after_trimming_and_ignoring_capitals_is_rejected(manager_client, again):
    assert manager_client.post("/users", json={"username": "ZZTEST_Admin", "password": "ab123456"}).status_code == 200
    r = manager_client.post("/users", json={"username": again, "password": "ab123456"})
    assert r.status_code == 400 and r.json()["detail"] == "User already exists"


def test_username_is_stored_trimmed_and_login_ignores_spaces(manager_client, db):
    assert manager_client.post("/users", json={"username": "  ZZTEST Delta  ", "password": "ab123456"}).status_code == 200
    assert db.query(models.User).filter(models.User.username == "ZZTEST Delta").one().username == "ZZTEST Delta"
    r = manager_client.post("/login", json={"username": " ZZTEST Delta ", "password": "ab123456"})
    assert r.status_code == 200
