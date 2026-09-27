"""Automatic retraining + prediction refresh. There is no "train" button:

  - after an upload that can add learning data (Surveys, Fire/Motor Quotations, Fire/Motor
    Policies, both Claims importers, a folder upload, or a Needs Review resolve), a FastAPI
    background task runs AFTER the response has been sent: every model is retrained if its
    training data changed (training.retrain_if_changed), then all predictions are rewritten;
  - at backend startup, a background thread trains only the models that have no active
    version yet, then rewrites the predictions.

Never raises: a refresh failure is logged and kept in `status`, and the upload that triggered
it has already succeeded. Requests that arrive while a refresh is running are coalesced into
ONE more run afterwards (not a queue).
"""
import datetime as dt
import logging
import threading

from fastapi import BackgroundTasks

from app.database import SessionLocal
from app.ml import predict, training

log = logging.getLogger(__name__)

_lock = threading.Lock()
_running = False
_pending = None  # reason of a run requested while one was running

# Process-local; shown by GET /ml/models. "running" stays True for the whole sequence,
# including a coalesced extra run, so a page polling it never stops between two runs.
status = {
    "running": False,
    "last_reason": None,
    "last_started_at": None,
    "last_finished_at": None,
    "last_retrained": [],
    "last_predictions": {},
    "last_error": None,
}


def run_refresh(db, reason, today=None, report_dir=None):
    """One refresh on `db`. reason "startup": only models with no active version are trained."""
    names = training.MODEL_NAMES
    if reason == "startup":
        names = [n for n in names if predict.active_model(db, n) is None]
    retrained = [n for n in names if training.retrain_if_changed(db, n, today, report_dir)[1]]
    counts = predict.refresh_predictions(db, today)
    return retrained, counts


def _run_once(reason, session_factory):
    status.update(last_reason=reason, last_started_at=dt.datetime.now(), last_error=None)
    db = None
    try:
        db = (session_factory or SessionLocal)()  # its own session: the request's is already closed
        retrained, counts = run_refresh(db, reason)
        status.update(last_retrained=retrained, last_predictions=counts)
        log.info("Model refresh (%s): retrained %s, predictions %s", reason, retrained or "none", counts)
    except Exception as exc:
        if db is not None:
            db.rollback()
        log.exception("Model refresh (%s) failed", reason)
        status["last_error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if db is not None:
            db.close()
        status["last_finished_at"] = dt.datetime.now()


def refresh_now(reason, session_factory=None):
    global _running, _pending
    with _lock:
        if _running:
            # "upload" also covers what "startup" would do, so it wins when both are waiting
            _pending = "upload" if "upload" in (_pending, reason) else reason
            return
        _running = True
        status["running"] = True
    try:
        while True:
            _run_once(reason, session_factory)
            with _lock:
                # Checked and cleared under the same lock, so a request arriving right now
                # either becomes _pending (and runs next) or finds _running False.
                if _pending is None:
                    _running = False
                    status["running"] = False
                    return
                reason, _pending = _pending, None
    except BaseException:  # _run_once catches Exception; this is only e.g. KeyboardInterrupt
        with _lock:
            _running = False
            status["running"] = False
        raise


def schedule_model_refresh(background_tasks: BackgroundTasks):
    """Route dependency for the learning-data upload endpoints. The task only runs if the
    endpoint returns normally (an error response carries no background tasks)."""
    background_tasks.add_task(refresh_now, "upload")


def start_startup_refresh():
    threading.Thread(target=refresh_now, args=("startup",), name="ml-startup-refresh", daemon=True).start()
