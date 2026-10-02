from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.security import hash_password, password_rule_error, verify_password
from app.services.user_service import get_user_by_username
from app.security import get_current_user

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Users"]
)


@router.post("/users", response_model=schemas.UserCreated)
def create_user( user: schemas.UserCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user.role != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only managers can create admin accounts."
        )

    username = user.username.strip()  # "X " and "X" are the same name
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    rule_error = password_rule_error(user.password)
    if rule_error:
        raise HTTPException(status_code=400, detail=rule_error)

    existing_user = get_user_by_username(db, username)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    hashed_password = hash_password(user.password) 

    db_user = models.User(
        username=username,
        password=hashed_password,
        role="admin"
    )

    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        # The username unique constraint is the source of truth; the
        # get_user_by_username check above can still race with a concurrent
        # request, so fall back to the same clean error instead of a raw 500.
        db.rollback()
        raise HTTPException(status_code=400, detail="User already exists")
    db.refresh(db_user)

    return {
        "message": "User created!",
        "user": db_user
    }


@router.post("/users/me/password")
def change_own_password(body: schemas.PasswordChange, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # 400, not 401, for a wrong current password: the frontend logs out on any 401.
    if not verify_password(body.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    rule_error = password_rule_error(body.new_password)
    if rule_error:
        raise HTTPException(status_code=400, detail=rule_error)

    if verify_password(body.new_password, current_user.password):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password."
        )

    current_user.password = hash_password(body.new_password)
    db.commit()

    return {"message": "Password changed."}
