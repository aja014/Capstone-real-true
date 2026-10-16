from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any, Literal, ClassVar
from enum import Enum

from sqlalchemy import Enum as SAEnum, String

from app import models


class ColumnLimited(BaseModel):
    """Base of the API's create/update bodies: a text longer than its database column is refused
    with a 422 naming the field (Pydantic's own "String should have at most N characters"),
    instead of MySQL's "Data too long" turning into a 500. Limits come from models.py, so they
    always match the columns. Importers don't use these schemas: they already report such a row
    as an error."""
    __column_limits__: ClassVar[dict] = {}

    @field_validator("*")
    @classmethod
    def _fit_column(cls, value, info):
        limit = cls.__column_limits__.get(info.field_name)
        if limit and isinstance(value, str) and len(value) > limit:
            raise PydanticCustomError("string_too_long", "String should have at most {max_length} characters",
                                      {"max_length": limit})
        return value


def _column_limits(model, only=None):
    return {c.name: c.type.length for c in model.__table__.columns
            if isinstance(c.type, String) and not isinstance(c.type, SAEnum)  # enums: Pydantic checks them
            and c.type.length and (only is None or c.name in only)}


class UserCreate(ColumnLimited):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserOut(BaseModel):
    """The only user fields the API may send back: never the password hash."""
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True


class UserCreated(BaseModel):
    message: str
    user: UserOut


# ------------------------------------------------------------
# Enums (must match the values used in models.py)
# ------------------------------------------------------------

class LineType(str, Enum):
    fire_property = "fire_property"
    motor_car = "motor_car"


# ------------------------------------------------------------
# POLICYHOLDER
# ------------------------------------------------------------

class PolicyholderCreate(ColumnLimited):
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

class InsuranceCaseCreate(ColumnLimited):
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

class FirePropertySurveyCreate(ColumnLimited):
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
    flood_risk_category: Optional[str] = None  # combined worst-of-river-flood/storm-surge result
    river_flood_category: Optional[str] = None
    storm_surge_category: Optional[str] = None

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

class FirePropertyQuotationCreate(ColumnLimited):
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

class FirePropertyPolicyCreate(ColumnLimited):
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
    premium: Optional[Decimal] = None
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

class VehicleCreate(ColumnLimited):
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

class MotorQuotationCreate(ColumnLimited):
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
    sum_insured: Optional[Decimal] = None

    # GIS — usually filled in automatically by the flood-risk lookup service, optional here
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    flood_risk_flag: Optional[bool] = None
    flood_risk_category: Optional[str] = None  # combined worst-of-river-flood/storm-surge result
    river_flood_category: Optional[str] = None
    storm_surge_category: Optional[str] = None


class MotorQuotationOut(MotorQuotationCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------
# MOTOR / CAR — POLICY
# ------------------------------------------------------------

class MotorPolicyCreate(ColumnLimited):
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
    sum_insured: Optional[Decimal] = None
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
# CLAIMS (Objective 1.3) — option lists are module-level so a future
# claims importer (which bypasses Pydantic) can reuse the same values
# ------------------------------------------------------------

MOTOR_NATURE_OF_LOSS_OPTIONS = ("Collision", "Flood", "Theft/Carnapping", "Fire", "Vandalism", "Other")
FIRE_NATURE_OF_LOSS_OPTIONS = ("Fire", "Flood", "Typhoon", "Earthquake", "Lightning", "Other")
MOTOR_COVERAGE_TYPE_OPTIONS = ("Own Damage", "Third Party Property Damage", "Third Party Bodily Injury/Death")
CLAIM_TYPE_OPTIONS = ("Paid Claim", "CNC Issuance")
CLAIM_FINAL_STATUS_OPTIONS = (
    "No Docs. Submitted", "Waiting for Evaluation", "Waiting for LOA",
    "Waiting for Billing", "Waiting for Claim Check", "Closed Claim",
    "Denied Claim", "CNC Only", "Not Push Through", "With Lacking Docs",
    "Hold per Client",
)
CLAIM_INVESTIGATION_RESULT_OPTIONS = ("Legitimate", "Suspected Fraud", "Confirmed Fraud")

# Protection Facilities checklist — display name -> JSON key, exactly as on Maagap's
# Survey Report paper form. The 3 keys already used before this list existed
# (sprinklers, fire_alarm, fire_extinguisher) are kept. Used by the Survey bulk
# importer; the manual create endpoint still accepts any JSON object.
PROTECTION_FACILITY_OPTIONS = {
    "Risk Management/Safety/Security Units": "risk_management_units",
    "Plant Safety": "plant_safety",
    "Flood Control": "flood_control",
    "Security Control": "security_control",
    "Access to Plant/Site": "access_to_site",
    "Automatic Sprinklers": "sprinklers",
    "Internal Hydrants": "internal_hydrants",
    "External Hydrants": "external_hydrants",
    "Fire Alarm System": "fire_alarm",
    "Smoke Detector": "smoke_detector",
    "Heat Detector": "heat_detector",
    "Fire Extinguisher": "fire_extinguisher",
    "Fire Brigade": "fire_brigade",
    "Fire Breaks/Doors": "fire_breaks_doors",
    "Fire Truck": "fire_truck",
    "Fire Pump": "fire_pump",
    "Jockey Pump": "jockey_pump",
    "Public/Private Fire Fighting": "public_private_fire_fighting",
    "Security Guards": "security_guards",
    "Hot Works Permit": "hot_works_permit",
    "Water Supply": "water_supply",
    "Power Supply": "power_supply",
    "Generator Set": "generator_set",
    "Telecommunications": "telecommunications",
    "CCTV/Monitor/Recording": "cctv",
    "Sniffing Dogs": "sniffing_dogs",
    "Metal Detectors/Frisking": "metal_detectors_frisking",
    "Fire Fighting Appliances Inspection": "fire_fighting_appliances_inspection",
    "Perimeter Fence": "perimeter_fence",
    "Police/Armed Force": "police_armed_force",
    "Redundancies/BCP/DRP": "redundancies_bcp_drp",
    "Others": "others",
}
# Extra accepted spellings (only the ones Maagap listed).
PROTECTION_FACILITY_ALIASES = {
    "Sprinkler": "sprinklers",
    "Sprinklers": "sprinklers",
    "Fire Alarm": "fire_alarm",
    "CCTV": "cctv",
}


def canonical_choice(v, options, field_name):
    # Same behavior as the risk-assessment validators above: blank passes
    # through, match is case-insensitive, stored value is the canonical spelling.
    if v is None or v == "":
        return v
    match = next((opt for opt in options if opt.lower() == v.strip().lower()), None)
    if not match:
        raise ValueError(f'{field_name} must be one of: {", ".join(options)}')
    return match


class MotorClaimCreate(ColumnLimited):
    motor_policy_id: int  # required — a claim must link to the policy it was filed against

    accuterm_claim_no: Optional[str] = None
    assured: Optional[str] = None
    claimant_name: Optional[str] = None
    plate_no: Optional[str] = None
    date_reported: Optional[date] = None
    date_of_loss: Optional[date] = None
    date_docs_submitted: Optional[date] = None
    nature_of_loss: Optional[str] = None
    coverage_type: Optional[str] = None
    claim_type: Optional[str] = None
    updates: Optional[str] = None
    date_updated: Optional[date] = None
    agent_name: Optional[str] = None
    repair_estimate_amount: Optional[Decimal] = None
    loa_received_date: Optional[date] = None
    loa_no: Optional[str] = None
    loa_amount: Optional[Decimal] = None
    net_liability: Optional[Decimal] = None
    shop_casa: Optional[str] = None
    status: Optional[str] = None
    billing_date_remarks: Optional[str] = None
    final_status: Optional[str] = None
    claim_investigation_result: Optional[str] = None

    @field_validator("nature_of_loss")
    @classmethod
    def validate_nature_of_loss(cls, v):
        return canonical_choice(v, MOTOR_NATURE_OF_LOSS_OPTIONS, "nature_of_loss")

    @field_validator("coverage_type")
    @classmethod
    def validate_coverage_type(cls, v):
        return canonical_choice(v, MOTOR_COVERAGE_TYPE_OPTIONS, "coverage_type")

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v):
        return canonical_choice(v, CLAIM_TYPE_OPTIONS, "claim_type")

    @field_validator("final_status")
    @classmethod
    def validate_final_status(cls, v):
        return canonical_choice(v, CLAIM_FINAL_STATUS_OPTIONS, "final_status")

    @field_validator("claim_investigation_result")
    @classmethod
    def validate_claim_investigation_result(cls, v):
        return canonical_choice(v, CLAIM_INVESTIGATION_RESULT_OPTIONS, "claim_investigation_result")


class MotorClaimOut(MotorClaimCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FirePropertyClaimCreate(ColumnLimited):
    fire_property_policy_id: int  # required — a claim must link to the policy it was filed against

    accuterm_claim_no: Optional[str] = None
    assured: Optional[str] = None
    claimant_name: Optional[str] = None
    date_reported: Optional[date] = None
    date_of_loss: Optional[date] = None
    date_docs_submitted: Optional[date] = None
    nature_of_loss: Optional[str] = None
    claim_type: Optional[str] = None
    updates: Optional[str] = None
    date_updated: Optional[date] = None
    agent_name: Optional[str] = None
    repair_estimate_amount: Optional[Decimal] = None
    loa_received_date: Optional[date] = None
    loa_no: Optional[str] = None
    loa_amount: Optional[Decimal] = None
    net_liability: Optional[Decimal] = None
    adjuster: Optional[str] = None
    status: Optional[str] = None
    billing_date_remarks: Optional[str] = None
    final_status: Optional[str] = None
    claim_investigation_result: Optional[str] = None

    @field_validator("nature_of_loss")
    @classmethod
    def validate_nature_of_loss(cls, v):
        return canonical_choice(v, FIRE_NATURE_OF_LOSS_OPTIONS, "nature_of_loss")

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v):
        return canonical_choice(v, CLAIM_TYPE_OPTIONS, "claim_type")

    @field_validator("final_status")
    @classmethod
    def validate_final_status(cls, v):
        return canonical_choice(v, CLAIM_FINAL_STATUS_OPTIONS, "final_status")

    @field_validator("claim_investigation_result")
    @classmethod
    def validate_claim_investigation_result(cls, v):
        return canonical_choice(v, CLAIM_INVESTIGATION_RESULT_OPTIONS, "claim_investigation_result")


class FirePropertyClaimOut(FirePropertyClaimCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MotorClaimUpdate(MotorClaimCreate):
    # PATCH — every field optional; inherits the canonical_choice validators.
    motor_policy_id: Optional[int] = None


class FirePropertyClaimUpdate(FirePropertyClaimCreate):
    fire_property_policy_id: Optional[int] = None


class DeletedMotorClaimOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

    class Config:
        from_attributes = True


class DeletedFirePropertyClaimOut(BaseModel):
    id: int
    original_id: int
    data: dict[str, Any]
    deleted_at: datetime

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
    motor_claim = "motor_claim"
    fire_property_claim = "fire_property_claim"


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


class ImportRowWarning(BaseModel):
    source_row: Optional[int] = None
    warning: str


class ImportSummary(BaseModel):
    source_file: str
    total_rows: int
    matched: int
    unmatched_created: int
    needs_review: int
    failed: int = 0
    import_record_ids: list[int]
    errors: list[ImportRowError] = []
    # Row imported, but something looked off (e.g. Occupancy - Total != sum of parts).
    warnings: list[ImportRowWarning] = []


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
    # or (Claims import rows only) create the claim against this explicitly chosen policy
    matched_policy_id: Optional[int] = None


class QuotationCandidate(BaseModel):
    id: int
    quotation_date: Optional[date] = None
    amount: Optional[Decimal] = None
    case_id: int


class PolicyCandidate(BaseModel):
    id: int
    policy_no: Optional[str] = None
    insured_name_address: Optional[str] = None
    period_from: Optional[date] = None
    period_to: Optional[date] = None


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
    renewal_rate: float  # renewed_count / (renewed_count + lost_count) * 100, 0 if both are 0

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
    filed_claims: int  # claims (both lines) with date_reported in the current month

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


# ------------------------------------------------------------
# QUOTATIONS / PROPOSAL PAGE STATS
# ------------------------------------------------------------

class QuotationProposalPieSlice(BaseModel):
    name: str  # "Quotation" | "Converted Account"
    value: int


class QuotationProposalTrendEntry(BaseModel):
    label: str  # rolling mode: month abbreviation (e.g. "Apr"); month mode: day-of-month (e.g. "1")
    quotation_count: int  # total quotations (fire+motor) dated in this bucket
    converted_count: int  # of those, how many have a linked policy


class QuotationProposalStats(BaseModel):
    date: date  # reference "today"

    # Scoped to range_start/range_end below (rolling window OR the one
    # selected month) — no longer all-time.
    total_quotations: int
    converted_accounts: int
    conversion_rate: float  # converted_accounts / total_quotations * 100, 0 if total is 0

    fire_pie: list[QuotationProposalPieSlice]
    motor_pie: list[QuotationProposalPieSlice]

    mode: str  # "rolling" | "month"
    range_start: date  # inclusive bounds actually used to scope everything above + trend
    range_end: date

    months: int | None  # echoes the requested rolling window (3/6/12); null in month mode
    year: int | None  # echoed back only in month mode
    month: int | None  # echoed back only in month mode

    trend: list[QuotationProposalTrendEntry]  # oldest → newest


# ------------------------------------------------------------
# POLICY FORECAST (Proposal page card) — plain statistics, not an ML model.
# Next month = quotations per month (past 12 months) × conversion rate; open
# quotations shown separately. See app/services/policy_forecast.py.
# ------------------------------------------------------------

class PolicyForecastLine(BaseModel):
    line: str  # "Motor Car" | "Fire & Property"
    wait_days: int  # W: 95th percentile of days from quotation to policy, rounded up
    decided_quotations: int  # at least W days old, within the past 12 months
    converted_quotations: int  # of those, became a policy within W days
    conversion_rate: Optional[float]  # 0..1; null when nothing is decided yet
    quotations_past_12_months: int
    avg_quotations_per_month: float
    expected_policies: Optional[float]  # next calendar month
    open_quotations: int  # younger than W days, no policy yet
    expected_from_open: Optional[float]  # policies expected from them within W days (age-aware)
    backtest_error_pct: Optional[float]  # mean |forecast − actual| ÷ actual, last 12 complete months
    backtest_total_error_pct: Optional[float]  # signed, summed over those 12 months
    open_backtest_error_pct: Optional[float]  # same, for the open-quotation forecast


class PolicyForecastBacktestLine(BaseModel):
    line: str
    forecast: Optional[float]
    actual: int  # policies issued in the target month
    open_quotations: int
    open_forecast: Optional[float]
    open_actual: int  # policies those open quotations actually became


class PolicyForecastBacktestRow(BaseModel):
    as_of: date  # the 1st of the month before the target month
    target_year: int
    target_month: int
    target_label: str  # e.g. "August 2026"
    lines: list[PolicyForecastBacktestLine]
    total_forecast: Optional[float]
    total_actual: int


class PolicyForecast(BaseModel):
    as_of: date  # today
    target_year: int
    target_month: int
    target_label: str  # next calendar month, e.g. "October 2026"
    history_months: int
    expected_policies: Optional[float]  # both lines
    avg_quotations_per_month: float
    open_quotations: int
    expected_from_open: Optional[float]
    backtest_error_pct: Optional[float]
    backtest_total_error_pct: Optional[float]
    lines: list[PolicyForecastLine]  # Motor Car, Fire & Property
    backtest: list[PolicyForecastBacktestRow]  # oldest → newest


# ------------------------------------------------------------
# CLAIMS MODULE PAGE STATS
# Every figure is scoped to claims FILED (date_reported) in range_start..range_end.
# Each claim row counts once (OD + TP rows of one accident are separate rows).
# ------------------------------------------------------------

class ClaimsTrendEntry(BaseModel):
    label: str  # month abbreviation, e.g. "Apr"
    year: int
    month: int
    motor_count: int
    fire_count: int
    fraud_labelled_count: int  # Suspected + Confirmed Fraud (human investigation label), CNC excluded


class ClaimsStats(BaseModel):
    date: date  # reference "today"
    months: int  # 3 | 6 | 12 (anything else -> 6)
    range_start: date  # first day of the oldest month in the window
    range_end: date  # last day of the current month
    period_label: str  # e.g. "Past 6 Months"

    total_claims: int
    motor_claims: int
    fire_claims: int
    open_claims: int  # final_status not one of Closed / Denied / CNC Only / Not Push Through
    closed_claims: int  # final_status == "Closed Claim"
    other_claims: int  # Total − Open − Closed: Denied / CNC Only / Not Push Through (or no status)
    total_net_liability: Decimal

    # Investigation result -- CNC Issuance rows are excluded (not investigated for fraud).
    legitimate: int
    suspected_fraud: int
    confirmed_fraud: int
    not_yet_investigated: int
    cnc_excluded: int  # CNC Issuance rows left out of the four counts above
    fraud_rate: Optional[float]  # (suspected + confirmed) / investigated * 100; null if none investigated
    investigation_pie: list[OverviewPieSlice]

    trend: list[ClaimsTrendEntry]  # oldest -> newest

# ------------------------------------------------------------
# PREDICTIVE MODELS (GET /ml/...) — see app/ml/ and app/routers/ml.py
# ------------------------------------------------------------

class MLMeanSD(BaseModel):
    mean: Optional[float] = None
    sd: Optional[float] = None


class MLModelFailure(BaseModel):
    version: int
    trained_at: datetime
    error: Optional[str] = None  # first line only


class MLModelSummary(BaseModel):
    model_name: str  # motor_lr | fire_lr | fraud_nb
    title: str
    available: bool  # False = no active version (never trained, or not enough data)
    version: Optional[int] = None
    trained_at: Optional[datetime] = None
    data_as_of: Optional[date] = None
    train_rows: Optional[int] = None
    test_rows: Optional[int] = None
    positive_rows: Optional[int] = None
    # LR: {"medium_from", "high_from"}; Naive Bayes: {"fraud_cutoff"}
    thresholds: Optional[dict[str, float]] = None
    # held-back 25% test data: accuracy, precision, recall, f1, roc_auc
    test: Optional[dict[str, Optional[float]]] = None
    # 5-fold stratified CV: accuracy, precision, recall, roc_auc -> mean / sd
    cross_validation: Optional[dict[str, MLMeanSD]] = None
    report_file: Optional[str] = None  # file name inside model_reports/
    last_failure: Optional[MLModelFailure] = None  # set when the LATEST attempt failed


class MLRefreshStatus(BaseModel):
    running: bool
    last_reason: Optional[str] = None  # "upload" | "startup"
    last_started_at: Optional[datetime] = None
    last_finished_at: Optional[datetime] = None
    last_retrained: list[str] = []
    last_predictions: dict[str, int] = {}
    last_error: Optional[str] = None


class MLModelsOverview(BaseModel):
    models: list[MLModelSummary]
    refresh: MLRefreshStatus


class MLModelAttempt(BaseModel):
    version: int
    status: str  # active | superseded | failed
    trained_at: datetime
    data_as_of: date
    error: Optional[str] = None


class MLModelDetail(MLModelSummary):
    metrics: Optional[dict[str, Any]] = None  # everything shown in the report
    history: list[MLModelAttempt]


class QuotationPrediction(BaseModel):
    line: str  # "Motor Car" | "Fire & Property"
    quotation_id: int
    claim_probability: float  # Claim Possibility, 0..1
    risk_level: str  # Low | Medium | High (Risk Assessment)
    model_version: int
    predicted_at: Optional[datetime] = None


class ClaimPrediction(BaseModel):
    line: str  # "Motor Car" | "Fire & Property"
    claim_id: int
    fraud_probability: float  # normalized P(Fraud), 0..1
    label: str  # Fraud | Legitimate, at the model's stored fraud_cutoff
    model_version: int
    predicted_at: Optional[datetime] = None



# GET /ml/inputs/... — the model inputs of each row, read from the same frames the models
# use (app/ml/features.py). null = missing on the record (the model fills it: Unknown /
# training mean / 0).
class MotorQuotationInputs(BaseModel):
    quotation_id: int
    flood_category: Optional[str] = None  # High / Medium / Low / None / Unknown
    classification: Optional[str] = None
    make: Optional[str] = None
    body_type: Optional[str] = None
    color: Optional[str] = None
    vehicle_age: Optional[int] = None  # years, quotation year − model year
    sum_insured: Optional[float] = None
    deductible: Optional[float] = None
    prior_claim: bool  # the frame's prior_counted_loss


class FireQuotationInputs(BaseModel):
    quotation_id: int
    survey_id: Optional[int] = None  # the case's latest survey; null = no survey
    flood_category: Optional[str] = None
    occupancy: Optional[str] = None
    overall_risk_assessment: Optional[str] = None
    total_sum_insured: Optional[float] = None
    fire_protection_count: Optional[int] = None  # of the 8 fire-protection items
    construction_class_b: Optional[bool] = None
    has_loss_record: Optional[bool] = None
    prior_claim: bool


class ClaimInputs(BaseModel):
    line: str  # "Motor Car" | "Fire & Property"
    claim_id: int
    days_coverage_start_to_loss: str
    days_loss_to_report: str
    estimate_to_sum_insured: str
    earlier_claims_12_months: str
    days_loss_to_expiry: str
    nature_of_loss: str
    coverage_type: str
    policy_type: str
    days_report_to_documents: str

# Column limits of the create/update bodies (see ColumnLimited). The Update schemas inherit them.
UserCreate.__column_limits__ = _column_limits(models.User, only={"username"})
PolicyholderCreate.__column_limits__ = _column_limits(models.Policyholder)
InsuranceCaseCreate.__column_limits__ = _column_limits(models.InsuranceCase)
FirePropertySurveyCreate.__column_limits__ = _column_limits(models.FirePropertySurvey)
FirePropertyQuotationCreate.__column_limits__ = _column_limits(models.FirePropertyQuotation)
FirePropertyPolicyCreate.__column_limits__ = _column_limits(models.FirePropertyPolicy)
VehicleCreate.__column_limits__ = _column_limits(models.Vehicle)
MotorQuotationCreate.__column_limits__ = _column_limits(models.MotorQuotation)
MotorPolicyCreate.__column_limits__ = _column_limits(models.MotorPolicy)
MotorClaimCreate.__column_limits__ = _column_limits(models.MotorClaim)
FirePropertyClaimCreate.__column_limits__ = _column_limits(models.FirePropertyClaim)
