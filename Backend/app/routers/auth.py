from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.security import verify_password, create_access_token, DUMMY_PASSWORD_HASH
from app.services import login_limiter
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
    key = login_limiter.key_for(request, user.username)
    if login_limiter.is_locked(key):
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
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )
    login_limiter.reset(key)

    access_token = create_access_token(
        data={
            "sub": db_user.username,
            "role": db_user.role
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": db_user.role
    }