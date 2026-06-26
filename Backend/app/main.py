import bcrypt
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from app.database import engine, Base, get_db
from app import models, schemas
from passlib.context import CryptContext
from fastapi.middleware.cors import CORSMiddleware
from fastapi import HTTPException # for getting users

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
    return db.query(models.User).filter(models.User.username == username).first()

# Simple POST endpoint to save user
@app.post("/users")
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):

    # print(f"DEBUG: Password received from docs is: {user.password}")
    # print(f"DEBUG: Length of password is: {len(user.password)}")

    # hashed_password = pwd_context.hash(user.password)
    # print(f"DEBUG: Hashed password is: {hashed_password}")
    
    # ✅ Check if user already exists
    existing_user = get_user_by_username(db, user.username)
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="User with this fullname already exists"
        )

    # 1. Convert the plain text password string to bytes
    password_bytes = user.password.encode('utf-8')
    
    # 2. Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    
    # 3. Convert the resulting hash back to a string so it can be saved in MySQL
    hashed_password_string = hashed_password_bytes.decode('utf-8')
    
    password_bytes = user.password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    hashed_password_string = hashed_password_bytes.decode('utf-8')

    # Create new user using the new string hash
    db_user = models.User(
    username=user.username,
    password=hashed_password_string
    )
    
    # Save to database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {"message": "User created!", "user": db_user}