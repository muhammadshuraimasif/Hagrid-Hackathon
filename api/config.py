import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    ENVIRONMENT: str = "development"
    IS_PROTOTYPE: bool = True
    # On Vercel the filesystem is read-only except /tmp, so the SQLite fallback lives there.
    DATABASE_URL: str = (
        "sqlite+aiosqlite:////tmp/amaanat_demo.db" if os.environ.get("VERCEL") else "sqlite+aiosqlite:///./demo.db"
    )
    UPLOAD_DIR: str = "/tmp/amaanat_uploads" if os.environ.get("VERCEL") else "./uploads"
    # Run the mock NADRA/Raast/Telco rails inside the API process (no separate mocks server needed).
    MOCKS_INPROCESS: bool = False
    JWT_SECRET: str = "amaanat-super-secure-jwt-secret-key-for-development-mode-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RATE_LIMIT_PER_MINUTE: int = 120
    PROTOTYPE_WARNING: str = "PROTOTYPE ONLY - Synthetic data only - Hagrid's Hackathon '26"
    DECISION_TOKEN_SECRET: str = "amaanat-capability-decision-token-secret-2026"
    SCAM_HMAC_SECRET: Optional[str] = None
    MOCK_SERVICES_URL: str = "http://127.0.0.1:8001"
    MOCKS_BASE_URL: Optional[str] = None
    NADRA_SERVICE_URL: Optional[str] = None
    RAAST_SERVICE_URL: Optional[str] = None
    SMS_SERVICE_URL: Optional[str] = None
    DEMO_HOLD_SECONDS: int = 60
    CORS_ORIGINS: str = "*"
    CIRCUIT_BREAKER_FAIL_MAX: int = 3
    CIRCUIT_BREAKER_RESET_TIMEOUT: float = 2.0
    GEMINI_API_KEY: Optional[str] = None
    TESSERACT_CMD: Optional[str] = "tesseract"

    @property
    def effective_mock_services_url(self) -> str:
        return self.MOCKS_BASE_URL or self.MOCK_SERVICES_URL

    @property
    def effective_scam_hmac_secret(self) -> str:
        return self.SCAM_HMAC_SECRET or self.DECISION_TOKEN_SECRET

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS or self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def validate_production_secrets(self) -> None:
        """Fail startup with a clear error if a secret is missing in production mode instead of using a default."""
        is_prod = self.ENVIRONMENT.lower() in ("production", "prod")
        if not is_prod:
            return

        if os.environ.get("TESTING"):
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: TESTING environment variable must be unset in production mode."
            )

        insecure_defaults = [
            "amaanat-super-secure-jwt-secret-key-for-development-mode-2026",
            "amaanat-capability-decision-token-secret-2026",
            "default",
            "secret",
            "",
        ]

        if not self.JWT_SECRET or self.JWT_SECRET in insecure_defaults:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: JWT_SECRET environment variable is missing or set to insecure default in production mode."
            )

        if not self.DECISION_TOKEN_SECRET or self.DECISION_TOKEN_SECRET in insecure_defaults:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: DECISION_TOKEN_SECRET environment variable is missing or set to insecure default in production mode."
            )

        if not self.effective_scam_hmac_secret or self.effective_scam_hmac_secret in insecure_defaults:
            raise RuntimeError(
                "CRITICAL CONFIGURATION ERROR: SCAM_HMAC_SECRET (or DECISION_TOKEN_SECRET) environment variable is missing or set to insecure default in production mode."
            )

settings = Settings()
