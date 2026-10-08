import bcrypt
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app import models, schemas
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException # for getting users
from app.routers import auth, users, policyholders, fire_property, motor_car, import_policyholders, import_fire_property, import_motor, import_vehicle, import_batch, stats, claims, import_claims, ml, public
from app.ml import jobs as ml_jobs
from app.config import settings
from app.http_security import SecurityHeadersMiddleware, server_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background thread: trains only models that have no active version yet, then
    # rewrites the predictions. Startup is not delayed (see app/ml/jobs.py).
    ml_jobs.start_startup_refresh()
    yield


app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last = outermost: the headers also go on CORS preflights and every 4xx.
app.add_middleware(SecurityHeadersMiddleware)
app.add_exception_handler(Exception, server_error)

Base.metadata.create_all(bind=engine)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first() # just for commit


    
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(policyholders.router)
app.include_router(fire_property.router) 
app.include_router(motor_car.router)
app.include_router(import_policyholders.router)
app.include_router(import_fire_property.router)
app.include_router(import_motor.router)
app.include_router(import_vehicle.router)
app.include_router(import_batch.router)
app.include_router(import_claims.router)
app.include_router(stats.router)
app.include_router(claims.router)
app.include_router(ml.router)
app.include_router(public.router)