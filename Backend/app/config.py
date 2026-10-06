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

settings = Settings()

if settings.APP_ENV == "production" and not os.getenv("SECRET_KEY"):
    raise RuntimeError("SECRET_KEY must be set when APP_ENV=production")