from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.security import hash_password
from app.services.user_service import get_user_by_username
from app.security import get_current_user

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Users"]
)


@router.post("/users")
def create_user( user: schemas.UserCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    if current_user.role != "manager":
        raise HTTPException(
            status_code=403,
            detail="Only managers can create admin accounts."
        )

    existing_user = get_user_by_username(db, user.username)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    hashed_password = hash_password(user.password) 

    db_user = models.User(
        username=user.username,
        password=hashed_password,
        role="admin"
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "message": "User created!",
        "user": db_user
    }