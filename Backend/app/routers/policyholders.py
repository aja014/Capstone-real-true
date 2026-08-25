from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Policyholders & Cases"]
)


# ------------------------------------------------------------
# POLICYHOLDERS
# ------------------------------------------------------------

@router.post("/policyholders", response_model=schemas.PolicyholderOut)
def create_policyholder(policyholder: schemas.PolicyholderCreate, db: Session = Depends(get_db)):
    db_policyholder = models.Policyholder(**policyholder.model_dump())

    db.add(db_policyholder)
    db.commit()
    db.refresh(db_policyholder)

    return db_policyholder


@router.get("/policyholders", response_model=list[schemas.PolicyholderOut])
def list_policyholders(db: Session = Depends(get_db)):
    return db.query(models.Policyholder).all()


@router.get("/policyholders/{policyholder_id}", response_model=schemas.PolicyholderOut)
def get_policyholder(policyholder_id: int, db: Session = Depends(get_db)):
    db_policyholder = db.query(models.Policyholder).filter(
        models.Policyholder.id == policyholder_id
    ).first()

    if not db_policyholder:
        raise HTTPException(status_code=404, detail="Policyholder not found")

    return db_policyholder


# ------------------------------------------------------------
# INSURANCE CASES
# ------------------------------------------------------------

@router.post("/insurance-cases", response_model=schemas.InsuranceCaseOut)
def create_insurance_case(case: schemas.InsuranceCaseCreate, db: Session = Depends(get_db)):
    # Confirm the policyholder actually exists before creating a case for them
    policyholder_exists = db.query(models.Policyholder).filter(
        models.Policyholder.id == case.policyholder_id
    ).first()

    if not policyholder_exists:
        raise HTTPException(status_code=404, detail="Policyholder not found")

    db_case = models.InsuranceCase(**case.model_dump())

    db.add(db_case)
    db.commit()
    db.refresh(db_case)

    return db_case


@router.get("/insurance-cases", response_model=list[schemas.InsuranceCaseOut])
def list_insurance_cases(db: Session = Depends(get_db)):
    return db.query(models.InsuranceCase).all()


@router.get("/insurance-cases/{case_id}", response_model=schemas.InsuranceCaseOut)
def get_insurance_case(case_id: int, db: Session = Depends(get_db)):
    db_case = db.query(models.InsuranceCase).filter(
        models.InsuranceCase.id == case_id
    ).first()

    if not db_case:
        raise HTTPException(status_code=404, detail="Insurance case not found")

    return db_case


@router.get("/policyholders/{policyholder_id}/insurance-cases", response_model=list[schemas.InsuranceCaseOut])
def get_cases_for_policyholder(policyholder_id: int, db: Session = Depends(get_db)):
    return db.query(models.InsuranceCase).filter(
        models.InsuranceCase.policyholder_id == policyholder_id
    ).all()