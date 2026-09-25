from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.security import get_current_user
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Claims"],
    dependencies=[Depends(get_current_user)],
)


def loss_period_error(date_of_loss, policy):
    # Only enforced when all three dates are known; bounds are inclusive.
    # Shared with the claims importer (import_claims.py), which bypasses this router.
    if date_of_loss is None or policy.period_from is None or policy.period_to is None:
        return None
    if policy.period_from <= date_of_loss <= policy.period_to:
        return None
    return (f"Date of loss {date_of_loss} is outside the policy's coverage period "
            f"({policy.period_from} to {policy.period_to}).")


def check_loss_within_period(date_of_loss, policy):
    error = loss_period_error(date_of_loss, policy)
    if error:
        raise HTTPException(status_code=400, detail=error)


# ------------------------------------------------------------
# MOTOR CLAIMS
# ------------------------------------------------------------

def get_motor_policy_or_404(db: Session, policy_id: int):
    policy = db.query(models.MotorPolicy).filter(
        models.MotorPolicy.id == policy_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


def get_motor_claim_or_404(db: Session, claim_id: int):
    claim = db.query(models.MotorClaim).filter(
        models.MotorClaim.id == claim_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/motor/claims", response_model=schemas.MotorClaimOut)
def create_motor_claim(claim: schemas.MotorClaimCreate, db: Session = Depends(get_db)):
    policy = get_motor_policy_or_404(db, claim.motor_policy_id)
    check_loss_within_period(claim.date_of_loss, policy)

    db_claim = models.MotorClaim(**claim.model_dump())
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return db_claim


@router.get("/motor/claims", response_model=list[schemas.MotorClaimOut])
def list_motor_claims(
    motor_policy_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.MotorClaim)
    if motor_policy_id is not None:
        query = query.filter(models.MotorClaim.motor_policy_id == motor_policy_id)
    return query.all()


@router.get("/motor/claims/{claim_id}", response_model=schemas.MotorClaimOut)
def get_motor_claim(claim_id: int, db: Session = Depends(get_db)):
    return get_motor_claim_or_404(db, claim_id)


@router.patch("/motor/claims/{claim_id}", response_model=schemas.MotorClaimOut)
def update_motor_claim(
    claim_id: int,
    claim: schemas.MotorClaimUpdate,
    db: Session = Depends(get_db),
):
    db_claim = get_motor_claim_or_404(db, claim_id)

    # Unsent fields are left untouched; fields sent as null are cleared.
    changes = claim.model_dump(exclude_unset=True)
    if "motor_policy_id" in changes and changes["motor_policy_id"] is None:
        raise HTTPException(status_code=400, detail="motor_policy_id cannot be empty")

    policy = get_motor_policy_or_404(db, changes.get("motor_policy_id", db_claim.motor_policy_id))
    check_loss_within_period(changes.get("date_of_loss", db_claim.date_of_loss), policy)

    for field, value in changes.items():
        setattr(db_claim, field, value)
    db.commit()
    db.refresh(db_claim)

    return db_claim


@router.delete("/motor/claims/{claim_id}", response_model=schemas.DeletedMotorClaimOut)
def delete_motor_claim(claim_id: int, db: Session = Depends(get_db)):
    db_claim = get_motor_claim_or_404(db, claim_id)

    # Nothing depends on a claim, so no blocking condition is needed here.
    snapshot = schemas.MotorClaimOut.model_validate(db_claim).model_dump(mode="json")
    archived = models.DeletedMotorClaim(original_id=db_claim.id, data=snapshot)
    db.add(archived)

    db.delete(db_claim)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-motor-claims", response_model=list[schemas.DeletedMotorClaimOut])
def list_deleted_motor_claims(db: Session = Depends(get_db)):
    return db.query(models.DeletedMotorClaim).order_by(
        models.DeletedMotorClaim.deleted_at.desc()
    ).all()


# ------------------------------------------------------------
# FIRE/PROPERTY CLAIMS
# ------------------------------------------------------------

def get_fire_property_policy_or_404(db: Session, policy_id: int):
    policy = db.query(models.FirePropertyPolicy).filter(
        models.FirePropertyPolicy.id == policy_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


def get_fire_property_claim_or_404(db: Session, claim_id: int):
    claim = db.query(models.FirePropertyClaim).filter(
        models.FirePropertyClaim.id == claim_id
    ).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("/fire-property/claims", response_model=schemas.FirePropertyClaimOut)
def create_fire_property_claim(claim: schemas.FirePropertyClaimCreate, db: Session = Depends(get_db)):
    policy = get_fire_property_policy_or_404(db, claim.fire_property_policy_id)
    check_loss_within_period(claim.date_of_loss, policy)

    db_claim = models.FirePropertyClaim(**claim.model_dump())
    db.add(db_claim)
    db.commit()
    db.refresh(db_claim)

    return db_claim


@router.get("/fire-property/claims", response_model=list[schemas.FirePropertyClaimOut])
def list_fire_property_claims(
    fire_property_policy_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(models.FirePropertyClaim)
    if fire_property_policy_id is not None:
        query = query.filter(models.FirePropertyClaim.fire_property_policy_id == fire_property_policy_id)
    return query.all()


@router.get("/fire-property/claims/{claim_id}", response_model=schemas.FirePropertyClaimOut)
def get_fire_property_claim(claim_id: int, db: Session = Depends(get_db)):
    return get_fire_property_claim_or_404(db, claim_id)


@router.patch("/fire-property/claims/{claim_id}", response_model=schemas.FirePropertyClaimOut)
def update_fire_property_claim(
    claim_id: int,
    claim: schemas.FirePropertyClaimUpdate,
    db: Session = Depends(get_db),
):
    db_claim = get_fire_property_claim_or_404(db, claim_id)

    # Unsent fields are left untouched; fields sent as null are cleared.
    changes = claim.model_dump(exclude_unset=True)
    if "fire_property_policy_id" in changes and changes["fire_property_policy_id"] is None:
        raise HTTPException(status_code=400, detail="fire_property_policy_id cannot be empty")

    policy = get_fire_property_policy_or_404(
        db, changes.get("fire_property_policy_id", db_claim.fire_property_policy_id)
    )
    check_loss_within_period(changes.get("date_of_loss", db_claim.date_of_loss), policy)

    for field, value in changes.items():
        setattr(db_claim, field, value)
    db.commit()
    db.refresh(db_claim)

    return db_claim


@router.delete("/fire-property/claims/{claim_id}", response_model=schemas.DeletedFirePropertyClaimOut)
def delete_fire_property_claim(claim_id: int, db: Session = Depends(get_db)):
    db_claim = get_fire_property_claim_or_404(db, claim_id)

    # Nothing depends on a claim, so no blocking condition is needed here.
    snapshot = schemas.FirePropertyClaimOut.model_validate(db_claim).model_dump(mode="json")
    archived = models.DeletedFirePropertyClaim(original_id=db_claim.id, data=snapshot)
    db.add(archived)

    db.delete(db_claim)
    db.commit()
    db.refresh(archived)

    return archived


@router.get("/deleted-fire-property-claims", response_model=list[schemas.DeletedFirePropertyClaimOut])
def list_deleted_fire_property_claims(db: Session = Depends(get_db)):
    return db.query(models.DeletedFirePropertyClaim).order_by(
        models.DeletedFirePropertyClaim.deleted_at.desc()
    ).all()
