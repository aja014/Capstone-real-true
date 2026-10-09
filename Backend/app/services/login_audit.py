"""Login attempt log (IAS2), on when LOGIN_AUDIT=true: one server-log line per attempt plus a
login_events row (kept 90 days). The password is never passed in here, so it can't be logged.
A failure to write the row is logged and never blocks the login."""
import logging
import sys
from datetime import datetime, timedelta, timezone

from app import models
from app.config import settings
from app.services.login_limiter import client_ip

SUCCESS, WRONG_PASSWORD, UNKNOWN_USER, LOCKED = "success", "wrong_password", "unknown_user", "locked"
RETENTION_DAYS = 90

logger = logging.getLogger("firemap.login")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # uvicorn configures only its own loggers; without a handler INFO lines would never reach the
    # Render log. Still propagates, so pytest's caplog sees the lines too.
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    logger.addHandler(_handler)


def _utcnow():
    # Whole seconds: MySQL DATETIME would round the fraction, and the log line must show the stored time.
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def previous_success(db, user):
    """The user's most recent successful login before this one (call before record())."""
    if not settings.LOGIN_AUDIT:
        return None
    try:
        return (db.query(models.LoginEvent)
                .filter(models.LoginEvent.user_id == user.id, models.LoginEvent.result == SUCCESS)
                .order_by(models.LoginEvent.occurred_at.desc(), models.LoginEvent.id.desc())
                .first())
    except Exception:
        logger.exception("Login log: could not read the previous login")
        return None


def record(db, request, username, result, user=None):
    if not settings.LOGIN_AUDIT:
        return
    now = _utcnow()
    name = (username or "").strip()[:255]
    ip = client_ip(request)[:45]
    # %r quotes the username, so a typed newline can't fake a second log line.
    logger.info("login time=%sZ user=%r ip=%s result=%s", now.isoformat(timespec="seconds"), name, ip, result)
    try:
        with db.begin_nested():  # a failure undoes only the log write, nothing else of the request
            db.add(models.LoginEvent(occurred_at=now, user_id=user.id if user else None,
                                     username=name, ip_address=ip, result=result))
            db.query(models.LoginEvent).filter(
                models.LoginEvent.occurred_at < now - timedelta(days=RETENTION_DAYS)
            ).delete(synchronize_session=False)
        db.commit()
    except Exception:
        logger.exception("Login log: could not save the login event")


def last_login_out(event):
    """The "last_login" value of the login response: the previous success, or None."""
    if event is None:
        return None
    return {"at": event.occurred_at.isoformat(timespec="seconds") + "Z", "ip": event.ip_address}
