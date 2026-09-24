"""Config okuma sınırı; çalışma yolları ortam değişkenleriyle değiştirilebilir."""

import os
from pathlib import Path

from pydantic import Field

from app.contracts import Contract, DiscoveryConfig


class Runtime(Contract):
    """Scraper ve keşfin HTTP davranışı (config/runtime.json)."""

    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    request_interval_seconds: float = Field(default=3.0, ge=0)
    request_attempts: int = Field(default=2, ge=1, le=3)


class Settings:
    def __init__(self):
        self.catalog_path = Path(os.getenv("CATALOG_PATH", "config/catalog.json"))
        self.discovery_path = Path(os.getenv("DISCOVERY_PATH", "config/discovery.json"))
        self.runtime_path = Path(os.getenv("RUNTIME_PATH", "config/runtime.json"))

    def runtime(self) -> Runtime:
        return Runtime.model_validate_json(
            self.runtime_path.read_text(encoding="utf-8")
        )

    def discovery(self) -> DiscoveryConfig:
        return DiscoveryConfig.model_validate_json(
            self.discovery_path.read_text(encoding="utf-8")
        )
