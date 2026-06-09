from pydantic_settings import BaseSettings 
from pydantic import ConfigDict
from pathlib import Path

class Settings(BaseSettings):
    HISTORY_KEY: str
    HISTORY_LIMIT: int = 10
    DB_URL:str
    REDIS_URL:str
    SERVER_URL:str
    model_config = ConfigDict(env_file=str(Path(__file__).resolve().parent / ".env"))
    IS_PRODUCTION:bool = False
settings = Settings()
