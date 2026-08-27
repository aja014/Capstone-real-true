import re
import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/import/motor",
    tags=["Bulk Import — Motor & Car"]
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


def full_name(last: str, first: str = "", middle: str = "") -> str:
    return f"{first or ''} {middle or ''} {last or ''}".strip().lower()


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
                    new_ph = models.Policyholder(last_name=fields.get("insured_name", "").strip() or None)
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
                )
                db.add(new_quotation)
                db.flush()

                matched_policyholder_id = policyholder_id
                matched_case_id = new_case.id
                status = models.MatchStatus.unmatched

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
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