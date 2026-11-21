from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    ENVIRONMENT: str = "development"
    IS_PROTOTYPE: bool = True
    DATABASE_URL: str = "sqlite+aiosqlite:///./test_amaanat.db"
    JWT_SECRET: str = "amaanat-super-secure-jwt-secret-key-for-development-mode-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMIT_PER_MINUTE: int = 120
    PROTOTYPE_WARNING: str = "PROTOTYPE ONLY - Synthetic data only - Hagrid's Hackathon '26"

settings = Settings()
