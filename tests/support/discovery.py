"""Keşif testlerinin ortak örnek dosyaları, sabit katalog ve hedefleri."""

import json
from pathlib import Path

from app.contracts import DiscoveryCandidate, DiscoveryTarget

FIXTURES = Path(__file__).parents[1] / "fixtures" / "discovery"
# Gerçek katalog keşifle değişir; testler 25 Eylül 2026 tarihli sabit kopyayı okur.
CATALOG = FIXTURES / "catalog.json"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def target(model="iPhone 16"):
    return DiscoveryTarget(key="apple_iphone_16", brand="Apple", model=model)


def network_target():
    return DiscoveryTarget(
        key="xiaomi_redmi_note_14_pro_4g",
        brand="Xiaomi",
        model="Redmi Note 14 Pro",
        network="4G",
        exclude_terms=["5G"],
    )


def conflict_candidates():
    """Katalogda 128 GB'a bağlı Trendyol sayfası 512 GB görünür; HB adayı geçerlidir.

    HB SKU'su bilerek sahtedir: gerçek katalog büyüdükçe test yeni aday olarak kalır.
    """
    conflicting = DiscoveryCandidate(
        target_key="apple_iphone_15",
        platform="trendyol",
        platform_product_id="762254881",
        url="https://www.trendyol.com/apple/iphone-15-128-gb-mavi-p-762254881",
        brand="Apple",
        model="iPhone 15",
        storage_gb=512,
        color="Mavi",
    )
    valid = conflicting.model_copy(
        update={
            "platform": "hepsiburada",
            "platform_product_id": "HBCV0000TEST01",
            "url": (
                "https://www.hepsiburada.com/"
                "apple-iphone-15-test-128gb-p-HBCV0000TEST01"
            ),
            "storage_gb": 128,
            "color": "Siyah",
        }
    )
    return conflicting, valid
