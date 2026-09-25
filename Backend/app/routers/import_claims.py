"""
Bulk import for claims (Objective 1.3) -- Motor and Fire & Property.

Each row links to an existing policy by Policy No. (exact match after trimming,
case-insensitive). No match or several -> needs_review, resolved by staff picking
the policy (import_policyholders.resolve_import_record). This importer bypasses
Pydantic, so fixed-list values go through schemas.canonical_choice() and the
date-of-loss rule reuses claims.loss_period_error() -- same rules as the Claims API.
"""
import re
from decimal import Decimal, InvalidOperation

import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.routers.claims import loss_period_error

router = APIRouter(
    prefix="/import/claims",
    tags=["Bulk Import — Claims"],
    dependencies=[Depends(get_current_user)],
)

_COMMON_COLUMN_MAP = {
    "accutermclaimno": "accuterm_claim_no",
    "assured": "assured",
    "claimantname": "claimant_name",          # optional column
    "policyno": "policy_no",                  # links the claim -- not stored on it
    "pladatedatereported": "date_reported",
    "pladate": "date_reported",
    "dateofloss": "date_of_loss",
    "dateofdocssubmission": "date_docs_submitted",
    "natureofloss": "nature_of_loss",
    "claimtype": "claim_type",
    "updates": "updates",
    "dateupdated": "date_updated",
    "agentname": "agent_name",
    "amountofrepairestimate": "repair_estimate_amount",
    "dateofloareceived": "loa_received_date",
    "loano": "loa_no",
    "loaamount": "loa_amount",
    "netliability": "net_liability",
    "status": "status",
    "billingdateandremarks": "billing_date_remarks",
    "finalstatus": "final_status",
    "claiminvestigationresult": "claim_investigation_result",
}
MOTOR_CLAIM_COLUMN_MAP = {**_COMMON_COLUMN_MAP, "plateno": "plate_no", "coveragetype": "coverage_type", "shopcasa": "shop_casa"}
FIRE_CLAIM_COLUMN_MAP = {**_COMMON_COLUMN_MAP, "adjuster": "adjuster"}

# Formula/duplicate columns in Maagap's own claims sheet: recognised as claims
# headers for detection, never stored. "dateofloss1" is how pandas renames a
# second "Date of Loss" column. "Assureds Name" is only read when the sheet has
# no "Assured" column at all (see row_to_claim_fields).
IGNORED_HEADERS = {"sn", "noofdaysasoftoday", "turnaroundtime", "dateofloss1", "assuredsname"}
# Headers only one claims line has -- import_batch uses these to tell the two apart.
MOTOR_ONLY_HEADERS = {"plateno", "coveragetype", "shopcasa"}
FIRE_ONLY_HEADERS = {"adjuster"}

BLANK_MARKERS = {"", "-", "–", "—"}
DATE_FIELDS = ("date_reported", "date_of_loss", "date_docs_submitted", "date_updated", "loa_received_date")
AMOUNT_FIELDS = ("repair_estimate_amount", "loa_amount", "net_liability")

# Re-upload duplicate key (see find_duplicate_claim). accuterm_claim_no alone isn't
# unique -- OD + TP rows of one accident share it -- so the key also includes who
# and what the claim is for. Progress fields (status, LOA, net liability, ...) are
# deliberately left out: they change over a claim's life.
_DEDUPE_FIELDS = ("accuterm_claim_no", "assured", "claimant_name", "date_of_loss", "nature_of_loss", "claim_type")

LINES = {
    models.ImportType.motor_claim: {
        "column_map": MOTOR_CLAIM_COLUMN_MAP,
        "policy_model": models.MotorPolicy,
        "claim_model": models.MotorClaim,
        "policy_fk": "motor_policy_id",
        "choices": {
            "nature_of_loss": schemas.MOTOR_NATURE_OF_LOSS_OPTIONS,
            "coverage_type": schemas.MOTOR_COVERAGE_TYPE_OPTIONS,
            "claim_type": schemas.CLAIM_TYPE_OPTIONS,
            "final_status": schemas.CLAIM_FINAL_STATUS_OPTIONS,
            "claim_investigation_result": schemas.CLAIM_INVESTIGATION_RESULT_OPTIONS,
        },
        "dedupe_fields": _DEDUPE_FIELDS + ("coverage_type", "plate_no"),
    },
    models.ImportType.fire_property_claim: {
        "column_map": FIRE_CLAIM_COLUMN_MAP,
        "policy_model": models.FirePropertyPolicy,
        "claim_model": models.FirePropertyClaim,
        "policy_fk": "fire_property_policy_id",
        "choices": {
            "nature_of_loss": schemas.FIRE_NATURE_OF_LOSS_OPTIONS,
            "claim_type": schemas.CLAIM_TYPE_OPTIONS,
            "final_status": schemas.CLAIM_FINAL_STATUS_OPTIONS,
            "claim_investigation_result": schemas.CLAIM_INVESTIGATION_RESULT_OPTIONS,
        },
        "dedupe_fields": _DEDUPE_FIELDS,
    },
}


def normalize_header(header) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).strip().lower())


def clean_claim_cell(value):
    """Same as the other importers' clean_cell_value, plus Maagap's "-" placeholder -> None."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return None if text in BLANK_MARKERS else text


def _parse_date(field, value):
    # Unlike the older importers (unparseable date -> silently NULL), a bad date
    # fails the row: a silently-NULL date_of_loss would skip the coverage check.
    try:
        return pd.to_datetime(value).date()
    except Exception:
        raise ValueError(f"{field}: '{value}' is not a valid date")


def _parse_amount(field, value):
    try:
        amount = Decimal(re.sub(r"[,\s₱]|php", "", value, flags=re.IGNORECASE))
    except InvalidOperation:
        raise ValueError(f"{field}: '{value}' is not a valid amount")
    if not amount.is_finite():
        raise ValueError(f"{field}: '{value}' is not a valid amount")
    return amount


def row_to_claim_fields(row, spec):
    """
    Parse one row (a pandas row, or a stored raw_data dict on resolve).
    Returns (claim fields, Policy No.). Raises ValueError naming the field on
    any invalid date, amount, or fixed-list value.
    """
    headers = {normalize_header(col): col for col in row.keys()}
    fields = {}
    for col, value in row.items():
        mapped = spec["column_map"].get(normalize_header(col))
        cleaned = clean_claim_cell(value)
        if mapped and cleaned is not None:
            fields[mapped] = cleaned

    if "assured" not in headers and "assuredsname" in headers:
        fallback = clean_claim_cell(row[headers["assuredsname"]])
        if fallback is not None:
            fields["assured"] = fallback

    for field in DATE_FIELDS:
        if field in fields:
            fields[field] = _parse_date(field, fields[field])
    for field in AMOUNT_FIELDS:
        if field in fields:
            fields[field] = _parse_amount(field, fields[field])
    for field, options in spec["choices"].items():
        if field in fields:
            fields[field] = schemas.canonical_choice(fields[field], options, field)

    policy_no = fields.pop("policy_no", None)
    return fields, policy_no


def find_policies_by_no(db: Session, spec, policy_no):
    if not policy_no:
        return []
    model = spec["policy_model"]
    return db.query(model).filter(
        func.lower(func.trim(model.policy_no)) == policy_no.strip().lower()
    ).all()


def _same(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return (a or "").strip().lower() == (b or "").strip().lower()
    return a == b


def find_duplicate_claim(db: Session, spec, policy_id, fields):
    model = spec["claim_model"]
    existing = db.query(model).filter(getattr(model, spec["policy_fk"]) == policy_id).all()
    return next(
        (c for c in existing if all(_same(getattr(c, f), fields.get(f)) for f in spec["dedupe_fields"])),
        None,
    )


def _create_claim(db: Session, spec, policy, fields):
    """Coverage-period check, then re-upload duplicate check, then insert. Returns the MatchStatus."""
    error = loss_period_error(fields.get("date_of_loss"), policy)
    if error:
        raise ValueError(error)
    if find_duplicate_claim(db, spec, policy.id, fields):
        return models.MatchStatus.matched
    db.add(spec["claim_model"](**{spec["policy_fk"]: policy.id}, **fields))
    db.flush()
    return models.MatchStatus.unmatched


def _policy_links(policy):
    case = policy.quotation.insurance_case
    return case.id, case.policyholder_id


def _upload_claims(file: UploadFile, db: Session, import_type):
    spec = LINES[import_type]
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        # dtype=str keeps claim/LOA/policy numbers exactly as typed (no float
        # upcast, no lost leading zeros) -- same reasoning as the Policyholder importer.
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file, dtype=str)
        else:
            df = pd.read_excel(file.file, dtype=str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    data_headers = set(spec["column_map"]) | {"assuredsname"}
    matched_count = 0
    unmatched_created_count = 0
    needs_review_count = 0
    failed_count = 0
    skipped_blank = 0
    import_record_ids = []
    errors = []

    for idx, row in df.iterrows():
        source_row = idx + 2
        raw_data = {str(k): clean_claim_cell(v) for k, v in row.items()}

        # Maagap's formula columns (SN, No. of Days, TAT) often run further down the
        # sheet than the real data -- a row with nothing in any claims column is
        # padding, not a claim, and isn't counted.
        if not any(v is not None for k, v in raw_data.items() if normalize_header(k) in data_headers):
            skipped_blank += 1
            continue

        try:
            fields, policy_no = row_to_claim_fields(row, spec)
            policies = find_policies_by_no(db, spec, policy_no)

            if len(policies) != 1:
                # Unknown, blank, or ambiguous Policy No. -- staff pick the policy in Needs Review.
                record = models.ImportRecord(
                    source_file=file.filename, source_row=source_row,
                    import_type=import_type,
                    match_status=models.MatchStatus.needs_review,
                    raw_data=raw_data,
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                db.commit()

                import_record_ids.append(record.id)
                needs_review_count += 1
                continue

            policy = policies[0]
            status = _create_claim(db, spec, policy, fields)
            case_id, policyholder_id = _policy_links(policy)

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=import_type,
                match_status=status,
                matched_case_id=case_id,
                matched_policyholder_id=policyholder_id,
                raw_data=raw_data,
            )
            db.add(record)
            db.flush()
            db.refresh(record)

            db.commit()  # everything created for this row is saved together, or not at all

            import_record_ids.append(record.id)
            if status == models.MatchStatus.matched:
                matched_count += 1
            else:
                unmatched_created_count += 1

        except Exception as e:
            db.rollback()
            failed_count += 1
            errors.append(schemas.ImportRowError(source_row=source_row, error=str(e)))

    return schemas.ImportSummary(
        source_file=file.filename,
        total_rows=len(df) - skipped_blank,
        matched=matched_count,
        unmatched_created=unmatched_created_count,
        needs_review=needs_review_count,
        failed=failed_count,
        import_record_ids=import_record_ids,
        errors=errors,
    )


@router.post("/motor/upload", response_model=schemas.ImportSummary)
def upload_motor_claims(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return _upload_claims(file, db, models.ImportType.motor_claim)


@router.post("/fire-property/upload", response_model=schemas.ImportSummary)
def upload_fire_property_claims(file: UploadFile = File(...), db: Session = Depends(get_db)):
    return _upload_claims(file, db, models.ImportType.fire_property_claim)


# ------------------------------------------------------------
# Needs-review resolution -- called from import_policyholders. A claims row is
# only ever stuck on WHICH POLICY it belongs to, never on a policyholder.
# ------------------------------------------------------------

def list_policy_candidates(db: Session, record: models.ImportRecord):
    """Every policy on the claim's line, closest Policy No. to the row's first -- a typo still surfaces near the top."""
    spec = LINES[record.import_type]
    wanted = ""
    for col, value in (record.raw_data or {}).items():
        if normalize_header(col) == "policyno":
            wanted = (clean_claim_cell(value) or "").lower()

    policies = db.query(spec["policy_model"]).all()
    policies.sort(key=lambda p: (-fuzz.ratio(wanted, (p.policy_no or "").lower()), p.id))
    return [
        schemas.PolicyCandidate(
            id=p.id, policy_no=p.policy_no, insured_name_address=p.insured_name_address,
            period_from=p.period_from, period_to=p.period_to,
        )
        for p in policies
    ]


def create_claim_for_policy(db: Session, record: models.ImportRecord, policy_id: int):
    """Same validation, coverage check and duplicate check as the upload path."""
    spec = LINES[record.import_type]
    policy = db.query(spec["policy_model"]).filter(spec["policy_model"].id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    try:
        fields, _ = row_to_claim_fields(record.raw_data or {}, spec)
        status = _create_claim(db, spec, policy, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    case_id, policyholder_id = _policy_links(policy)
    return case_id, policyholder_id, status
