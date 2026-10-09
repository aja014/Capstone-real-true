from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.config import settings
from app.security import verify_password, token_for_user, DUMMY_PASSWORD_HASH
from app.services import login_audit, login_limiter
from app.services.user_service import get_user_by_username


from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Authentication"]
)

# login endpoint
@router.post("/login")
def login(user: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    login_audit.debug_client_ip(request)
    key = login_limiter.key_for(request, user.username)
    if login_limiter.is_locked(key):
        login_audit.record(db, request, user.username, login_audit.LOCKED)
        raise HTTPException(
            status_code=429,
            detail=login_limiter.MESSAGE,
            headers={"Retry-After": str(login_limiter.LOCK_SECONDS)}
        )

    db_user = get_user_by_username(db, user.username)

    # An unknown username still runs one bcrypt check (same response time as a wrong password).
    password_ok = verify_password(user.password, db_user.password if db_user else DUMMY_PASSWORD_HASH)
    if not db_user or not password_ok:
        login_limiter.record_failure(key)
        login_audit.record(db, request, user.username,
                           login_audit.WRONG_PASSWORD if db_user else login_audit.UNKNOWN_USER, db_user)
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    login_limiter.reset(key)

    previous = login_audit.previous_success(db, db_user)  # read before this login is recorded
    login_audit.record(db, request, user.username, login_audit.SUCCESS, db_user)

    access_token = token_for_user(db_user)

    body = {
        "access_token": access_token,
        "token_type": "bearer",
        "role": db_user.role
    }
    if settings.LOGIN_AUDIT:
        body["last_login"] = login_audit.last_login_out(previous)  # None on the first login
    return body