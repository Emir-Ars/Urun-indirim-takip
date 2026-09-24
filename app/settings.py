"""Config okuma sınırı; çalışma yolları ortam değişkenleriyle değiştirilebilir."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator

from app.contracts import Contract, DiscoveryConfig


class Runtime(Contract):
    timezone: str = "Europe/Istanbul"
    collection_times: list[str] = Field(default_factory=lambda: ["06:00"], min_length=1)
    training_weekday: int = Field(default=6, ge=0, le=6)
    training_time: str = "07:00"
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    request_interval_seconds: float = Field(default=3.0, ge=0)
    request_attempts: int = Field(default=2, ge=1, le=3)
    forecast_horizon_days: int = Field(default=7, ge=1, le=30)
    discount_threshold: float = Field(default=0.05, gt=0, lt=1)
    history_days: int = Field(default=30, ge=30, le=365)
    stale_after_hours: float = Field(default=30.0, gt=0)
    api_rate_limit: str = "60/minute"

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        ZoneInfo(value)
        return value

    @field_validator("training_time")
    @classmethod
    def valid_time(cls, value):
        from datetime import time

        parsed = time.fromisoformat(value)
        if parsed.strftime("%H:%M") != value:
            raise ValueError("Saat HH:MM biçiminde olmalı")
        return value

    @field_validator("collection_times")
    @classmethod
    def valid_times(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Toplama saatleri benzersiz olmalı")
        return sorted(cls.valid_time(value) for value in values)

    @field_validator("api_rate_limit")
    @classmethod
    def valid_limit(cls, value):
        from limits import parse

        parse(value)
        return value

    def model_policy(self) -> dict:
        return {
            "timezone": self.timezone,
            "history_days": self.history_days,
            "forecast_horizon_days": self.forecast_horizon_days,
            "discount_threshold": self.discount_threshold,
        }


class Settings:
    def __init__(self):
        self.db_path = Path(os.getenv("DB_PATH", "data/prices.sqlite3")).resolve()
        self.artifact_dir = Path(os.getenv("ARTIFACT_DIR", "artifacts")).resolve()
        self.catalog_path = Path(os.getenv("CATALOG_PATH", "config/catalog.json"))
        self.discovery_path = Path(os.getenv("DISCOVERY_PATH", "config/discovery.json"))
        self.runtime_path = Path(os.getenv("RUNTIME_PATH", "config/runtime.json"))
        self.api_base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

    def runtime(self) -> Runtime:
        return Runtime.model_validate_json(
            self.runtime_path.read_text(encoding="utf-8")
        )

    def discovery(self) -> DiscoveryConfig:
        return DiscoveryConfig.model_validate_json(
            self.discovery_path.read_text(encoding="utf-8")
        )
