"""Katalogdaki canlı scraper sonuçlarını DB'ye yazmadan ekrana basar."""

import json
from pathlib import Path

from app.contracts import Catalog, ProductListing
from app.scraper.factory import create_scraper
from app.settings import Settings


def main() -> None:
    settings = Settings()
    runtime = settings.runtime()
    catalog = Catalog.model_validate_json(
        Path(settings.catalog_path).read_text(encoding="utf-8")
    )
    products = {product.product_id: product for product in catalog.products}
    platforms = {platform.key: platform for platform in catalog.platforms}
    observations = []

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
            print(observation.model_dump_json(indent=2))
        finally:
            scraper.close()

    available = [item for item in observations if item.current_price is not None]
    winner = min(available, key=lambda item: item.current_price) if available else None
    result = {
        "checked_listings": len(observations),
        "best_offer": winner.model_dump(mode="json") if winner else None,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
