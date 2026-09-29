"""Katalogdaki canlı scraper sonuçlarını hiçbir yere yazmadan ekrana basar."""

import argparse
import json
import sys
from pathlib import Path

from app.collection.service import format_try, plan_listings
from app.contracts import Catalog
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.scraper.factory import create_scraper
from app.scraper.http import FetchError
from app.settings import Settings


def with_price_display(values: dict) -> dict:
    result = dict(values)
    for field in ("current_price", "original_price"):
        value = result.get(field)
        # JSON'da fiyatsız alan null kalır (turun ekran çıktısındaki "-" değil).
        result[f"{field}_display"] = None if value is None else format_try(value)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "prefix", nargs="?", default="", help="Yalnızca bu product_key ön eki"
    )
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        # Fiyat turu veya başka bir tarama sürerken siteye gidilmesin.
        with scrape_lock():
            check(args.prefix)
    except ScrapeBusy as exc:
        sys.exit(f"Başlatılmadı: {exc}")


def check(prefix: str) -> None:
    settings = Settings()
    runtime = settings.runtime()
    catalog = Catalog.model_validate_json(
        Path(settings.catalog_path).read_text(encoding="utf-8-sig")
    )
    platforms = {platform.key: platform for platform in catalog.platforms}
    observations = []
    platform_results = []
    errors = []

    # Fiyat turuyla aynı sayfa seçimi: etkin sayfa + ürün + platform, ön ek.
    for listing in plan_listings(catalog, prefix):
        platform = platforms[listing.platform]
        scraper = create_scraper(platform.key, platform.hosts, runtime)
        try:
            observation = scraper.fetch(listing)
            observations.append(observation)
            offers = sorted(
                getattr(scraper, "_last_offers", []),
                key=lambda offer: (
                    offer.get("current_price") is None,
                    offer.get("current_price") or 0,
                    offer.get("seller_name") or "",
                ),
            )
            platform_results.append(
                {
                    "platform": platform.name,
                    "product_id": listing.product_id,
                    "listing_id": listing.listing_id,
                    "production_result": with_price_display(
                        observation.model_dump(mode="json")
                    ),
                    "offer_count": len(offers),
                    "all_offers": [with_price_display(offer) for offer in offers],
                }
            )
        except (FetchError, ValueError) as exc:
            errors.append({"listing_id": listing.listing_id, "error": str(exc)})
        finally:
            scraper.close()

    winners = {}
    for item in observations:
        if item.current_price is None:
            continue
        previous = winners.get(item.product_id)
        if previous is None or item.current_price < previous.current_price:
            winners[item.product_id] = item
    result = {
        "checked_listings": len(observations),
        "money_unit": "kurus",
        "platform_results": platform_results,
        "errors": errors,
        "best_offers_by_product": {
            str(product_id): with_price_display(item.model_dump(mode="json"))
            for product_id, item in winners.items()
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
