"""Failed-attempt limit, reusable: `max_failures` failures for one client IP + username within
`window_seconds` lock that pair for `lock_seconds`; a success clears it. In memory, so it resets on
restart (one process). Used by Forgot password and the recovery code change.

client_ip() is login_limiter.client_ip(): the same TRUSTED_PROXY_HOPS / CLIENT_IP_SOURCE rule as the
login, so users behind Render's proxy don't all share one IP and one lock. Unset = the connection's
address (the laptop behaviour). account_events.ip_address uses it too."""
import threading
import time

from app.services import login_limiter

MESSAGE = "Too many attempts. Please try again in 5 minutes."


def client_ip(request):
    return login_limiter.client_ip(request)


def key_for(request, username):
    return client_ip(request), (username or "").strip().lower()  # usernames are case-insensitive


class AttemptLimiter:
    def __init__(self, max_failures=5, window_seconds=300, lock_seconds=300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lock_seconds = lock_seconds
        self._lock = threading.Lock()
        self._failures = {}      # key -> failure times inside the window
        self._locked_until = {}  # key -> time the lock ends
        self._now = time.monotonic

    def is_locked(self, key):
        with self._lock:
            until = self._locked_until.get(key)
            if until is not None and until <= self._now():
                del self._locked_until[key]
                until = None
            return until is not None

    def record_failure(self, key):
        with self._lock:
            now = self._now()
            recent = [t for t in self._failures.get(key, []) if now - t < self.window_seconds] + [now]
            if len(recent) >= self.max_failures:
                self._locked_until[key] = now + self.lock_seconds
                self._failures.pop(key, None)
            else:
                self._failures[key] = recent
            if len(self._failures) > 10_000:  # keep memory bounded: forget pairs with no recent failure
                for k in [k for k, ts in self._failures.items() if now - ts[-1] >= self.window_seconds]:
                    del self._failures[k]

    def reset(self, key):
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)

    def clear(self):
        """Tests only."""
        with self._lock:
            self._failures.clear()
            self._locked_until.clear()
