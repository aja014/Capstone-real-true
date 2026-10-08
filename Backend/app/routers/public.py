"""The only endpoints besides /login that need no login: uptime check and security.txt."""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Public"])

SECURITY_TXT = ("Contact: mailto:gaj@firemap.local\n"
                "Expires: 2027-10-08T00:00:00.000Z\n"
                "Preferred-Languages: en\n")


@router.api_route("/health", methods=["GET", "HEAD"], include_in_schema=False)
def health(db: Session = Depends(get_db)):
    """Touches the database (GET and HEAD alike) so UptimeRobot keeps both Render and Aiven
    awake. No details out."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check: database unavailable")
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}


@router.get("/.well-known/security.txt", response_class=PlainTextResponse, include_in_schema=False)
def security_txt():
    return SECURITY_TXT
