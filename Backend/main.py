import bcrypt
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app import models, schemas
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException # for getting users
from app.routers import auth, users

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # ✅ Added 5173
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first() # just for commit


    
app.include_router(auth.router)
app.include_router(users.router)