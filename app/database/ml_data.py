"""ML veri görüntüsü için ürün, sayfa, tur, sonuç ve Cimri satırlarını yalnız okur.

Bütün tablolar tek REPEATABLE READ, READ ONLY işlemde okunur: hepsi aynı anın
kaydıdır, okuma sırasında biten bir tur görüntüyü bölemez. Süren tur varken
okunmaz; görüntü yarım tur içermesin.
"""

from dataclasses import dataclass

import psycopg

from app.database.migrate import MigrationError, applied, pending
from app.database.read import _read_transaction, _rows

# Yalnız ML'in kullandığı alanlar; satıcı adı, adres ve hata metni görüntüye girmez.
_QUERIES = {
    "products": (
        "SELECT product_id, product_key, brand, model, storage_gb, active"
        " FROM products ORDER BY product_id"
    ),
    "platforms": "SELECT key, active FROM platforms ORDER BY key",
    "listings": (
        "SELECT listing_id, product_id, platform, active"
        " FROM listings ORDER BY listing_id"
    ),
    "collection_runs": (
        'SELECT run_id, "trigger", status, started_at, finished_at, planned_count'
        " FROM collection_runs ORDER BY run_id"
    ),
    "listing_checks": (
        "SELECT run_id, listing_id, product_id, checked_at, outcome, current_price"
        " FROM listing_checks ORDER BY run_id, listing_id"
    ),
    "market_history": (
        "SELECT product_id, source, source_product_id, day, price_kurus, captured_at"
        " FROM market_history ORDER BY product_id, source, day"
    ),
}


class MlDataError(Exception):
    """Görüntü alınamaz: bağlantı okuma hesabı değil veya şema kodla uyuşmuyor."""


class MlDataBusy(Exception):
    """Toplama turu sürüyor."""


@dataclass(frozen=True)
class MlData:
    schema_version: int
    tables: dict[str, list[dict]]


def read_ml_data(conn: psycopg.Connection) -> MlData:
    with _read_transaction(conn):
        # Okuma hesabının varsayılanı salt okunurdur (scripts/api_okuma_rolu.sql);
        # yazan hesapla alınmış görüntü olmasın.
        if conn.execute("SHOW default_transaction_read_only").fetchone()[0] != "on":
            raise MlDataError(
                "Bağlantı okuma hesabı değil; API_DATABASE_URL fiyat_takip_api "
                "hesabını göstermeli."
            )
        try:
            waiting = pending(conn)
        except MigrationError as exc:
            raise MlDataError(f"Şema kodla uyuşmuyor: {exc}") from None
        if waiting:
            raise MlDataError(
                "Bekleyen migration var: "
                + ", ".join(migration.file_name for migration in waiting)
            )
        running = conn.execute(
            "SELECT run_id FROM collection_runs WHERE status = 'running'"
        ).fetchone()
        if running:
            raise MlDataBusy(
                f"Tur {running[0]} sürüyor; tur bitince yeniden çalıştırın."
            )
        tables = {name: _rows(conn, query) for name, query in _QUERIES.items()}
        return MlData(applied(conn)[-1][0], tables)
