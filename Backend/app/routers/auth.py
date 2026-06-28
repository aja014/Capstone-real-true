from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.security import verify_password, create_access_token
from app.services.user_service import get_user_by_username


from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Authentication"]
)

# login endpoint
@router.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):

    db_user = get_user_by_username(db, user.username)

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    if not verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

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