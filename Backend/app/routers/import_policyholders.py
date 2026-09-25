import re
import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.routers import import_fire_property, import_motor, import_vehicle, import_shared, import_claims

router = APIRouter(
    prefix="/import/policyholders",
    tags=["Bulk Import — Policyholders"],
    dependencies=[Depends(get_current_user)],
)

# ------------------------------------------------------------
# Matching thresholds — tune these based on real data later
# ------------------------------------------------------------
MATCH_THRESHOLD = 90       # score >= this  -> confidently the same person
REVIEW_THRESHOLD = 70      # score >= this (but below MATCH_THRESHOLD) -> needs_review
# score below REVIEW_THRESHOLD -> treated as a new, unmatched person


# Maps expected Excel column headers -> Policyholder model fields.
# Headers are matched case-insensitively with spaces stripped, so
# "Last Name", "last name", "LastName" all work.
COLUMN_MAP = {
    "lastname": "last_name",
    "firstname": "first_name",
    "middlename": "middle_name",
    "nationality": "nationality",
    "maritalstatus": "marital_status",
    "completenameofspouse": "spouse_full_name",
    "gender": "gender",
    "presentaddress": "present_address",
    "permanentaddress": "permanent_address",
    "residencephonenumber": "residence_phone",
    "mobilenumber": "mobile_number",
    "emailaddress": "email_address",
    "zipcode": "zip_code",
    "occupation": "occupation",
    "tin": "tin",
    "sssno": "sss_no",
    "employer": "employer",
}


def normalize_header(header: str) -> str:
    return str(header).strip().lower().replace(" ", "").replace(".", "").replace("/", "")


def clean_cell_value(value):
    """
    Converts a pandas cell value to a clean string.

    IMPORTANT: when an Excel column mixes numbers with any blank cells,
    pandas silently upcasts the WHOLE column to float64 — so a phone number
    like 9171234567 becomes 9171234567.0, and a plain str(value) would
    produce "9171234567.0" instead of "9171234567". That broken trailing
    ".0" then makes exact-match comparisons (phone numbers, plate numbers,
    engine/chassis numbers) silently fail even for genuinely identical
    values. This strips it, while leaving real decimals untouched.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def row_to_policyholder_fields(row: pd.Series) -> dict:
    """Map one Excel row to Policyholder model field names, ignoring unknown columns."""
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
    Strips periods and collapses whitespace before lowercasing. Both sides of
    this importer's own comparisons are already built from separate
    first/middle/last columns, so this isn't fixing an active bug here — it's
    the same hardening applied to import_fire_property.py/import_motor.py,
    where a combined "First M. Last" string on one side of the comparison did
    cause an active bug (a stray middle-initial period kept an exact-name
    match from clearing MATCH_THRESHOLD).
    """
    return re.sub(r"\s+", " ", (value or "").replace(".", "")).strip().lower()


def full_name(last: str, first: str, middle: str = "") -> str:
    return normalize_name(f"{first or ''} {middle or ''} {last or ''}")


def normalize_phone(value: str) -> str:
    """
    Strips formatting and reduces a phone number to its bare subscriber
    number, so differently formatted versions of the same number are
    recognized as equal. This needs to explicitly strip the PH country code
    (63) and local trunk prefix (0) rather than just keeping the last N
    digits — those two prefixes are different lengths, so "+63 49 543 2109"
    and "049-543-2109" would otherwise misalign and still fail to match
    despite being the exact same number.
    """
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("63") and len(digits) > 10:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits


def match_score(candidate_name: str, candidate_addr: str, candidate_phone: str,
                 existing_name: str, existing_addr: str, existing_phone: str) -> float:
    """
    Weighted blend of name, address, and phone similarity.
    Name-only matching misses real duplicates when a name is abbreviated or
    merged differently (e.g. "Dela Cruz" vs "Delacruz") — address and an
    exact phone match are used as corroborating evidence to catch those cases.
    """
    if candidate_name and existing_name and candidate_name == existing_name:
        addr_exact = candidate_addr and existing_addr and candidate_addr == existing_addr
        phone_exact = candidate_phone and candidate_phone == existing_phone
        if addr_exact or phone_exact:
            # Exact name plus at least one corroborating signal — confident match.
            return 100
        # Exact name with NO corroborating data at all. The weighted formula
        # below caps at 60 in this case (name_score*0.6, addr/phone both 0),
        # which is BELOW REVIEW_THRESHOLD (70) — so an exact name match with
        # blank address/phone was being scored as "confidently new" and
        # SILENTLY CREATING A DUPLICATE POLICYHOLDER, no human review at all
        # (worse than merely missing an auto-match: it actively duplicated
        # the same repeat customer on every upload with no address/phone on
        # file). Floor it at REVIEW_THRESHOLD instead so it's at minimum
        # flagged for a human to confirm, never silently duplicated.
        return REVIEW_THRESHOLD

    name_score = fuzz.token_sort_ratio(candidate_name, existing_name)
    addr_score = fuzz.token_sort_ratio(candidate_addr, existing_addr) if candidate_addr and existing_addr else 0
    phone_match = 100 if candidate_phone and candidate_phone == existing_phone else 0

    return (name_score * 0.6) + (addr_score * 0.25) + (phone_match * 0.15)


@router.post("/upload", response_model=schemas.ImportSummary)
def upload_policyholders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        # dtype=str stops pandas from inferring a numeric column type at all —
        # without it, a single blank cell in an otherwise-numeric column (e.g.
        # phone number) upcasts the WHOLE column to float64, which silently
        # drops leading zeros ("09171234567" -> 9171234567.0) with no way to
        # recover the lost digit afterward. clean_cell_value() below still
        # strips a stray trailing ".0" as a second line of defense.
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file, dtype=str)
        else:
            df = pd.read_excel(file.file, dtype=str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    # The comparison pool holds both confirmed database records AND rows
    # flagged needs_review earlier in THIS SAME upload. Without the pending
    # entries, a duplicate of an already-ambiguous row would have nothing
    # to compare against and could wrongly slip through as "new."
    pool = []
    for ph in db.query(models.Policyholder).all():
        pool.append({
            "source": "db",
            "id": ph.id,
            "name": full_name(ph.last_name, ph.first_name, ph.middle_name),
            "addr": (ph.present_address or "").lower(),
            "phone": normalize_phone(ph.mobile_number),
        })

    matched_count = 0
    unmatched_created_count = 0
    needs_review_count = 0
    failed_count = 0
    import_record_ids = []
    errors = []

    for idx, row in df.iterrows():
        source_row = idx + 2  # +2 accounts for the header row + 0-based index, matching Excel's row numbers

        try:
            fields = row_to_policyholder_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            candidate_name = full_name(
                fields.get("last_name", ""),
                fields.get("first_name", ""),
                fields.get("middle_name", "")
            )
            candidate_addr = (fields.get("present_address") or "").lower()
            candidate_phone = normalize_phone(fields.get("mobile_number"))

            best_score = 0
            best_entry = None
            for entry in pool:
                score = match_score(
                    candidate_name, candidate_addr, candidate_phone,
                    entry["name"], entry["addr"], entry["phone"]
                )
                if score > best_score:
                    best_score = score
                    best_entry = entry

            if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                # Confidently the same, already-confirmed person
                status = models.MatchStatus.matched
                matched_policyholder_id = best_entry["id"]

            elif best_score >= REVIEW_THRESHOLD:
                # Either close to a confirmed record, or close to another
                # ambiguous row earlier in this same file — either way, a
                # human should look at it. Add it to the pool so any FURTHER
                # duplicates later in the file also get linked to this group.
                status = models.MatchStatus.needs_review
                matched_policyholder_id = None

                pool.append({
                    "source": "pending",
                    "id": None,
                    "name": candidate_name,
                    "addr": candidate_addr,
                    "phone": candidate_phone,
                })

            else:
                # Confidently new — auto-create the policyholder.
                # flush() (not commit()) pushes this to the DB and assigns a
                # real ID within the CURRENT transaction, without finalizing
                # it — so if anything later in this row fails, rolling back
                # undoes this too, instead of leaving an orphaned record.
                import_shared.require_name(fields.get("first_name"), fields.get("last_name"), "Last Name/First Name")
                new_ph = models.Policyholder(**fields)
                db.add(new_ph)
                db.flush()
                db.refresh(new_ph)

                status = models.MatchStatus.unmatched
                matched_policyholder_id = new_ph.id

                pool.append({
                    "source": "db",
                    "id": new_ph.id,
                    "name": candidate_name,
                    "addr": candidate_addr,
                    "phone": candidate_phone,
                })

            import_record = models.ImportRecord(
                source_file=file.filename,
                source_row=source_row,
                import_type=models.ImportType.policyholder,
                match_status=status,
                matched_policyholder_id=matched_policyholder_id,
                raw_data=raw_data,
            )
            db.add(import_record)
            db.flush()
            db.refresh(import_record)

            db.commit()  # everything created for this row is saved together, or not at all

            import_record_ids.append(import_record.id)
            if status == models.MatchStatus.matched:
                matched_count += 1
            elif status == models.MatchStatus.needs_review:
                needs_review_count += 1
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


@router.get("/needs-review", response_model=list[schemas.ImportRecordOut])
def list_needs_review(db: Session = Depends(get_db)):
    return db.query(models.ImportRecord).filter(
        models.ImportRecord.match_status == models.MatchStatus.needs_review
    ).all()


@router.delete("/records/{record_id}", response_model=schemas.DeletedImportRecordOut)
def delete_import_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(models.ImportRecord).filter(models.ImportRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")

    snapshot = schemas.ImportRecordOut.model_validate(record).model_dump(mode="json")
    archived = models.DeletedImportRecord(original_id=record.id, data=snapshot)
    db.add(archived)

    db.delete(record)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-records", response_model=list[schemas.DeletedImportRecordOut])
def list_deleted_import_records(db: Session = Depends(get_db)):
    return db.query(models.DeletedImportRecord).order_by(models.DeletedImportRecord.deleted_at.desc()).all()


# Per-import-type "create a new policyholder from this row's raw_data" field
# mapping, and the post-policyholder completion step that actually builds the
# case/survey/vehicle/quotation the original importer would have created.
# Without branching on import_type here, every needs-review row — regardless
# of which importer produced it — was reduced to a bare Policyholder insert,
# silently discarding survey/vehicle data for Fire/Property and Motor rows.
_NEW_POLICYHOLDER_FIELDS = {
    models.ImportType.fire_property: import_fire_property.new_policyholder_fields,
    models.ImportType.motor: import_motor.new_policyholder_fields,
    models.ImportType.fire_property_quotation: import_fire_property.new_policyholder_fields_for_fire_quotation,
    models.ImportType.fire_property_policy: import_fire_property.new_policyholder_fields_for_fire_policy,
    models.ImportType.motor_policy: import_motor.new_policyholder_fields_for_motor_policy,
    models.ImportType.vehicle: import_vehicle.new_policyholder_fields,
}
_RESOLVE_FOR_POLICYHOLDER = {
    models.ImportType.fire_property: import_fire_property.resolve_for_policyholder,
    models.ImportType.motor: import_motor.resolve_for_policyholder,
    models.ImportType.fire_property_quotation: import_fire_property.resolve_fire_quotation_for_policyholder,
    models.ImportType.fire_property_policy: import_fire_property.resolve_fire_policy_for_policyholder,
    models.ImportType.motor_policy: import_motor.resolve_motor_policy_for_policyholder,
    models.ImportType.vehicle: import_vehicle.resolve_for_policyholder,
}
# The two Policy types only: once a policyholder is already resolved, staff can
# explicitly pick which quotation a stuck row belongs to (see the quotation-candidates
# endpoint below) instead of relying on the amount/date matching heuristic.
_CREATE_POLICY_FROM_QUOTATION = {
    models.ImportType.fire_property_policy: import_fire_property.create_fire_policy_from_quotation,
    models.ImportType.motor_policy: import_motor.create_motor_policy_from_quotation,
}
_LIST_QUOTATION_CANDIDATES = {
    models.ImportType.fire_property_policy: import_fire_property.list_fire_policy_quotation_candidates,
    models.ImportType.motor_policy: import_motor.list_motor_policy_quotation_candidates,
}


@router.get("/records/{record_id}/quotation-candidates", response_model=list[schemas.QuotationCandidate])
def get_quotation_candidates(record_id: int, db: Session = Depends(get_db)):
    record = db.query(models.ImportRecord).filter(models.ImportRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")
    if record.import_type not in _LIST_QUOTATION_CANDIDATES:
        raise HTTPException(status_code=400, detail="This import type has no quotation candidates")
    if not record.matched_policyholder_id:
        raise HTTPException(status_code=400, detail="Resolve the policyholder for this row first")

    return _LIST_QUOTATION_CANDIDATES[record.import_type](db, record.matched_policyholder_id)


@router.get("/records/{record_id}/policy-candidates", response_model=list[schemas.PolicyCandidate])
def get_policy_candidates(record_id: int, db: Session = Depends(get_db)):
    record = db.query(models.ImportRecord).filter(models.ImportRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")
    if record.import_type not in import_claims.LINES:
        raise HTTPException(status_code=400, detail="This import type has no policy candidates")

    return import_claims.list_policy_candidates(db, record)


@router.patch("/records/{record_id}/resolve", response_model=schemas.ImportRecordOut)
def resolve_import_record(
    record_id: int,
    resolution: schemas.ResolveImportRecord,
    db: Session = Depends(get_db)
):
    record = db.query(models.ImportRecord).filter(models.ImportRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")

    if record.match_status != models.MatchStatus.needs_review:
        raise HTTPException(status_code=400, detail="Only needs_review records can be resolved")

    # Claims rows — only ever stuck on which policy the claim belongs to, so they're
    # resolved by picking a policy, never via the policyholder paths below.
    if record.import_type in import_claims.LINES:
        if not resolution.matched_policy_id:
            raise HTTPException(status_code=400, detail="Claims rows are resolved by picking a policy (matched_policy_id)")
        case_id, policyholder_id, status = import_claims.create_claim_for_policy(db, record, resolution.matched_policy_id)
        record.matched_case_id = case_id
        record.matched_policyholder_id = policyholder_id
        record.match_status = status
        db.commit()
        db.refresh(record)
        return record
    if resolution.matched_policy_id:
        raise HTTPException(status_code=400, detail="matched_policy_id only applies to Claims import rows")

    # Path A — finalize a Policy row using an explicitly chosen quotation. Only
    # reachable once the policyholder is already resolved (see get_quotation_candidates).
    if resolution.matched_quotation_id:
        if record.import_type not in _CREATE_POLICY_FROM_QUOTATION:
            raise HTTPException(status_code=400, detail="matched_quotation_id only applies to Policy import rows")
        if not record.matched_policyholder_id:
            raise HTTPException(status_code=400, detail="Resolve the policyholder for this row first")

        matched_case_id, status = _CREATE_POLICY_FROM_QUOTATION[record.import_type](
            db, record, resolution.matched_quotation_id
        )
        record.matched_case_id = matched_case_id
        record.match_status = status
        db.commit()
        db.refresh(record)
        return record

    # Path B — resolve/confirm the policyholder. If it was already set on an earlier
    # attempt (a Policy row that got stuck purely on the quotation step), reuse it
    # instead of requiring the caller to re-supply matched_policyholder_id/create_new.
    if record.matched_policyholder_id is not None:
        policyholder_id = record.matched_policyholder_id

    elif resolution.matched_policyholder_id:
        ph = db.query(models.Policyholder).filter(
            models.Policyholder.id == resolution.matched_policyholder_id
        ).first()
        if not ph:
            raise HTTPException(status_code=404, detail="Policyholder not found")
        policyholder_id = ph.id

    elif resolution.create_new:
        if record.import_type == models.ImportType.policyholder:
            # raw_data holds the ORIGINAL Excel headers (e.g. "Last Name"), so
            # re-apply the same header mapping used during upload.
            fields = {}
            for header, value in (record.raw_data or {}).items():
                mapped = COLUMN_MAP.get(normalize_header(header))
                if mapped:
                    cleaned = clean_cell_value(value)
                    if cleaned is not None:
                        fields[mapped] = cleaned
        else:
            fields = _NEW_POLICYHOLDER_FIELDS[record.import_type](record)

        try:
            import_shared.require_name(fields.get("first_name"), fields.get("last_name"), "Policyholder")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        new_ph = models.Policyholder(**fields)
        db.add(new_ph)
        db.flush()
        db.refresh(new_ph)
        policyholder_id = new_ph.id

    else:
        raise HTTPException(
            status_code=400,
            detail="Provide matched_policyholder_id, create_new=true, or matched_quotation_id"
        )

    record.matched_policyholder_id = policyholder_id

    if record.import_type == models.ImportType.policyholder:
        record.match_status = models.MatchStatus.matched if resolution.matched_policyholder_id else models.MatchStatus.unmatched
    else:
        # Fire/Property and Motor rows still need their case/survey/vehicle/
        # quotation built — the same work the main upload path does once a
        # policyholder is resolved, not just a policyholder link. For the two
        # Policy types this can legitimately stay needs_review (ambiguous or no
        # quotation found) — the frontend then shows the quotation picker instead
        # of asking about the policyholder again, since matched_policyholder_id
        # is now set.
        matched_case_id, status = _RESOLVE_FOR_POLICYHOLDER[record.import_type](db, record, policyholder_id)
        record.matched_case_id = matched_case_id
        record.match_status = status

    db.commit()
    db.refresh(record)
    return record