import bcrypt
from datetime import datetime, timedelta
from app.config import settings
from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.user_service import get_user_by_username

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

PASSWORD_MIN_LENGTH = 8
PASSWORD_MIN_LETTERS = 2
PASSWORD_MAX_BYTES = 72  # bcrypt's limit; bcrypt 5 raises above it instead of truncating
PASSWORD_RULE_MESSAGE = "Password must be at least 8 characters and include at least 2 letters."
PASSWORD_TOO_LONG_MESSAGE = "Password must be at most 72 characters (accented characters count as 2)."


def password_rule_error(password: str) -> str | None:
    """None if `password` is acceptable as a NEW password, else the message to show.
    Checked only where a password is set, never at login, so existing passwords keep working."""
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return PASSWORD_TOO_LONG_MESSAGE
    letters = sum(1 for ch in password if "a" <= ch <= "z" or "A" <= ch <= "Z")
    if len(password) < PASSWORD_MIN_LENGTH or letters < PASSWORD_MIN_LETTERS:
        return PASSWORD_RULE_MESSAGE
    return None


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return False  # can't match any stored hash; bcrypt 5 would raise (raw 500)
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )
    
def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=60)

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )
        
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(token)

    username = payload.get("sub")

    if username is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = get_user_by_username(db, username)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user

def require_manager(current_user=Depends(get_current_user)):
    """Manager-only endpoints: 401 without a login (from get_current_user), 403 for any other role."""
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Manager access only.")
    return current_user
