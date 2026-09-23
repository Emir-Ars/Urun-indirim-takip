"""Katalogdaki canlı scraper sonuçlarını DB'ye yazmadan ekrana basar."""

import json
import sys
from pathlib import Path

from app.contracts import Catalog, ProductListing
from app.scraper.factory import create_scraper
from app.settings import Settings


def format_try(value: int | None) -> str | None:
    if value is None:
        return None
    lira, kurus = divmod(value, 100)
    grouped = f"{lira:,}".replace(",", ".")
    return f"{grouped},{kurus:02d} TL"


def with_price_display(values: dict) -> dict:
    result = dict(values)
    for field in ("current_price", "original_price"):
        result[f"{field}_display"] = format_try(result.get(field))
    return result


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = Settings()
    runtime = settings.runtime()
    catalog = Catalog.model_validate_json(
        Path(settings.catalog_path).read_text(encoding="utf-8")
    )
    products = {product.product_id: product for product in catalog.products}
    platforms = {platform.key: platform for platform in catalog.platforms}
    observations = []
    platform_results = []

    for item in catalog.listings:
        product = products[item.product_id]
        platform = platforms[item.platform]
        if not (item.active and product.active and platform.active):
            continue
        listing = ProductListing(
            **item.model_dump(),
            product_name=product.name,
            brand=product.brand,
            model=product.model,
            storage_gb=product.storage_gb,
            platform_name=platform.name,
            hosts=platform.hosts,
            coverage_version="manual-check",
        )
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
                    "production_result": with_price_display(
                        observation.model_dump(mode="json")
                    ),
                    "offer_count": len(offers),
                    "all_offers": [with_price_display(offer) for offer in offers],
                }
            )
        finally:
            scraper.close()

    available = [item for item in observations if item.current_price is not None]
    winner = min(available, key=lambda item: item.current_price) if available else None
    result = {
        "checked_listings": len(observations),
        "money_unit": "kurus",
        "platform_results": platform_results,
        "best_offer": (
            with_price_display(winner.model_dump(mode="json")) if winner else None
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
