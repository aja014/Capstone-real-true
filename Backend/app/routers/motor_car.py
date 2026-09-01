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


@router.delete("/motor/vehicles/{vehicle_id}", response_model=schemas.DeletedVehicleOut)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    db_vehicle = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id
    ).first()
    if not db_vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    # Unlike policies (nothing depends on them yet), motor_quotations.vehicle_id
    # is a required FK — deleting a vehicle out from under an existing
    # quotation would orphan it. Block rather than cascade, same as
    # policyholders blocking on insurance_cases.
    quotation_count = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.vehicle_id == vehicle_id
    ).count()
    if quotation_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: this vehicle has {quotation_count} motor quotation(s) on file. "
                   "Remove or reassign those first.",
        )

    snapshot = schemas.VehicleOut.model_validate(db_vehicle).model_dump(mode="json")
    archived = models.DeletedVehicle(original_id=db_vehicle.id, data=snapshot)
    db.add(archived)

    db.delete(db_vehicle)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-vehicles", response_model=list[schemas.DeletedVehicleOut])
def list_deleted_vehicles(db: Session = Depends(get_db)):
    return db.query(models.DeletedVehicle).order_by(models.DeletedVehicle.deleted_at.desc()).all()


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


@router.delete("/motor/quotations/{quotation_id}", response_model=schemas.DeletedMotorQuotationOut)
def delete_quotation(quotation_id: int, db: Session = Depends(get_db)):
    db_quotation = db.query(models.MotorQuotation).filter(
        models.MotorQuotation.id == quotation_id
    ).first()
    if not db_quotation:
        raise HTTPException(status_code=404, detail="Quotation not found")

    # motor_policies.quotation_id is a required FK — same blocking shape as
    # Vehicle blocking on motor_quotations.
    policy = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.quotation_id == quotation_id
    ).first()
    if policy:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: this quotation has a policy on file. "
                   "Remove or reassign it first.",
        )

    snapshot = schemas.MotorQuotationOut.model_validate(db_quotation).model_dump(mode="json")
    archived = models.DeletedMotorQuotation(original_id=db_quotation.id, data=snapshot)
    db.add(archived)

    db.delete(db_quotation)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-motor-quotations", response_model=list[schemas.DeletedMotorQuotationOut])
def list_deleted_motor_quotations(db: Session = Depends(get_db)):
    return db.query(models.DeletedMotorQuotation).order_by(
        models.DeletedMotorQuotation.deleted_at.desc()
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