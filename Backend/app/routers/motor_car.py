from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Motor & Car"],
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
# VEHICLES
# ------------------------------------------------------------

@router.post("/motor/vehicles", response_model=schemas.VehicleOut)
def create_vehicle(vehicle: schemas.VehicleCreate, db: Session = Depends(get_db)):
    get_case_or_404(db, vehicle.insurance_case_id)

    db_vehicle = models.Vehicle(**vehicle.model_dump())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)

    return db_vehicle


@router.get("/motor/vehicles", response_model=list[schemas.VehicleOut])
def list_vehicles(db: Session = Depends(get_db)):
    return db.query(models.Vehicle).all()


@router.get("/motor/vehicles/{vehicle_id}", response_model=schemas.VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    db_vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id
    ).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return db_vehicle


# ------------------------------------------------------------
# QUOTATIONS
# ------------------------------------------------------------

@router.post("/motor/quotations", response_model=schemas.MotorQuotationOut)
def create_quotation(quotation: schemas.MotorQuotationCreate, db: Session = Depends(get_db)):
    get_case_or_404(db, quotation.insurance_case_id)

    vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == quotation.vehicle_id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    db_quotation = models.MotorQuotation(**quotation.model_dump())
    db.add(db_quotation)
    db.commit()
    db.refresh(db_quotation)

    return db_quotation


@router.get("/motor/quotations", response_model=list[schemas.MotorQuotationOut])
def list_quotations(db: Session = Depends(get_db)):
    return db.query(models.MotorQuotation).all()


@router.get("/motor/quotations/{quotation_id}", response_model=schemas.MotorQuotationOut)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    db_quotation = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.id == quotation_id
    ).first()
    if not db_quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return db_quotation


@router.get(
    "/insurance-cases/{case_id}/motor/quotations",
    response_model=list[schemas.MotorQuotationOut]
)
def get_quotations_for_case(case_id: int, db: Session = Depends(get_db)):
    return db.query(models.MotorQuotation).filter(
        models.MotorQuotation.insurance_case_id == case_id
    ).all()


# ------------------------------------------------------------
# POLICIES
# ------------------------------------------------------------

@router.post("/motor/policies", response_model=schemas.MotorPolicyOut)
def create_policy(policy: schemas.MotorPolicyCreate, db: Session = Depends(get_db)):
    quotation = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.id == policy.quotation_id
    ).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    db_policy = models.MotorPolicy(**policy.model_dump())
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)

    return db_policy


@router.get("/motor/policies", response_model=list[schemas.MotorPolicyOut])
def list_policies(db: Session = Depends(get_db)):
    return db.query(models.MotorPolicy).all()


@router.get("/motor/policies/{policy_id}", response_model=schemas.MotorPolicyOut)
def get_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.id == policy_id
    ).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return db_policy


@router.delete("/motor/policies/{policy_id}", response_model=schemas.DeletedMotorPolicyOut)
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    db_policy = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.id == policy_id
    ).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # No claims/renewals implemented yet, so nothing downstream depends on a
    # policy — unlike policyholders, no blocking condition is needed here.
    snapshot = schemas.MotorPolicyOut.model_validate(db_policy).model_dump(mode="json")
    archived = models.DeletedMotorPolicy(original_id=db_policy.id, data=snapshot)
    db.add(archived)

    db.delete(db_policy)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-motor-policies", response_model=list[schemas.DeletedMotorPolicyOut])
def list_deleted_motor_policies(db: Session = Depends(get_db)):
    return db.query(models.DeletedMotorPolicy).order_by(
        models.DeletedMotorPolicy.deleted_at.desc()
    ).all()