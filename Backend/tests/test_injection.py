"""Injection tests (IAS2 item 5; the free Pentest-Tools Light scan doesn't run them).

Common SQL-injection and XSS payloads go to every endpoint that takes text: query and path
parameters, JSON bodies, upload cells, header rows and file names, the folder-import form field,
login and account fields. The endpoint list is read from the app's own OpenAPI schema, so a new
endpoint is covered automatically.

Pass means: never a 500; no SQL or driver text in any reply; no extra rows (an injected login logs
nobody in, a create adds exactly one row); a payload is stored as plain text and comes back
byte-for-byte as JSON data (React then shows it as text: Frontend/src/lib/noHtmlSinks.test.js).

All inside the rolled-back `db` fixture with ZZTEST records; GIS and the model refresh stubbed."""
import io
import json
from datetime import date, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.ml import jobs
from app.security import get_current_user, hash_password
from app.services import flood_risk
from app.services.user_service import get_user_by_username
from main import app

SQLI = ["' OR '1'='1' -- ", "\" OR \"\"=\"", "1; DROP TABLE users; --", "1 UNION SELECT username, password FROM users",
        "') OR SLEEP(5) #", "%' OR 1=1 #", "admin'/*", "\\'; SELECT 1; --"]
XSS = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "\"><svg onload=alert(1)>",
       "javascript:alert(1)", "{{7*7}}${7*7}", "ZZTEST\r\nSet-Cookie: x=1"]
PAYLOADS = SQLI + XSS
# Error/driver words that must never appear in a reply (after removing the echoed payload).
LEAK_SIGNS = ["sql syntax", "pymysql", "sqlalchemy", "operationalerror", "programmingerror", "integrityerror",
              "dataerror", "traceback", "mysql", "select ", "insert into", "update `", "delete from", "where "]
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NATO = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India", "Juliett", "Kilo",
        "Lima", "Mike", "November", "Oscar", "Papa"]


def assert_safe(r, payloads=PAYLOADS):
    assert r.status_code < 500, (r.request.method, r.request.url, r.status_code, r.text[:300])
    text = r.text
    for p in payloads:  # the reply may echo the payload itself (422 "input", stored value)
        for form in (p, json.dumps(p)[1:-1]):
            text = text.replace(form, "")
    low = text.lower()
    leaks = [s for s in LEAK_SIGNS if s in low]
    assert not leaks, (r.request.method, r.request.url, leaks, r.text[:300])


# ---- fixtures ----

def _add(db, obj):
    db.add(obj)
    db.flush()
    return obj


@pytest.fixture
def world(db, monkeypatch):
    """A ZZTEST chain for every required id, GIS off, model refresh off, a manager login."""
    monkeypatch.setattr(settings, "GIS_ENABLED", False)
    monkeypatch.setattr(flood_risk, "_geocode", lambda *a, **k: pytest.fail("no geocoding in tests"))
    today = date.today()
    ph = _add(db, models.Policyholder(last_name="ZZTEST Tango Injection"))
    fire_case = _add(db, models.InsuranceCase(policyholder_id=ph.id, line_type=models.LineType.fire_property))
    motor_case = _add(db, models.InsuranceCase(policyholder_id=ph.id, line_type=models.LineType.motor_car))
    vehicle = _add(db, models.Vehicle(insurance_case_id=motor_case.id, plate_no="ZZT 9001"))
    fq_free = _add(db, models.FirePropertyQuotation(insurance_case_id=fire_case.id))
    fq_used = _add(db, models.FirePropertyQuotation(insurance_case_id=fire_case.id))
    mq_free = _add(db, models.MotorQuotation(insurance_case_id=motor_case.id, vehicle_id=vehicle.id))
    mq_used = _add(db, models.MotorQuotation(insurance_case_id=motor_case.id, vehicle_id=vehicle.id))
    period = dict(period_from=today - timedelta(days=30), period_to=today + timedelta(days=300))
    fpol = _add(db, models.FirePropertyPolicy(quotation_id=fq_used.id, policy_no="ZZTEST-FP-INJ-1", **period))
    mpol = _add(db, models.MotorPolicy(quotation_id=mq_used.id, policy_no="ZZTEST-MC-INJ-1", **period))
    mclaim = _add(db, models.MotorClaim(motor_policy_id=mpol.id, date_of_loss=today))
    fclaim = _add(db, models.FirePropertyClaim(fire_property_policy_id=fpol.id, date_of_loss=today))
    manager = _add(db, models.User(username="ZZTEST Tango Manager", password=hash_password("zz-tango-pass1"),
                                   role="manager"))
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: manager
    app.dependency_overrides[jobs.schedule_model_refresh] = lambda: None
    ids = {
        "policyholder_id": ph.id, "vehicle_id": vehicle.id, "motor_policy_id": mpol.id,
        "fire_property_policy_id": fpol.id,
        "insurance_case_id": {"/fire-property": fire_case.id, "/motor": motor_case.id},
        "quotation_id": {"/fire-property": fq_free.id, "/motor": mq_free.id},
        "claim_id": {"/fire-property": fclaim.id, "/motor": mclaim.id},
    }
    try:
        # A 500 must show up as a status code here (as a client would see it), not as a raised error.
        yield {"client": TestClient(app, raise_server_exceptions=False), "ids": ids}
    finally:
        app.dependency_overrides.clear()


# ---- OpenAPI walk ----

SPEC = app.openapi()
COMPONENTS = SPEC["components"]["schemas"]


def _resolve(schema):
    return _resolve(COMPONENTS[schema["$ref"].split("/")[-1]]) if "$ref" in schema else schema


def _variants(schema):
    schema = _resolve(schema)
    return [_resolve(s) for s in schema.get("anyOf", [schema])]


def _is_free_text(schema):
    """A plain string field (no date/number/enum/object meaning): payloads must be stored as is."""
    vs = [v for v in _variants(schema) if v.get("type") != "null"]
    return bool(vs) and all(v.get("type") == "string" and "format" not in v and "enum" not in v for v in vs)


def _is_text(schema):
    return any(v.get("type") == "string" for v in _variants(schema))


def _operations(kind):
    for path, ops in SPEC["paths"].items():
        for method, op in ops.items():
            body = op.get("requestBody", {}).get("content", {})
            if kind == "params" and op.get("parameters"):
                yield method, path, op
            elif kind == "json" and "application/json" in body and path not in ("/login", "/users", "/users/me/password"):
                yield method, path, op


PARAM_OPS = list(_operations("params"))
JSON_OPS = list(_operations("json"))


def _id_for(name, path, ids):
    value = ids.get(name)
    if isinstance(value, dict):
        return next((v for prefix, v in value.items() if path.startswith(prefix) or f"{prefix}/" in path),
                    next(iter(value.values())))
    return value


def test_the_walk_found_every_text_endpoint():
    assert len(PARAM_OPS) >= 30 and len(JSON_OPS) >= 11
    assert ("post", "/policyholders") in [(m, p) for m, p, _ in JSON_OPS]
    assert ("get", "/ml/models/{model_name}") in [(m, p) for m, p, _ in PARAM_OPS]


# ---- query and path parameters ----

@pytest.mark.parametrize("payload", PAYLOADS)
def test_query_and_path_parameters(world, payload):
    """Every parameter of every endpoint gets the payload (one at a time, the rest valid)."""
    client, ids = world["client"], world["ids"]
    for method, path, op in PARAM_OPS:
        params = op["parameters"]
        for target in params:
            url, query = path, {}
            for p in params:
                value = payload if p is target else _valid_param(p, path, ids)
                if p["in"] == "path":
                    url = url.replace("{" + p["name"] + "}", _quote(str(value)))
                elif value is not None:
                    query[p["name"]] = value
            r = client.request(method.upper(), url, params=query)
            assert_safe(r, [payload])
            assert r.status_code in (400, 404, 405, 422), (method, url, query, r.status_code)


def _quote(s):
    from urllib.parse import quote
    return quote(s, safe="")


def _valid_param(p, path, ids):
    name, schema = p["name"], _resolve(p["schema"])
    if p["in"] == "path":
        return _id_for(name if name != "case_id" else "insurance_case_id", path, ids) or 999999999
    if name == "period":
        return "daily"
    if name == "date":
        return date.today().isoformat()
    return None  # optional query parameters: left out


# ---- JSON bodies ----

def _body(op, path, ids, payload, only_free_text):
    schema = _resolve(op["requestBody"]["content"]["application/json"]["schema"])
    body = {}
    for name, field in schema.get("properties", {}).items():
        if name.endswith("_id"):
            body[name] = _id_for(name, path, ids)
        elif (_is_free_text(field) if only_free_text else _is_text(field)):
            body[name] = payload
    for name in schema.get("required", []):
        if name not in body:
            body[name] = "fire_property" if name == "line_type" else payload
    return body


def _url(path, ids):
    for name in ("claim_id", "record_id"):
        path = path.replace("{" + name + "}", str(_id_for(name, path, ids) or 999999999))
    return path


@pytest.mark.parametrize("payload", PAYLOADS)
def test_every_json_text_field_with_payloads(world, payload):
    """Payload in EVERY string field, dates and choice lists included: rejected cleanly or saved."""
    client, ids = world["client"], world["ids"]
    for method, path, op in JSON_OPS:
        r = client.request(method.upper(), _url(path, ids), json=_body(op, path, ids, payload, only_free_text=False))
        assert_safe(r, [payload])


STORED_CHECKS = [  # (create endpoint, read-back endpoint)
    ("post", "/policyholders", "/policyholders/{id}"),
    ("post", "/fire-property/surveys", "/fire-property/surveys/{id}"),
    ("post", "/fire-property/quotations", "/fire-property/quotations/{id}"),
    ("post", "/fire-property/policies", "/fire-property/policies/{id}"),
    ("post", "/motor/vehicles", "/motor/vehicles/{id}"),
    ("post", "/motor/quotations", "/motor/quotations/{id}"),
    ("post", "/motor/policies", "/motor/policies/{id}"),
    ("patch", "/motor/claims/{claim_id}", "/motor/claims/{id}"),
    ("patch", "/fire-property/claims/{claim_id}", "/fire-property/claims/{id}"),
]


@pytest.mark.parametrize("payload", PAYLOADS)
@pytest.mark.parametrize("method, path, read_path", STORED_CHECKS)
def test_free_text_payloads_are_stored_and_returned_as_plain_text(world, db, method, path, read_path, payload):
    """Free-text fields hold the payload exactly; the API answers JSON data, never markup."""
    client, ids = world["client"], world["ids"]
    op = SPEC["paths"][path][method]
    body = _body(op, path, ids, payload, only_free_text=True)
    if "policies" in path:
        body["policy_no"] = f"ZZTEST-INJ-{PAYLOADS.index(payload)}-{path.split('/')[1]}"  # must be unique
    table = {"/policyholders": models.Policyholder}.get(path)
    before = db.query(table).count() if table else None

    r = client.request(method.upper(), _url(path, ids), json=body)
    assert_safe(r, [payload])
    if r.status_code == 422:  # fixed-list fields (claim status etc.) refuse it cleanly: drop those, retry
        refused = {e["loc"][-1] for e in r.json()["detail"]}
        assert refused and all(body.get(k) == payload for k in refused), r.text[:500]
        body = {k: v for k, v in body.items() if k not in refused}
        r = client.request(method.upper(), _url(path, ids), json=body)
        assert_safe(r, [payload])
    assert r.status_code == 200, (path, r.text[:500])
    assert r.headers["content-type"].startswith("application/json")
    created = r.json()
    texts = {k: v for k, v in body.items() if v == payload}
    assert texts, "no free-text field in " + path
    for k in texts:
        assert created[k] == payload, (path, k)

    back = client.get(read_path.replace("{id}", str(created["id"])))
    assert back.status_code == 200 and back.headers["content-type"].startswith("application/json")
    for k in texts:
        assert back.json()[k] == payload, (path, k)
    assert payload in json.loads(back.text).values()  # JSON-decoded: exact, not HTML-escaped or altered
    if table:
        assert db.query(table).count() == before + 1  # exactly one row, no more


# ---- login and accounts ----

@pytest.mark.parametrize("payload", PAYLOADS)
def test_injected_logins_log_nobody_in(world, payload):
    client = world["client"]
    for body in ({"username": payload, "password": payload}, {"username": "ZZTEST Tango Manager", "password": payload},
                 {"username": payload, "password": "zz-tango-pass1"}):
        r = client.post("/login", json=body)
        assert_safe(r, [payload])
        assert r.status_code == 401 and "access_token" not in r.text


@pytest.mark.parametrize("payload", PAYLOADS)
def test_user_lookup_matches_only_the_exact_name(world, db, payload):
    assert get_user_by_username(db, payload) is None
    assert get_user_by_username(db, "ZZTEST Tango Manager' -- ") is None


@pytest.mark.parametrize("payload", ["ZZTEST ' OR '1'='1' -- ", "ZZTEST <script>alert(1)</script>"])
def test_injected_usernames_are_stored_as_text_and_only_log_themselves_in(world, db, payload):
    client = world["client"]
    count = db.query(models.User).count()
    r = client.post("/users", json={"username": payload, "password": "zz-uniform-pass9"})
    assert_safe(r, [payload])
    assert r.status_code == 200 and r.json()["user"]["username"] == payload.strip()  # names are trimmed
    assert db.query(models.User).count() == count + 1
    r = client.post("/login", json={"username": payload, "password": "zz-uniform-pass9"})
    assert r.status_code == 200 and r.json()["role"] == "admin"  # its own account, not the manager's
    assert client.post("/login", json={"username": payload, "password": "zz-tango-pass1"}).status_code == 401


@pytest.mark.parametrize("payload", PAYLOADS)
def test_password_fields_with_payloads(world, payload):
    r = world["client"].post("/users/me/password", json={"current_password": payload, "new_password": payload})
    assert_safe(r, [payload])
    assert r.status_code == 400


# ---- uploads ----

def _xlsx(columns, rows):
    buf = io.BytesIO()
    pd.DataFrame(rows, columns=columns).to_excel(buf, index=False)
    return buf.getvalue()


UPLOAD_PATHS = [p for p, ops in SPEC["paths"].items() if "post" in ops and p.endswith("/upload")
                and "multipart/form-data" in ops["post"].get("requestBody", {}).get("content", {})
                and p != "/import/batch/upload"]


def test_every_single_file_importer_gets_payload_headers_cells_and_file_names(world):
    client = world["client"]
    assert len(UPLOAD_PATHS) == 9
    content = _xlsx(PAYLOADS, [PAYLOADS, list(reversed(PAYLOADS))])  # payloads as headers AND cells
    for path in UPLOAD_PATHS:
        for name in ("<script>alert(1)</script>.xlsx", "x' OR '1'='1.xlsx"):
            r = client.post(path, files={"file": (name, content, XLSX)})
            assert_safe(r, PAYLOADS + [name])


def test_policyholder_upload_cells_are_stored_as_text(world, db):
    client = world["client"]
    columns = ["Last Name", "First Name", "Present Address", "Occupation", "Employer"]
    names = [f"ZZTEST {w} Uniform" for w in NATO[:len(PAYLOADS)]]  # distinct roots: no fuzzy matches
    rows = [[n, p, p, p, p] for n, p in zip(names, PAYLOADS)]
    before = db.query(models.Policyholder).count()
    r = client.post("/import/policyholders/upload", files={"file": ("zz.xlsx", _xlsx(columns, rows), XLSX)})
    assert_safe(r)
    assert r.status_code == 200 and r.json()["errors"] == []
    stored = {ph.last_name: ph for ph in db.query(models.Policyholder).filter(
        models.Policyholder.last_name.in_(names)).all()}
    assert db.query(models.Policyholder).count() - before == len(stored) == len(PAYLOADS)  # one row each
    in_file = pd.read_excel(io.BytesIO(_xlsx(columns, rows)), dtype=str)["First Name"].tolist()
    for n, p, cell in zip(names, PAYLOADS, in_file):
        ph = stored[n]
        # Stored = the cell as Excel holds it (openpyxl turns \r\n into \n\n), trimmed on import
        # (clean_cell_value); nothing else about the text changes.
        assert cell.strip() == p.strip() or "\r" in p
        assert (ph.first_name, ph.present_address, ph.occupation, ph.employer) == (cell.strip(),) * 4, p


def test_vehicle_upload_cells(world):
    columns = ["Insured Name", "Make", "Model", "Body Type", "Color", "Plate No", "Motor Engine No", "Serial Chassis No"]
    rows = [[p] * len(columns) for p in PAYLOADS]
    r = world["client"].post("/import/vehicles/upload", files={"file": ("zz.xlsx", _xlsx(columns, rows), XLSX)})
    assert_safe(r)
    assert r.status_code == 200


@pytest.mark.parametrize("payload", PAYLOADS)
def test_folder_import_type_field_and_file_name(world, payload):
    client = world["client"]
    content = _xlsx(["Last Name"], [["ZZTEST Victor"]])
    r = client.post("/import/batch/upload", files=[("files", (f"{payload}.xlsx", content, XLSX))],
                    data={"import_types": [payload]})
    assert_safe(r, [payload])
    assert r.status_code in (200, 400, 422)
    r = client.post("/import/batch/detect", files=[("files", (f"{payload}.xlsx", content, XLSX))])
    assert_safe(r, [payload])


# ---- finding F1 (fixed): text longer than its column is a 422, not a 500 ----

def test_every_limited_field_one_character_too_long_is_a_clean_422(world):
    """Before the fix MySQL's "Data too long" became a 500 (e.g. gender > 20, plate_no > 30)."""
    client, ids = world["client"], world["ids"]
    from app import schemas
    checked = 0
    for method, path, op in JSON_OPS + [("post", "/users", SPEC["paths"]["/users"]["post"])]:
        ref = op["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
        limits = getattr(getattr(schemas, ref), "__column_limits__", {})  # no text fields: no limits
        if not limits:
            continue
        valid = _body(op, path, ids, "ZZTEST Whiskey", only_free_text=True)
        for name, limit in limits.items():
            body = dict(valid, **{name: "W" * (limit + 1)})
            r = client.request(method.upper(), _url(path, ids), json=body)
            assert_safe(r)
            assert r.status_code == 422, (path, name, r.status_code, r.text[:200])
            errors = [e for e in r.json()["detail"] if e["loc"][-1] == name]
            assert errors and errors[0]["msg"] == f"String should have at most {limit} characters", (path, name)
            checked += 1
    assert checked >= 120  # 130 on 2026-10-09: every length-limited field of every JSON endpoint
