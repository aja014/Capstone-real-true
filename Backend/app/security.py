import bcrypt
import hashlib
import hmac
from datetime import datetime, timedelta
from app.config import settings
from jose import JWTError, jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import common_passwords
from app.services.user_service import get_user_by_username

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

PASSWORD_MIN_LETTERS = 2
PASSWORD_MAX_BYTES = 72  # bcrypt's limit; bcrypt 5 raises above it instead of truncating
# The message at the default minimum (8); password_rule_message() follows PASSWORD_MIN_LENGTH.
PASSWORD_RULE_MESSAGE = "Password must be at least 8 characters and include at least 2 letters."
PASSWORD_TOO_LONG_MESSAGE = "Password must be at most 72 characters (accented characters count as 2)."
PASSWORD_COMMON_MESSAGE = "This password is too common. Please choose a less predictable one."
PASSWORD_HAS_USERNAME_MESSAGE = "Password must not contain your username."
SESSION_ENDED_MESSAGE = "Your password was changed. Please log in again."


def password_rule_message() -> str:
    return (f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters "
            "and include at least 2 letters.")


def _contains_username(password: str, username: str | None) -> bool:
    """Case-insensitive: the whole username without spaces (3+ characters), or any one word of
    it with 4+ characters ("Aaron James" blocks aaronjames, aaron and james)."""
    name = (username or "").strip().casefold()
    parts = {name.replace(" ", "")} | {w for w in name.split() if len(w) >= 4}
    pw = password.casefold()
    return any(len(p) >= 3 and p in pw for p in parts)


def password_rule_error(password: str, username: str | None = None) -> str | None:
    """None if `password` is acceptable as a NEW password, else the message to show.
    Checked only where a password is set, never at login, so existing passwords keep working."""
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return PASSWORD_TOO_LONG_MESSAGE
    letters = sum(1 for ch in password if "a" <= ch <= "z" or "A" <= ch <= "Z")
    if len(password) < settings.PASSWORD_MIN_LENGTH or letters < PASSWORD_MIN_LETTERS:
        return password_rule_message()
    if settings.PASSWORD_BLOCK_COMMON:
        if _contains_username(password, username):
            return PASSWORD_HAS_USERNAME_MESSAGE
        if common_passwords.is_common(password):
            return PASSWORD_COMMON_MESSAGE
    return None


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)

    return hashed_password.decode("utf-8")


# Checked when the username doesn't exist, so that answer takes as long as a wrong password.
DUMMY_PASSWORD_HASH = hash_password("zz-timing-equaliser-not-a-real-password")


def verify_password(password: str, hashed_password: str) -> bool:
    if len(password.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return False  # can't match any stored hash; bcrypt 5 would raise (raw 500)
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )
    
def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(minutes=settings.TOKEN_MINUTES)

    to_encode.update({
        "exp": expire
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def password_fingerprint(password_hash: str) -> str:
    """Ties a token to the password it was issued under. An HMAC with SECRET_KEY, so the readable
    token payload reveals nothing about the hash and can't be forged; any change of the hash (Change
    Password or an SQL reset) makes every older token fail."""
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), b"firemap-session:" + password_hash.encode("utf-8"),
                    hashlib.sha256).hexdigest()[:32]


def token_for_user(user) -> str:
    """The login token for `user`: sub + role, plus the password fingerprint when
    SESSION_ENDS_ON_PASSWORD_CHANGE is on."""
    data = {"sub": user.username, "role": user.role}
    if settings.SESSION_ENDS_ON_PASSWORD_CHANGE:
        data["pwf"] = password_fingerprint(user.password)
    return create_access_token(data)


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
        
def get_logged_in_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    """The token's user, even while a temporary password must still be changed. Only
    POST /users/me/password and GET /users/me/account-status use this directly."""
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

    if settings.SESSION_ENDS_ON_PASSWORD_CHANGE:
        claim = payload.get("pwf")
        if not isinstance(claim, str) or not hmac.compare_digest(claim, password_fingerprint(user.password or "")):
            raise HTTPException(status_code=401, detail=SESSION_ENDED_MESSAGE)

    return user


PASSWORD_CHANGE_REQUIRED_MESSAGE = "Password change required"


def get_current_user(user=Depends(get_logged_in_user)):
    """Every other route: 403 (not 401, which logs the frontend out) until a temporary password
    from a Manager reset has been changed."""
    if user.must_change_password:
        raise HTTPException(status_code=403, detail=PASSWORD_CHANGE_REQUIRED_MESSAGE)
    return user

def require_manager(current_user=Depends(get_current_user)):
    """Manager-only endpoints: 401 without a login (from get_current_user), 403 for any other role."""
    if current_user.role != "manager":
        raise HTTPException(status_code=403, detail="Manager access only.")
    return current_user
