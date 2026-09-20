import re
import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.routers import import_shared
from app.services.flood_risk import lookup_flood_risk

router = APIRouter(
    prefix="/import/motor",
    tags=["Bulk Import — Motor & Car"],
    dependencies=[Depends(get_current_user)],
)

MATCH_THRESHOLD = 90     # policyholder name-match confidence
REVIEW_THRESHOLD = 70


COLUMN_MAP = {
    "date": "quotation_date",
    "insuredname": "insured_name",          # drives the policyholder, not stored on the quotation
    "address": "address",
    "unit": "unit",
    "classification": "classification",
    "color": "color",
    "deductible": "deductible",
    "plateno": "plate_no",
    "bank": "bank",
    "totalamountdue": "total_amount_due",
    # Vehicle Description fields
    "model": "model",
    "make": "make",
    "bodytype": "body_type",
    "motorengineno": "motor_engine_no",
    "serialchasisno": "serial_chassis_no",
    "serialchassisno": "serial_chassis_no",
    "authorizedcapacity": "authorized_capacity",
}

MOTOR_POLICY_COLUMN_MAP = {
    "issuedate": "issue_date",
    "insurednameaddress": "insured_name_address",
    "lineofinsurance": "line_of_insurance",
    "policyno": "policy_no",
    "renewingpolicyno": "renewing_policy_no",
    "periodfrom": "period_from",
    "periodto": "period_to",
    "tin": "tin",
    "agencycode": "agency_code",
    "cocno": "coc_no",
    "coino": "coi_no",
    "endorsementno": "endorsement_no",
    "totalamountdue": "total_amount_due",
    "replacingcovernoteno": "replacing_cover_note_no",
    "premiuminvoiceno": "premium_invoice_no",
    "officialreceiptno": "official_receipt_no",
    "deductible": "deductible",
}


def normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).strip().lower())


def clean_cell_value(value):
    """
    Converts a pandas cell value to a clean string. If an Excel column mixes
    numbers with any blank cells, pandas upcasts the whole column to float64
    (e.g. plate/engine/chassis number becomes "...0"). This matters MOST here,
    since vehicle matching is an EXACT string comparison — a single blank cell
    anywhere in the column would otherwise corrupt every value, silently
    breaking duplicate-vehicle detection for the whole file. Strips the fake
    ".0" while leaving genuine decimals untouched.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def row_to_fields(row: pd.Series) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned

    for money_field in ("total_amount_due", "deductible"):
        if money_field in fields:
            cleaned = re.sub(r"[^\d.]", "", fields[money_field])
            fields[money_field] = cleaned if cleaned else None

    if "quotation_date" in fields:
        try:
            fields["quotation_date"] = pd.to_datetime(fields["quotation_date"]).date()
        except Exception:
            fields["quotation_date"] = None

    return fields


def row_to_motor_policy_fields(row) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = MOTOR_POLICY_COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned

    for money_field in ("total_amount_due", "deductible"):
        if money_field in fields:
            cleaned = re.sub(r"[^\d.]", "", fields[money_field])
            fields[money_field] = cleaned if cleaned else None

    for date_field in ("issue_date", "period_from", "period_to"):
        if date_field in fields:
            try:
                fields[date_field] = pd.to_datetime(fields[date_field]).date()
            except Exception:
                fields[date_field] = None

    return fields


def normalize_name(value: str) -> str:
    """
    Strips periods and collapses whitespace before lowercasing, so a combined
    "First M. Last" string and a name rebuilt from separate first/middle/last
    DB columns (no period on the middle initial) compare as identical instead
    of relying on raw fuzzy-ratio alone to clear MATCH_THRESHOLD.
    """
    return re.sub(r"\s+", " ", (value or "").replace(".", "")).strip().lower()


def full_name(last: str, first: str = "", middle: str = "") -> str:
    return normalize_name(f"{first or ''} {middle or ''} {last or ''}")


def find_existing_vehicle(db: Session, plate_no: str, engine_no: str, chassis_no: str):
    """Exact match on ANY one identifier is enough to call it the same vehicle."""
    query = db.query(models.Vehicle)
    conditions = []
    if plate_no:
        conditions.append(models.Vehicle.plate_no == plate_no)
    if engine_no:
        conditions.append(models.Vehicle.motor_engine_no == engine_no)
    if chassis_no:
        conditions.append(models.Vehicle.serial_chassis_no == chassis_no)

    if not conditions:
        return None

    from sqlalchemy import or_
    return query.filter(or_(*conditions)).first()


@router.post("/quotations/upload", response_model=schemas.ImportSummary)
def upload_motor_quotations(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        df = pd.read_csv(file.file) if file.filename.lower().endswith(".csv") else pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    ph_pool = []
    for ph in db.query(models.Policyholder).all():
        ph_pool.append({
            "source": "db", "id": ph.id,
            "name": full_name(ph.last_name, ph.first_name, ph.middle_name),
        })

    matched_count = 0
    unmatched_created_count = 0
    needs_review_count = 0
    failed_count = 0
    import_record_ids = []
    errors = []

    for idx, row in df.iterrows():
        source_row = idx + 2

        try:
            fields = row_to_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            plate_no = fields.get("plate_no", "")
            engine_no = fields.get("motor_engine_no", "")
            chassis_no = fields.get("serial_chassis_no", "")

            existing_vehicle = find_existing_vehicle(db, plate_no, engine_no, chassis_no)

            matched_policyholder_id = None
            matched_case_id = None

            # ------------------------------------------------------------
            # CASE A — this exact vehicle is already known.
            # This is a re-quote: reuse its existing case, unless this specific
            # quotation (same date + same amount) is a re-uploaded duplicate.
            # ------------------------------------------------------------
            if existing_vehicle:
                case = existing_vehicle.insurance_case
                matched_policyholder_id = case.policyholder_id
                matched_case_id = case.id

                existing_quotations = db.query(models.MotorQuotation).filter(
                    models.MotorQuotation.vehicle_id == existing_vehicle.id
                ).all()

                def _amount_equal(a, b):
                    try:
                        return a is not None and b is not None and float(a) == float(b)
                    except (TypeError, ValueError):
                        return False

                is_duplicate = any(
                    q.quotation_date == fields.get("quotation_date")
                    and _amount_equal(q.total_amount_due, fields.get("total_amount_due"))
                    for q in existing_quotations
                )

                if is_duplicate:
                    status = models.MatchStatus.matched
                else:
                    new_quotation = models.MotorQuotation(
                        insurance_case_id=case.id,
                        vehicle_id=existing_vehicle.id,
                        quotation_date=fields.get("quotation_date") or None,
                        insured_name=fields.get("insured_name"),
                        address=fields.get("address"),
                        unit=fields.get("unit"),
                        classification=fields.get("classification"),
                        color=fields.get("color"),
                        deductible=fields.get("deductible") or None,
                        plate_no=plate_no or None,
                        total_amount_due=fields.get("total_amount_due") or None,
                        **lookup_flood_risk(fields.get("address")),
                    )
                    db.add(new_quotation)
                    db.flush()

                    status = models.MatchStatus.unmatched

            # ------------------------------------------------------------
            # CASE B — brand new vehicle. Match/create the owner, then create
            # a fresh case + vehicle + quotation.
            # ------------------------------------------------------------
            else:
                candidate_name = full_name(fields.get("insured_name", ""))

                best_score, best_entry = 0, None
                for entry in ph_pool:
                    score = fuzz.token_sort_ratio(candidate_name, entry["name"])
                    if score > best_score:
                        best_score, best_entry = score, entry

                if best_score >= MATCH_THRESHOLD and best_entry:
                    policyholder_id = best_entry["id"]

                elif best_score >= REVIEW_THRESHOLD:
                    record = models.ImportRecord(
                        source_file=file.filename, source_row=source_row,
                        import_type=models.ImportType.motor,
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

                else:
                    last_name = fields.get("insured_name", "").strip() or None
                    import_shared.require_name(None, last_name, "Insured Name")
                    new_ph = models.Policyholder(last_name=last_name)
                    db.add(new_ph)
                    db.flush()
                    db.refresh(new_ph)

                    ph_pool.append({"source": "db", "id": new_ph.id, "name": candidate_name})
                    policyholder_id = new_ph.id

                new_case = models.InsuranceCase(
                    policyholder_id=policyholder_id,
                    line_type=models.LineType.motor_car,
                )
                db.add(new_case)
                db.flush()
                db.refresh(new_case)

                new_vehicle = models.Vehicle(
                    insurance_case_id=new_case.id,
                    model=fields.get("model"),
                    make=fields.get("make"),
                    body_type=fields.get("body_type"),
                    color=fields.get("color"),
                    plate_no=plate_no or None,
                    motor_engine_no=engine_no or None,
                    serial_chassis_no=chassis_no or None,
                    authorized_capacity=fields.get("authorized_capacity"),
                )
                db.add(new_vehicle)
                db.flush()
                db.refresh(new_vehicle)

                new_quotation = models.MotorQuotation(
                    insurance_case_id=new_case.id,
                    vehicle_id=new_vehicle.id,
                    quotation_date=fields.get("quotation_date") or None,
                    insured_name=fields.get("insured_name"),
                    address=fields.get("address"),
                    unit=fields.get("unit"),
                    classification=fields.get("classification"),
                    color=fields.get("color"),
                    deductible=fields.get("deductible") or None,
                    plate_no=plate_no or None,
                    total_amount_due=fields.get("total_amount_due") or None,
                    **lookup_flood_risk(fields.get("address")),
                )
                db.add(new_quotation)
                db.flush()

                matched_policyholder_id = policyholder_id
                matched_case_id = new_case.id
                status = models.MatchStatus.unmatched

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.motor,
                match_status=status,
                matched_policyholder_id=matched_policyholder_id,
                matched_case_id=matched_case_id,
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
            # One bad row should never take down the whole upload. Undo
            # anything this row partially created, record what went wrong,
            # and move on to the next row.
            db.rollback()
            failed_count += 1
            errors.append(schemas.ImportRowError(source_row=source_row, error=str(e)))

    return schemas.ImportSummary(
        source_file=file.filename,
        total_rows=len(df),
        matched=matched_count,
        unmatched_created=unmatched_created_count,
        needs_review=needs_review_count,
        failed=failed_count,
        import_record_ids=import_record_ids,
        errors=errors,
    )


# ------------------------------------------------------------
# Needs-review resolution — called from import_policyholders.resolve_import_record
# once it knows the policyholder for a motor-origin row. Runs the same
# vehicle/quotation creation the main upload path above uses, so resolving a
# review row doesn't just link a policyholder while silently dropping the
# vehicle/quotation data. Re-checks for an existing vehicle in case one was
# created by a separate upload after this row was queued for review.
# ------------------------------------------------------------

def new_policyholder_fields(record: models.ImportRecord) -> dict:
    fields = row_to_fields(record.raw_data or {})
    return {"last_name": (fields.get("insured_name") or "").strip() or None}


def resolve_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_fields(record.raw_data or {})
    plate_no = fields.get("plate_no", "")
    engine_no = fields.get("motor_engine_no", "")
    chassis_no = fields.get("serial_chassis_no", "")

    existing_vehicle = find_existing_vehicle(db, plate_no, engine_no, chassis_no)

    if existing_vehicle:
        case = existing_vehicle.insurance_case
        existing_quotations = db.query(models.MotorQuotation).filter(
            models.MotorQuotation.vehicle_id == existing_vehicle.id
        ).all()

        def _amount_equal(a, b):
            try:
                return a is not None and b is not None and float(a) == float(b)
            except (TypeError, ValueError):
                return False

        is_duplicate = any(
            q.quotation_date == fields.get("quotation_date")
            and _amount_equal(q.total_amount_due, fields.get("total_amount_due"))
            for q in existing_quotations
        )
        if is_duplicate:
            return case.id, models.MatchStatus.matched

        new_quotation = models.MotorQuotation(
            insurance_case_id=case.id,
            vehicle_id=existing_vehicle.id,
            quotation_date=fields.get("quotation_date") or None,
            insured_name=fields.get("insured_name"),
            address=fields.get("address"),
            unit=fields.get("unit"),
            classification=fields.get("classification"),
            color=fields.get("color"),
            deductible=fields.get("deductible") or None,
            plate_no=plate_no or None,
            total_amount_due=fields.get("total_amount_due") or None,
            **lookup_flood_risk(fields.get("address")),
        )
        db.add(new_quotation)
        db.flush()
        return case.id, models.MatchStatus.unmatched

    new_case = models.InsuranceCase(policyholder_id=policyholder_id, line_type=models.LineType.motor_car)
    db.add(new_case)
    db.flush()
    db.refresh(new_case)

    new_vehicle = models.Vehicle(
        insurance_case_id=new_case.id,
        model=fields.get("model"),
        make=fields.get("make"),
        body_type=fields.get("body_type"),
        color=fields.get("color"),
        plate_no=plate_no or None,
        motor_engine_no=engine_no or None,
        serial_chassis_no=chassis_no or None,
        authorized_capacity=fields.get("authorized_capacity"),
    )
    db.add(new_vehicle)
    db.flush()
    db.refresh(new_vehicle)

    new_quotation = models.MotorQuotation(
        insurance_case_id=new_case.id,
        vehicle_id=new_vehicle.id,
        quotation_date=fields.get("quotation_date") or None,
        insured_name=fields.get("insured_name"),
        address=fields.get("address"),
        unit=fields.get("unit"),
        classification=fields.get("classification"),
        color=fields.get("color"),
        deductible=fields.get("deductible") or None,
        plate_no=plate_no or None,
        total_amount_due=fields.get("total_amount_due") or None,
        **lookup_flood_risk(fields.get("address")),
    )
    db.add(new_quotation)
    db.flush()

    return new_case.id, models.MatchStatus.unmatched


# ------------------------------------------------------------
# MOTOR POLICIES
# A policy MUST link to an existing quotation (required FK, no shared ID in the
# source data) -- see import_shared.find_best_unattached_quotation for the
# amount/date matching heuristic this relies on. Same structure as the Fire &
# Property Policy importer.
# ------------------------------------------------------------

def _resolve_or_create_motor_policy(db: Session, policyholder_id: int, fields: dict):
    """Shared by the main upload loop and resolve_motor_policy_for_policyholder."""
    policy_no = fields.get("policy_no")
    if policy_no:
        existing = (
            db.query(models.MotorPolicy)
            .join(models.MotorQuotation)
            .join(models.InsuranceCase)
            .filter(
                models.MotorPolicy.policy_no == policy_no,
                models.InsuranceCase.policyholder_id == policyholder_id,
            )
            .first()
        )
        if existing:
            return existing.quotation.insurance_case_id, models.MatchStatus.matched

    result = import_shared.find_best_unattached_quotation(
        db, policyholder_id, models.LineType.motor_car,
        models.MotorQuotation, models.MotorPolicy,
        amount_getter=lambda q: q.total_amount_due,
        date_getter=lambda q: q.quotation_date,
        candidate_amount=fields.get("total_amount_due"),
        candidate_date=fields.get("issue_date") or fields.get("period_from"),
    )

    if result["status"] != "confident":
        return None, models.MatchStatus.needs_review

    quotation = result["candidate"]
    policy_fields = {k: v for k, v in fields.items() if k != "insured_name_address"}
    new_policy = models.MotorPolicy(
        quotation_id=quotation.id,
        insured_name_address=fields.get("insured_name_address"),
        **policy_fields,
    )
    db.add(new_policy)
    db.flush()

    return quotation.insurance_case_id, models.MatchStatus.unmatched


@router.post("/policies/upload", response_model=schemas.ImportSummary)
def upload_motor_policies(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        df = pd.read_csv(file.file) if file.filename.lower().endswith(".csv") else pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    ph_pool = []
    for ph in db.query(models.Policyholder).all():
        ph_pool.append({
            "source": "db", "id": ph.id,
            "name": full_name(ph.last_name, ph.first_name, ph.middle_name),
            "addr": (ph.present_address or "").lower(),
            "phone": "",
        })

    matched_count = 0
    unmatched_created_count = 0
    needs_review_count = 0
    failed_count = 0
    import_record_ids = []
    errors = []

    for idx, row in df.iterrows():
        source_row = idx + 2

        try:
            fields = row_to_motor_policy_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            raw_name, raw_addr = import_shared.split_insured_name_address(fields.get("insured_name_address"))
            candidate_name = full_name(raw_name)
            candidate_addr = raw_addr.lower()

            # Plain name fuzzy-match, same as upload_motor_quotations, so
            # policyholder-matching confidence is consistent across both Motor
            # importers (a policyholder that already auto-matches via Motor
            # Quotation shouldn't need extra corroboration via Motor Policy).
            best_score, best_entry = 0, None
            for entry in ph_pool:
                score = fuzz.token_sort_ratio(candidate_name, entry["name"])
                if score > best_score:
                    best_score, best_entry = score, entry

            # NOTE: unlike upload_motor_quotations (which never adds "pending" pool
            # entries and so can skip this check), this importer DOES add pending
            # entries below -- the source=="db" check is required here to avoid ever
            # selecting a pending entry (id=None) as the matched policyholder.
            if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                policyholder_id = best_entry["id"]

            elif best_score >= REVIEW_THRESHOLD:
                record = models.ImportRecord(
                    source_file=file.filename, source_row=source_row,
                    import_type=models.ImportType.motor_policy,
                    match_status=models.MatchStatus.needs_review,
                    raw_data=raw_data,
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                db.commit()

                import_record_ids.append(record.id)
                needs_review_count += 1

                ph_pool.append({"source": "pending", "id": None, "name": candidate_name, "addr": candidate_addr, "phone": ""})
                continue

            else:
                last_name = raw_name.strip() or None
                import_shared.require_name(None, last_name, "Insured Name & Address")
                new_ph = models.Policyholder(
                    last_name=last_name,
                    present_address=raw_addr.strip() or None,
                )
                db.add(new_ph)
                db.flush()
                db.refresh(new_ph)

                ph_pool.append({"source": "db", "id": new_ph.id, "name": candidate_name, "addr": candidate_addr, "phone": ""})
                policyholder_id = new_ph.id

            matched_case_id, status = _resolve_or_create_motor_policy(db, policyholder_id, fields)

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.motor_policy,
                match_status=status,
                matched_policyholder_id=policyholder_id,
                matched_case_id=matched_case_id,
                raw_data=raw_data,
            )
            db.add(record)
            db.flush()
            db.refresh(record)

            db.commit()

            import_record_ids.append(record.id)
            if status == models.MatchStatus.matched:
                matched_count += 1
            elif status == models.MatchStatus.needs_review:
                needs_review_count += 1
            else:
                unmatched_created_count += 1

        except Exception as e:
            db.rollback()
            failed_count += 1
            errors.append(schemas.ImportRowError(source_row=source_row, error=str(e)))

    return schemas.ImportSummary(
        source_file=file.filename,
        total_rows=len(df),
        matched=matched_count,
        unmatched_created=unmatched_created_count,
        needs_review=needs_review_count,
        failed=failed_count,
        import_record_ids=import_record_ids,
        errors=errors,
    )


# ------------------------------------------------------------
# Needs-review resolution — Motor Policies
# ------------------------------------------------------------

def new_policyholder_fields_for_motor_policy(record: models.ImportRecord) -> dict:
    fields = row_to_motor_policy_fields(record.raw_data or {})
    raw_name, raw_addr = import_shared.split_insured_name_address(fields.get("insured_name_address"))
    return {"last_name": raw_name.strip() or None, "present_address": raw_addr.strip() or None}


def resolve_motor_policy_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_motor_policy_fields(record.raw_data or {})
    return _resolve_or_create_motor_policy(db, policyholder_id, fields)


def create_motor_policy_from_quotation(db: Session, record: models.ImportRecord, quotation_id: int):
    """Used by the quotation-picker resolve path once staff explicitly chooses a quotation."""
    quotation = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.id == quotation_id
    ).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.insurance_case.line_type != models.LineType.motor_car:
        raise HTTPException(status_code=400, detail="Quotation is not a Motor quotation")
    if quotation.policy is not None:
        raise HTTPException(status_code=409, detail="This quotation already has a policy attached")

    fields = row_to_motor_policy_fields(record.raw_data or {})
    policy_fields = {k: v for k, v in fields.items() if k != "insured_name_address"}
    new_policy = models.MotorPolicy(
        quotation_id=quotation.id,
        insured_name_address=fields.get("insured_name_address"),
        **policy_fields,
    )
    db.add(new_policy)
    db.flush()

    return quotation.insurance_case_id, models.MatchStatus.unmatched


def list_motor_policy_quotation_candidates(db: Session, policyholder_id: int) -> list:
    return import_shared.list_quotation_candidates(
        db, policyholder_id, models.LineType.motor_car,
        models.MotorQuotation, models.MotorPolicy,
        amount_getter=lambda q: q.total_amount_due,
        date_getter=lambda q: q.quotation_date,
    )