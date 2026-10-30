"""ML veri görüntüsü testlerinin küçük, tutarlı tablo örneği (veritabanısız)."""

from datetime import date, datetime, timedelta, timezone

CAPTURED_AT = datetime(2026, 10, 28, 9, 30, tzinfo=timezone.utc)
START = datetime(2026, 10, 27, 19, tzinfo=timezone.utc)


def snapshot_tables():
    """Veritabanının döndürdüğü biçimde satırlar: tamamlanan ve yarıda kalan tur,
    üç sonuç türü, kontrol edilmemiş sayfa ve fiyatı boş Cimri günü."""
    return {
        "products": [
            {
                "product_id": 1,
                "product_key": "apple_iphone_15_128gb",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 128,
                "active": True,
            },
            {
                "product_id": 2,
                "product_key": "samsung_galaxy_s24_256gb",
                "brand": "Samsung",
                "model": "Galaxy S24",
                "storage_gb": 256,
                "active": False,
            },
        ],
        "platforms": [
            {"key": "hepsiburada", "active": True},
            {"key": "trendyol", "active": True},
        ],
        "listings": [
            {
                "listing_id": "hepsiburada_a",
                "product_id": 1,
                "platform": "hepsiburada",
                "active": True,
            },
            {
                "listing_id": "trendyol_b",
                "product_id": 1,
                "platform": "trendyol",
                "active": False,
            },
            {
                "listing_id": "trendyol_c",
                "product_id": 2,
                "platform": "trendyol",
                "active": True,
            },
        ],
        "collection_runs": [
            {
                "run_id": 1,
                "trigger": "scheduled",
                "status": "completed",
                "started_at": START,
                "finished_at": START + timedelta(minutes=31),
                "planned_count": 3,
            },
            {
                "run_id": 2,
                "trigger": "manual",
                "status": "interrupted",
                "started_at": START + timedelta(hours=12),
                "finished_at": START + timedelta(hours=12, minutes=5),
                "planned_count": 2,
            },
        ],
        "listing_checks": [
            check(1, "hepsiburada_a", 1, "offer", 4_299_900, minutes=1),
            check(1, "trendyol_b", 1, "sold_out", minutes=2),
            check(1, "trendyol_c", 2, "error", minutes=3),
            check(2, "hepsiburada_a", 1, "offer", 4_199_900, minutes=12 * 60 + 1),
            check(2, "trendyol_c", 2),
        ],
        "market_history": [
            market(1, date(2026, 10, 7), 4_350_000),
            market(1, date(2026, 10, 8), None),
        ],
    }


def check(run_id, listing_id, product_id, outcome=None, price=None, minutes=None):
    return {
        "run_id": run_id,
        "listing_id": listing_id,
        "product_id": product_id,
        "checked_at": None if minutes is None else START + timedelta(minutes=minutes),
        "outcome": outcome,
        "current_price": price,
    }


def market(product_id, day, price):
    return {
        "product_id": product_id,
        "source": "cimri",
        "source_product_id": "123456",
        "day": day,
        "price_kurus": price,
        "captured_at": datetime(2026, 10, 8, 13, 51, 42, 423000, tzinfo=timezone.utc),
    }
