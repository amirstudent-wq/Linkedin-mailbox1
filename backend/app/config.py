from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    linkedin_email: str = ""
    linkedin_password: str = ""
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/linkedin_mailbox.db"
    # Hour (0-23) to run the daily unanswered-message scan
    daily_scan_hour: int = 8
    daily_scan_minute: int = 0
    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
