"""Platform anahtarından sabit paket içindeki Scraper sınıfını yükler."""

import importlib
import inspect
import re

from app.scraper.base import BaseScraper
from app.scraper.http import FetchError


def create_scraper(platform: str, hosts: list[str], runtime) -> BaseScraper:
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
