import re
from decimal import Decimal, InvalidOperation

import pandas as pd
from rapidfuzz import fuzz
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.http_security import check_upload_size, row_error_text
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas
from app.ml.jobs import schedule_model_refresh
from app.routers import import_shared
from app.services.flood_risk import lookup_flood_risk

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
# Fire Quotation -> case, for a policyholder with 2+ fire cases: the best-matching
# case must also lead the runner-up by this much, else fall back to a new case.
LOCATION_MATCH_MARGIN = 8


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

    # Perils Assessment — 18 individual perils, header = the peril name
    # itself. Not real model columns; assembled into perils_assessment
    # JSON in row_to_survey_fields() below, ratings only (no remarks —
    # those stay manual-entry-only via the create endpoint).
    "fire": "peril__fire",
    "earthquake": "peril__earthquake",
    "typhoon": "peril__typhoon",
    "flood": "peril__flood",
    "landslidesubsidence": "peril__landslide_subsidence",
    "smokeaircraftvehicleimpactexplosion": "peril__smoke_aircraft_vehicle_impact_explosion",
    "rsmd": "peril__rsmd",
    "burglaryrobbery": "peril__burglary_robbery",
    "volcaniceruption": "peril__volcanic_eruption",
    "tsunami": "peril__tsunami",
    "terroristattack": "peril__terrorist_attack",
    "spontaneouscombustion": "peril__spontaneous_combustion",
    "machinerybreakdown": "peril__machinery_breakdown",
    "generalliability": "peril__general_liability",
    "money": "peril__money",
    "fidelityguarantee": "peril__fidelity_guarantee",
    "goodstransit": "peril__goods_transit",
    "others": "peril__others",

    # Hazard Assessment — 6 items, same placeholder pattern.
    "maintenance": "hazard__maintenance",
    "housekeeping": "hazard__housekeeping",
    "storagearrangement": "hazard__storage_arrangement",
    "safetysecurity": "hazard__safety_security",
    "blockcondition": "hazard__block_condition",
    "surroundingcommunity": "hazard__surrounding_community",

    "overallriskassessment": "overall_risk_assessment",
    "surveyorriskacceptability": "surveyor_risk_acceptability",
    "protectionfacilities": "protection_facilities",

    # Main Occupancy breakdown (peso amounts) and Boundaries (text) from the paper
    # Survey Report. Prefixed headers ("Occupancy - Others", not "Others") so they
    # never collide with the "Others" peril. Placeholders, folded into the
    # occupancy_breakdown / boundaries JSON in row_to_survey_fields() below.
    "occupancybuilding": "occupancy__building",
    "occupancymainoccupancy": "occupancy__main_occupancy",
    "occupancystocks": "occupancy__stocks",
    "occupancyme": "occupancy__me",
    "occupancyfff": "occupancy__fff",
    "occupancybilop": "occupancy__bi_lop",
    "occupancyothers": "occupancy__others",
    "occupancytotal": "occupancy__total",
    "boundaryfront": "boundary__front",
    "boundaryright": "boundary__right",
    "boundaryleft": "boundary__left",
    "boundaryrear": "boundary__rear",
    "boundarysketch": "boundary__sketch",
}

# JSON key -> upload header, for error/warning messages.
OCCUPANCY_HEADERS = {
    "building": "Occupancy - Building", "main_occupancy": "Occupancy - Main Occupancy",
    "stocks": "Occupancy - Stocks", "me": "Occupancy - M/E", "fff": "Occupancy - FFF",
    "bi_lop": "Occupancy - BI/LOP", "others": "Occupancy - Others", "total": "Occupancy - Total",
}
OCCUPANCY_TOTAL_TOLERANCE = Decimal("1")

FIRE_QUOTATION_COLUMN_MAP = {
    "date": "quotation_date",
    "nameofinsured": "insured_name",
    "locationofrisk": "location_of_risk",
    "periodofcover": "period_cover",
    "periodcover": "period_cover",
    "propertysumsinsured": "property_sums_insured",
    "basisofevaluation": "basis_of_evaluation",
    "deductibles": "deductibles",
    "subjective": "subjective",
    "occupancy": "occupancy",
    "totalsuminsured": "total_sum_insured",
    "mortgagee": "mortgagee",
    "perilscovered": "perils_covered",
    "lineofinsurance": "line_of_insurance",
    "totalpremium": "total_premium",
}

FIRE_POLICY_COLUMN_MAP = {
    "issuedate": "issue_date",
    "insurednameaddress": "insured_name_address",
    "lineofinsurance": "line_of_insurance",
    "policyno": "policy_no",
    "renewingpolicyno": "renewing_policy_no",
    "periodfrom": "period_from",
    "periodto": "period_to",
    "tin": "tin",
    "totalamountdue": "total_amount_due",
    "agencycode": "agency_code",
    "coveragedescription": "coverage_description",
    "suminsured": "sum_insured",
    # Total Premium before taxes. The old "Unit Cost Premium" header held a rate, so it is not mapped.
    "premium": "premium",
    "replacingcovernoteno": "replacing_cover_note_no",
    "premiuminvoiceno": "premium_invoice_no",
    "officialreceiptno": "official_receipt_no",
    "propertyinsured": "property_insured",
    "construction": "construction",
    "occupancy": "occupancy",
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


def _validate_choice(value: str, choices: tuple, context: str, output_lower: bool = False) -> str:
    """
    Case-insensitive match against a fixed set of allowed values — same
    approach as risk_class's explicit check below. output_lower=True gives
    perils_assessment/hazard_assessment ratings ("low"), matching the JSON
    shape shown in the task spec; output_lower=False (default) gives
    overall_risk_assessment/surveyor_risk_acceptability the same
    Title-Case canonical form the Pydantic validator on the manual
    create endpoint already normalizes to (e.g. "Fair", "Key Consideration").
    """
    match = next((c for c in choices if c.lower() == value.strip().lower()), None)
    if not match:
        raise ValueError(f'{context} must be one of: {", ".join(choices)} (got "{value}")')
    return match.lower() if output_lower else match


def _normalize_facility_name(name: str) -> str:
    # Case/whitespace-insensitive, and "Fire Breaks / Doors" == "Fire Breaks/Doors".
    return re.sub(r"\s*/\s*", "/", re.sub(r"\s+", " ", name.strip().lower()))


_FACILITY_LOOKUP = {
    _normalize_facility_name(label): key
    for label, key in {**schemas.PROTECTION_FACILITY_OPTIONS, **schemas.PROTECTION_FACILITY_ALIASES}.items()
}


def parse_protection_facilities(value: str):
    """
    "Fire Extinguisher, Automatic Sprinklers" -> the FULL checklist, every key
    true/false (so "surveyed, no sprinkler" is False, not missing). "None" -> every
    key False. Unknown names, or "None" mixed with other names, fail the row --
    same approach as risk_class. A cell with no names at all returns None (field
    left unset, same as a blank cell).
    """
    names = [n.strip() for n in value.split(",") if n.strip()]
    if not names:
        return None
    normalized = [_normalize_facility_name(n) for n in names]
    all_keys = schemas.PROTECTION_FACILITY_OPTIONS.values()

    if "none" in normalized:
        if len(set(normalized)) > 1:
            raise ValueError('Protection Facilities: "None" cannot be combined with other facilities')
        return {key: False for key in all_keys}

    unknown = [n for n, norm in zip(names, normalized) if norm not in _FACILITY_LOOKUP]
    if unknown:
        raise ValueError(
            f'Protection Facilities: unknown facility "{unknown[0]}". Allowed: '
            f'{", ".join(schemas.PROTECTION_FACILITY_OPTIONS)}, or None'
        )
    present = {_FACILITY_LOOKUP[norm] for norm in normalized}
    return {key: key in present for key in all_keys}


def _keep_literal_protection_facilities(df, file):
    """pandas' default NA list turns the text "None" into a blank cell, which would
    make "None" (= no facilities, all False) indistinguishable from "not recorded".
    Re-read the sheet with that list switched off and take ONLY this column from it,
    so every other Survey column keeps today's exact parsing."""
    col = next((c for c in df.columns if normalize_header(c) == "protectionfacilities"), None)
    if col is None:
        return
    file.file.seek(0)
    reader = pd.read_csv if file.filename.lower().endswith(".csv") else pd.read_excel
    raw = reader(file.file, keep_default_na=False, na_values=[""])
    df[col] = raw[col]


def _parse_occupancy_amount(key: str, value: str):
    """Same cleanup as maximum_amount_subject (strip "Php", "₱", commas, spaces), but an
    unusable value FAILS the row instead of silently becoming NULL. Stored as a plain
    JSON number -- int when whole (matches the schema example {"building": 1000000})."""
    cleaned = re.sub(r"[^\d.]", "", value)
    try:
        amount = Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f'{OCCUPANCY_HEADERS[key]}: "{value}" is not a valid amount')
    return int(amount) if amount == amount.to_integral_value() else float(amount)


def occupancy_total_warning(fields: dict):
    """Occupancy - Total is stored as given; if it's more than 1 peso off the sum of
    the other filled parts, return a warning message (the row still imports)."""
    occ = fields.get("occupancy_breakdown") or {}
    parts = [Decimal(str(v)) for k, v in occ.items() if k != "total"]
    if "total" not in occ or not parts:
        return None
    total, parts_sum = Decimal(str(occ["total"])), sum(parts)
    if abs(total - parts_sum) > OCCUPANCY_TOTAL_TOLERANCE:
        return (f"Occupancy - Total {total:,.2f} differs from the sum of the other parts "
                f"{parts_sum:,.2f}; imported as given")
    return None


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

    if "overall_risk_assessment" in fields:
        fields["overall_risk_assessment"] = _validate_choice(
            fields["overall_risk_assessment"], ("Poor", "Fair", "Good", "Others"), "overall_risk_assessment"
        )
    if "surveyor_risk_acceptability" in fields:
        fields["surveyor_risk_acceptability"] = _validate_choice(
            fields["surveyor_risk_acceptability"], ("Accept", "Decline", "Key Consideration"), "surveyor_risk_acceptability"
        )
    if "protection_facilities" in fields:
        parsed = parse_protection_facilities(fields["protection_facilities"])
        if parsed is None:
            fields.pop("protection_facilities")
        else:
            fields["protection_facilities"] = parsed

    # Perils/Hazard Assessment ratings — RATINGS ONLY (see SURVEY_COLUMN_MAP
    # above). Any peril__<key>/hazard__<key> placeholder present gets folded
    # into the same {"rating": ..., "remarks": null} shape the manual create
    # endpoint uses, remarks always null for imported rows. A dict that ends
    # up empty (none of that section's columns had data in THIS row) is
    # left out of fields entirely — never written as an empty {} — which
    # also naturally covers "file doesn't have these columns at all".
    perils_assessment = {}
    hazard_assessment = {}
    for key in list(fields.keys()):
        if key.startswith("peril__"):
            peril_key = key[len("peril__"):]
            rating = _validate_choice(
                fields.pop(key), ("Low", "Moderate", "High"),
                f'perils_assessment["{peril_key}"] rating', output_lower=True,
            )
            perils_assessment[peril_key] = {"rating": rating, "remarks": None}
        elif key.startswith("hazard__"):
            hazard_key = key[len("hazard__"):]
            rating = _validate_choice(
                fields.pop(key), ("Good", "Fair", "Poor"),
                f'hazard_assessment["{hazard_key}"] rating', output_lower=True,
            )
            hazard_assessment[hazard_key] = {"rating": rating, "remarks": None}
    if perils_assessment:
        fields["perils_assessment"] = perils_assessment
    if hazard_assessment:
        fields["hazard_assessment"] = hazard_assessment

    # Occupancy breakdown (amounts) / Boundaries (text): blank cells are simply left
    # out; a group with nothing filled stays unset (NULL), same as before.
    occupancy_breakdown, boundaries = {}, {}
    for key in list(fields.keys()):
        if key.startswith("occupancy__"):
            sub = key[len("occupancy__"):]
            occupancy_breakdown[sub] = _parse_occupancy_amount(sub, fields.pop(key))
        elif key.startswith("boundary__"):
            boundaries[key[len("boundary__"):]] = fields.pop(key)
    if occupancy_breakdown:
        fields["occupancy_breakdown"] = occupancy_breakdown
    if boundaries:
        fields["boundaries"] = boundaries

    return fields


def row_to_fire_quotation_fields(row) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = FIRE_QUOTATION_COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned

    for money_field in ("property_sums_insured", "total_sum_insured", "total_premium"):
        if money_field in fields:
            cleaned = re.sub(r"[^\d.]", "", fields[money_field])
            fields[money_field] = cleaned if cleaned else None

    if "quotation_date" in fields:
        fields["quotation_date"] = import_shared.parse_import_date("quotation_date", fields["quotation_date"])

    return fields


def row_to_fire_policy_fields(row) -> dict:
    fields = {}
    for col, value in row.items():
        mapped = FIRE_POLICY_COLUMN_MAP.get(normalize_header(col))
        if mapped:
            cleaned = clean_cell_value(value)
            if cleaned is not None:
                fields[mapped] = cleaned

    for money_field in ("total_amount_due", "sum_insured", "premium"):
        if money_field in fields:
            cleaned = re.sub(r"[^\d.]", "", fields[money_field])
            fields[money_field] = cleaned if cleaned else None

    for date_field in ("issue_date", "period_from", "period_to"):
        if date_field in fields:
            fields[date_field] = import_shared.parse_import_date(date_field, fields[date_field])

    return fields


def normalize_name(value: str) -> str:
    """
    Strips periods and collapses whitespace before lowercasing, so a combined
    "First M. Last" string (as typed on the paper form) and a name rebuilt from
    separate first/middle/last DB columns (no period on the middle initial)
    compare as identical instead of landing just short of MATCH_THRESHOLD.
    """
    return re.sub(r"\s+", " ", (value or "").replace(".", "")).strip().lower()


def full_name(last: str, first: str = "", middle: str = "") -> str:
    return normalize_name(f"{first or ''} {middle or ''} {last or ''}")


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


@router.post("/surveys/upload", response_model=schemas.ImportSummary,
              dependencies=[Depends(schedule_model_refresh)])
def upload_surveys(file: UploadFile = File(...), db: Session = Depends(get_db)):
    check_upload_size(file)
    if not file.filename.lower().endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, or .csv files are supported")

    try:
        df = pd.read_csv(file.file) if file.filename.lower().endswith(".csv") else pd.read_excel(file.file)
        _keep_literal_protection_facilities(df, file)
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
    warnings = []

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
                last_name = fields.get("name_of_insured", "").strip() or None
                import_shared.require_name(None, last_name, "Name of Insured")
                new_ph = models.Policyholder(last_name=last_name)
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
                survey_fields.update(lookup_flood_risk(fields.get("location_of_risk")))
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
                warning = occupancy_total_warning(fields)
                if warning:
                    warnings.append(schemas.ImportRowWarning(source_row=source_row, warning=warning))

        except Exception as e:
            # One bad row should never take down the whole upload. Undo
            # anything this row partially created, record what went wrong,
            # and move on to the next row.
            db.rollback()
            failed_count += 1
            errors.append(schemas.ImportRowError(source_row=source_row, error=row_error_text(e, source_row)))

    return schemas.ImportSummary(
        source_file=file.filename,
        total_rows=len(df),
        matched=matched_count,
        unmatched_created=unmatched_created_count,
        needs_review=needs_review_count,
        failed=failed_count,
        import_record_ids=import_record_ids,
        errors=errors,
        warnings=warnings,
    )


# ------------------------------------------------------------
# FIRE & PROPERTY QUOTATIONS
# ------------------------------------------------------------

def _match_fire_case_by_location(db: Session, cases: list, location_of_risk):
    """
    For a policyholder with 2+ fire_property cases: compare the quotation's Location
    of Risk with the LATEST Survey (highest id) of each case, using the same
    lowercase + token_sort_ratio the Survey duplicate check uses. Returns the case
    only if it scores >= SURVEY_DUPLICATE_THRESHOLD and leads the runner-up by
    LOCATION_MATCH_MARGIN; otherwise None (caller keeps today's new-case behavior).
    A case with no survey scores 0 and is never picked.
    """
    candidate_loc = (location_of_risk or "").lower()
    if not candidate_loc:
        return None

    latest_survey_by_case = {}
    for survey in db.query(models.FirePropertySurvey).filter(
        models.FirePropertySurvey.insurance_case_id.in_([c.id for c in cases])
    ).all():
        current = latest_survey_by_case.get(survey.insurance_case_id)
        if current is None or survey.id > current.id:
            latest_survey_by_case[survey.insurance_case_id] = survey

    scored = []
    for case in cases:
        survey = latest_survey_by_case.get(case.id)
        existing_loc = (survey.location_of_risk or "").lower() if survey else ""
        score = fuzz.token_sort_ratio(candidate_loc, existing_loc) if existing_loc else 0
        scored.append((score, case))
    scored.sort(key=lambda s: s[0], reverse=True)

    best_score, best_case = scored[0]
    runner_up_score = scored[1][0] if len(scored) > 1 else 0
    if best_score >= SURVEY_DUPLICATE_THRESHOLD and best_score - runner_up_score >= LOCATION_MATCH_MARGIN:
        return best_case
    return None


def _resolve_or_create_fire_quotation(db: Session, policyholder_id: int, fields: dict):
    """
    Shared by the main upload loop below and resolve_fire_quotation_for_policyholder
    (the needs-review resolve path), so both stay in sync automatically.
    Exactly one existing fire_property case -> reuse it. 2+ -> reuse the case whose
    latest Survey location clearly matches this quotation's Location of Risk (see
    _match_fire_case_by_location), so the quotation gets that property's Survey/GIS.
    A reused case gets the exact-duplicate check (same date + total_premium). Zero
    cases, or 2+ with no clear location match -> create a new case (unchanged).
    """
    existing_cases = (
        db.query(models.InsuranceCase)
        .filter(
            models.InsuranceCase.policyholder_id == policyholder_id,
            models.InsuranceCase.line_type == models.LineType.fire_property,
        )
        .all()
    )

    def _amount_equal(a, b):
        try:
            return a is not None and b is not None and float(a) == float(b)
        except (TypeError, ValueError):
            return False

    case = None
    if len(existing_cases) == 1:
        case = existing_cases[0]
    elif len(existing_cases) >= 2:
        case = _match_fire_case_by_location(db, existing_cases, fields.get("location_of_risk"))

    if case is not None:
        existing_quotations = db.query(models.FirePropertyQuotation).filter(
            models.FirePropertyQuotation.insurance_case_id == case.id
        ).all()
        is_duplicate = any(
            q.quotation_date == fields.get("quotation_date")
            and _amount_equal(q.total_premium, fields.get("total_premium"))
            for q in existing_quotations
        )
        if is_duplicate:
            return case.id, models.MatchStatus.matched
        target_case = case
    else:
        target_case = models.InsuranceCase(policyholder_id=policyholder_id, line_type=models.LineType.fire_property)
        db.add(target_case)
        db.flush()
        db.refresh(target_case)

    quotation_fields = {k: v for k, v in fields.items() if k != "insured_name"}
    new_quotation = models.FirePropertyQuotation(
        insurance_case_id=target_case.id,
        insured_name=fields.get("insured_name"),
        **quotation_fields,
    )
    db.add(new_quotation)
    db.flush()

    return target_case.id, models.MatchStatus.unmatched


@router.post("/quotations/upload", response_model=schemas.ImportSummary,
              dependencies=[Depends(schedule_model_refresh)])
def upload_fire_property_quotations(file: UploadFile = File(...), db: Session = Depends(get_db)):
    check_upload_size(file)
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
            fields = row_to_fire_quotation_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            candidate_name = full_name(fields.get("insured_name", ""))

            # No phone column exists on this document type -- match_score() still
            # works correctly with an empty candidate phone, it just can never
            # corroborate via phone (only the exact-name short-circuit or an
            # existing DB record's own phone data can push it to matched).
            best_score, best_entry = 0, None
            for entry in ph_pool:
                score = match_score(candidate_name, "", entry["name"], entry["phone"])
                if score > best_score:
                    best_score, best_entry = score, entry

            if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                policyholder_id = best_entry["id"]

            elif best_score >= REVIEW_THRESHOLD:
                record = models.ImportRecord(
                    source_file=file.filename, source_row=source_row,
                    import_type=models.ImportType.fire_property_quotation,
                    match_status=models.MatchStatus.needs_review,
                    raw_data=raw_data,
                )
                db.add(record)
                db.flush()
                db.refresh(record)
                db.commit()

                import_record_ids.append(record.id)
                needs_review_count += 1

                ph_pool.append({"source": "pending", "id": None, "name": candidate_name, "addr": "", "phone": ""})
                continue

            else:
                last_name = fields.get("insured_name", "").strip() or None
                import_shared.require_name(None, last_name, "Name of Insured")
                new_ph = models.Policyholder(last_name=last_name)
                db.add(new_ph)
                db.flush()
                db.refresh(new_ph)

                ph_pool.append({"source": "db", "id": new_ph.id, "name": candidate_name, "addr": "", "phone": ""})
                policyholder_id = new_ph.id

            matched_case_id, status = _resolve_or_create_fire_quotation(db, policyholder_id, fields)

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.fire_property_quotation,
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
            else:
                unmatched_created_count += 1

        except Exception as e:
            db.rollback()
            failed_count += 1
            errors.append(schemas.ImportRowError(source_row=source_row, error=row_error_text(e, source_row)))

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
# FIRE & PROPERTY POLICIES
# A policy MUST link to an existing quotation (required FK, no shared ID in the
# source data) -- see import_shared.find_best_unattached_quotation for the
# amount/date matching heuristic this relies on.
# ------------------------------------------------------------

def _resolve_or_create_fire_policy(db: Session, policyholder_id: int, fields: dict):
    """Shared by the main upload loop and resolve_fire_policy_for_policyholder."""
    policy_no = fields.get("policy_no")
    if policy_no:
        existing = (
            db.query(models.FirePropertyPolicy)
            .join(models.FirePropertyQuotation)
            .join(models.InsuranceCase)
            .filter(
                models.FirePropertyPolicy.policy_no == policy_no,
                models.InsuranceCase.policyholder_id == policyholder_id,
            )
            .first()
        )
        if existing:
            return existing.quotation.insurance_case_id, models.MatchStatus.matched

    result = import_shared.find_best_unattached_quotation(
        db, policyholder_id, models.LineType.fire_property,
        models.FirePropertyQuotation, models.FirePropertyPolicy,
        amount_getter=lambda q: q.total_premium,
        date_getter=lambda q: q.quotation_date,
        candidate_amount=fields.get("total_amount_due"),
        candidate_date=fields.get("issue_date") or fields.get("period_from"),
    )

    if result["status"] != "confident":
        # Ambiguous or no candidate at all -- stays needs_review with the
        # policyholder already recorded, so the frontend can switch straight to
        # the quotation-picker instead of re-asking who the policyholder is.
        return None, models.MatchStatus.needs_review

    quotation = result["candidate"]
    policy_fields = {k: v for k, v in fields.items() if k != "insured_name_address"}
    new_policy = models.FirePropertyPolicy(
        quotation_id=quotation.id,
        insured_name_address=fields.get("insured_name_address"),
        **policy_fields,
    )
    db.add(new_policy)
    db.flush()

    return quotation.insurance_case_id, models.MatchStatus.unmatched


@router.post("/policies/upload", response_model=schemas.ImportSummary,
              dependencies=[Depends(schedule_model_refresh)])
def upload_fire_property_policies(file: UploadFile = File(...), db: Session = Depends(get_db)):
    check_upload_size(file)
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
            fields = row_to_fire_policy_fields(row)
            raw_data = {str(k): clean_cell_value(v) for k, v in row.items()}

            raw_name, raw_addr = import_shared.split_insured_name_address(fields.get("insured_name_address"))
            candidate_name = full_name(raw_name)
            candidate_addr = raw_addr.lower()

            # Reuses this file's own match_score (same one Survey/Quotation use) on
            # just the extracted name, so policyholder-matching confidence is
            # consistent across all three Fire/Property importers.
            best_score, best_entry = 0, None
            for entry in ph_pool:
                score = match_score(candidate_name, "", entry["name"], entry["phone"])
                if score > best_score:
                    best_score, best_entry = score, entry

            if best_score >= MATCH_THRESHOLD and best_entry and best_entry["source"] == "db":
                policyholder_id = best_entry["id"]

            elif best_score >= REVIEW_THRESHOLD:
                record = models.ImportRecord(
                    source_file=file.filename, source_row=source_row,
                    import_type=models.ImportType.fire_property_policy,
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

            matched_case_id, status = _resolve_or_create_fire_policy(db, policyholder_id, fields)

            record = models.ImportRecord(
                source_file=file.filename, source_row=source_row,
                import_type=models.ImportType.fire_property_policy,
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
            errors.append(schemas.ImportRowError(source_row=source_row, error=row_error_text(e, source_row)))

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
    survey_fields.update(lookup_flood_risk(fields.get("location_of_risk")))
    new_survey = models.FirePropertySurvey(
        insurance_case_id=new_case.id,
        name_of_insured=fields.get("name_of_insured"),
        **survey_fields,
    )
    db.add(new_survey)
    db.flush()

    return new_case.id, models.MatchStatus.unmatched


# ------------------------------------------------------------
# Needs-review resolution — Fire & Property Quotations
# ------------------------------------------------------------

def new_policyholder_fields_for_fire_quotation(record: models.ImportRecord) -> dict:
    fields = row_to_fire_quotation_fields(record.raw_data or {})
    return {"last_name": (fields.get("insured_name") or "").strip() or None}


def resolve_fire_quotation_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_fire_quotation_fields(record.raw_data or {})
    return _resolve_or_create_fire_quotation(db, policyholder_id, fields)


# ------------------------------------------------------------
# Needs-review resolution — Fire & Property Policies
# ------------------------------------------------------------

def new_policyholder_fields_for_fire_policy(record: models.ImportRecord) -> dict:
    fields = row_to_fire_policy_fields(record.raw_data or {})
    raw_name, raw_addr = import_shared.split_insured_name_address(fields.get("insured_name_address"))
    return {"last_name": raw_name.strip() or None, "present_address": raw_addr.strip() or None}


def resolve_fire_policy_for_policyholder(db: Session, record: models.ImportRecord, policyholder_id: int):
    fields = row_to_fire_policy_fields(record.raw_data or {})
    return _resolve_or_create_fire_policy(db, policyholder_id, fields)


def create_fire_policy_from_quotation(db: Session, record: models.ImportRecord, quotation_id: int):
    """Used by the quotation-picker resolve path once staff explicitly chooses a quotation."""
    quotation = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.id == quotation_id
    ).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    if quotation.insurance_case.line_type != models.LineType.fire_property:
        raise HTTPException(status_code=400, detail="Quotation is not a Fire & Property quotation")
    if quotation.policy is not None:
        raise HTTPException(status_code=409, detail="This quotation already has a policy attached")

    fields = row_to_fire_policy_fields(record.raw_data or {})
    policy_fields = {k: v for k, v in fields.items() if k != "insured_name_address"}
    new_policy = models.FirePropertyPolicy(
        quotation_id=quotation.id,
        insured_name_address=fields.get("insured_name_address"),
        **policy_fields,
    )
    db.add(new_policy)
    db.flush()

    return quotation.insurance_case_id, models.MatchStatus.unmatched


def list_fire_policy_quotation_candidates(db: Session, policyholder_id: int) -> list:
    return import_shared.list_quotation_candidates(
        db, policyholder_id, models.LineType.fire_property,
        models.FirePropertyQuotation, models.FirePropertyPolicy,
        amount_getter=lambda q: q.total_premium,
        date_getter=lambda q: q.quotation_date,
    )