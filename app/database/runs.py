"""Toplama turlarının veritabanı işlemleri: aç, sayfa sonucunu yaz, kapat."""

from dataclasses import dataclass, fields
from datetime import datetime

import psycopg
from psycopg import sql

# Veritabanı düzeyindeki tur kilidi. Dosya kilidi (app/scrape_lock.py) aynı
# bilgisayardaki süreçleri ayırır; bu kilit aynı veritabanını kullanan her
# süreci (ör. ileride Docker) ayırır. Bağlantı kapanınca kendiliğinden düşer.
# Advisory kilit numaraları veritabanı başına tek ad alanıdır: migrate.py'deki
# _LOCK_ID (2026_0928) ve testlerin kilidi (tests/conftest.py, 2026_0930) ile
# aynı olmamalı. Oturum kilidi yeniden girilebilir (reentrant): aynı bağlantı
# kilidi ikinci kez isterse yine alır; başka bir sürecin kilidi tuttuğunu
# sınamak için ayrı bağlantı gerekir.
_RUN_LOCK_ID = 2026_0929


@dataclass(frozen=True)
class CheckResult:
    """Bir sayfanın bu turdaki sonucu; alanlar listing_checks sütunlarıdır."""

    outcome: str  # offer | sold_out | error
    checked_at: datetime
    current_price: int | None = None
    original_price: int | None = None
    seller_name: str | None = None
    seller_rating: float | None = None
    seller_rating_scale: float | None = None
    stock_status: str | None = None
    error_code: str | None = None
    error_message: str | None = None


_RESULT_COLUMNS = [f.name for f in fields(CheckResult)]


@dataclass(frozen=True)
class RunSummary:
    outcomes: dict[str, int]  # offer / sold_out / error / unchecked
    error_codes: dict[str, int]


def try_lock_runs(conn: psycopg.Connection) -> bool:
    """Veritabanı tur kilidini almayı dener; başka bir bağlantı tutuyorsa False."""
    row = conn.execute("SELECT pg_try_advisory_lock(%s)", (_RUN_LOCK_ID,)).fetchone()
    return row[0]


def unlock_runs(conn: psycopg.Connection) -> None:
    conn.execute("SELECT pg_advisory_unlock(%s)", (_RUN_LOCK_ID,))


def close_stale_runs(conn: psycopg.Connection) -> list[int]:
    """'running' görünen turları 'interrupted' yapar.

    Yalnızca veritabanı tur kilidini tutan tur çağırır: kilit bizdeyse başka
    tur çalışmıyor, 'running' kalan her tur yarıda kalmıştır (ör. bilgisayar
    kapandı).
    """
    # greatest(now(), started_at): sistem saati geri alınmışsa now() turun
    # başlangıcından küçük olabilir; CHECK (finished_at >= started_at) bozulmasın
    # diye büyük olan yazılır (finish_run da aynı ifadeyi kullanır).
    rows = conn.execute(
        "UPDATE collection_runs"
        " SET status = 'interrupted', finished_at = greatest(now(), started_at),"
        " note = concat_ws('; ', note, 'Yarıda kaldı; sonraki tur başlarken kapatıldı')"
        " WHERE status = 'running' RETURNING run_id"
    ).fetchall()
    return [row[0] for row in rows]


def start_run(
    conn: psycopg.Connection,
    *,
    trigger: str,
    catalog_sha256: str,
    listings: list[tuple[str, int]],
    note: str | None = None,
) -> int:
    """Tur satırını ve planlanan sayfaları (sonuçsuz) tek transaction'da yazar."""
    with conn.transaction():
        run_id = conn.execute(
            "INSERT INTO collection_runs"
            " (trigger, status, catalog_sha256, planned_count, note)"
            " VALUES (%s, 'running', %s, %s, %s) RETURNING run_id",
            (trigger, catalog_sha256, len(listings), note),
        ).fetchone()[0]
        with conn.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO listing_checks (run_id, listing_id, product_id)"
                " VALUES (%s, %s, %s)",
                [(run_id, *listing) for listing in listings],
            )
    return run_id


def record_result(
    conn: psycopg.Connection, run_id: int, listing_id: str, result: CheckResult
) -> None:
    """Sayfanın sonucunu yazar; bağlantı autocommit olduğu için hemen kalıcıdır.

    Yalnızca süren turun planlanmış ve henüz sonuçsuz satırına yazılır: aynı
    sayfaya bir turda ikinci kez, kapanmış bir tura hiç sonuç yazılamaz.
    """
    query = sql.SQL(
        "UPDATE listing_checks SET {} WHERE run_id = %s AND listing_id = %s"
        " AND outcome IS NULL AND EXISTS (SELECT 1 FROM collection_runs r"
        " WHERE r.run_id = listing_checks.run_id AND r.status = 'running')"
    ).format(
        sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(column))
            for column in _RESULT_COLUMNS
        )
    )
    cursor = conn.execute(
        query,
        [getattr(result, column) for column in _RESULT_COLUMNS] + [run_id, listing_id],
    )
    if cursor.rowcount != 1:
        raise RuntimeError(
            f"{listing_id} tur {run_id} için yazılamadı: sayfa planlı değil, "
            "sonucu zaten yazılmış veya tur kapanmış"
        )


def finish_run(
    conn: psycopg.Connection, run_id: int, status: str, note: str | None = None
) -> None:
    """Süren turu kapatır; tur zaten kapanmışsa hata verir (sessiz geçmez)."""
    # concat_ws bütün parçalar NULL olunca '' döndürür; not yoksa NULL kalsın.
    # greatest(now(), started_at): nedeni close_stale_runs'ta.
    cursor = conn.execute(
        "UPDATE collection_runs"
        " SET status = %s, finished_at = greatest(now(), started_at),"
        " note = nullif(concat_ws('; ', note, %s::text), '')"
        " WHERE run_id = %s AND status = 'running'",
        (status, note, run_id),
    )
    if cursor.rowcount != 1:
        raise RuntimeError(f"Tur {run_id} kapatılamadı: artık 'running' değil")


def run_summary(conn: psycopg.Connection, run_id: int) -> RunSummary:
    outcomes, error_codes = {}, {}
    rows = conn.execute(
        "SELECT coalesce(outcome, 'unchecked'), error_code, count(*)"
        " FROM listing_checks WHERE run_id = %s GROUP BY 1, 2 ORDER BY 1, 2",
        (run_id,),
    ).fetchall()
    for outcome, error_code, count in rows:
        outcomes[outcome] = outcomes.get(outcome, 0) + count
        if error_code:
            error_codes[error_code] = count
    return RunSummary(outcomes, error_codes)
