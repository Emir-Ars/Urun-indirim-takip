"""Doğrulanmış Cimri geçmişini ürün başına atomik ve tekrarlanabilir aktarır."""

from dataclasses import dataclass
from datetime import timedelta
from zoneinfo import ZoneInfo

import psycopg

from app.database.migrate import MigrationError, pending
from app.database.runs import try_lock_runs, unlock_runs
from app.market_history.importer import (
    CapturedProduct,
    HistoryImportError,
    ImportBatch,
    product_identity,
)

ISTANBUL = ZoneInfo("Europe/Istanbul")


class HistoryImportBusy(RuntimeError):
    """Aynı veritabanında tur veya aktarım sürüyor."""


@dataclass(frozen=True)
class ProductImportResult:
    product_key: str
    added: int
    unchanged: int
    conflicts: tuple[str, ...] = ()
    partial_days: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImportResult:
    products: tuple[ProductImportResult, ...]
    skipped: int

    @property
    def partial(self):
        return bool(self.skipped or any(product.conflicts for product in self.products))


class _ProductConflict(Exception):
    def __init__(self, conflicts, partial_days):
        self.conflicts = conflicts
        self.partial_days = partial_days


def _prepare(conn, batch):
    if pending(conn):
        raise MigrationError("Şema güncel değil; önce `migrate` çalıştırın")
    rows = conn.execute(
        "SELECT product_id, product_key, brand, model, storage_gb"
        " FROM products WHERE product_id = ANY(%s)",
        ([product.product_id for product in batch.products],),
    ).fetchall()
    current = {row[0]: row for row in rows}
    for product in batch.products:
        if current.get(product.product_id) != product_identity(product):
            raise HistoryImportError(
                f"{product.product_key}: katalog ve veritabanı ürün kimliği "
                "uyuşmuyor; hiçbir ürün yazılmadı"
            )


def _existing(conn, product):
    rows = conn.execute(
        "SELECT day, price_kurus, source_product_id, captured_at FROM market_history"
        " WHERE product_id = %s AND source = 'cimri' AND day = ANY(%s)",
        (product.product.product_id, [point.day for point in product.points]),
    ).fetchall()
    return {row[0]: row[1:] for row in rows}


def _partial_day(day, captured_at):
    # Alım günü Cimri'de henüz kapanmamıştır; o günün değeri gün içinde değişir.
    return day == captured_at.astimezone(ISTANBUL).date()


def _compare(product, existing):
    conflicts, partial_days = [], []
    source = product.mapping.cimri_product_id
    for point in product.points:
        if point.day not in existing:
            continue
        old_price, old_source, old_captured_at = existing[point.day]
        if (old_price, old_source) == (point.price_kurus, source):
            continue
        if old_source == source and (
            _partial_day(point.day, old_captured_at)
            or _partial_day(point.day, product.captured_at)
        ):
            partial_days.append(
                f"{point.day}: eski fiyat={old_price}, yeni fiyat={point.price_kurus} "
                "kuruş"
            )
            continue
        conflicts.append(
            f"{point.day}: eski fiyat={old_price}, yeni fiyat={point.price_kurus} "
            f"kuruş; eski Cimri={old_source}, yeni Cimri={source}"
        )
    return tuple(conflicts), tuple(partial_days)


def _insert(conn, product):
    values = [
        (
            product.product.product_id,
            "cimri",
            product.mapping.cimri_product_id,
            product.mapping.url,
            point.day,
            point.price_kurus,
            product.captured_at,
            product.page_sha256,
            product.api_sha256,
            product.report_sha256,
        )
        for point in product.points
    ]
    placeholders = ", ".join(["(" + ", ".join(["%s"] * 10) + ")"] * len(values))
    rows = conn.execute(
        "INSERT INTO market_history (product_id, source, source_product_id,"
        " source_url, day, price_kurus, captured_at, page_sha256, api_sha256,"
        " report_sha256) VALUES "
        + placeholders
        + " ON CONFLICT (product_id, source, day) DO NOTHING RETURNING day",
        [value for row in values for value in row],
    ).fetchall()
    return len(rows)


def _import_product(conn, product: CapturedProduct) -> ProductImportResult:
    key = product.product.product_key
    committing = False
    try:
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            conflicts, partial_days = _compare(product, _existing(conn, product))
            if conflicts:
                raise _ProductConflict(conflicts, partial_days)
            added = _insert(conn, product)
            # DO NOTHING eşzamanlı farklı fiyatı da atlayabilir; yeni görünümle
            # karşılaştırmadan commit edersek ürünün bir kısmını yazmış oluruz.
            existing = _existing(conn, product)
            conflicts, partial_days = _compare(product, existing)
            if conflicts:
                raise _ProductConflict(conflicts, partial_days)
            if len(existing) != len(product.points):
                raise HistoryImportError(f"{key}: yazılan günler doğrulanamadı")
            committing = True
    except _ProductConflict as exc:
        return ProductImportResult(key, 0, 0, exc.conflicts, exc.partial_days)
    except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
        if committing:
            raise HistoryImportError(
                f"{key}: kayıt kesinleşirken bağlantı hatası; son ürünün sonucu "
                "belirsiz. Aynı klasörü yeniden çalıştırarak doğrulayın; "
                "tekrar aktarım kayıt çoğaltmaz"
            ) from exc
        raise
    unchanged = len(product.points) - added - len(partial_days)
    return ProductImportResult(key, added, unchanged, (), partial_days)


def _day_ranges(days):
    spans = []
    start = end = days[0]
    for day in days[1:]:
        if day == end + timedelta(days=1):
            end = day
        else:
            spans.append((start, end))
            start = end = day
    spans.append((start, end))
    return ", ".join(
        str(start) if start == end else f"{start}–{end}" for start, end in spans
    )


def _report_product(product, result, dry_run, out):
    if result.conflicts:
        out(f"{result.product_key}: çelişki; bu ürünün hiçbir yeni günü yazılmadı")
        for conflict in result.conflicts:
            out(f"  {conflict}")
    else:
        action = "eklenecek" if dry_run else "eklendi"
        out(
            f"{result.product_key}: {result.added} {action}, "
            f"{result.unchanged} aynı"
        )
    if result.partial_days:
        out(f"  Yarım gün farkı (eski kayıt {'korunacak' if dry_run else 'korundu'}):")
        for difference in result.partial_days:
            out(f"    {difference}")
    summary = product.summary
    out(
        f"  {len(product.points)} nokta, {product.points[0].day}–"
        f"{product.points[-1].day}; eksik fiyat: "
        f"{summary['missing_price_count']}; tablo eşleşmesi: "
        f"{summary['table_compared_rows']}"
    )
    if summary["table_comparison"] == "unavailable":
        out("  Tabloyla karşılaştırma yapılamadı.")
    elif summary["latest_price"]["table_comparison"] == "unavailable":
        out("  Son gün için tablo karşılaştırması yapılamadı.")
    if product.uncompared_days:
        out(
            f"  Tabloyla karşılaştırılamayan {len(product.uncompared_days)} gün: "
            f"{_day_ranges(product.uncompared_days)}"
        )


def _process(conn, batch, dry_run, out):
    _prepare(conn, batch)
    for key, reason in batch.skipped:
        out(f"{key}: atlandı; {reason}")
    results = []
    for product in batch.verified:
        if dry_run:
            existing = _existing(conn, product)
            conflicts, partial_days = _compare(product, existing)
            result = ProductImportResult(
                product.product.product_key,
                0 if conflicts else len(product.points) - len(existing),
                0 if conflicts else len(existing) - len(partial_days),
                conflicts,
                partial_days,
            )
        else:
            result = _import_product(conn, product)
        results.append(result)
        _report_product(product, result, dry_run, out)
    return ImportResult(tuple(results), len(batch.skipped))


def import_history(
    conn: psycopg.Connection, batch: ImportBatch, *, dry_run=False, out=print
) -> ImportResult:
    if not try_lock_runs(conn):
        raise HistoryImportBusy("Veritabanında başka bir tur veya aktarım sürüyor")
    try:
        if dry_run:
            with conn.transaction():
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                return _process(conn, batch, True, out)
        return _process(conn, batch, False, out)
    finally:
        if not conn.closed:
            unlock_runs(conn)
