from pydantic import BaseModel, field_validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any, Literal
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
    last_name: Optional[str] = None  # unlike PolicyholderCreate's required field -- a bad
                                      # pre-existing record must still be READABLE, not
                                      # crash the whole list (see import_shared.require_name
                                      # for the write-side guard against creating new ones)
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

    # 18 individual perils, each rated Low/Moderate/High with details/remarks —
    # e.g. {"fire": {"rating": "Low", "remarks": "..."}, "earthquake": {...}, ...}
    perils_assessment: Optional[dict[str, Any]] = None
    # 6 items rated Good/Fair/Poor with details/remarks — same shape as above
    hazard_assessment: Optional[dict[str, Any]] = None
    overall_risk_assessment: Optional[str] = None  # Poor / Fair / Good / Others
    surveyor_risk_acceptability: Optional[str] = None  # Accept / Decline / Key Consideration

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

    @field_validator("overall_risk_assessment")
    @classmethod
    def validate_overall_risk_assessment(cls, v):
        if v is None or v == "":
            return v
        options = ("Poor", "Fair", "Good", "Others")
        match = next((opt for opt in options if opt.lower() == v.strip().lower()), None)
        if not match:
            raise ValueError(f'overall_risk_assessment must be one of: {", ".join(options)}')
        return match

    @field_validator("surveyor_risk_acceptability")
    @classmethod
    def validate_surveyor_risk_acceptability(cls, v):
        if v is None or v == "":
            return v
        options = ("Accept", "Decline", "Key Consideration")
        match = next((opt for opt in options if opt.lower() == v.strip().lower()), None)
        if not match:
            raise ValueError(f'surveyor_risk_acceptability must be one of: {", ".join(options)}')
        return match


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


class ImportType(str, Enum):
    policyholder = "policyholder"
    fire_property = "fire_property"                    # survey
    motor = "motor"                                     # motor quotation
    fire_property_quotation = "fire_property_quotation"
    fire_property_policy = "fire_property_policy"
    motor_policy = "motor_policy"
    vehicle = "vehicle"


class ImportRecordOut(BaseModel):
    id: int
    source_file: str
    source_row: Optional[int] = None
    import_type: ImportType
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


class DeletedFirePropertyPolicyOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedMotorPolicyOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedVehicleOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedFirePropertyQuotationOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedMotorQuotationOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedFirePropertySurveyOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class ResolveImportRecord(BaseModel):
    # Provide ONE of these three:
    matched_policyholder_id: Optional[int] = None  # link this row to an existing policyholder
    create_new: bool = False  # or create a brand-new policyholder from this row's raw_data
    # or (Policy import rows only, once matched_policyholder_id is already set on the
    # record) finalize the policy using this explicitly chosen quotation
    matched_quotation_id: Optional[int] = None


class QuotationCandidate(BaseModel):
    id: int
    quotation_date: Optional[date] = None
    amount: Optional[Decimal] = None
    case_id: int


# ------------------------------------------------------------
# BULK IMPORT — BATCH (folder upload with auto type detection)
# ------------------------------------------------------------

class ImportTypeCandidate(BaseModel):
    import_type: ImportType
    label: str
    score: float
    matched_columns: list[str]


class DetectedFile(BaseModel):
    filename: str
    candidates: list[ImportTypeCandidate]
    best_guess: Optional[ImportType] = None
    confidence: Literal["high", "low", "none"]
    ambiguous: bool
    error: Optional[str] = None


class BatchDetectResult(BaseModel):
    files: list[DetectedFile]


class BatchFileResult(BaseModel):
    filename: str
    import_type: ImportType
    summary: Optional[ImportSummary] = None
    error: Optional[str] = None


class BatchImportSummary(BaseModel):
    files: list[BatchFileResult]


# ------------------------------------------------------------
# POLICY DISTRIBUTION STATS (Objective-agnostic dashboard aggregation)
# ------------------------------------------------------------

class PolicyDistributionBarEntry(BaseModel):
    label: str  # day-of-month ("1".."31") for MTD, month name ("January", ...) for YTD
    fire_count: int
    motor_count: int


class PolicyDistributionPieSlice(BaseModel):
    name: str  # "New Policy" | "Renewed Policy"
    value: int


class PolicyDistributionStats(BaseModel):
    period: Literal["daily", "mtd", "ytd"]
    date: date            # the reference date the request was made for
    range_start: date
    range_end: date

    total_policies: int
    fire_count: int
    motor_count: int
    total_amount_due: Decimal

    # Empty for "daily" (no chart in that view) — always present with the
    # same shape so the frontend doesn't need period-specific parsing.
    bar_chart: list[PolicyDistributionBarEntry] = []
    fire_pie: list[PolicyDistributionPieSlice] = []
    motor_pie: list[PolicyDistributionPieSlice] = []


# ------------------------------------------------------------
# RENEWAL RATIO STATS (Objective 1.4 groundwork — live calculation,
# no Renewal table yet; see models.py "NOT YET INCLUDED" note)
# ------------------------------------------------------------

class RenewalRatioBarEntry(BaseModel):
    label: str  # day-of-month ("1".."31") for MTD, month name ("January", ...) for YTD
    renewed_count: int
    lost_count: int
    pending_count: int


class RenewalRatioPieSlice(BaseModel):
    name: str  # "Renewed Policy" | "Lost Policy" | "Pending"
    value: int


class RenewalPolicyRow(BaseModel):
    id: int
    policy_no: Optional[str] = None
    client_name: str
    line: str  # "Fire & Property" | "Motor Car"
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    total_amount_due: Optional[Decimal] = None
    sum_insured: Optional[Decimal] = None
    status: Literal["Renewed", "Lost", "Pending"]


class RenewalRatioStats(BaseModel):
    period: Literal["daily", "mtd", "ytd"]
    date: date            # reference "today" for both bucketing and Lost/Pending math
    range_start: date
    range_end: date

    # Aggregates cover Renewed+Lost+Pending policies whose expiry
    # (period_to) falls in [range_start, range_end] — that's every policy
    # in range, since "New" no longer exists as a status.
    expiring_count: int
    renewed_count: int
    lost_count: int
    pending_count: int
    renewal_rate: float  # renewed_count / expiring_count * 100, 0 if expiring_count is 0

    # Empty for "daily" (no chart in that view), same convention as
    # /stats/policy-distribution.
    bar_chart: list[RenewalRatioBarEntry] = []
    fire_pie: list[RenewalRatioPieSlice] = []
    motor_pie: list[RenewalRatioPieSlice] = []

    # Individual policies whose expiry falls in [range_start, range_end].
    policies: list[RenewalPolicyRow] = []


# ------------------------------------------------------------
# OVERVIEW DASHBOARD (fixed one-view dashboard, no period selector —
# see Backend/app/routers/stats.py get_overview for the 3 time windows
# combined here: this-month totals, last-4-calendar-years bar, rolling
# 6-month line)
# ------------------------------------------------------------

class OverviewPieSlice(BaseModel):
    name: str  # "Converted" | "Quotation"
    value: int


class OverviewYearlyBarEntry(BaseModel):
    label: str  # calendar year, e.g. "2023"
    fire_count: int
    motor_count: int


class OverviewMonthlyLineEntry(BaseModel):
    label: str  # month abbreviation, e.g. "Apr" — always distinct within a 6-month window, no year suffix needed
    fire_count: int
    motor_count: int


class OverviewStats(BaseModel):
    date: date  # reference "today"
    month_label: str  # e.g. "September 2026", for stat card captions

    gross_premium_written: Decimal
    policies_made: int
    quotations_offered: int

    # Rolling 3-month window ending at the current month (not calendar-year
    # aligned) — split by whether a policy has since been attached
    # (FirePropertyQuotation.policy / MotorQuotation.policy, uselist=False).
    # Deliberately a DIFFERENT scope than `quotations_offered` above, which
    # stays current-month-only.
    quotation_pie: list[OverviewPieSlice]
    quotation_pie_label: str  # e.g. "Past 3 Months (Jul-Sep 2026)", for the pie's own sub-caption

    # Last 4 calendar years including the current one, oldest first.
    yearly_bar: list[OverviewYearlyBarEntry]

    # Rolling 6-month window ending at the current month (not calendar-year
    # aligned), oldest first.
    monthly_line: list[OverviewMonthlyLineEntry]