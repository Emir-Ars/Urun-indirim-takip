"""Bir fiyat toplama turu.

Akış: şema kontrolü → veritabanı tur kilidi → yarım kalmış turları kapatma →
katalog eşitleme → turu ve planlanan sayfaları açma → her sayfayı mevcut
scraper'la okuyup sonucunu hemen yazma → `network` hatası alan sayfaları bir kez
yeniden okuma → turu kapatma. Ortak dosya kilidini çağıran taraf (komut satırı)
tutar.
"""

import traceback
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

import psycopg

from app.contracts import (
    Catalog,
    Platform,
    PriceObservation,
    ProductListing,
    utc_now,
)
from app.database import runs
from app.database.catalog_sync import read_catalog, sync_catalog
from app.database.migrate import pending
from app.scraper.factory import create_scraper
from app.scraper.http import FetchError
from app.settings import Runtime

MAX_ERROR_MESSAGE = 500
# Tur sonu ikinci okumada ardışık bu kadar sayfa yine `network` verirse geçiş
# durur: bağlantı hâlâ yoktur ve kalan sayfaları denemek (3 sn aralıkla ~17 dk)
# boşa gider.
NETWORK_RETRY_STOP = 5


class CollectionError(Exception):
    """Tur başlatılamadı."""


class RunInProgress(Exception):
    """Aynı veritabanında başka bir fiyat turu sürüyor."""


@dataclass(frozen=True)
class RunReport:
    run_id: int
    planned: int
    summary: runs.RunSummary
    closed_stale: list[int]

    @property
    def errors(self) -> int:
        return self.summary.outcomes.get("error", 0)


def plan_listings(catalog: Catalog, prefix: str = "") -> list[ProductListing]:
    """Etkin sayfa + etkin ürün + etkin platform; isteğe bağlı product_key ön eki."""
    products = {product.product_id: product for product in catalog.products}
    platforms = {platform.key: platform for platform in catalog.platforms}
    planned = []
    for item in catalog.listings:
        product = products[item.product_id]
        if not (item.active and product.active and platforms[item.platform].active):
            continue
        if not product.product_key.startswith(prefix):
            continue
        planned.append(
            ProductListing(
                **item.model_dump(),
                product_name=product.name,
                model=product.model,
                storage_gb=product.storage_gb,
            )
        )
    return planned


def _clean(text: str | None) -> str | None:
    # PostgreSQL metin alanı NUL (\x00) karakterini kabul etmez.
    return text.replace("\x00", "") if text else text


def to_result(observation: PriceObservation) -> runs.CheckResult:
    if observation.stock_status == "Tükendi":
        # Satın alınamayan sayfanın fiyatı "en ucuz" hesabına karışmasın diye
        # Tükendi sonucunda fiyat ve satıcı yazılmaz.
        return runs.CheckResult(
            outcome="sold_out",
            checked_at=observation.timestamp,
            stock_status="Tükendi",
        )
    return runs.CheckResult(
        outcome="offer",
        checked_at=observation.timestamp,
        current_price=observation.current_price,
        original_price=observation.original_price,
        seller_name=_clean(observation.seller_name),
        seller_rating=observation.seller_rating,
        seller_rating_scale=observation.seller_rating_scale,
        stock_status=observation.stock_status,
    )


def error_result(code: str, message: str) -> runs.CheckResult:
    return runs.CheckResult(
        outcome="error",
        checked_at=utc_now(),
        error_code=code,
        error_message=_clean(message)[:MAX_ERROR_MESSAGE] or None,
    )


def check_listing(
    listing: ProductListing, platform: Platform, runtime: Runtime, create: Callable
) -> runs.CheckResult:
    """Tek sayfayı okur; ne olursa olsun bir sonuç döndürür (Ctrl+C hariç)."""
    scraper = None
    try:
        scraper = create(platform.key, platform.hosts, runtime)
        observation = scraper.fetch(listing)
        if (observation.listing_id, observation.product_id) != (
            listing.listing_id,
            listing.product_id,
        ):
            return error_result("validation", "Gözlem başka bir sayfaya ait")
        return to_result(observation)
    except FetchError as exc:
        return error_result(exc.code, str(exc))
    # Gerçek scraper'larda doğrulama hataları (Pydantic dahil) BaseScraper.fetch
    # içinde 'parse' FetchError'a çevrilir ve factory yalnız BaseScraper kabul
    # eder; bu dal yalnız enjekte edilen `create`'e (testler) karşı savunmadır.
    except ValueError as exc:
        return error_result("validation", str(exc))
    except Exception as exc:  # Tek bir sayfa bütün turu düşürmesin.
        traceback.print_exc()
        return error_result("unexpected", f"{type(exc).__name__}: {exc}")
    finally:
        if scraper is not None:
            try:
                scraper.close()
            except Exception:  # Kapatma hatası sayfanın sonucunu kaybettirmesin.
                traceback.print_exc()


def record(
    conn: psycopg.Connection, run_id: int, listing_id: str, result: runs.CheckResult
) -> runs.CheckResult:
    """Sonucu yazar. Veritabanı değeri reddederse (ör. sütuna sığmayan fiyat)
    sayfa `storage` hatası olarak yazılır ve tur sürer."""
    try:
        runs.record_result(conn, run_id, listing_id, result)
        return result
    except (psycopg.DataError, psycopg.IntegrityError) as exc:
        stored = error_result("storage", f"Veritabanı sonucu reddetti: {exc}")
        runs.record_result(conn, run_id, listing_id, stored)
        return stored


def collect(
    conn: psycopg.Connection,
    catalog_path: Path,
    runtime: Runtime,
    *,
    trigger: str = "manual",
    prefix: str = "",
    create: Callable | None = None,
    out: Callable[[str], None] = print,
) -> RunReport:
    if pending(conn):
        raise CollectionError(
            "Şema güncel değil; önce `python -m app.database migrate` çalıştırın"
        )
    if not runs.try_lock_runs(conn):
        raise RunInProgress("Veritabanında başka bir fiyat turu sürüyor")
    try:
        return _collect(
            conn, catalog_path, runtime, trigger, prefix, create or create_scraper, out
        )
    finally:
        with suppress(psycopg.Error):
            runs.unlock_runs(conn)


def _collect(conn, catalog_path, runtime, trigger, prefix, create, out) -> RunReport:
    closed_stale = runs.close_stale_runs(conn)
    if closed_stale:
        out(f"Yarıda kalmış tur(lar) kapatıldı: {closed_stale}")
    catalog, digest = read_catalog(catalog_path)
    sync_catalog(conn, catalog)
    planned = plan_listings(catalog, prefix)
    if not planned:
        raise CollectionError(f"Planlanacak etkin sayfa yok (ön ek: {prefix!r})")
    platforms = {platform.key: platform for platform in catalog.platforms}
    run_id = runs.start_run(
        conn,
        trigger=trigger,
        catalog_sha256=digest,
        listings=[(item.listing_id, item.product_id) for item in planned],
        note=f"--prefix {prefix}" if prefix else None,
    )
    try:
        out(f"Tur {run_id} başladı: {len(planned)} sayfa (katalog {digest[:12]}…)")
        network_failed = []
        for index, listing in enumerate(planned, 1):
            result = check_listing(
                listing, platforms[listing.platform], runtime, create
            )
            result = record(conn, run_id, listing.listing_id, result)
            out(f"[{index}/{len(planned)}] {listing.listing_id}  {describe(result)}")
            if result.outcome == "error" and result.error_code == "network":
                network_failed.append(listing)
        retry_note = (
            retry_network_errors(
                conn, run_id, network_failed, platforms, runtime, create, out
            )
            if network_failed
            else None
        )
        runs.finish_run(conn, run_id, "completed", note=retry_note)
    except BaseException as exc:
        # Ctrl+C veya veritabanı hatası: yazılanlar kalır, bakılmayanlar sonuçsuz.
        # Bağlantı kopmuşsa kapatma da başarısız olur; asıl hata gölgelenmesin
        # diye yutulur, 'running' kalan turu sonraki tur 'interrupted' yapar.
        with suppress(psycopg.Error, RuntimeError):
            runs.finish_run(
                conn, run_id, "interrupted", note=f"Durduruldu: {type(exc).__name__}"
            )
        raise
    return RunReport(run_id, len(planned), runs.run_summary(conn, run_id), closed_stale)


def retry_network_errors(
    conn: psycopg.Connection,
    run_id: int,
    failed: list[ProductListing],
    platforms: dict[str, Platform],
    runtime: Runtime,
    create: Callable,
    out: Callable[[str], None],
) -> str:
    """Tur sonunda yalnız `network` hatası alan sayfaları bir kez yeniden okur.

    Bağlantı tur ortasında koptuysa ve tur bitmeden döndüyse (28 Eylül: 47 sayfa,
    4 Ekim: 109 sayfa) bu sayfalar okunabilir durumdadır. Yeni sonuç hata satırının
    üzerine yazılır; sayfa başına tek satır kuralı korunur. İkinci okuma da
    `network` verirse yeni bilgi yoktur ve ilk satır olduğu gibi kalır. `blocked`
    ve diğer hatalar yeniden denenmez (zaten bu listeye girmezler). Ardışık
    NETWORK_RETRY_STOP sayfa yine `network` verirse bağlantı hâlâ yok demektir ve
    kalan sayfalar denenmez. Tur notuna yazılacak sayıları döndürür.

    Ctrl+C ve veritabanı bağlantı hatası çağıranda ele alınır (tur `interrupted`).
    """
    out(f"Tur sonu: network hatası alan {len(failed)} sayfa yeniden okunuyor")
    fixed = still_failing = consecutive = 0
    for index, listing in enumerate(failed, 1):
        result = check_listing(listing, platforms[listing.platform], runtime, create)
        label = f"[tekrar {index}/{len(failed)}] {listing.listing_id}"
        if result.outcome == "error" and result.error_code == "network":
            still_failing += 1
            consecutive += 1
            out(f"{label}  {describe(result)}")
            if consecutive >= NETWORK_RETRY_STOP:
                break
            continue
        consecutive = 0
        try:
            runs.rewrite_network_result(conn, run_id, listing.listing_id, result)
        except (psycopg.DataError, psycopg.IntegrityError) as exc:
            # İlk satır (network hatası) kalır; tur sürer.
            still_failing += 1
            out(f"{label}  veritabanı yeni sonucu reddetti, ilk hata kaldı: {exc}")
            continue
        out(f"{label}  {describe(result)}")
        if result.outcome == "error":
            still_failing += 1
        else:
            fixed += 1
    skipped = len(failed) - fixed - still_failing
    parts = [f"{fixed} düzeldi", f"{still_failing} hâlâ hatalı"]
    if skipped:
        out(
            f"Ardışık {NETWORK_RETRY_STOP} network hatası: bağlantı hâlâ yok; "
            f"{skipped} sayfa yeniden denenmedi"
        )
        parts.append(
            f"{skipped} denenmedi "
            f"(ardışık {NETWORK_RETRY_STOP} network hatasında durdu)"
        )
    note = f"network hatası alan {len(failed)} sayfa, ikinci okuma: " + ", ".join(parts)
    out(note)
    return note


def describe(result: runs.CheckResult) -> str:
    if result.outcome == "offer":
        return (
            f"fiyat {format_try(result.current_price)} · {result.seller_name}"
            f" ({result.stock_status})"
        )
    if result.outcome == "sold_out":
        return "Tükendi"
    return f"HATA {result.error_code}: {(result.error_message or '')[:100]}"


def format_try(value: int | None) -> str:
    if value is None:
        return "-"
    lira, kurus = divmod(value, 100)
    return f"{lira:,}".replace(",", ".") + f",{kurus:02d} TL"
