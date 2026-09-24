"""Keşif sonuçlarını kimlikleri koruyarak kataloğa aktarır."""

import importlib
import inspect
import json
import os
import re
import tempfile
from pathlib import Path

from filelock import FileLock

from app.contracts import Catalog, DiscoveryReport, Listing, Product
from app.discovery.base import BaseDiscovery
from app.settings import Settings


def _adapter(platform: str):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", platform):
        raise ValueError("Geçersiz platform anahtarı")
    module = importlib.import_module(f"app.discovery.{platform}")
    implementation = module.Discovery
    if (
        not inspect.isclass(implementation)
        or not issubclass(implementation, BaseDiscovery)
        or inspect.isabstract(implementation)
    ):
        raise ValueError("Keşif adaptörü sözleşmeye uymuyor")
    return implementation


def _url_identity(platform, url):
    patterns = {
        "trendyol": r"-p-(\d+)(?:[/?]|$)",
        "hepsiburada": r"-p-(HBCV[A-Z0-9]+)(?:[/?]|$)",
    }
    pattern = patterns.get(platform)
    if pattern:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def merge_catalog(catalog: Catalog, candidates):
    """Salt veri dönüşümü; var olan ürün ve bağlantı kimliklerine dokunmaz."""
    products = list(catalog.products)
    listings = list(catalog.listings)
    identities = {
        (p.brand.casefold(), p.model.casefold(), p.storage_gb): p for p in products
    }
    existing = {
        (item.platform, _url_identity(item.platform, item.url)): item
        for item in listings
        if _url_identity(item.platform, item.url)
    }
    next_id = max((product.product_id for product in products), default=0) + 1
    added_products = []
    added_listings = []
    existing_listings = []
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item.target_key,
            item.storage_gb,
            item.platform,
            item.platform_product_id,
        ),
    ):
        identity = (
            candidate.brand.casefold(),
            candidate.model.casefold(),
            candidate.storage_gb,
        )
        product = identities.get(identity)
        if product is None:
            product_key = f"{candidate.target_key}_{candidate.storage_gb}gb"
            product = Product(
                product_id=next_id,
                product_key=product_key,
                brand=candidate.brand,
                model=candidate.model,
                storage_gb=candidate.storage_gb,
            )
            products.append(product)
            identities[identity] = product
            added_products.append(product_key)
            next_id += 1
        listing_key = (candidate.platform, candidate.platform_product_id.upper())
        old = existing.get(listing_key)
        if old is not None:
            if old.product_id != product.product_id:
                raise ValueError("Aynı platform ürünü iki farklı telefona bağlanamaz")
            existing_listings.append(old.listing_id)
            continue
        listing_id = f"{candidate.platform}_{candidate.platform_product_id.lower()}"
        if any(item.listing_id == listing_id for item in listings):
            raise ValueError("Bağlantı kimliği çakışıyor")
        new = Listing(
            listing_id=listing_id,
            product_id=product.product_id,
            platform=candidate.platform,
            url=candidate.url,
            color=candidate.color,
        )
        listings.append(new)
        existing[listing_key] = new
        added_listings.append(listing_id)
    updated = Catalog(
        platforms=catalog.platforms,
        products=products,
        listings=listings,
        history_sources=catalog.history_sources,
    )
    return updated, added_products, added_listings, existing_listings


def _atomic_catalog(path: Path, catalog: Catalog):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                catalog.model_dump(mode="json"), handle, ensure_ascii=False, indent=2
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def observed_colors(candidates):
    """Doğrulanan renkleri kapasite ve platform bazında raporlar."""
    colors = {}
    for candidate in candidates:
        capacity = colors.setdefault(candidate.target_key, {}).setdefault(
            str(candidate.storage_gb), {}
        )
        capacity.setdefault(candidate.platform, set()).add(
            candidate.color or "Bilinmiyor"
        )
    return {
        target: {
            capacity: {
                platform: sorted(values) for platform, values in platforms.items()
            }
            for capacity, platforms in capacities.items()
        }
        for target, capacities in colors.items()
    }


def retained_unobserved_listings(catalog, targets, results):
    """Bu taramada görünmeyen, ancak katalogdan silinmeyen bağlantıları gösterir."""
    by_key = {target.key: target for target in targets}
    retained = set()
    for result in results:
        target = by_key[result.target_key]
        product_ids = {
            product.product_id
            for product in catalog.products
            if product.brand.casefold() == target.brand.casefold()
            and product.model.casefold() == target.model.casefold()
        }
        observed = {
            candidate.platform_product_id.upper() for candidate in result.candidates
        }
        for listing in catalog.listings:
            if (
                listing.product_id in product_ids
                and listing.platform == result.platform
                and _url_identity(listing.platform, listing.url) not in observed
            ):
                retained.add(listing.listing_id)
    return sorted(retained)


def run(*, dry_run=False, target_key=None, settings=None, adapters=None):
    settings = settings or Settings()
    config = settings.discovery()
    catalog_path = settings.catalog_path
    catalog = Catalog.model_validate_json(catalog_path.read_text(encoding="utf-8"))
    runtime = settings.runtime()
    targets = [
        item
        for item in config.targets
        if item.active and (target_key is None or item.key == target_key)
    ]
    if target_key and not targets:
        raise ValueError(f"Keşif hedefi bulunamadı: {target_key}")
    results = []
    for target in targets:
        for platform in catalog.platforms:
            if not platform.active:
                continue
            implementation = (
                adapters[platform.key]
                if adapters is not None
                else _adapter(platform.key)
            )
            discovery = implementation(target, config, runtime)
            try:
                results.append(discovery.discover())
            finally:
                discovery.close()
    candidates = [candidate for result in results for candidate in result.candidates]
    if dry_run:
        _, products, listings, existing = merge_catalog(catalog, candidates)
    else:
        with FileLock(str(catalog_path) + ".lock", timeout=30):
            latest = Catalog.model_validate_json(
                catalog_path.read_text(encoding="utf-8")
            )
            updated, products, listings, existing = merge_catalog(latest, candidates)
            if updated != latest:
                _atomic_catalog(catalog_path, updated)
    report = DiscoveryReport(
        complete=bool(results) and all(result.complete for result in results),
        dry_run=dry_run,
        results=results,
        added_products=products,
        added_listings=listings,
        existing_listings=existing,
        retained_unobserved_listings=retained_unobserved_listings(
            catalog, targets, results
        ),
        pending=[
            issue
            for result in results
            for issue in result.issues
            if issue.reason != "candidate_rejected"
        ],
        rejected=[
            issue
            for result in results
            for issue in result.issues
            if issue.reason == "candidate_rejected"
        ],
        coverage_changes={
            platform.key: sum(
                listing_id.startswith(platform.key + "_") for listing_id in listings
            )
            for platform in catalog.platforms
        },
        observed_colors=observed_colors(candidates),
    )
    report_path = Path("data/discovery_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
