"""Hosting security controls (IAS2): response headers, upload size limit, safe row errors."""
import logging

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import PlainTextResponse

from app.config import settings

logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
FILE_TOO_LARGE = "File is too large (max 10 MB)."
DATABASE_ROW_ERROR = "could not be saved (database error)"  # the page shows "Row N: " before it


def security_headers():
    headers = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
               "Referrer-Policy": "no-referrer"}
    if settings.APP_ENV == "production":  # HTTPS only there; local http must not be pinned
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


class SecurityHeadersMiddleware:
    """Adds security_headers() to every response, 4xx and CORS preflights included."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        extra = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in security_headers().items()]

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + extra
            await send(message)

        await self.app(scope, receive, send_with_headers)


async def server_error(request, exc):
    """Unhandled exceptions are answered outside every middleware, so the 500 adds the headers itself."""
    return PlainTextResponse("Internal Server Error", status_code=500, headers=security_headers())


def check_upload_size(file):
    """413 for a file over 10 MB; single-file and folder uploads both pass through here."""
    size = file.size
    if size is None:
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=FILE_TOO_LARGE)


def row_error_text(exc, source_row=None):
    """A database exception becomes a plain message (the SQL goes to the server log only);
    validation messages such as the date error are shown unchanged."""
    if isinstance(exc, SQLAlchemyError):
        logger.error("Import row %s: database error", source_row, exc_info=exc)
        return DATABASE_ROW_ERROR
    return str(exc)
