import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _env_flag(name, default):
    """An on/off env variable: "true" (any case) = on, any other value = off, unset or blank = default."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() == "true"


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-this")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")

    # Hosting switches (IAS2, branch deploy-ias2). Unset = today's local behaviour.
    APP_ENV = os.getenv("APP_ENV", "local")
    CORS_ORIGINS = [o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()]
    DB_SSL_CA = os.getenv("DB_SSL_CA")  # path to the DB's CA certificate (Aiven); unset = no SSL
    DOCS_ENABLED = _env_flag("DOCS_ENABLED", True)
    # Off = no geocoding and no hazard shapefiles: the river-flood file alone needs ~280 MB, too
    # much for a 512 MB host. Records still save, with empty GIS fields ("not yet available").
    GIS_ENABLED = _env_flag("GIS_ENABLED", True)
    # How many proxies append to X-Forwarded-For in front of the app (Render: 1). 0 = ignore the
    # header (local). Used only to key the failed-login limit.
    TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS") or 0)

    # IAS2 round 2 (stolen-password controls). Unset = today's local behaviour.
    TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES") or 60)
    # On = a login token stops working as soon as its user's password changes (every device).
    SESSION_ENDS_ON_PASSWORD_CHANGE = _env_flag("SESSION_ENDS_ON_PASSWORD_CHANGE", False)
    # On = log every login attempt (server log + login_events table) and show "Last login".
    LOGIN_AUDIT = _env_flag("LOGIN_AUDIT", False)
    PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH") or 8)
    # On = new passwords may not be a common password or contain the username.
    PASSWORD_BLOCK_COMMON = _env_flag("PASSWORD_BLOCK_COMMON", False)

settings = Settings()

if settings.APP_ENV == "production" and not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY must be set when APP_ENV=production")
if not 8 <= settings.PASSWORD_MIN_LENGTH <= 64:
    raise RuntimeError("PASSWORD_MIN_LENGTH must be between 8 and 64")
if settings.TOKEN_MINUTES < 1:
    raise RuntimeError("TOKEN_MINUTES must be at least 1")