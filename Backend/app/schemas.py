from pydantic import BaseModel, field_validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any
from enum import Enum


class UserCreate(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str


# ------------------------------------------------------------
# Enums (must match the values used in models.py)
# ------------------------------------------------------------

class LineType(str, Enum):
    fire_property = "fire_property"
    motor_car = "motor_car"


# ------------------------------------------------------------
# POLICYHOLDER
# ------------------------------------------------------------

class PolicyholderCreate(BaseModel):
    last_name: str
    first_name: Optional[str] = None  # blank for business-name-only records (e.g. Fire/Property "Name of Insured")
    middle_name: Optional[str] = None
    nationality: Optional[str] = None
    marital_status: Optional[str] = None
    spouse_full_name: Optional[str] = None
    gender: Optional[str] = None

    present_address: Optional[str] = None
    permanent_address: Optional[str] = None
    residence_phone: Optional[str] = None
    mobile_number: Optional[str] = None
    email_address: Optional[str] = None
    zip_code: Optional[str] = None

    occupation: Optional[str] = None
    tin: Optional[str] = None
    sss_no: Optional[str] = None
    employer: Optional[str] = None


class PolicyholderOut(PolicyholderCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # lets this read directly from a SQLAlchemy model


# ------------------------------------------------------------
# INSURANCE CASE
# ------------------------------------------------------------

class InsuranceCaseCreate(BaseModel):
    policyholder_id: int
    line_type: LineType
    status: Optional[str] = "open"


class InsuranceCaseOut(BaseModel):
    id: int
    policyholder_id: int
    line_type: LineType
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# FIRE / PROPERTY — SURVEY
# ------------------------------------------------------------

class FirePropertySurveyCreate(BaseModel):
    insurance_case_id: int

    name_of_insured: Optional[str] = None
    contact_person: Optional[str] = None
    owner_business_description: Optional[str] = None
    location_of_risk: Optional[str] = None
    district_block_no: Optional[str] = None
    tel_fax_no: Optional[str] = None
    current_block_accumulation: Optional[str] = None
    zone: Optional[str] = None
    ti: Optional[str] = None
    risk_class: Optional[str] = None  # "a" or "b"

    occupancy_breakdown: Optional[dict[str, Any]] = None  # e.g. {"building": 1000000, "stocks": 200000}
    description: Optional[str] = None
    boundaries: Optional[dict[str, Any]] = None  # e.g. {"front": "...", "right": "...", "left": "...", "rear": "..."}
    maximum_amount_subject: Optional[Decimal] = None
    protection_facilities: Optional[dict[str, Any]] = None  # checklist e.g. {"sprinklers": true, "fire_alarm": false}
    loss_record: Optional[str] = None

    # GIS — usually filled in after a separate flood-check step, so optional here
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    flood_risk_flag: Optional[bool] = None
    flood_risk_category: Optional[str] = None

    @field_validator("risk_class")
    @classmethod
    def validate_risk_class(cls, v):
        if v is None or v == "":
            return v
        v = v.strip().lower()
        if v not in ("a", "b"):
            raise ValueError('risk_class must be "a" (concrete) or "b" (concrete & wood/light materials)')
        return v


class FirePropertySurveyOut(FirePropertySurveyCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# FIRE / PROPERTY — QUOTATION
# ------------------------------------------------------------

class FirePropertyQuotationCreate(BaseModel):
    insurance_case_id: int

    quotation_date: Optional[date] = None
    insured_name: Optional[str] = None
    location_of_risk: Optional[str] = None
    period_cover: Optional[str] = None
    property_sums_insured: Optional[Decimal] = None
    basis_of_evaluation: Optional[str] = None
    deductibles: Optional[str] = None
    subjective: Optional[str] = None
    occupancy: Optional[str] = None
    total_sum_insured: Optional[Decimal] = None
    mortgagee: Optional[str] = None
    perils_covered: Optional[str] = None
    line_of_insurance: Optional[str] = None
    total_premium: Optional[Decimal] = None
    conditions: Optional[dict[str, Any]] = None  # combined: coinsurance/other/general/important conditions


class FirePropertyQuotationOut(FirePropertyQuotationCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# FIRE / PROPERTY — POLICY
# ------------------------------------------------------------

class FirePropertyPolicyCreate(BaseModel):
    quotation_id: int  # required — a policy must link to the quotation it came from

    issue_date: Optional[date] = None
    insured_name_address: Optional[str] = None
    line_of_insurance: Optional[str] = None
    policy_no: Optional[str] = None
    renewing_policy_no: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    tin: Optional[str] = None
    total_amount_due: Optional[Decimal] = None
    agency_code: Optional[str] = None
    coverage_description: Optional[str] = None
    sum_insured: Optional[Decimal] = None
    unit_cost_premium: Optional[Decimal] = None
    replacing_cover_note_no: Optional[str] = None
    premium_invoice_no: Optional[str] = None
    official_receipt_no: Optional[str] = None
    property_insured: Optional[str] = None
    construction: Optional[str] = None
    occupancy: Optional[str] = None


class FirePropertyPolicyOut(FirePropertyPolicyCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# MOTOR / CAR — VEHICLE
# ------------------------------------------------------------

class VehicleCreate(BaseModel):
    insurance_case_id: int

    model: Optional[str] = None
    make: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    plate_no: Optional[str] = None
    motor_engine_no: Optional[str] = None
    serial_chassis_no: Optional[str] = None
    authorized_capacity: Optional[str] = None


class VehicleOut(VehicleCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# MOTOR / CAR — QUOTATION
# ------------------------------------------------------------

class MotorQuotationCreate(BaseModel):
    insurance_case_id: int
    vehicle_id: int

    quotation_date: Optional[date] = None
    insured_name: Optional[str] = None
    address: Optional[str] = None
    unit: Optional[str] = None
    classification: Optional[str] = None
    color: Optional[str] = None
    deductible: Optional[Decimal] = None
    plate_no: Optional[str] = None
    total_amount_due: Optional[Decimal] = None


class MotorQuotationOut(MotorQuotationCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# MOTOR / CAR — POLICY
# ------------------------------------------------------------

class MotorPolicyCreate(BaseModel):
    quotation_id: int  # required — a policy must link to the quotation it came from

    issue_date: Optional[date] = None
    insured_name_address: Optional[str] = None
    line_of_insurance: Optional[str] = None
    policy_no: Optional[str] = None
    renewing_policy_no: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    tin: Optional[str] = None
    agency_code: Optional[str] = None
    coc_no: Optional[str] = None
    coi_no: Optional[str] = None
    endorsement_no: Optional[str] = None
    total_amount_due: Optional[Decimal] = None
    replacing_cover_note_no: Optional[str] = None
    premium_invoice_no: Optional[str] = None
    official_receipt_no: Optional[str] = None
    deductible: Optional[Decimal] = None


class MotorPolicyOut(MotorPolicyCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# BULK IMPORT & VALIDATION
# ------------------------------------------------------------

class MatchStatus(str, Enum):
    matched = "matched"
    unmatched = "unmatched"
    needs_review = "needs_review"


class ImportRecordOut(BaseModel):
    id: int
    source_file: str
    source_row: Optional[int] = None
    match_status: MatchStatus
    matched_case_id: Optional[int] = None
    matched_policyholder_id: Optional[int] = None
    raw_data: Optional[dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ImportRowError(BaseModel):
    source_row: Optional[int] = None
    error: str


class ImportSummary(BaseModel):
    source_file: str
    total_rows: int
    matched: int
    unmatched_created: int
    needs_review: int
    failed: int = 0
    import_record_ids: list[int]
    errors: list[ImportRowError] = []


class DeletedPolicyholderOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedImportRecordOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class ResolveImportRecord(BaseModel):
    # Provide ONE of these two:
    matched_policyholder_id: Optional[int] = None  # link this row to an existing policyholder
    create_new: bool = False  # or create a brand-new policyholder from this row's raw_data