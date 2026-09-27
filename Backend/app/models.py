from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Boolean,
    DECIMAL, Double, ForeignKey, JSON, Enum, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    role = Column(String(20), nullable=False, default="admin")


# ------------------------------------------------------------
# ENUMS
# ------------------------------------------------------------

class LineType(str, enum.Enum):
    fire_property = "fire_property"
    motor_car = "motor_car"


class MatchStatus(str, enum.Enum):
    matched = "matched"
    unmatched = "unmatched"
    needs_review = "needs_review"


class ImportType(str, enum.Enum):
    """
    Which bulk importer produced an ImportRecord. Needed because all three
    importers share the same needs-review queue and resolve endpoint — the
    resolver has to know this to reconstruct the right kind of record
    (Policyholder vs. Survey vs. Vehicle/Quotation) instead of only ever
    creating a bare Policyholder.
    """
    policyholder = "policyholder"
    fire_property = "fire_property"                    # survey
    motor = "motor"                                     # motor quotation
    fire_property_quotation = "fire_property_quotation"
    fire_property_policy = "fire_property_policy"
    motor_policy = "motor_policy"
    vehicle = "vehicle"                                  # standalone Vehicle Information import
    motor_claim = "motor_claim"
    fire_property_claim = "fire_property_claim"


# ------------------------------------------------------------
# CORE
# ------------------------------------------------------------

class Policyholder(Base):
    __tablename__ = "policyholders"

    id = Column(Integer, primary_key=True, index=True)

    last_name = Column(String(100))
    first_name = Column(String(100))
    middle_name = Column(String(100))
    nationality = Column(String(100))
    marital_status = Column(String(30))
    spouse_full_name = Column(String(200))
    gender = Column(String(20))

    # Contact Details
    present_address = Column(String(255))
    permanent_address = Column(String(255))
    residence_phone = Column(String(30))
    mobile_number = Column(String(30))
    email_address = Column(String(150))
    zip_code = Column(String(20))

    # Occupational Information
    occupation = Column(String(150))
    tin = Column(String(50))
    sss_no = Column(String(50))
    employer = Column(String(150))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    insurance_cases = relationship("InsuranceCase", back_populates="policyholder")


class InsuranceCase(Base):
    """
    Internal grouping concept: links a policyholder's Survey/Quotation/Policy
    (Fire/Property) or Vehicle/Quotation/Policy (Motor/Car) documents together.
    System-generated — not a company-provided identifier, since the source
    documents have no reliable universal ID across each other.
    """
    __tablename__ = "insurance_cases"

    id = Column(Integer, primary_key=True, index=True)
    policyholder_id = Column(Integer, ForeignKey("policyholders.id"), nullable=False)
    line_type = Column(Enum(LineType), nullable=False)
    status = Column(String(30), default="open")  # open, quoted, policy_issued, rejected, closed

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    policyholder = relationship("Policyholder", back_populates="insurance_cases")

    fire_property_surveys = relationship("FirePropertySurvey", back_populates="insurance_case")
    fire_property_quotations = relationship("FirePropertyQuotation", back_populates="insurance_case")
    vehicles = relationship("Vehicle", back_populates="insurance_case")
    motor_quotations = relationship("MotorQuotation", back_populates="insurance_case")


class ImportRecord(Base):
    """
    Traceability for bulk-imported records (Bulk Client Data Import & Validation).
    Since source documents lack a universal identifier, imported rows are staged
    here with a match status until they're confirmed/linked to an insurance_case.
    """
    __tablename__ = "import_records"

    id = Column(Integer, primary_key=True, index=True)
    source_file = Column(String(255), nullable=False)
    source_row = Column(Integer)
    import_type = Column(Enum(ImportType), nullable=False, default=ImportType.policyholder)
    match_status = Column(Enum(MatchStatus), nullable=False, default=MatchStatus.needs_review)
    matched_case_id = Column(Integer, ForeignKey("insurance_cases.id"), nullable=True)
    # Set when the policyholder is recognized but no existing case matches
    # (e.g. a known person getting a brand-new case) — prevents accidentally
    # creating a duplicate policyholder in that situation.
    matched_policyholder_id = Column(Integer, ForeignKey("policyholders.id"), nullable=True)
    raw_data = Column(JSON)  # original row data, for audit/debugging

    created_at = Column(DateTime, server_default=func.now())

    matched_case = relationship("InsuranceCase")
    matched_policyholder = relationship("Policyholder")


# ------------------------------------------------------------
# DELETED-RECORD ARCHIVE
# ------------------------------------------------------------
# Separate tables (rather than a soft-delete flag on the live tables) so a
# delete never requires ALTERing an existing table — create_all() only
# creates new tables, it doesn't add columns to ones that already exist.
# Each row is a full JSON snapshot of the record at the moment it was
# deleted, so it can be inspected or manually restored later if needed.

class DeletedPolicyholder(Base):
    __tablename__ = "deleted_policyholders"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)  # populated once auth is required on this router


class DeletedImportRecord(Base):
    __tablename__ = "deleted_import_records"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedFirePropertyPolicy(Base):
    __tablename__ = "deleted_fire_property_policies"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedMotorPolicy(Base):
    __tablename__ = "deleted_motor_policies"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedVehicle(Base):
    __tablename__ = "deleted_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedFirePropertyQuotation(Base):
    __tablename__ = "deleted_fire_property_quotations"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedMotorQuotation(Base):
    __tablename__ = "deleted_motor_quotations"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedFirePropertySurvey(Base):
    __tablename__ = "deleted_fire_property_surveys"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedMotorClaim(Base):
    __tablename__ = "deleted_motor_claims"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


class DeletedFirePropertyClaim(Base):
    __tablename__ = "deleted_fire_property_claims"

    id = Column(Integer, primary_key=True, index=True)
    original_id = Column(Integer, nullable=False)
    data = Column(JSON, nullable=False)
    deleted_at = Column(DateTime, server_default=func.now())
    deleted_by = Column(String(255), nullable=True)


# ------------------------------------------------------------
# FIRE / PROPERTY
# ------------------------------------------------------------

class FirePropertySurvey(Base):
    __tablename__ = "fire_property_surveys"

    id = Column(Integer, primary_key=True, index=True)
    insurance_case_id = Column(Integer, ForeignKey("insurance_cases.id"), nullable=False)

    name_of_insured = Column(String(200))
    contact_person = Column(String(150))
    owner_business_description = Column(Text)
    location_of_risk = Column(String(255))
    district_block_no = Column(String(100))
    tel_fax_no = Column(String(50))
    current_block_accumulation = Column(String(100))
    zone = Column(String(50))
    ti = Column(String(50))
    risk_class = Column(String(1))  # a = concrete, b = concrete & wood/light materials

    # Main Occupancy breakdown — combined into one JSON (was 8 separate columns)
    occupancy_breakdown = Column(JSON)

    description = Column(Text)

    # Boundaries — combined into one JSON (was 4 text columns + sketch)
    boundaries = Column(JSON)

    maximum_amount_subject = Column(DECIMAL(15, 2))

    # Protection Facilities — many checklist/detail sub-fields, stored as JSON
    protection_facilities = Column(JSON)

    loss_record = Column(Text)  # e.g. "No known loss history since built in 2019"

    # Added later — confirmed against the real paper Survey Report, missed
    # during original schema design. 18 individual perils, each rated
    # Low/Moderate/High with details/remarks (same JSON pattern as
    # protection_facilities above).
    perils_assessment = Column(JSON)
    # 6 items rated Good/Fair/Poor with details/remarks — same pattern.
    hazard_assessment = Column(JSON)
    overall_risk_assessment = Column(String(50))  # Poor / Fair / Good / Others
    surveyor_risk_acceptability = Column(String(50))  # Accept / Decline / Key Consideration

    # GIS — populated after QGIS/API lookup
    latitude = Column(DECIMAL(10, 7))
    longitude = Column(DECIMAL(10, 7))
    flood_risk_flag = Column(Boolean)
    flood_risk_category = Column(String(50))  # combined worst-of-river-flood/storm-surge result
    river_flood_category = Column(String(50))  # river-flood-alone breakdown, for future ML use
    storm_surge_category = Column(String(50))  # storm-surge-alone breakdown, for future ML use

    created_at = Column(DateTime, server_default=func.now())

    insurance_case = relationship("InsuranceCase", back_populates="fire_property_surveys")


class FirePropertyQuotation(Base):
    __tablename__ = "fire_property_quotations"

    id = Column(Integer, primary_key=True, index=True)
    insurance_case_id = Column(Integer, ForeignKey("insurance_cases.id"), nullable=False)  # multiple allowed

    quotation_date = Column(Date)
    insured_name = Column(String(200))
    location_of_risk = Column(String(255))
    period_cover = Column(String(100))
    property_sums_insured = Column(DECIMAL(15, 2))
    basis_of_evaluation = Column(String(150))
    deductibles = Column(String(150))
    subjective = Column(Text)
    occupancy = Column(String(150))
    total_sum_insured = Column(DECIMAL(15, 2))
    mortgagee = Column(String(200))  # kept — relevant to future claims payout
    perils_covered = Column(Text)
    line_of_insurance = Column(String(100))
    total_premium = Column(DECIMAL(15, 2))

    # Combined: declaration_of_coinsurance, other_condition, general_condition,
    # important_condition — into one flexible JSON field
    conditions = Column(JSON)

    created_at = Column(DateTime, server_default=func.now())

    insurance_case = relationship("InsuranceCase", back_populates="fire_property_quotations")
    policy = relationship("FirePropertyPolicy", back_populates="quotation", uselist=False)


class FirePropertyPolicy(Base):
    __tablename__ = "fire_property_policies"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("fire_property_quotations.id"), nullable=False)  # required

    issue_date = Column(Date)
    insured_name_address = Column(String(255))
    line_of_insurance = Column(String(100))
    policy_no = Column(String(100))              # anchor field for future renewal matching
    renewing_policy_no = Column(String(100))      # anchor field for future renewal matching
    period_from = Column(Date)
    period_to = Column(Date)
    tin = Column(String(50))
    total_amount_due = Column(DECIMAL(15, 2))
    agency_code = Column(String(50))
    coverage_description = Column(Text)
    sum_insured = Column(DECIMAL(15, 2))
    unit_cost_premium = Column(DECIMAL(15, 2))

    replacing_cover_note_no = Column(String(100))
    premium_invoice_no = Column(String(100))
    official_receipt_no = Column(String(100))
    property_insured = Column(String(200))
    construction = Column(String(150))
    occupancy = Column(String(150))

    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("FirePropertyQuotation", back_populates="policy")


# ------------------------------------------------------------
# MOTOR / CAR
# ------------------------------------------------------------

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    insurance_case_id = Column(Integer, ForeignKey("insurance_cases.id"), nullable=False)

    model = Column(String(100))
    make = Column(String(100))
    body_type = Column(String(100))
    color = Column(String(50))
    plate_no = Column(String(30))
    motor_engine_no = Column(String(100))
    serial_chassis_no = Column(String(100))
    authorized_capacity = Column(String(100))

    created_at = Column(DateTime, server_default=func.now())

    insurance_case = relationship("InsuranceCase", back_populates="vehicles")
    quotations = relationship("MotorQuotation", back_populates="vehicle")


class MotorQuotation(Base):
    __tablename__ = "motor_quotations"

    id = Column(Integer, primary_key=True, index=True)
    insurance_case_id = Column(Integer, ForeignKey("insurance_cases.id"), nullable=False)  # multiple allowed
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    quotation_date = Column(Date)
    insured_name = Column(String(200))
    address = Column(String(255))
    unit = Column(String(100))
    classification = Column(String(100))
    color = Column(String(50))
    deductible = Column(DECIMAL(15, 2))
    plate_no = Column(String(30))
    total_amount_due = Column(DECIMAL(15, 2))
    sum_insured = Column(DECIMAL(15, 2))

    # GIS — populated after geocode + flood-hazard lookup (app/services/flood_risk.py)
    latitude = Column(DECIMAL(10, 7))
    longitude = Column(DECIMAL(10, 7))
    flood_risk_flag = Column(Boolean)
    flood_risk_category = Column(String(50))  # combined worst-of-river-flood/storm-surge result
    river_flood_category = Column(String(50))  # river-flood-alone breakdown, for future ML use
    storm_surge_category = Column(String(50))  # storm-surge-alone breakdown, for future ML use

    created_at = Column(DateTime, server_default=func.now())

    insurance_case = relationship("InsuranceCase", back_populates="motor_quotations")
    vehicle = relationship("Vehicle", back_populates="quotations")
    policy = relationship("MotorPolicy", back_populates="quotation", uselist=False)


class MotorPolicy(Base):
    __tablename__ = "motor_policies"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("motor_quotations.id"), nullable=False)  # required

    issue_date = Column(Date)
    insured_name_address = Column(String(255))
    line_of_insurance = Column(String(100))
    policy_no = Column(String(100))              # anchor field for future renewal matching
    renewing_policy_no = Column(String(100))      # anchor field for future renewal matching
    period_from = Column(Date)
    period_to = Column(Date)
    tin = Column(String(50))
    agency_code = Column(String(50))
    coc_no = Column(String(100))
    coi_no = Column(String(100))
    endorsement_no = Column(String(100))
    total_amount_due = Column(DECIMAL(15, 2))
    sum_insured = Column(DECIMAL(15, 2))

    replacing_cover_note_no = Column(String(100))
    premium_invoice_no = Column(String(100))
    official_receipt_no = Column(String(100))
    deductible = Column(DECIMAL(15, 2))

    created_at = Column(DateTime, server_default=func.now())

    quotation = relationship("MotorQuotation", back_populates="policy")


# ------------------------------------------------------------
# CLAIMS (Objective 1.3 — Fraud Detection groundwork)
# ------------------------------------------------------------
# Fixed-list fields are String + Pydantic validation (schemas.py), same as
# risk_class — not SQL ENUM, so a new Maagap value never needs an ALTER.
# Relationships are one-way (claim -> policy) so the existing policy
# classes stay untouched. ON DELETE RESTRICT: a policy with claims on file
# cannot be deleted at the DB level.

class MotorClaim(Base):
    __tablename__ = "motor_claims"

    id = Column(Integer, primary_key=True, index=True)  # system claim ID
    motor_policy_id = Column(Integer, ForeignKey("motor_policies.id", ondelete="RESTRICT"), nullable=False)

    accuterm_claim_no = Column(String(100))  # NOT unique — OD + TP rows of one accident share it; CNC may have none
    assured = Column(String(200))
    claimant_name = Column(String(200))      # third-party claimant, e.g. "... - TP: MARIO SANTOS"
    plate_no = Column(String(30))            # may be a third party's plate for TPPD claims
    date_reported = Column(Date)             # Maagap's "PLA Date"
    date_of_loss = Column(Date)
    date_docs_submitted = Column(Date)
    nature_of_loss = Column(String(50))      # see schemas.MOTOR_NATURE_OF_LOSS_OPTIONS
    coverage_type = Column(String(50))       # see schemas.MOTOR_COVERAGE_TYPE_OPTIONS
    claim_type = Column(String(50))          # see schemas.CLAIM_TYPE_OPTIONS
    updates = Column(Text)
    date_updated = Column(Date)
    agent_name = Column(String(150))
    repair_estimate_amount = Column(DECIMAL(15, 2))
    loa_received_date = Column(Date)
    loa_no = Column(String(100))
    loa_amount = Column(DECIMAL(15, 2))
    net_liability = Column(DECIMAL(15, 2))
    shop_casa = Column(String(200))
    status = Column(String(255))             # free-text progress note
    billing_date_remarks = Column(Text)      # mixed date/text in source
    final_status = Column(String(50))        # see schemas.CLAIM_FINAL_STATUS_OPTIONS
    claim_investigation_result = Column(String(50))  # fraud LABEL for training, not a model prediction

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    motor_policy = relationship("MotorPolicy")


class FirePropertyClaim(Base):
    __tablename__ = "fire_property_claims"

    id = Column(Integer, primary_key=True, index=True)  # system claim ID
    fire_property_policy_id = Column(Integer, ForeignKey("fire_property_policies.id", ondelete="RESTRICT"), nullable=False)

    accuterm_claim_no = Column(String(100))  # NOT unique
    assured = Column(String(200))
    claimant_name = Column(String(200))
    date_reported = Column(Date)             # Maagap's "PLA Date"
    date_of_loss = Column(Date)
    date_docs_submitted = Column(Date)
    nature_of_loss = Column(String(50))      # see schemas.FIRE_NATURE_OF_LOSS_OPTIONS
    claim_type = Column(String(50))          # see schemas.CLAIM_TYPE_OPTIONS
    updates = Column(Text)
    date_updated = Column(Date)
    agent_name = Column(String(150))
    repair_estimate_amount = Column(DECIMAL(15, 2))
    loa_received_date = Column(Date)
    loa_no = Column(String(100))
    loa_amount = Column(DECIMAL(15, 2))
    net_liability = Column(DECIMAL(15, 2))
    adjuster = Column(String(200))
    status = Column(String(255))             # free-text progress note
    billing_date_remarks = Column(Text)      # mixed date/text in source
    final_status = Column(String(50))        # see schemas.CLAIM_FINAL_STATUS_OPTIONS
    claim_investigation_result = Column(String(50))  # fraud LABEL for training, not a model prediction

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    fire_property_policy = relationship("FirePropertyPolicy")


# ------------------------------------------------------------
# GEOCODE CACHE (address memory for services/flood_risk.py)
# ------------------------------------------------------------
# Only the Nominatim answer is cached (found coordinates, or a definite "no
# result"); hazard classification still runs on every lookup. Kept by the reset
# script. utf8mb4_bin so two addresses differing only by an accent never share a
# row (the DB default collation is accent-insensitive). DOUBLE (not DECIMAL) so a
# cache hit returns the exact float the original network call produced.

class GeocodeCache(Base):
    __tablename__ = "geocode_cache"

    id = Column(Integer, primary_key=True)
    normalized_address = Column(String(255, collation="utf8mb4_bin"), nullable=False, unique=True)
    latitude = Column(Double)
    longitude = Column(Double)
    status = Column(String(20), nullable=False)  # found | not_found
    created_at = Column(DateTime, server_default=func.now())


# ------------------------------------------------------------
# PREDICTIVE MODELS (app/ml/) — saved models and their predictions. Predictions live
# here, never in the business tables: a real field (e.g. claim_investigation_result)
# is never overwritten by a model.
# ------------------------------------------------------------

class MLModel(Base):
    __tablename__ = "ml_models"
    __table_args__ = (UniqueConstraint("model_name", "version", name="uq_ml_models_name_version"),)

    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(30), nullable=False, index=True)  # motor_lr | fire_lr | fraud_nb
    version = Column(Integer, nullable=False)                    # 1, 2, 3 ... per model_name
    status = Column(String(20), nullable=False)                  # active | superseded | failed
    trained_at = Column(DateTime, nullable=False)
    data_as_of = Column(Date, nullable=False)                    # "today" for the ended-policy rule
    train_rows = Column(Integer)
    test_rows = Column(Integer)
    positive_rows = Column(Integer)                              # counted-loss policies / fraud claims
    parameters = Column(JSON)   # weights + encoder (LR) or priors + counts + likelihoods (NB)
    metrics = Column(JSON)      # test scores, confusion matrix, 5-fold CV, ROC AUC, top clues
    thresholds = Column(JSON)   # LR {"medium_from", "high_from"}; NB {"fraud_cutoff"}
    report_path = Column(String(255))
    error = Column(Text)        # failed runs only
    created_at = Column(DateTime, server_default=func.now())


class MLPrediction(Base):
    __tablename__ = "ml_predictions"
    __table_args__ = (UniqueConstraint("target_type", "target_id", name="uq_ml_predictions_target"),)

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("ml_models.id"), nullable=False)
    target_type = Column(String(30), nullable=False)  # motor_quotation | fire_quotation | motor_claim | fire_claim
    target_id = Column(Integer, nullable=False)
    probability = Column(DECIMAL(6, 5), nullable=False)  # P(claim) or P(Fraud)
    label = Column(String(30), nullable=False)           # Low/Medium/High, or Fraud/Legitimate
    predicted_at = Column(DateTime, server_default=func.now())

    model = relationship("MLModel")


# ------------------------------------------------------------
# NOT YET INCLUDED (do not fabricate — build once real data/fields arrive):
#   - Renewal           -> will link via renewing_policy_no on the policy tables above
# ------------------------------------------------------------