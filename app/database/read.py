"""API için kayıtlı ürün, tur ve iki ayrı fiyat geçmişini yalnız okur."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

import psycopg
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from app.contracts import Product


@dataclass(frozen=True)
class RunInfo:
    run_id: int
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    planned_count: int
    note: str | None


@dataclass(frozen=True)
class RunStatus:
    running: RunInfo | None
    completed: RunInfo | None


@dataclass(frozen=True)
class ListingResult:
    run_id: int
    listing_id: str
    product_id: int
    platform: str
    platform_name: str
    platform_active: bool
    url: str
    color: str
    listing_active: bool
    checked_at: datetime | None
    outcome: str | None
    current_price: int | None
    original_price: int | None
    seller_name: str | None
    seller_rating: Decimal | None
    seller_rating_scale: Decimal | None
    stock_status: str | None
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class ProductRun:
    run_id: int
    product_id: int
    run_started_at: datetime
    run_finished_at: datetime
    planned_pages: int
    answered_pages: int
    offer_pages: int
    sold_out_pages: int
    error_pages: int
    best_price: int | None
    best_listing_id: str | None
    best_checked_at: datetime | None
    last_checked_at: datetime | None
    previous_run_id: int | None
    previous_best_price: int | None
    hours_since_previous: Decimal | None
    comparable_with_previous: bool
    planned_listing_ids: tuple[str, ...]

    @property
    def unchecked_pages(self) -> int:
        return self.planned_pages - self.answered_pages - self.error_pages

    @property
    def partial(self) -> bool:
        return self.answered_pages < self.planned_pages


@dataclass(frozen=True)
class MarketPoint:
    day: date
    price_kurus: int | None
    source: str
    source_product_id: str
    source_url: str
    captured_at: datetime


@dataclass(frozen=True)
class ProductSnapshot:
    product: Product
    current: ProductRun | None
    checks: tuple[ListingResult, ...]
    best_offer: ListingResult | None
    last_successful_offer: ListingResult | None
    history: tuple[ProductRun, ...]
    all_history: tuple[ProductRun, ...]
    cimri_history: tuple[MarketPoint, ...]

    @property
    def state(self) -> Literal["offer", "sold_out", "unverified", "no_history"]:
        if self.current is None:
            return "no_history"
        if self.current.best_price is not None:
            return "offer"
        if self.current.sold_out_pages == self.current.planned_pages:
            return "sold_out"
        return "unverified"


_PRODUCT_QUERY = (
    "SELECT product_id, product_key, brand, model, storage_gb, active FROM products"
)
_RUN_QUERY = (
    'SELECT run_id, "trigger", status, started_at, finished_at, planned_count, note'
    " FROM collection_runs WHERE status = %s ORDER BY run_id DESC LIMIT 1"
)
_CHECK_QUERY = """
SELECT c.run_id, c.listing_id, c.product_id, l.platform,
       p.name AS platform_name, p.active AS platform_active,
       l.url, l.color, l.active AS listing_active,
       c.checked_at, c.outcome, c.current_price, c.original_price,
       c.seller_name, c.seller_rating, c.seller_rating_scale, c.stock_status,
       c.error_code, c.error_message
FROM listing_checks c
JOIN listings l ON l.listing_id = c.listing_id
JOIN platforms p ON p.key = l.platform
WHERE c.product_id = %s AND c.run_id = %s
"""
_HISTORY_QUERY = """
SELECT v.*, r.finished_at AS run_finished_at,
       b.checked_at AS best_checked_at,
       pages.last_checked_at, pages.planned_listing_ids
FROM product_run_prices v
JOIN collection_runs r ON r.run_id = v.run_id
JOIN (
    SELECT run_id, max(checked_at) AS last_checked_at,
           array_agg(listing_id ORDER BY listing_id) AS planned_listing_ids
    FROM listing_checks WHERE product_id = %s GROUP BY run_id
) pages ON pages.run_id = v.run_id
LEFT JOIN listing_checks b ON b.run_id = v.run_id
    AND b.product_id = v.product_id AND b.listing_id = v.best_listing_id
WHERE v.product_id = %s ORDER BY v.run_id
"""
_MARKET_QUERY = """
WITH latest AS (
    SELECT max(day) AS day FROM market_history
    WHERE product_id = %s AND source = 'cimri'
)
SELECT m.day, m.price_kurus, m.source, m.source_product_id,
       m.source_url, m.captured_at
FROM market_history m CROSS JOIN latest
WHERE m.product_id = %s AND m.source = 'cimri'
  AND m.day BETWEEN latest.day - (%s::integer - 1) AND latest.day
ORDER BY m.day
"""


@contextmanager
def _read_transaction(conn: psycopg.Connection) -> Iterator[None]:
    if conn.closed:
        raise psycopg.InterfaceError("Veritabanı bağlantısı kapalı")
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise ValueError("Okuma için bağlantıda açık bir işlem bulunmamalı")
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        conn.execute("SET LOCAL TimeZone = 'UTC'")
        yield


def _rows(conn, query, params=()):
    with conn.cursor(row_factory=dict_row) as cursor:
        cursor.execute(query, params)
        return cursor.fetchall()


def _checks(conn, product_id, run_id, listing_id=None):
    query = _CHECK_QUERY
    params = (product_id, run_id)
    if listing_id is not None:
        query += " AND c.listing_id = %s"
        params += (listing_id,)
    rows = _rows(conn, query + " ORDER BY c.listing_id", params)
    return tuple(ListingResult(**row) for row in rows)


def list_products(conn: psycopg.Connection) -> tuple[Product, ...]:
    with _read_transaction(conn):
        rows = _rows(conn, _PRODUCT_QUERY + " WHERE active ORDER BY product_id")
        return tuple(Product(**row) for row in rows)


def read_run_status(conn: psycopg.Connection) -> RunStatus:
    with _read_transaction(conn):
        results = []
        for status in ("running", "completed"):
            rows = _rows(conn, _RUN_QUERY, (status,))
            results.append(RunInfo(**rows[0]) if rows else None)
        return RunStatus(*results)


def read_product(
    conn: psycopg.Connection,
    product_key: str,
    history_days: int = 30,
    cimri_days: int = 366,
) -> ProductSnapshot | None:
    for name, value in (("history_days", history_days), ("cimri_days", cimri_days)):
        if type(value) is not int or not 1 <= value <= 366:
            raise ValueError(f"{name}, 1–366 arasında bir tam sayı olmalı")
    with _read_transaction(conn):
        rows = _rows(conn, _PRODUCT_QUERY + " WHERE product_key = %s", (product_key,))
        if not rows:
            return None
        product = Product(**rows[0])
        rows = _rows(conn, _HISTORY_QUERY, (product.product_id, product.product_id))
        for row in rows:
            row["planned_listing_ids"] = tuple(row["planned_listing_ids"])
        all_history = tuple(ProductRun(**row) for row in rows)
        current = all_history[-1] if all_history else None
        checks = _checks(conn, product.product_id, current.run_id) if current else ()
        best_offer = next(
            (check for check in checks if check.listing_id == current.best_listing_id),
            None,
        )
        successful = next(
            (run for run in reversed(all_history) if run.best_price is not None), None
        )
        if successful is None:
            last_successful_offer = None
        elif successful == current:
            last_successful_offer = best_offer
        else:
            last_successful_offer = _checks(
                conn, product.product_id, successful.run_id, successful.best_listing_id
            )[0]
        history = ()
        if current:
            start = current.run_started_at - timedelta(days=history_days)
            history = tuple(
                run
                for run in all_history
                if start <= run.run_started_at <= current.run_started_at
            )
        cimri_history = tuple(
            MarketPoint(**row)
            for row in _rows(
                conn,
                _MARKET_QUERY,
                (product.product_id, product.product_id, cimri_days),
            )
        )
        return ProductSnapshot(
            product,
            current,
            checks,
            best_offer,
            last_successful_offer,
            history,
            all_history,
            cimri_history,
        )
