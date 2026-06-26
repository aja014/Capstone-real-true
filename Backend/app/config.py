import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")
    SECRET_KEY = os.getenv("SECRET_KEY", "fallback-secret-key-change-this")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")

settings = Settings()