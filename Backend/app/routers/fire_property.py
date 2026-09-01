from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Fire & Property"],
    dependencies=[Depends(get_current_user)],
)


def get_case_or_404(db: Session, insurance_case_id: int):
    case = db.query(models.InsuranceCase).filter(
        models.InsuranceCase.id == insurance_case_id
    ).first()
    if not case:
        raise HTTPException(status_code=404, detail="Insurance case not found")
    return case


# ------------------------------------------------------------
# SURVEYS
# ------------------------------------------------------------

@router.post("/fire-property/surveys", response_model=schemas.FirePropertySurveyOut)
def create_survey(survey: schemas.FirePropertySurveyCreate, db: Session = Depends(get_db)):
    get_case_or_404(db, survey.insurance_case_id)

    db_survey = models.FirePropertySurvey(**survey.model_dump())
    db.add(db_survey)
    db.commit()
    db.refresh(db_survey)

    return db_survey


@router.get("/fire-property/surveys", response_model=list[schemas.FirePropertySurveyOut])
def list_surveys(db: Session = Depends(get_db)):
    return db.query(models.FirePropertySurvey).all()


@router.get("/fire-property/surveys/{survey_id}", response_model=schemas.FirePropertySurveyOut)
def get_survey(survey_id: int, db: Session = Depends(get_db)):
    db_survey = db.query(models.FirePropertySurvey).filter(
        models.FirePropertySurvey.id == survey_id
    ).first()
    if not db_survey:
        raise HTTPException(status_code=404, detail="Survey not found")
    return db_survey


@router.delete("/fire-property/surveys/{survey_id}", response_model=schemas.DeletedFirePropertySurveyOut)
def delete_survey(survey_id: int, db: Session = Depends(get_db)):
    db_survey = db.query(models.FirePropertySurvey).filter(
        models.FirePropertySurvey.id == survey_id
    ).first()
    if not db_survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Unconditional — nothing in the schema has a FK pointing at a survey
    # (unlike Vehicle/Quotation, which have real dependents), same as Policy.
    snapshot = schemas.FirePropertySurveyOut.model_validate(db_survey).model_dump(mode="json")
    archived = models.DeletedFirePropertySurvey(original_id=db_survey.id, data=snapshot)
    db.add(archived)

    db.delete(db_survey)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-fire-property-surveys", response_model=list[schemas.DeletedFirePropertySurveyOut])
def list_deleted_fire_property_surveys(db: Session = Depends(get_db)):
    return db.query(models.DeletedFirePropertySurvey).order_by(
        models.DeletedFirePropertySurvey.deleted_at.desc()
    ).all()


# ------------------------------------------------------------
# QUOTATIONS
# ------------------------------------------------------------

@router.post("/fire-property/quotations", response_model=schemas.FirePropertyQuotationOut)
def create_quotation(quotation: schemas.FirePropertyQuotationCreate, db: Session = Depends(get_db)):
    get_case_or_404(db, quotation.insurance_case_id)

    db_quotation = models.FirePropertyQuotation(**quotation.model_dump())
    db.add(db_quotation)
    db.commit()
    db.refresh(db_quotation)

    return db_quotation


@router.get("/fire-property/quotations", response_model=list[schemas.FirePropertyQuotationOut])
def list_quotations(db: Session = Depends(get_db)):
    return db.query(models.FirePropertyQuotation).all()


@router.get("/fire-property/quotations/{quotation_id}", response_model=schemas.FirePropertyQuotationOut)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    db_quotation = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.id == quotation_id
    ).first()
    if not db_quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return db_quotation


@router.get(
    "/insurance-cases/{case_id}/fire-property/quotations",
    response_model=list[schemas.FirePropertyQuotationOut]
)
def get_quotations_for_case(case_id: int, db: Session = Depends(get_db)):
    return db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.insurance_case_id == case_id
    ).all()


@router.delete("/fire-property/quotations/{quotation_id}", response_model=schemas.DeletedFirePropertyQuotationOut)
def delete_quotation(quotation_id: int, db: Session = Depends(get_db)):
    db_quotation = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.id == quotation_id
    ).first()
    if not db_quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    # fire_property_policies.quotation_id is a required FK — deleting a
    # quotation out from under an existing policy would orphan it. Block
    # rather than cascade, same as Vehicle blocking on motor_quotations.
    policy = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.quotation_id == quotation_id
    ).first()
    if policy:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: this quotation has a policy on file. "
                   "Remove or reassign it first.",
        )

    snapshot = schemas.FirePropertyQuotationOut.model_validate(db_quotation).model_dump(mode="json")
    archived = models.DeletedFirePropertyQuotation(original_id=db_quotation.id, data=snapshot)
    db.add(archived)

    db.delete(db_quotation)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-fire-property-quotations", response_model=list[schemas.DeletedFirePropertyQuotationOut])
def list_deleted_fire_property_quotations(db: Session = Depends(get_db)):
    return db.query(models.DeletedFirePropertyQuotation).order_by(
        models.DeletedFirePropertyQuotation.deleted_at.desc()
    ).all()


# ------------------------------------------------------------
# POLICIES
# ------------------------------------------------------------

@router.post("/fire-property/policies", response_model=schemas.FirePropertyPolicyOut)
def create_policy(policy: schemas.FirePropertyPolicyCreate, db: Session = Depends(get_db)):
    quotation = db.query(models.FirePropertyQuotation).filter(
        models.FirePropertyQuotation.id == policy.quotation_id
    ).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    db_policy = models.FirePropertyPolicy(**policy.model_dump())
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.get("/fire-property/policies", response_model=list[schemas.FirePropertyPolicyOut])
def list_policies(db: Session = Depends(get_db)):
    return db.query(models.FirePropertyPolicy).all()


@router.get("/fire-property/policies/{policy_id}", response_model=schemas.FirePropertyPolicyOut)
def get_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.id == policy_id
    ).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return db_policy


@router.delete("/fire-property/policies/{policy_id}", response_model=schemas.DeletedFirePropertyPolicyOut)
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.id == policy_id
    ).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # No claims/renewals implemented yet, so nothing downstream depends on a
    # policy — unlike policyholders, no blocking condition is needed here.
    snapshot = schemas.FirePropertyPolicyOut.model_validate(db_policy).model_dump(mode="json")
    archived = models.DeletedFirePropertyPolicy(original_id=db_policy.id, data=snapshot)
    db.add(archived)

    db.delete(db_policy)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-fire-property-policies", response_model=list[schemas.DeletedFirePropertyPolicyOut])
def list_deleted_fire_property_policies(db: Session = Depends(get_db)):
    return db.query(models.DeletedFirePropertyPolicy).order_by(
        models.DeletedFirePropertyPolicy.deleted_at.desc()
    ).all()