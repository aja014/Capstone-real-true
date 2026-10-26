"""Forgot password with recovery codes, the recovery code in Settings, the Manager's Reset a
Password and the after-login account status. Codes and passwords appear only in the one response
that hands them out; they are never logged or written to account_events."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.security import (get_current_user, get_logged_in_user, hash_password, password_rule_error,
                          require_manager, verify_password)
from app.services import recovery
from app.services.attempt_limiter import MESSAGE as TOO_MANY_ATTEMPTS, AttemptLimiter, client_ip, key_for
from app.services.user_service import get_user_by_username

router = APIRouter(prefix="", tags=["Account recovery"])

INVALID_RESET_MESSAGE = "Invalid username or recovery code"
WRONG_PASSWORD_MESSAGE = "Current password is incorrect."
WRONG_CODE_MESSAGE = "Current recovery code is incorrect."

forgot_limiter = AttemptLimiter()       # POST /auth/forgot-password
code_change_limiter = AttemptLimiter()  # POST /users/me/recovery-code


def _too_many():
    return HTTPException(status_code=429, detail=TOO_MANY_ATTEMPTS,
                         headers={"Retry-After": str(forgot_limiter.lock_seconds)})


@router.post("/auth/forgot-password", response_model=schemas.NewRecoveryCode)
def forgot_password(body: schemas.ForgotPassword, request: Request, db: Session = Depends(get_db)):
    """Public. Right username + code: the password changes, the used code is replaced by a new one
    (returned once) and any temporary-password flag is cleared. Any wrong part: the same 400."""
    key = key_for(request, body.username)
    if forgot_limiter.is_locked(key):
        raise _too_many()

    rule_error = password_rule_error(body.new_password)
    if rule_error:
        raise HTTPException(status_code=400, detail=rule_error)

    user = get_user_by_username(db, body.username)
    # verify_code runs one bcrypt check even for an unknown user (same answer time).
    if not recovery.verify_code(body.recovery_code, user.recovery_code_hash if user else None) or not user:
        forgot_limiter.record_failure(key)
        raise HTTPException(status_code=400, detail=INVALID_RESET_MESSAGE)
    forgot_limiter.reset(key)

    user.password = hash_password(body.new_password)
    user.must_change_password = False
    new_code = recovery.set_new_code(user)  # one-time use: the code just used stops working
    recovery.record_event(db, user, recovery.CODE_USED_RESET, user.username, client_ip(request))
    db.commit()
    return {"recovery_code": new_code}


@router.get("/users/me/account-status", response_model=schemas.AccountStatus)
def account_status(db: Session = Depends(get_db), current_user=Depends(get_logged_in_user)):
    """Read after every login: the forced password change, the "Not you?" notice (the latest unseen
    one) and whether the account has a recovery code. Allowed while a password change is required."""
    notice = recovery.unseen_notice(db, current_user)
    return {
        "must_change_password": bool(current_user.must_change_password),
        "has_recovery_code": current_user.recovery_code_hash is not None,
        "notice": notice,
    }


@router.post("/users/me/account-status/seen")
def notice_seen(body: schemas.NoticeSeen, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """The notice was shown: it and every older unseen notice of this user are marked seen."""
    (db.query(models.AccountEvent)
     .filter(models.AccountEvent.user_id == current_user.id,
             models.AccountEvent.id <= body.id,
             models.AccountEvent.event.in_(recovery.NOTICE_EVENTS),
             models.AccountEvent.seen.is_(False))
     .update({models.AccountEvent.seen: True}, synchronize_session=False))
    db.commit()
    return {"message": "Notice marked as seen."}


@router.get("/users/me/recovery-code", response_model=schemas.RecoveryCodeStatus)
def recovery_code_status(current_user=Depends(get_current_user)):
    return {"has_code": current_user.recovery_code_hash is not None,
            "set_at": current_user.recovery_code_set_at}


@router.post("/users/me/recovery-code", response_model=schemas.NewRecoveryCode)
def change_recovery_code(body: schemas.RecoveryCodeChange, request: Request, db: Session = Depends(get_db),
                         current_user=Depends(get_current_user)):
    """The first code needs only the current password; replacing a code needs the current password
    AND the current code, so a stolen password alone cannot take over the account's code.
    400 (not 401) for wrong answers: the frontend logs out on any 401."""
    key = key_for(request, current_user.username)
    if code_change_limiter.is_locked(key):
        raise _too_many()

    if not verify_password(body.current_password, current_user.password):
        code_change_limiter.record_failure(key)
        raise HTTPException(status_code=400, detail=WRONG_PASSWORD_MESSAGE)

    had_code = current_user.recovery_code_hash is not None
    if had_code and not recovery.verify_code(body.current_code, current_user.recovery_code_hash):
        code_change_limiter.record_failure(key)
        raise HTTPException(status_code=400, detail=WRONG_CODE_MESSAGE)
    code_change_limiter.reset(key)

    new_code = recovery.set_new_code(current_user)
    recovery.record_event(db, current_user, recovery.CODE_CHANGED if had_code else recovery.CODE_CREATED,
                          current_user.username, client_ip(request))
    db.commit()
    return {"recovery_code": new_code}


@router.get("/users/staff", response_model=list[schemas.StaffAccount])
def list_staff(db: Session = Depends(get_db), manager=Depends(require_manager)):
    """Admin & Finance accounts only (never a Manager): the Reset a Password list."""
    return db.query(models.User).filter(models.User.role == "admin").order_by(models.User.username).all()


@router.post("/users/{user_id}/reset-password", response_model=schemas.PasswordResetOut)
def reset_password(user_id: int, request: Request, db: Session = Depends(get_db),
                   manager=Depends(require_manager)):
    """Manager only: a temporary password and a new recovery code for an Admin & Finance account,
    both returned once. The user must set a new password at the next login."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admin & Finance accounts can be reset here.")

    temporary_password = recovery.temporary_password()
    user.password = hash_password(temporary_password)
    user.must_change_password = True
    new_code = recovery.set_new_code(user)
    recovery.record_event(db, user, recovery.MANAGER_RESET, manager.username, client_ip(request))
    db.commit()
    return {"username": user.username, "temporary_password": temporary_password, "recovery_code": new_code}
