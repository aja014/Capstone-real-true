import re
import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="/import/fire-property",
    tags=["Bulk Import — Fire & Property"],
    dependencies=[Depends(get_current_user)],
)

# ------------------------------------------------------------
# Thresholds — same starting points as the Policyholder import.
# Retune once real company data is available.
# ------------------------------------------------------------
MATCH_THRESHOLD = 90
REVIEW_THRESHOLD = 70
SURVEY_DUPLICATE_THRESHOLD = 85  # how similar location_of_risk must be to call it the same property


SURVEY_COLUMN_MAP = {
    "nameofinsured": "name_of_insured",
    "contactperson": "contact_person",
    "briefdescriptionofownersbusiness": "owner_business_description",
    "locationofrisk": "location_of_risk",
    "districtnoblockno": "district_block_no",
    "telfaxno": "tel_fax_no",
    "currentblockaccumulation": "current_block_accumulation",
    "zone": "zone",
    "ti": "ti",
    "riskclass": "risk_class",
    "description": "description",
    "maximumamountsubject": "maximum_amount_subject",
    "lossrecord": "loss_record",
}


def normalize_header(header: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(header).strip().lower())


def clean_cell_value(value):
    """
    Converts a pandas cell value to a clean string. If an Excel column mixes
    numbers with any blank cells, pandas upcasts the whole column to float64
    (e.g. a phone/reference number becomes "...0"). This strips that fake
    trailing ".0" while leaving genuine decimals untouched.
    """
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def row_to_survey_fields(row: pd.Series) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = SURVEY_COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned

    # maximum_amount_subject needs to become a real number — strip "Php", commas, spaces
    if "maximum_amount_subject" in fields:
        cleaned = re.sub(r"[^\d.]", "", fields["maximum_amount_subject"])
        fields["maximum_amount_subject"] = cleaned if cleaned else None

    # risk_class must be "a" or "b" — normalize case, and fail with a clear,
    # specific message here rather than letting a bad value hit the database
    # and surface as a raw "Data too long for column" error instead.
    if "risk_class" in fields:
        normalized = fields["risk_class"].strip().lower()
        if normalized not in ("a", "b"):
            raise ValueError(
                f'risk_class must be "a" or "b", got "{fields["risk_class"]}"'
            )
        fields["risk_class"] = normalized

    return fields


def full_name(last: str, first: str = "", middle: str = "") -> str:
    return f"{first or ''} {middle or ''} {last or ''}".strip().lower()


def normalize_phone(value: str) -> str:
    """
    Strips formatting and reduces a phone number to its bare subscriber
    number. Explicitly strips the PH country code (63) and local trunk
    prefix (0) — those two prefixes are different lengths, so a naive
    "keep the last N digits" approach would misalign local vs international
    formats of the same number and still fail to match them.
    """
    if not value:
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("63") and len(digits) > 10:
        digits = digits[2:]
    if digits.startswith("0"):
        digits = digits[1:]
    return digits


def match_score(cn, cp, en, ep) -> float:
    """
    Policyholder-level match: name + phone only.
    NOTE: deliberately does NOT factor in location_of_risk. That field is the
    PROPERTY's address, not the policyholder's — the same company insuring two
    different properties would otherwise score as "different companies" just
    because the locations differ. Location-based duplicate detection happens
    separately, at the survey level (see the duplicate-survey check below).
    """
    if cn and en and cn == en:
        # A character-for-character identical name is confident enough to
        # auto-match on its own. Without this: the weighted score below maxes
        # out at 80 (name_score*0.8) whenever there's no phone number to
        # corroborate with — which is common, survey data often has a blank
        # tel_fax_no — and 80 can NEVER clear MATCH_THRESHOLD (90). That
        # made even an exact name match permanently unable to auto-match
        # without phone data, so every repeat survey from the same client
        # landed in needs_review instead of being recognized automatically.
        return 100
    name_score = fuzz.token_sort_ratio(cn, en)
    phone_match = 100 if cp and cp == ep else 0
    return (name_score * 0.8) + (phone_match * 0.2)


@router.post("/surveys/upload", response_model=schemas.ImportSummary)
def upload_surveys(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        df = pd.read_csv(file.file) if file.filename.lower().endswith(".csv") else pd.read_excel(file.file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read file: {e}")

    # Policyholder comparison pool — same pending-pool pattern as the
    # Customer Information import, so in-batch ambiguous rows still chain correctly.
    ph_pool = []
    for ph in db.query(models.Policyholder).all():
        ph_pool.append({
            "source": "db", "id": ph.id,
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
        source_row = idx + 2

        try:
            fields = row_to_survey_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            candidate_name = full_name(fields.get("name_of_insured", ""))
            candidate_addr = (fields.get("location_of_risk") or "").lower()
            candidate_phone = normalize_phone(fields.get("tel_fax_no"))

            best_score, best_entry = 0, None
            for entry in ph_pool:
                score = match_score(candidate_name, candidate_phone, entry["name"], entry["phone"])
                if score > best_score:
                    best_score, best_entry = score, entry

            matched_case_id = None

            # ------------------------------------------------------------
            # STEP 1 — resolve the policyholder
            # ------------------------------------------------------------
            if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                policyholder_id = best_entry["id"]
                is_new_policyholder = False

            elif best_score >= REVIEW_THRESHOLD:
                # Ambiguous — pause the whole row, don't touch cases/surveys
                record = models.ImportRecord(
                    source_file=file.filename, source_row=source_row,
                    import_type=models.ImportType.fire_property,
                    match_status=models.MatchStatus.needs_review,
                    raw_data=raw_data,
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                db.commit()

                import_record_ids.append(record.id)
                needs_review_count += 1

                ph_pool.append({
                    "source": "pending", "id": None,
                    "name": candidate_name, "addr": candidate_addr, "phone": candidate_phone,
                })
                continue

            else:
                # Brand new policyholder (individual OR business name in last_name).
                # flush() (not commit()) so a later failure in this same row
                # can still roll this back cleanly instead of leaving it orphaned.
                new_ph = models.Policyholder(last_name=fields.get("name_of_insured", "").strip() or None)
                db.add(new_ph)
                db.flush()
                db.refresh(new_ph)

                ph_pool.append({
                    "source": "db", "id": new_ph.id,
                    "name": candidate_name, "addr": candidate_addr, "phone": candidate_phone,
                })

                policyholder_id = new_ph.id
                is_new_policyholder = True

            # ------------------------------------------------------------
            # STEP 2 — for a KNOWN policyholder, check for a duplicate survey.
            # A brand new policyholder can't have a duplicate, so skip straight to creating.
            # ------------------------------------------------------------
            is_duplicate = False

            if not is_new_policyholder:
                existing_surveys = (
                    db.query(models.FirePropertySurvey)
                    .join(models.InsuranceCase)
                    .filter(
                        models.InsuranceCase.policyholder_id == policyholder_id,
                        models.InsuranceCase.line_type == models.LineType.fire_property,
                    )
                    .all()
                )

                best_dup_score, best_dup_case_id = 0, None
                for survey in existing_surveys:
                    existing_loc = (survey.location_of_risk or "").lower()
                    score = fuzz.token_sort_ratio(candidate_addr, existing_loc) if candidate_addr and existing_loc else 0
                    if score > best_dup_score:
                        best_dup_score, best_dup_case_id = score, survey.insurance_case_id

                if best_dup_score >= SURVEY_DUPLICATE_THRESHOLD:
                    is_duplicate = True
                    matched_case_id = best_dup_case_id

            # ------------------------------------------------------------
            # STEP 3 — create the case + survey, unless it's a confirmed duplicate
            # ------------------------------------------------------------
            if is_duplicate:
                status = models.MatchStatus.matched
            else:
                new_case = models.InsuranceCase(
                    policyholder_id=policyholder_id,
                    line_type=models.LineType.fire_property,
                )
                db.add(new_case)
                db.flush()
                db.refresh(new_case)

                survey_fields = {k: v for k, v in fields.items() if k != "name_of_insured"}
                new_survey = models.FirePropertySurvey(
                    insurance_case_id=new_case.id,
                    name_of_insured=fields.get("name_of_insured"),
                    **survey_fields,
                )
                db.add(new_survey)
                db.flush()

                matched_case_id = new_case.id
                status = models.MatchStatus.unmatched

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.fire_property,
                match_status=status,
                matched_policyholder_id=policyholder_id,
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
# once it knows the policyholder for a fire_property-origin row. Runs the same
# survey-duplicate check and case/survey creation the main upload path above
# uses, so resolving a review row doesn't just link a policyholder while
# silently dropping the survey data.
# ------------------------------------------------------------

def new_policyholder_fields(record: models.ImportRecord) -> dict:
    fields = row_to_survey_fields(record.raw_data or {})
    return {"last_name": (fields.get("name_of_insured") or "").strip() or None}


def resolve_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_survey_fields(record.raw_data or {})
    candidate_addr = (fields.get("location_of_risk") or "").lower()

    existing_surveys = (
        db.query(models.FirePropertySurvey)
        .join(models.InsuranceCase)
        .filter(
            models.InsuranceCase.policyholder_id == policyholder_id,
            models.InsuranceCase.line_type == models.LineType.fire_property,
        )
        .all()
    )

    best_dup_score, best_dup_case_id = 0, None
    for survey in existing_surveys:
        existing_loc = (survey.location_of_risk or "").lower()
        score = fuzz.token_sort_ratio(candidate_addr, existing_loc) if candidate_addr and existing_loc else 0
        if score > best_dup_score:
            best_dup_score, best_dup_case_id = score, survey.insurance_case_id

    if best_dup_score >= SURVEY_DUPLICATE_THRESHOLD:
        return best_dup_case_id, models.MatchStatus.matched

    new_case = models.InsuranceCase(policyholder_id=policyholder_id, line_type=models.LineType.fire_property)
    db.add(new_case)
    db.flush()
    db.refresh(new_case)

    survey_fields = {k: v for k, v in fields.items() if k != "name_of_insured"}
    new_survey = models.FirePropertySurvey(
        insurance_case_id=new_case.id,
        name_of_insured=fields.get("name_of_insured"),
        **survey_fields,
    )
    db.add(new_survey)
    db.flush()

    return new_case.id, models.MatchStatus.unmatched