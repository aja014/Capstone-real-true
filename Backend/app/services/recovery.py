"""Recovery codes: the one-time spare key that resets a forgotten password (FIREMAP accounts have
no email and the laptop copy runs offline). A code is 12 characters from ALPHABET, shown as
XXXX-XXXX-XXXX, and stored only as a bcrypt hash. Codes and passwords are never logged, never
written to account_events and never returned except once, to the person who gets the new code."""
import secrets
from datetime import datetime, timezone

import bcrypt

from app import models
from app.config import settings
from app.security import password_rule_error

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
CODE_LENGTH = 12
TEMP_PASSWORD_LENGTH = 12
TEMP_PASSWORD_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"

CODE_CREATED = "code_created"
CODE_CHANGED = "code_changed"
CODE_USED_RESET = "code_used_reset"
MANAGER_RESET = "manager_reset"
TEMP_PASSWORD_CHANGED = "temp_password_changed"
# Events that show the "Your recovery code was changed ... Not you?" notice at the next login.
NOTICE_EVENTS = (CODE_CHANGED, CODE_USED_RESET, MANAGER_RESET)


def new_code() -> str:
    raw = "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def normalize_code(code: str | None) -> str:
    """What is compared: no dashes, no spaces, upper case ("abcd efgh-jkmn" = "ABCDEFGHJKMN")."""
    return "".join((code or "").split()).replace("-", "").upper()


def hash_code(code: str) -> str:
    return bcrypt.hashpw(normalize_code(code).encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# Checked when there is no stored code (unknown user, or no code yet), so that answer takes as long
# as a wrong code.
_DUMMY_CODE_HASH = hash_code("ZZZZ-ZZZZ-ZZZZ")


def verify_code(code: str | None, code_hash: str | None) -> bool:
    normalized = normalize_code(code)
    well_formed = len(normalized) == CODE_LENGTH and all(ch in ALPHABET for ch in normalized)
    target = code_hash if code_hash and well_formed else _DUMMY_CODE_HASH
    match = bcrypt.checkpw((normalized if well_formed else "X").encode("utf-8"), target.encode("utf-8"))
    return match and well_formed and bool(code_hash)


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def set_new_code(user) -> str:
    """Gives `user` a new code (the old one stops working) and returns it; the caller commits."""
    code = new_code()
    user.recovery_code_hash = hash_code(code)
    user.recovery_code_set_at = _utcnow()
    return code


def temporary_password() -> str:
    """Random letters and digits that already pass the password rule (at least 12 characters, or
    the minimum length if a hosted copy sets it higher)."""
    length = max(TEMP_PASSWORD_LENGTH, getattr(settings, "PASSWORD_MIN_LENGTH", 8))
    while True:
        password = "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(length))
        if password_rule_error(password) is None:
            return password


def record_event(db, user, event, actor_username, ip_address):
    """Adds one account_events row; the caller commits it together with the change."""
    db.add(models.AccountEvent(
        occurred_at=_utcnow(), user_id=user.id, event=event,
        actor_username=actor_username, ip_address=ip_address, seen=False,
    ))


def unseen_notice(db, user):
    """The latest notice event the user has not been shown yet, or None."""
    return (db.query(models.AccountEvent)
            .filter(models.AccountEvent.user_id == user.id,
                    models.AccountEvent.event.in_(NOTICE_EVENTS),
                    models.AccountEvent.seen.is_(False))
            .order_by(models.AccountEvent.id.desc())
            .first())
