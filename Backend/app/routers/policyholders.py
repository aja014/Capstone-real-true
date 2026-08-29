from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Policyholders & Cases"],
    dependencies=[Depends(get_current_user)],
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


@router.delete("/policyholders/{policyholder_id}", response_model=schemas.DeletedPolicyholderOut)
def delete_policyholder(policyholder_id: int, db: Session = Depends(get_db)):
    db_policyholder = db.query(models.Policyholder).filter(
        models.Policyholder.id == policyholder_id
    ).first()

    if not db_policyholder:
        raise HTTPException(status_code=404, detail="Policyholder not found")

    case_count = db.query(models.InsuranceCase).filter(
        models.InsuranceCase.policyholder_id == policyholder_id
    ).count()
    if case_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: this policyholder has {case_count} insurance case(s) on file. "
                   "Remove or reassign those first.",
        )

    snapshot = schemas.PolicyholderOut.model_validate(db_policyholder).model_dump(mode="json")
    archived = models.DeletedPolicyholder(original_id=db_policyholder.id, data=snapshot)
    db.add(archived)

    # Import records referencing this policyholder are independent audit
    # trail entries, not dependents — unlink rather than delete them.
    db.query(models.ImportRecord).filter(
        models.ImportRecord.matched_policyholder_id == policyholder_id
    ).update({"matched_policyholder_id": None})

    db.delete(db_policyholder)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-policyholders", response_model=list[schemas.DeletedPolicyholderOut])
def list_deleted_policyholders(db: Session = Depends(get_db)):
    return db.query(models.DeletedPolicyholder).order_by(models.DeletedPolicyholder.deleted_at.desc()).all()


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