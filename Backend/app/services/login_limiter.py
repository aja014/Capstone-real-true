"""Failed-login limit (IAS2): 5 failures for one client IP + username within 5 minutes lock that
pair for 5 minutes; a successful login clears it. In memory, so it resets on restart (one process)."""
import threading
import time

from app.config import settings

MAX_FAILURES = 5
WINDOW_SECONDS = 300
LOCK_SECONDS = 300
MESSAGE = "Too many failed login attempts. Please try again in 5 minutes."

_lock = threading.Lock()
_failures = {}      # key -> failure times inside the window
_locked_until = {}  # key -> time the lock ends
_now = time.monotonic


def client_ip(request):
    """Render's proxy APPENDS to X-Forwarded-For and keeps whatever the client sent, so only
    entries counted from the right are trustworthy: TRUSTED_PROXY_HOPS=1 takes the last one.
    0 (local default) ignores the header and uses the connection's address."""
    hops = settings.TRUSTED_PROXY_HOPS
    if hops > 0:
        forwarded = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.client.host if request.client else "unknown"


def key_for(request, username):
    return client_ip(request), (username or "").strip().lower()  # usernames are case-insensitive


def is_locked(key):
    with _lock:
        until = _locked_until.get(key)
        if until is not None and until <= _now():
            del _locked_until[key]
            until = None
        return until is not None


def record_failure(key):
    with _lock:
        now = _now()
        recent = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS] + [now]
        if len(recent) >= MAX_FAILURES:
            _locked_until[key] = now + LOCK_SECONDS
            _failures.pop(key, None)
        else:
            _failures[key] = recent
        if len(_failures) > 10_000:  # keep memory bounded: forget pairs with no recent failure
            for k in [k for k, ts in _failures.items() if now - ts[-1] >= WINDOW_SECONDS]:
                del _failures[k]


def reset(key):
    with _lock:
        _failures.pop(key, None)
        _locked_until.pop(key, None)


def clear():
    """Tests only."""
    with _lock:
        _failures.clear()
        _locked_until.clear()
