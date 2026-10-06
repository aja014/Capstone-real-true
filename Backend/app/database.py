from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings  # ← This is correct now

# The hosted DB (Aiven) requires SSL; pre-ping replaces connections it closed while idle.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"ssl": {"ca": settings.DB_SSL_CA}} if settings.DB_SSL_CA else {},
    pool_pre_ping=settings.APP_ENV == "production",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # Note: autocommit not auto_commit
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()