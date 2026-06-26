from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import bcrypt

from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="",
    tags=["Users"]
)


def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()


@router.post("/users")
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):

    existing_user = get_user_by_username(db, user.username)

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User already exists"
        )

    password_bytes = user.password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

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