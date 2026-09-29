"""Platform anahtarından sabit paket içindeki Scraper sınıfını yükler."""

import importlib
import inspect
import re

from app.scraper.base import BaseScraper
from app.scraper.http import FetchError
from app.settings import Runtime


def create_scraper(platform: str, hosts: list[str], runtime: Runtime) -> BaseScraper:
    """Platform adaptörünü yükleyip kurar.

    Eklenti sözleşmesi: katalogdaki `Platform.key` (ör. "trendyol") →
    `app/scraper/<key>_scraper.py` modülündeki `Scraper` sınıfı; sınıf
    BaseScraper'ın soyut olmayan bir alt sınıfı olmalıdır. Yeni site kendi
    modülüyle eklenir, mevcut scraper'a koşul eklenmez. Anahtar deseni
    contracts.Key ile aynıdır; katalog dışından çağıranlara karşı (ör. "../x")
    burada yeniden denetlenir. Her türlü yükleme veya kurma hatası
    FetchError("plugin") olur; toplama turu bunu sayfa hatası olarak kaydeder.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]*", platform):
        raise FetchError("plugin", "Geçersiz platform anahtarı")
    try:
        module = importlib.import_module(f"app.scraper.{platform}_scraper")
        implementation = module.Scraper
        if (
            not inspect.isclass(implementation)
            or not issubclass(implementation, BaseScraper)
            or inspect.isabstract(implementation)
        ):
            raise TypeError("Scraper, BaseScraper sözleşmesini uygulamalı")
        return implementation(hosts, runtime)
    except Exception as exc:
        raise FetchError("plugin", f"{platform} adaptörü yüklenemedi: {exc}") from exc
