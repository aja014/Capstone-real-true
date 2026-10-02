from sqlalchemy import func
from sqlalchemy.orm import Session
from app import models


def get_user_by_username(db: Session, username: str):
    # Spaces around a name never count, and capitals don't either (the column's collation
    # is case-insensitive). TRIM on the column also finds an old name saved with spaces.
    return db.query(models.User).filter(
        func.trim(models.User.username) == (username or "").strip()
    ).first()
