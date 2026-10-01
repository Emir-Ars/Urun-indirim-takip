"""Ayar dosyalarını (config/runtime.json, config/discovery.json) doğrulayarak okur.

Katalog, keşif ve çalışma ayarı dosyalarının, ortak tarama kilidinin, log ve keşif
raporu klasörlerinin yollarını tutar; her yol ortam değişkeniyle değiştirilebilir
(Settings.__init__).
"""

import os
from pathlib import Path

from pydantic import Field

from app.contracts import Contract, DiscoveryConfig


class Runtime(Contract):
    """Scraper ve keşfin HTTP davranışı (config/runtime.json)."""

    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    request_interval_seconds: float = Field(default=3.0, ge=0)
    # İlk istek dahil toplam deneme; yalnız ağ hatası ve 5xx tekrar denenir,
    # aradaki bekleme 1 sn, sonra 2 sn (app/scraper/http.py).
    request_attempts: int = Field(default=2, ge=1, le=3)


class Settings:
    def __init__(self):
        self.catalog_path = Path(os.getenv("CATALOG_PATH", "config/catalog.json"))
        self.discovery_path = Path(os.getenv("DISCOVERY_PATH", "config/discovery.json"))
        self.runtime_path = Path(os.getenv("RUNTIME_PATH", "config/runtime.json"))
        # Siteye giden bütün girişlerin paylaştığı kilit (app/scrape_lock.py).
        self.lock_path = Path(os.getenv("SCRAPE_LOCK_PATH", "data/scrape.lock"))
        # Zamanlanmış turların log dosyaları (python -m app.collection --scheduled).
        self.log_dir = Path(os.getenv("LOG_DIR", "data/logs"))
        # Zamanlanmış keşfin tarihli raporları (python -m app.discovery --scheduled).
        self.discovery_report_dir = Path(
            os.getenv("DISCOVERY_REPORT_DIR", "data/discovery")
        )

    # utf-8-sig: elle düzenlenen dosyada Windows düzenleyicilerinin koyduğu BOM da
    # okunur; BOM'suz dosyada sonuç aynıdır.
    def runtime(self) -> Runtime:
        return Runtime.model_validate_json(
            self.runtime_path.read_text(encoding="utf-8-sig")
        )

    def discovery(self) -> DiscoveryConfig:
        return DiscoveryConfig.model_validate_json(
            self.discovery_path.read_text(encoding="utf-8-sig")
        )
