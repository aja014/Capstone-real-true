from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.config import settings
from app.security import hash_password, password_rule_error, token_for_user, verify_password
from app.services.user_service import get_user_by_username
from app.security import get_current_user, get_logged_in_user

from app.database import get_db
from app import models, schemas
from app.services import recovery
from app.services.attempt_limiter import client_ip

router = APIRouter(
    prefix="",
    tags=["Users"]
)


@router.post("/users", response_model=schemas.UserCreated)
def create_user( user: schemas.UserCreate, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user.role != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only managers can create admin accounts."
        )

    username = user.username.strip()  # "X " and "X" are the same name
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")

    rule_error = password_rule_error(user.password, username)
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
    # The first recovery code, shown once on the Account Created screen for the Manager to hand over.
    recovery_code = recovery.set_new_code(db_user)

    db.add(db_user)
    try:
        db.flush()  # db_user.id for the event
        recovery.record_event(db, db_user, recovery.CODE_CREATED, current_user.username, client_ip(request))
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
        "user": db_user,
        "recovery_code": recovery_code
    }


# get_logged_in_user: also works while a temporary password must be changed (that is how it's changed).
@router.post("/users/me/password")
def change_own_password(body: schemas.PasswordChange, request: Request, db: Session = Depends(get_db), current_user = Depends(get_logged_in_user)):
    # 400, not 401, for a wrong current password: the frontend logs out on any 401.
    if not verify_password(body.current_password, current_user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")

    rule_error = password_rule_error(body.new_password, current_user.username)
    if rule_error:
        raise HTTPException(status_code=400, detail=rule_error)

    if verify_password(body.new_password, current_user.password):
        raise HTTPException(
            status_code=400,
            detail="New password must be different from the current password."
        )

    if current_user.must_change_password:  # the temporary password from a Manager reset is now replaced
        current_user.must_change_password = False
        recovery.record_event(db, current_user, recovery.TEMP_PASSWORD_CHANGED,
                              current_user.username, client_ip(request))

    current_user.password = hash_password(body.new_password)
    db.commit()

    result = {"message": "Password changed."}
    if settings.SESSION_ENDS_ON_PASSWORD_CHANGE:
        # Every older token now fails (new hash); the user who changed it stays logged in.
        result["access_token"] = token_for_user(current_user)
    return result
