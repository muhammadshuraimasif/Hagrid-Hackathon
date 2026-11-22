"""Tests for Deployment Configuration, Production Secret Validation, and Environment Handling."""
import os
import pytest
from api.config import Settings

def test_production_mode_fails_if_testing_env_set(monkeypatch):
    """Production mode strictly forbids TESTING env var."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("JWT_SECRET", "custom-prod-jwt-secret-xyz-123456789")
    monkeypatch.setenv("DECISION_TOKEN_SECRET", "custom-prod-decision-secret-xyz-123456789")

    s = Settings()
    with pytest.raises(RuntimeError, match="TESTING environment variable must be unset in production mode"):
        s.validate_production_secrets()

def test_production_mode_fails_if_jwt_secret_insecure_default(monkeypatch):
    """Production mode strictly requires non-default JWT_SECRET."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("JWT_SECRET", "amaanat-super-secure-jwt-secret-key-for-development-mode-2026")
    monkeypatch.setenv("DECISION_TOKEN_SECRET", "custom-prod-decision-secret-xyz-123456789")

    s = Settings()
    with pytest.raises(RuntimeError, match="JWT_SECRET environment variable is missing or set to insecure default"):
        s.validate_production_secrets()

def test_production_mode_fails_if_decision_secret_insecure_default(monkeypatch):
    """Production mode strictly requires non-default DECISION_TOKEN_SECRET."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("JWT_SECRET", "custom-prod-jwt-secret-xyz-123456789")
    monkeypatch.setenv("DECISION_TOKEN_SECRET", "amaanat-capability-decision-token-secret-2026")

    s = Settings()
    with pytest.raises(RuntimeError, match="DECISION_TOKEN_SECRET environment variable is missing or set to insecure default"):
        s.validate_production_secrets()

def test_production_mode_succeeds_with_strong_secrets(monkeypatch):
    """Production validation succeeds when strong unique secrets are supplied."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("JWT_SECRET", "super-strong-unique-production-jwt-secret-2026")
    monkeypatch.setenv("DECISION_TOKEN_SECRET", "super-strong-unique-production-decision-secret-2026")
    monkeypatch.setenv("SCAM_HMAC_SECRET", "super-strong-unique-production-scam-hmac-secret-2026")

    s = Settings()
    # Must not raise
    s.validate_production_secrets()

def test_config_cors_and_mocks_base_url_handling(monkeypatch):
    """Parses comma-separated CORS_ORIGINS and prioritizes MOCKS_BASE_URL."""
    monkeypatch.setenv("CORS_ORIGINS", "https://amaanat.vercel.app, https://preview.amaanat.vercel.app")
    monkeypatch.setenv("MOCKS_BASE_URL", "https://mocks.up.railway.app")
    monkeypatch.setenv("DEMO_HOLD_SECONDS", "120")

    s = Settings()
    assert s.cors_origins_list == ["https://amaanat.vercel.app", "https://preview.amaanat.vercel.app"]
    assert s.effective_mock_services_url == "https://mocks.up.railway.app"
    assert s.DEMO_HOLD_SECONDS == 120
