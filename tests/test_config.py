from __future__ import annotations

from app.core.config import Settings


def test_csv_environment_settings(monkeypatch: object) -> None:
    monkeypatch.setenv("ALLOWED_TABLES", "customers, orders")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://admin.example.com")
    settings = Settings(_env_file=None)
    assert settings.allowed_tables == ("customers", "orders")
    assert settings.cors_origins == ("https://app.example.com", "https://admin.example.com")


def test_blank_optional_environment_settings_become_none(monkeypatch: object) -> None:
    monkeypatch.setenv("DATABASE_SCHEMA", "")
    monkeypatch.setenv("ADAPTER_PATH", "   ")
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("HF_SPACE_TOKEN", "  ")
    settings = Settings(_env_file=None)
    assert settings.database_schema is None
    assert settings.adapter_path is None
    assert settings.api_key is None
    assert settings.hf_space_token is None
