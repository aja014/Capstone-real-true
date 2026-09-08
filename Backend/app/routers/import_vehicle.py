import re
import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.routers import import_motor, import_shared

router = APIRouter(
    prefix="/import/vehicles",
    tags=["Bulk Import — Vehicle Information"],
    dependencies=[Depends(get_current_user)],
)

MATCH_THRESHOLD = 90     # policyholder name-match confidence
REVIEW_THRESHOLD = 70


# Vehicle Information has no real paper-document precedent (unlike every other
# importer, it was never its own separate company form -- vehicle details
# always appeared as part of a Quotation/Policy). These 9 columns are defined
# to match exactly what the Vehicle Information tab already displays as raw
# input fields (Vehicle ID, Client Name, and Quotation ID(s) are computed/
# derived display columns, not raw input, so excluded here).
COLUMN_MAP = {
    "insuredname": "insured_name",
    "make": "make",
    "model": "model",
    "bodytype": "body_type",
    "color": "color",
    "plateno": "plate_no",
    "motorengineno": "motor_engine_no",
    "serialchasisno": "serial_chassis_no",
    "serialchassisno": "serial_chassis_no",
    "authorizedcapacity": "authorized_capacity",
}


def normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).strip().lower())


def clean_cell_value(value):
    """
    Same ".0" corruption fix as every other importer -- matters MOST here
    since vehicle matching is an EXACT string comparison on plate/engine/
    chassis number, exactly the numeric-looking fields pandas silently
    corrupts when an Excel column mixes numbers with any blank cells.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def row_to_fields(row) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned
    return fields


def normalize_name(value: str) -> str:
    """
    Strips periods and collapses whitespace before lowercasing, so a combined
    "First M. Last" string (as typed on the paper form) and a name rebuilt
    from separate first/middle/last DB columns (no period on the middle
    initial) compare as identical instead of relying on raw fuzzy-ratio alone
    to clear MATCH_THRESHOLD -- same fix already applied in
    import_fire_property.py/import_motor.py/import_policyholders.py.
    """
    return re.sub(r"\s+", " ", (value or "").replace(".", "")).strip().lower()


def full_name(last: str, first: str = "", middle: str = "") -> str:
    return normalize_name(f"{first or ''} {middle or ''} {last or ''}")


def _create_vehicle_for_policyholder(db: Session, policyholder_id: int, fields: dict) -> int:
    """
    Shared by the main upload loop and resolve_for_policyholder. Vehicle
    Information carries no quotation data, so a genuinely new vehicle only
    ever produces Policyholder -> Insurance Case -> Vehicle -- never a
    Quotation, unlike Motor Quotation import.
    """
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
        plate_no=fields.get("plate_no") or None,
        motor_engine_no=fields.get("motor_engine_no") or None,
        serial_chassis_no=fields.get("serial_chassis_no") or None,
        authorized_capacity=fields.get("authorized_capacity"),
    )
    db.add(new_vehicle)
    db.flush()

    return new_case.id


@router.post("/upload", response_model=schemas.ImportSummary)
def upload_vehicles(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        df = pd.read_csv(file.file) if file.filename.lower().endswith(".csv") else pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    # Comparison pool holds confirmed DB policyholders AND rows flagged
    # needs_review earlier in this same upload, same pending-pool chaining
    # pattern as the Policyholder/Fire-Property/Motor-Policy importers.
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

            existing_vehicle = import_motor.find_existing_vehicle(db, plate_no, engine_no, chassis_no)

            # ------------------------------------------------------------
            # CASE A -- this exact vehicle is already on file. Treat the
            # whole row as a duplicate re-upload: matched status, no new
            # Case/Vehicle created.
            # ------------------------------------------------------------
            if existing_vehicle:
                case = existing_vehicle.insurance_case
                status = models.MatchStatus.matched
                matched_policyholder_id = case.policyholder_id
                matched_case_id = case.id

            # ------------------------------------------------------------
            # CASE B -- brand new vehicle. Match/create the owner, then
            # create a fresh case + vehicle. This importer never creates a
            # Quotation -- the source file only carries vehicle data.
            # ------------------------------------------------------------
            else:
                candidate_name = full_name(fields.get("insured_name", ""))

                best_score, best_entry = 0, None
                for entry in ph_pool:
                    score = fuzz.token_sort_ratio(candidate_name, entry["name"])
                    if score > best_score:
                        best_score, best_entry = score, entry

                if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                    policyholder_id = best_entry["id"]

                elif best_score >= REVIEW_THRESHOLD:
                    record = models.ImportRecord(
                        source_file=file.filename, source_row=source_row,
                        import_type=models.ImportType.vehicle,
                        match_status=models.MatchStatus.needs_review,
                        raw_data=raw_data,
                    )
                    db.add(record)
                    db.flush()
                    db.refresh(record)
                    db.commit()

                    import_record_ids.append(record.id)
                    needs_review_count += 1

                    ph_pool.append({"source": "pending", "id": None, "name": candidate_name})
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

                matched_case_id = _create_vehicle_for_policyholder(db, policyholder_id, fields)
                matched_policyholder_id = policyholder_id
                status = models.MatchStatus.unmatched

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.vehicle,
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
# Needs-review resolution -- called from import_policyholders.resolve_import_record
# once it knows the policyholder for a vehicle-origin row. Re-runs the SAME
# vehicle dedup + case/vehicle creation the main upload path uses, so a
# manually-resolved row ends up identical to what auto-matching would have
# produced.
# ------------------------------------------------------------

def new_policyholder_fields(record: models.ImportRecord) -> dict:
    fields = row_to_fields(record.raw_data or {})
    return {"last_name": (fields.get("insured_name") or "").strip() or None}


def resolve_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_fields(record.raw_data or {})
    plate_no = fields.get("plate_no", "")
    engine_no = fields.get("motor_engine_no", "")
    chassis_no = fields.get("serial_chassis_no", "")

    # Re-check for an existing vehicle in case one was created by a separate
    # upload after this row was queued for review.
    existing_vehicle = import_motor.find_existing_vehicle(db, plate_no, engine_no, chassis_no)
    if existing_vehicle:
        return existing_vehicle.insurance_case_id, models.MatchStatus.matched

    matched_case_id = _create_vehicle_for_policyholder(db, policyholder_id, fields)
    return matched_case_id, models.MatchStatus.unmatched
