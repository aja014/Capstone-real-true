"""Hosting switches (IAS2, branch deploy-ias2). Every switch left unset keeps the local
behaviour; GIS_ENABLED=false skips geocoding and the hazard shapefiles, while surveys and motor
quotations still save with empty GIS fields (the GIS View then shows "Flood risk not yet
available").

API tests run inside the rolled-back `db` fixture with ZZTEST records, TestClient WITHOUT `with`
(no startup model refresh). app.config reads the environment once at import, so the defaults and
the env parsing are checked in a fresh Python process."""
import datetime as dt
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.routers import import_motor
from app.security import get_current_user, hash_password
from app.services import flood_risk
from main import app

BACKEND = Path(__file__).resolve().parents[1]
SWITCHES = ("APP_ENV", "CORS_ORIGINS", "DB_SSL_CA", "DOCS_ENABLED", "GIS_ENABLED")
GIS_FIELDS = ("latitude", "longitude", "flood_risk_flag", "flood_risk_category",
              "river_flood_category", "storm_surge_category")
ADDRESS = "Canalate, Malolos City, Bulacan, Philippines"  # Medium river flood when GIS is on
READ_SETTINGS = ("import json; from app.config import settings as s; "
                 "print(json.dumps([s.APP_ENV, s.CORS_ORIGINS, s.DB_SSL_CA, s.DOCS_ENABLED, s.GIS_ENABLED]))")


def _run(code, **env):
    """`code` in a fresh interpreter from Backend/, with every switch unset plus `env`."""
    clean = {k: v for k, v in os.environ.items() if k not in SWITCHES}
    clean.update(env)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=clean,
                          capture_output=True, text=True, timeout=300)


def _last_line(result):
    assert result.returncode == 0, result.stderr[-2000:]
    return result.stdout.strip().splitlines()[-1]


# ---- defaults and env parsing ----

def test_unset_switches_keep_the_local_behaviour():
    assert json.loads(_last_line(_run(READ_SETTINGS))) == [
        "local", ["http://localhost:3000", "http://localhost:5173"], None, True, True]


def test_switches_are_read_from_the_environment():
    out = _run(READ_SETTINGS, APP_ENV="production", SECRET_KEY="zztest-not-a-real-key",
               CORS_ORIGINS="https://zztest-a.example, https://zztest-b.example",
               DB_SSL_CA="/etc/secrets/zztest-ca.pem", DOCS_ENABLED="false", GIS_ENABLED="FALSE")
    assert json.loads(_last_line(out)) == [
        "production", ["https://zztest-a.example", "https://zztest-b.example"],
        "/etc/secrets/zztest-ca.pem", False, False]


def test_production_refuses_to_start_without_its_own_secret_key():
    out = _run("import app.config", APP_ENV="production", SECRET_KEY="")
    assert out.returncode != 0
    assert "SECRET_KEY must be set when APP_ENV=production" in out.stderr


def test_docs_on_by_default_and_can_be_switched_off():
    code = ("from fastapi.testclient import TestClient; from main import app; c = TestClient(app); "
            "print([c.get(p).status_code for p in ('/docs', '/redoc', '/openapi.json')])")
    assert _last_line(_run(code)) == "[200, 200, 200]"
    assert _last_line(_run(code, DOCS_ENABLED="false")) == "[404, 404, 404]"


def test_cors_origins_come_from_the_environment():
    code = ("from fastapi.testclient import TestClient; from main import app; c = TestClient(app); "
            "h = lambda o: c.options('/policyholders', headers={'Origin': o, "
            "'Access-Control-Request-Method': 'GET'}); "
            "print([(r.status_code, r.headers.get('access-control-allow-origin')) for r in "
            "(h('https://zztest.vercel.app'), h('http://localhost:5173'))])")
    assert _last_line(_run(code)) == "[(400, None), (200, 'http://localhost:5173')]"
    assert _last_line(_run(code, CORS_ORIGINS="https://zztest.vercel.app")) == \
        "[(200, 'https://zztest.vercel.app'), (400, None)]"


# ---- GIS switched off ----

@pytest.fixture
def gis_off(monkeypatch):
    """GIS_ENABLED=false for this test; records any geocoding or shapefile load (lookup_flood_risk
    swallows exceptions, so a raising stub would go unnoticed)."""
    calls = []
    monkeypatch.setattr(settings, "GIS_ENABLED", False)
    monkeypatch.setattr(flood_risk, "_geocode", lambda *a, **k: calls.append(("geocode", a)))
    monkeypatch.setattr(flood_risk, "_load_zones", lambda *a, **k: calls.append(("load_zones", a)) or [])
    return calls


def _add(db, obj):
    db.add(obj)
    db.flush()
    return obj


@pytest.fixture
def client(db):
    manager = _add(db, models.User(username="ZZTEST Golf Manager", password=hash_password("zz-test-pass1"),
                                   role="manager"))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_gis_off_lookup_is_empty_and_does_no_gis_work(gis_off):
    assert flood_risk.lookup_flood_risk(ADDRESS) == dict.fromkeys(GIS_FIELDS)
    assert gis_off == []


def test_gis_off_survey_and_motor_quotation_still_save_without_flood_risk(db, client, gis_off):
    owner = _add(db, models.Policyholder(last_name="ZZTEST Hotel", first_name="Gisoff"))
    fire_case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.fire_property))
    motor_case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.motor_car))
    vehicle = _add(db, models.Vehicle(insurance_case_id=motor_case.id, plate_no="ZZGIS01"))

    r = client.post("/fire-property/surveys", json={
        "insurance_case_id": fire_case.id, "name_of_insured": "ZZTEST Hotel Gisoff", "location_of_risk": ADDRESS})
    assert r.status_code == 200, r.text
    assert {f: r.json()[f] for f in GIS_FIELDS} == dict.fromkeys(GIS_FIELDS)
    survey = db.get(models.FirePropertySurvey, r.json()["id"])
    assert survey.location_of_risk == ADDRESS and survey.latitude is None and survey.flood_risk_category is None

    r = client.post("/motor/quotations", json={
        "insurance_case_id": motor_case.id, "vehicle_id": vehicle.id, "quotation_date": "2026-10-05",
        "insured_name": "ZZTEST Hotel Gisoff", "address": ADDRESS, "plate_no": "ZZGIS01"})
    assert r.status_code == 200, r.text
    assert {f: r.json()[f] for f in GIS_FIELDS} == dict.fromkeys(GIS_FIELDS)
    quotation = db.get(models.MotorQuotation, r.json()["id"])
    assert quotation.address == ADDRESS and quotation.latitude is None and quotation.flood_risk_category is None

    assert gis_off == []


def test_gis_off_motor_quotation_import_still_saves_without_flood_risk(db, gis_off):
    owner = _add(db, models.Policyholder(last_name="ZZTEST India", first_name="Gisoff"))
    case = _add(db, models.InsuranceCase(policyholder_id=owner.id, line_type=models.LineType.motor_car))
    _add(db, models.Vehicle(insurance_case_id=case.id, plate_no="ZZGIS02"))
    buf = io.BytesIO()
    pd.DataFrame([{"Date": dt.date(2026, 10, 5), "Insured Name": "ZZTEST India Gisoff", "Address": ADDRESS,
                   "Plate No.": "ZZGIS02", "Motor/Engine No.": "", "Serial/Chasis No.": "",
                   "Total Amount Due": 15000, "Sum Insured": 500000, "Make": "Toyota", "Model": "2020"}]
                 ).to_excel(buf, index=False)
    buf.seek(0)

    summary = import_motor.upload_motor_quotations(file=UploadFile(file=buf, filename="zztest_gis_off.xlsx"), db=db)

    assert summary.errors == []
    saved = db.query(models.MotorQuotation).filter(models.MotorQuotation.plate_no == "ZZGIS02").one()
    assert saved.address == ADDRESS
    assert all(getattr(saved, f) is None for f in GIS_FIELDS)
    assert gis_off == []
