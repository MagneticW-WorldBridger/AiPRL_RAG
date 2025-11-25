from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    auth_base_url: str = os.getenv("AUTH_BASE_URL", "http://localhost:8000")
    database_url: str = os.getenv("DATABASE_URL", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

