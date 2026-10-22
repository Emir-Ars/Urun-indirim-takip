"""Katalog birleştirme ve rapor içeriği; siteye ve dosyaya gitmeden."""

from app.contracts import (
    Catalog,
    DiscoveryCandidate,
    DiscoveryIssue,
    DiscoveryReport,
    DiscoveryResult,
    DiscoveryTarget,
)
from app.discovery.service import (
    merge_catalog,
    observed_colors,
    retained_unobserved_listings,
    summarize_report,
)
from tests.support.discovery import CATALOG, conflict_candidates


def test_catalog_merge_keeps_existing_ids_and_is_idempotent():
    source = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    catalog = source.model_copy(
        update={"products": source.products[:1], "listings": source.listings[:2]}
    )
    existing = DiscoveryCandidate(
        target_key="apple_iphone_15",
        platform="trendyol",
        platform_product_id="762254881",
        url="https://www.trendyol.com/apple/iphone-15-128-gb-mavi-p-762254881",
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
        color="Mavi",
    )
    new = existing.model_copy(
        update={
            "platform_product_id": "762254862",
            "url": "https://www.trendyol.com/apple/iphone-15-256-gb-mavi-p-762254862",
            "storage_gb": 256,
        }
    )
    updated, products, listings, old, conflicts = merge_catalog(
        catalog, [existing, new]
    )
    assert products == ["apple_iphone_15_256gb"]
    assert listings == ["trendyol_762254862"]
    assert old == ["trendyol_iphone_15_128gb_mavi"]
    assert updated.products[0].product_id == 1
    assert updated.products[-1].product_id == 2
    assert not conflicts
    again, products, listings, _, _ = merge_catalog(updated, [existing, new])
    assert again == updated
    assert not products and not listings


def test_catalog_merge_assigns_same_ids_whatever_order_sites_return():
    # Yeni product_id'ler sırayla verilir; adaylar sıralanmasaydı kimlik, sitenin
    # kartları döndürme sırasına bağlı olurdu.
    source = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    catalog = source.model_copy(
        update={"products": source.products[:1], "listings": source.listings[:2]}
    )
    candidates = [
        DiscoveryCandidate(
            target_key="apple_iphone_15",
            platform="trendyol",
            platform_product_id=product_id,
            url=f"https://www.trendyol.com/apple/iphone-15-{capacity}gb-p-{product_id}",
            brand="Apple",
            model="iPhone 15",
            storage_gb=capacity,
        )
        for product_id, capacity in (("900000001", 512), ("900000002", 256))
    ]
    forward, *_ = merge_catalog(catalog, candidates)
    backward, *_ = merge_catalog(catalog, list(reversed(candidates)))
    assert forward == backward
    ids = {product.storage_gb: product.product_id for product in forward.products}
    assert ids[256] < ids[512]


def test_catalog_conflict_is_reported_and_other_candidates_still_merge():
    catalog = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    updated, products, listings, _, conflicts = merge_catalog(
        catalog, list(conflict_candidates())
    )

    assert [issue.reason for issue in conflicts] == ["catalog_conflict"]
    assert "762254881" in conflicts[0].detail and "128 GB" in conflicts[0].detail
    assert listings == ["hepsiburada_hbcv0000test01"]
    # Çakışan aday yeni (512 GB) bir ürün de oluşturmadı; eski kayıt aynı kaldı.
    assert not products
    assert updated.products == catalog.products
    assert all(item in updated.listings for item in catalog.listings)


def test_catalog_merge_preserves_listings_missing_from_current_search():
    catalog = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    updated, products, listings, existing, _ = merge_catalog(catalog, [])
    assert updated == catalog
    assert not products and not listings and not existing


def test_report_summary_counts_warnings_by_reason():
    def issue(reason):
        return DiscoveryIssue(
            platform="hepsiburada", target_key="apple_iphone_15", reason=reason
        )

    report = DiscoveryReport(
        complete=False,
        dry_run=True,
        results=[
            DiscoveryResult(
                platform="hepsiburada", target_key="apple_iphone_15", complete=True
            ),
            DiscoveryResult(platform="trendyol", target_key="apple_iphone_15"),
        ],
        added_products=["apple_iphone_17_256gb"],
        added_listings=["trendyol_1", "hepsiburada_hbcv1"],
        existing_listings=["trendyol_2"],
        retained_unobserved_listings=["trendyol_3", "trendyol_4"],
        pending=[issue("search_api"), issue("search_api"), issue("html_partial")],
        rejected=[issue("candidate_rejected"), issue("catalog_conflict")],
        coverage_changes={"trendyol": 1, "hepsiburada": 1, "diger": 0},
    )
    assert summarize_report(report) == (
        "Özet: yeni ürün 1 · yeni sayfa 2 (hepsiburada 1, trendyol 1) · "
        "zaten kayıtlı 1 · görülmeyen 2 · çakışma 1 · reddedilen 1 · "
        "tam sonuç 1/2 · uyarı html_partial 1, search_api 2"
    )
    empty = DiscoveryReport(complete=True, dry_run=True, results=[])
    assert summarize_report(empty) == (
        "Özet: yeni ürün 0 · yeni sayfa 0 · zaten kayıtlı 0 · görülmeyen 0 · "
        "çakışma 0 · reddedilen 0 · tam sonuç 0/0"
    )


def test_report_distinguishes_retained_links_from_current_discovery():
    catalog = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    candidate = DiscoveryCandidate(
        target_key="apple_iphone_15",
        platform="trendyol",
        platform_product_id="762254881",
        url="https://www.trendyol.com/apple/iphone-15-128-gb-mavi-p-762254881",
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
        color="Mavi",
    )
    result = DiscoveryResult(
        platform="trendyol", target_key="apple_iphone_15", candidates=[candidate]
    )
    retained = retained_unobserved_listings(
        catalog,
        [DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15")],
        [result],
    )
    assert "trendyol_762254849" in retained
    assert "trendyol_iphone_15_128gb_mavi" not in retained


def test_retained_report_skips_inactive_listings():
    # Pasif bağlantı zaten takip edilmiyor; "görülmedi ama korunuyor" listesine
    # girmesi yanıltıcı olurdu.
    source = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    catalog = source.model_copy(
        update={
            "listings": [
                (
                    item.model_copy(update={"active": False})
                    if item.listing_id == "trendyol_762254849"
                    else item
                )
                for item in source.listings
            ]
        }
    )
    result = DiscoveryResult(platform="trendyol", target_key="apple_iphone_15")
    retained = retained_unobserved_listings(
        catalog,
        [DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15")],
        [result],
    )
    assert "trendyol_762254849" not in retained
    assert "trendyol_762254854" in retained  # etkin ve görülmedi


def test_color_report_keeps_platform_coverage_separate():
    base = DiscoveryCandidate(
        target_key="apple_iphone_15",
        platform="trendyol",
        platform_product_id="762254849",
        url="https://www.trendyol.com/apple/iphone-15-256-gb-sari-p-762254849",
        brand="Apple",
        model="iPhone 15",
        storage_gb=256,
        color="Sarı",
    )
    other = base.model_copy(
        update={
            "platform": "hepsiburada",
            "platform_product_id": "HBCV00004X9ZCP",
            "url": (
                "https://www.hepsiburada.com/"
                "apple-iphone-15-256-gb-sari-p-HBCV00004X9ZCP"
            ),
        }
    )
    assert observed_colors([base, other])["apple_iphone_15"]["256"] == {
        "trendyol": ["Sarı"],
        "hepsiburada": ["Sarı"],
    }
