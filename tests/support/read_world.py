"""Salt okunur sorgu ve API testlerinin küçük test veritabanı dünyası."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tests.support.database import insert

START = datetime(2024, 11, 1, 7, tzinfo=timezone.utc)
KEY = "apple_iphone_15_128gb"
OWNER = {"a": 1, "b": 1, "c": 1, "d": 2, "e": 3}


@pytest.fixture
def world(api_db, db):
    for key, name in (("trendyol", "Trendyol"), ("hepsiburada", "Hepsiburada")):
        insert(db, "platforms", key=key, name=name, active=True)
    for product_id, key, brand, model, capacity, active in (
        (1, KEY, "Apple", "iPhone 15", 128, True),
        (2, "samsung_s24_256gb", "Samsung", "Galaxy S24", 256, True),
        (3, "poco_x6_pro_512gb", "POCO", "X6 Pro", 512, False),
    ):
        insert(
            db,
            "products",
            product_id=product_id,
            product_key=key,
            brand=brand,
            model=model,
            storage_gb=capacity,
            active=active,
        )
    for page, product_id in OWNER.items():
        platform = "hepsiburada" if page == "c" else "trendyol"
        insert(
            db,
            "listings",
            listing_id=page,
            product_id=product_id,
            platform=platform,
            url=f"https://www.{platform}.com/urun-{page}",
            color="Siyah",
            active=True,
        )
    return db


def add_run(conn, at, results, status="completed"):
    run_id = conn.execute(
        "INSERT INTO collection_runs"
        " (trigger,status,started_at,catalog_sha256,planned_count,note)"
        " VALUES ('manual','running',%s,%s,%s,'Yerel test') RETURNING run_id",
        (at, "0" * 64, len(results)),
    ).fetchone()[0]
    for index, (page, result) in enumerate(sorted(results.items()), 1):
        outcome, price = result if isinstance(result, tuple) else (result, None)
        values = {"run_id": run_id, "listing_id": page, "product_id": OWNER[page]}
        if outcome != "planned":
            values.update(outcome=outcome, checked_at=at + timedelta(minutes=index))
        if outcome == "offer":
            values.update(
                current_price=price,
                original_price=price + 1000,
                seller_name=f"Satıcı {page}",
                seller_rating=Decimal("9.25"),
                seller_rating_scale=Decimal("10"),
                stock_status="Kritik Stok" if page == "b" else "Stokta Var",
            )
        elif outcome == "sold_out":
            values["stock_status"] = "Tükendi"
        elif outcome == "error":
            values.update(error_code="network", error_message="Yerel test hatası")
        insert(conn, "listing_checks", **values)
    if status != "running":
        close_run(conn, run_id, at, status)
    return run_id


def close_run(conn, run_id, at, status="completed"):
    conn.execute(
        "UPDATE collection_runs SET status=%s,finished_at=%s WHERE run_id=%s",
        (status, at + timedelta(minutes=30), run_id),
    )


def add_market(conn, day, price, product_id=1):
    insert(
        conn,
        "market_history",
        product_id=product_id,
        source="cimri",
        source_product_id="123456",
        source_url="https://www.cimri.com/cep-telefonlari/test,a123456",
        day=day,
        price_kurus=price,
        captured_at=START,
        page_sha256="1" * 64,
        api_sha256="2" * 64,
        report_sha256="3" * 64,
    )
