from pathlib import Path
from pydantic_settings import BaseSettings

# Look for .env in the backend dir, then in the project root (one level up)
_backend_dir = Path(__file__).resolve().parent.parent   # backend/
_root_dir = _backend_dir.parent                          # project root

# pydantic-settings accepts a list; first file wins for a given key
_env_files = [str(_backend_dir / ".env"), str(_root_dir / ".env")]


class Settings(BaseSettings):
    linkedin_email: str = ""
    linkedin_password: str = ""
    anthropic_api_key: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/linkedin_mailbox.db"
    # Hour (0-23, UTC) to run the daily unanswered-message scan
    daily_scan_hour: int = 8
    daily_scan_minute: int = 0
    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:3000,http://frontend:3000"

    model_config = {
        "env_file": _env_files,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
