from __future__ import annotations

from app.core.config import Settings


def test_csv_environment_settings(monkeypatch: object) -> None:
    monkeypatch.setenv("ALLOWED_TABLES", "customers, orders")
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example.com, https://admin.example.com")
    settings = Settings(_env_file=None)
    assert settings.allowed_tables == ("customers", "orders")
    assert settings.cors_origins == ("https://app.example.com", "https://admin.example.com")
