import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/import/policyholders",
    tags=["Bulk Import — Policyholders"]
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


def full_name(last: str, first: str, middle: str = "") -> str:
    return f"{first or ''} {middle or ''} {last or ''}".strip().lower()


def match_score(candidate_name: str, candidate_addr: str, candidate_phone: str,
                 existing_name: str, existing_addr: str, existing_phone: str) -> float:
    """
    Weighted blend of name, address, and phone similarity.
    Name-only matching misses real duplicates when a name is abbreviated or
    merged differently (e.g. "Dela Cruz" vs "Delacruz") — address and an
    exact phone match are used as corroborating evidence to catch those cases.
    """
    name_score = fuzz.token_sort_ratio(candidate_name, existing_name)
    addr_score = fuzz.token_sort_ratio(candidate_addr, existing_addr) if candidate_addr and existing_addr else 0
    phone_match = 100 if candidate_phone and candidate_phone == existing_phone else 0

    return (name_score * 0.6) + (addr_score * 0.25) + (phone_match * 0.15)


@router.post("/upload", response_model=schemas.ImportSummary)
def upload_policyholders(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        if file.filename.lower().endswith(".csv"):
            df = pd.read_csv(file.file)
        else:
            df = pd.read_excel(file.file)
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
            "phone": (ph.mobile_number or "").strip(),
        })

    matched_count = 0
    unmatched_created_count = 0
    needs_review_count = 0
    import_record_ids = []

    for idx, row in df.iterrows():
        source_row = idx + 2  # +2 accounts for the header row + 0-based index, matching Excel's row numbers
        fields = row_to_policyholder_fields(row)
        raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

        candidate_name = full_name(
            fields.get("last_name", ""),
            fields.get("first_name", ""),
            fields.get("middle_name", "")
        )
        candidate_addr = (fields.get("present_address") or "").lower()
        candidate_phone = (fields.get("mobile_number") or "").strip()

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
            matched_count += 1

        elif best_score >= REVIEW_THRESHOLD:
            # Either close to a confirmed record, or close to another
            # ambiguous row earlier in this same file — either way, a
            # human should look at it. Add it to the pool so any FURTHER
            # duplicates later in the file also get linked to this group.
            status = models.MatchStatus.needs_review
            matched_policyholder_id = None
            needs_review_count += 1

            pool.append({
                "source": "pending",
                "id": None,
                "name": candidate_name,
                "addr": candidate_addr,
                "phone": candidate_phone,
            })

        else:
            # Confidently new — auto-create the policyholder
            new_ph = models.Policyholder(**fields)
            db.add(new_ph)
            db.commit()
            db.refresh(new_ph)

            status = models.MatchStatus.unmatched
            matched_policyholder_id = new_ph.id
            unmatched_created_count += 1

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
            match_status=status,
            matched_policyholder_id=matched_policyholder_id,
            raw_data=raw_data,
        )
        db.add(import_record)
        db.commit()
        db.refresh(import_record)
        import_record_ids.append(import_record.id)

    return schemas.ImportSummary(
        source_file=file.filename,
        total_rows=len(df),
        matched=matched_count,
        unmatched_created=unmatched_created_count,
        needs_review=needs_review_count,
        import_record_ids=import_record_ids,
    )


@router.get("/needs-review", response_model=list[schemas.ImportRecordOut])
def list_needs_review(db: Session = Depends(get_db)):
    return db.query(models.ImportRecord).filter(
        models.ImportRecord.match_status == models.MatchStatus.needs_review
    ).all()


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

    if resolution.matched_policyholder_id:
        ph = db.query(models.Policyholder).filter(
            models.Policyholder.id == resolution.matched_policyholder_id
        ).first()
        if not ph:
            raise HTTPException(status_code=404, detail="Policyholder not found")

        record.matched_policyholder_id = ph.id
        record.match_status = models.MatchStatus.matched

    elif resolution.create_new:
        # raw_data holds the ORIGINAL Excel headers (e.g. "Last Name"), so we
        # re-apply the same header mapping used during upload to get real field names.
        fields = {}
        for header, value in (record.raw_data or {}).items():
            mapped = COLUMN_MAP.get(normalize_header(header))
            if mapped:
                cleaned = clean_cell_value(value)
                if cleaned is not None:
                    fields[mapped] = cleaned

        new_ph = models.Policyholder(**fields)
        db.add(new_ph)
        db.commit()
        db.refresh(new_ph)

        record.matched_policyholder_id = new_ph.id
        record.match_status = models.MatchStatus.unmatched

    else:
        raise HTTPException(
            status_code=400,
            detail="Provide either matched_policyholder_id or create_new=true"
        )

    db.commit()
    db.refresh(record)
    return record