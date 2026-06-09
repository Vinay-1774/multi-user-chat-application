from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from pathlib import Path

class Settings(BaseSettings):
    HISTORY_KEY: str = "chat:history"   # default so .env is optional for basic runs
    HISTORY_LIMIT: int = 10
    DB_URL: str = "sqlite+aiosqlite:///./chat.db"
    REDIS_URL: str = "redis://localhost:6379"
    SERVER_URL: str = "ws://localhost:8000/ws"
    IS_PRODUCTION: bool = False

    model_config = ConfigDict(
        env_file=str(Path(__file__).resolve().parent / ".env"),
        extra="ignore",
    )

settings = Settings()