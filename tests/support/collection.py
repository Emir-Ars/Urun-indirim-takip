"""Toplama turu testlerinin küçük sahte kataloğu ve sahte scraper'ları."""

import json

from app.scraper.base import BaseScraper

PLATFORMS = [
    {"key": "trendyol", "name": "Trendyol", "hosts": ["www.trendyol.com"]},
    {"key": "hepsiburada", "name": "Hepsiburada", "hosts": ["www.hepsiburada.com"]},
]
PRODUCTS = [
    {
        "product_id": 1,
        "product_key": "apple_iphone_15_128gb",
        "brand": "Apple",
        "model": "iPhone 15",
        "storage_gb": 128,
    },
    {
        "product_id": 2,
        "product_key": "poco_x6_pro_512gb",
        "brand": "POCO",
        "model": "X6 Pro",
        "storage_gb": 512,
    },
]
HOSTS = {"trendyol": "www.trendyol.com", "hepsiburada": "www.hepsiburada.com"}


def listing(listing_id, product_id=1, active=True):
    platform = listing_id.split("_")[0]
    return {
        "listing_id": listing_id,
        "product_id": product_id,
        "platform": platform,
        "url": f"https://{HOSTS[platform]}/urun-p-{listing_id.split('_')[1]}",
        "active": active,
    }


LISTINGS = [
    listing("trendyol_1"),
    listing("trendyol_2"),
    listing("trendyol_3"),
    listing("hepsiburada_4"),
    listing("hepsiburada_5"),
    listing("hepsiburada_6"),
    listing("trendyol_7", product_id=2),
    listing("trendyol_8", active=False),
]

OFFER = {
    "current_price": 5724900,
    "seller_name": "Satıcı A",
    "seller_rating": 9.5,
    "seller_rating_scale": 10.0,
    "stock_status": "Stokta Var",
}


class FakeScrapers:
    """create_scraper yerine geçer; her sayfa için verilen davranışı uygular.

    Davranış: gözlem alanları (dict), fırlatılacak istisna ya da gözlemi kendisi
    üreten bir fonksiyon.
    """

    def __init__(self, behaviours, close_error=None):
        self.behaviours = behaviours
        self.close_error = close_error
        self.created = self.closed = 0

    def __call__(self, platform, hosts, runtime):
        self.created += 1
        return _FakeScraper(self)


class _FakeScraper:
    def __init__(self, owner):
        self.owner = owner

    def fetch(self, item):
        action = self.owner.behaviours[item.listing_id]
        if isinstance(action, BaseException):
            raise action
        if callable(action):
            return action(item)
        return BaseScraper.observation(item, **action)

    def close(self):
        self.owner.closed += 1
        if self.owner.close_error:
            raise self.owner.close_error


def write_catalog(path, listings=LISTINGS, products=PRODUCTS, platforms=PLATFORMS):
    path.write_text(
        json.dumps(
            {"platforms": platforms, "products": products, "listings": listings}
        ),
        encoding="utf-8",
    )
    return path


def run_snapshot(conn, run_id):
    run = conn.execute(
        "SELECT * FROM collection_runs WHERE run_id = %s", (run_id,)
    ).fetchone()
    checks = conn.execute(
        "SELECT * FROM listing_checks WHERE run_id = %s ORDER BY listing_id",
        (run_id,),
    ).fetchall()
    return run, checks
