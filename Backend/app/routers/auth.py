from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.security import verify_password
from Backend.app.services.user_service import get_user_by_username


from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Authentication"]
)


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

    return {
        "message": "Login successful",
        "role": db_user.role
    }