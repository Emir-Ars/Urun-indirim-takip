"""Siteye giden bütün girişlerin paylaştığı kilit.

İstekler arası 3 sn bekleme süreç içinde tutulur; iki süreç aynı anda çalışırsa
aynı siteye iki kat hızla gidilir. Fiyat turu, keşif ve canlı kontrol araçları
bu kilidi alır: biri sürerken diğeri başlamaz, beklemez. Süreç çökse bile
işletim sistemi kilidi bırakır.
"""

from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock, Timeout

from app.settings import Settings


class ScrapeBusy(Exception):
    """Başka bir fiyat turu, keşif veya canlı kontrol sürüyor."""


@contextmanager
def scrape_lock(path: Path | None = None):
    path = Path(path or Settings().lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(path), timeout=0)
    try:
        lock.acquire()
    except Timeout as exc:
        raise ScrapeBusy(
            f"Başka bir fiyat turu, keşif veya canlı kontrol sürüyor (kilit: {path})"
        ) from exc
    try:
        yield
    finally:
        lock.release()
