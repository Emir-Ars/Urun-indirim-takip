"""Keşfin kimlik, sayfalama ve katalog sürekliliği kontrolleri."""

import json
from pathlib import Path

import pytest

from app.contracts import (
    Catalog,
    DiscoveryCandidate,
    DiscoveryConfig,
    DiscoveryResult,
    DiscoveryTarget,
)
from app.discovery.base import BaseDiscovery
from app.discovery.hepsiburada import Discovery as HepsiburadaDiscovery
from app.discovery.service import (
    merge_catalog,
    observed_colors,
    retained_unobserved_listings,
    run,
)
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.http import FetchError, PageClient
from app.scraper.parsing import (
    excluded_term,
    identify,
    matches_model,
    storage_gb,
    title_storage,
    verify_identity,
)
from app.settings import Runtime

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"
CATALOG = Path(__file__).parents[1] / "config" / "catalog.json"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def target(model="iPhone 16"):
    return DiscoveryTarget(key="apple_iphone_16", brand="Apple", model=model)


def test_discovery_target_requires_model_instead_of_manual_urls():
    with pytest.raises(ValueError):
        DiscoveryTarget(
            key="apple_iphone_15",
            brand="Apple",
            model="iPhone 15",
            seed_urls={"trendyol": ["https://www.trendyol.com/example-p-1"]},
        )


def test_exact_model_and_storage():
    assert matches_model("iPhone 16 128 GB Siyah", "iPhone 16")
    for wrong in (
        "iPhone 16e 128 GB",
        "iPhone 16 Pro 128 GB",
        "iPhone 16+ 128 GB",
        "iPhone 16 uyumlu kılıf",
        "iPhone 16 yenilenmiş 128 GB",
    ):
        assert not matches_model(wrong, "iPhone 16")
    assert storage_gb("1 TB") == 1024
    assert title_storage("iPhone 16 8 GB RAM 256 GB") is None
    assert matches_model("Samsung Galaxy S24 8 GB RAM 256 GB", "Galaxy S24")
    assert not matches_model("Samsung Galaxy S24 Ultra 256 GB", "Galaxy S24")


def test_identity_rules_shared_by_discovery_and_scraper():
    # Canlı Hepsiburada adları: kapasite başlıkta yok, yapısal veride var.
    assert identify(["Apple  iPhone 15 128"], "iPhone 15", 128) == 128
    assert (
        identify(["Apple iphone 15 Siyah", "Apple iphone 15 Siyah 128GB"], "iPhone 15")
        == 128
    )
    assert identify(["iPhone 15 Pro Max 1 TB Siyah"], "iPhone 15 Pro Max") == 1024
    assert identify(["Samsung Galaxy S24 8 GB RAM 256 GB"], "Galaxy S24", 256) == 256
    for names, model, capacity in (
        (["Apple iPhone 15 256 GB"], "iPhone 15", 128),  # kaynaklar çelişiyor
        (["Apple iPhone 15 Mavi"], "iPhone 15", None),  # kapasite yok
        (["Apple iPhone 13 mini 128 GB"], "iPhone 13", None),
        (["Samsung Galaxy S24+ 256 GB"], "Galaxy S24", None),
        (["Samsung Galaxy S24 FE 128 GB"], "Galaxy S24", None),
        (["Apple iPhone 15 128 GB Yenilenmiş"], "iPhone 15", 128),
    ):
        with pytest.raises(FetchError) as error:
            identify(names, model, capacity)
        assert error.value.code == "identity"
        assert names[0] in str(error.value)
    with pytest.raises(FetchError):
        verify_identity(["Apple iPhone 15 128 GB"], "iPhone 15", 256)


def test_target_exclude_terms_split_same_named_phones():
    # Canlı veri: Redmi Note 14 (4G) ile Note 14 5G farklı telefonlardır.
    note_4g = ["Redmi Note 14 8+256 Mavi(Xiaomi Türkiye Garantili)"]
    note_5g = ["Redmi Note 14 5G 8GB+256GB Siyah"]
    assert identify(note_4g, "Redmi Note 14", 256, exclude=["5G"]) == 256
    with pytest.raises(FetchError) as error:
        identify(note_5g, "Redmi Note 14", 256, exclude=["5G"])
    assert "5G" in str(error.value)
    assert identify(note_5g, "Redmi Note 14 5G", 256) == 256
    with pytest.raises(FetchError):
        identify(["Redmi Note 14 Pro 5G 8GB+256GB"], "Redmi Note 14 5G", 256)
    # "5 GB" bir kapasite ifadesidir; "5G" sanılmaz.
    assert excluded_term(["Telefon 4 GB + 5 GB RAM 128 GB"], ["5G"]) is None

    target = DiscoveryTarget(
        key="xiaomi_redmi_note_14",
        brand="Xiaomi",
        model="Redmi Note 14",
        exclude_terms=["5G"],
    )
    discovery = TrendyolDiscovery(
        target, DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    card = {
        "name": note_5g[0],
        "brand": "Xiaomi",
        "category": {"name": "Android Cep Telefonu"},
    }
    assert discovery._card_reason(card) == "excluded_term"
    assert discovery._card_reason({**card, "name": note_4g[0]}) is None
    discovery.close()
    with pytest.raises(ValueError):
        DiscoveryTarget(key="x", brand="Xiaomi", model="Redmi", exclude_terms=[""])


def test_trendyol_deduplicates_axes_and_uses_response_cursor(monkeypatch):
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    first = fixture("trendyol_search.json")
    first["products"][0]["url"] = "/apple/iphone-16-128-gb-siyah-p-11"
    second = {**first, "products": [], "pageIndex": 2, "_links": {"next": None}}
    first["_links"] = {
        "next": "https://apigw.trendyol.com/search?pi=2&offsetParameters=old"
    }
    responses = [second]
    calls = []

    def fake_json(url, headers=None):
        calls.append(url)
        return responses.pop(0)

    monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
    monkeypatch.setattr(discovery, "get_json", fake_json)
    groups, cards, complete = discovery._search_candidates()
    assert groups == {"7": "11"}
    assert cards == {"11": "https://www.trendyol.com/apple/iphone-16-128-gb-siyah-p-11"}
    assert "offsetParameters=Product_3" in calls[0]
    assert complete
    variants = fixture("trendyol_variants.json")
    ids = {
        str(product["id"])
        for axis in variants["result"]
        for value in axis["values"]
        for product in value["products"]
    }
    assert ids == {"11", "14"}
    discovery.close()


def test_trendyol_search_card_survives_missing_variant(monkeypatch):
    iphone_15 = DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15")
    discovery = TrendyolDiscovery(
        iphone_15,
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    monkeypatch.setattr(
        discovery,
        "_search_candidates",
        lambda: (
            {"7": "11"},
            {
                "762254849": (
                    "https://www.trendyol.com/apple/iphone-15-256-gb-sari-p-762254849"
                )
            },
            True,
        ),
    )
    monkeypatch.setattr(
        discovery, "get_json", lambda url: fixture("trendyol_variants.json")
    )

    def candidate(url, product_id):
        return DiscoveryCandidate(
            target_key=iphone_15.key,
            platform="trendyol",
            platform_product_id=product_id,
            url=url,
            brand="Apple",
            model="iPhone 15",
            storage_gb=256,
            color="Sarı",
        )

    monkeypatch.setattr(discovery, "_candidate", candidate)
    result = discovery.discover()
    assert {item.platform_product_id for item in result.candidates} == {
        "11",
        "14",
        "762254849",
    }
    discovery.close()


def test_trendyol_gone_search_card_is_reported_without_candidate(monkeypatch):
    discovery = TrendyolDiscovery(
        DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    monkeypatch.setattr(
        discovery,
        "_search_candidates",
        lambda: (
            {},
            {
                "762254885": (
                    "https://www.trendyol.com/apple/iphone-15-512-gb-siyah-p-762254885"
                )
            },
            True,
        ),
    )

    def gone(url, product_id):
        raise FetchError("http_error", "Kaynak HTTP 410 döndürdü")

    monkeypatch.setattr(discovery, "_candidate", gone)
    result = discovery.discover()
    assert not result.candidates
    assert not result.complete
    assert result.issues[0].reason == "candidate_rejected"
    assert "410" in result.issues[0].detail
    discovery.close()


def test_trendyol_search_skips_refurbished_category(monkeypatch):
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    first = {
        "products": [],
        "canonicalFilters": {"brands": [{"key": 101470, "name": "Apple"}]},
        "_links": {"aggregation": "https://apigw.trendyol.com/aggregation"},
    }
    aggregation = {
        "aggregation": [
            {
                "filterKey": "LeafCategory",
                "values": [
                    {"id": 109461, "text": "Yenilenmiş Cep Telefonu"},
                    {"id": 164462, "text": "iPhone IOS Cep Telefonları"},
                    {"id": 1, "text": "Telefon Kılıfı"},
                ],
            }
        ]
    }
    searches = []

    def get_json(url, headers=None):
        if "aggregation" in url:
            return aggregation
        searches.append(url)
        return first

    monkeypatch.setattr(discovery, "get", lambda url, headers=None: "")
    monkeypatch.setattr(discovery, "get_json", get_json)
    discovery._search()

    assert "lc=164462" in searches[-1] and "wb=101470" in searches[-1]
    assert not discovery.issues

    # İkinci geçerli telefon kategorisi taranmadığı için tarama kısmi sayılır.
    aggregation["aggregation"][0]["values"].append(
        {"id": 2, "text": "Android Cep Telefonları"}
    )
    discovery._search()
    assert [issue.reason for issue in discovery.issues] == ["category_partial"]
    discovery.close()


def test_trendyol_brand_filter_falls_back_to_aggregation(monkeypatch):
    # Canlı Xiaomi araması: canonicalFilters boş, marka filtre listesinde.
    xiaomi = DiscoveryTarget(
        key="xiaomi_redmi_note_14", brand="Xiaomi", model="Redmi Note 14"
    )
    discovery = TrendyolDiscovery(
        xiaomi, DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    first = {
        "products": [],
        "canonicalFilters": {"brands": []},
        "_links": {"aggregation": "https://apigw.trendyol.com/aggregation"},
    }
    aggregation = {
        "aggregation": [
            {
                "filterKey": "LeafCategory",
                "values": [
                    {"id": 164461, "text": "Android Cep Telefonu"},
                    {"id": 109349, "text": "Telefon Kılıfı"},
                ],
            },
            {
                "filterKey": "WebBrand",
                "values": [
                    {"id": 172374, "text": "Generic"},
                    {"id": 101939, "text": "Xiaomi"},
                ],
            },
        ]
    }
    searches = []

    def get_json(url, headers=None):
        if "aggregation" in url:
            return aggregation
        searches.append(url)
        return first

    monkeypatch.setattr(discovery, "get", lambda url, headers=None: "")
    monkeypatch.setattr(discovery, "get_json", get_json)
    discovery._search()

    assert "wb=101939" in searches[-1] and "lc=164461" in searches[-1]
    assert not discovery.issues
    discovery.close()


def test_trendyol_trace_explains_skipped_search_cards(monkeypatch):
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    monkeypatch.setattr(
        discovery, "_search", lambda: (fixture("trendyol_search.json"), {})
    )
    groups, _, complete = discovery._search_candidates()
    decisions = {
        entry["id"]: entry["decision"]
        for entry in discovery.trace
        if entry["kind"] == "search_card"
    }
    assert decisions == {11: "accepted", 12: "other_model", 13: "excluded_word"}
    assert groups == {"7": "11"}
    assert complete
    discovery.close()


def test_hepsiburada_trace_keeps_rejected_page_name(monkeypatch):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    state = {
        "sku": "HBCV00004X9ZCK",
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": fixture("hepsiburada_variants.json")[
            "allVariantCombinations"
        ],
    }
    html = (
        "<html><h1>Apple iPhone 15 Pro 128 GB Mavi</h1><script>"
        f"window.DATA = {json.dumps(state)};"
        "</script></html>"
    )
    monkeypatch.setattr(discovery, "get", lambda url: html)
    with pytest.raises(FetchError):
        discovery._product(
            "https://www.hepsiburada.com/apple-iphone-15-pro-p-HBCV00004X9ZCK",
            "HBCV00004X9ZCK",
        )
    page = next(entry for entry in discovery.trace if entry["kind"] == "product_page")
    assert page["names"] == ["Apple iPhone 15 Pro 128 GB Mavi"]
    discovery.close()


def test_hepsiburada_group_card_resolves_to_verified_variant(monkeypatch):
    # Canlı iPhone 15 model sayfasındaki 6. kart: -pm- grup bağlantısı.
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    variant = {
        "sku": "HBCV0000D3AULB",
        "Kapasite": None,
        "Renk": "Siyah",
        "urlName": "apple-iphone-15-siyah-128gb",
    }
    state = {
        "sku": "HBCV0000D3AULB",
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": [variant],
    }
    identity = {
        "@type": "Product",
        "name": "Apple iphone 15 Siyah",
        "sku": "HBCV0000D3AULB",
    }
    pages = {
        "ara?": (
            '<a href="/iphone-15-iphone-ios-telefonlar-xc-60005202-t3">iPhone 15</a>'
        ),
        "-xc-": (
            '<a title="Apple iphone 15 Siyah 128GB" '
            'href="/iphone-15-siyah-128gb-pm-HBC0000D3AULA">Ürün</a>'
        ),
        "-pm-": (
            "<script>window.DATA = "
            f"{json.dumps({'allVariantCombinations': [variant]})};</script>"
        ),
        "-p-": (
            f'<script type="application/ld+json">{json.dumps(identity)}</script>'
            "<h1>Apple iphone 15 Siyah 128GB</h1>"
            f"<script>window.DATA = {json.dumps(state)};</script>"
        ),
    }
    requested = []

    def get(url):
        requested.append(url)
        return next(html for marker, html in pages.items() if marker in url)

    def blocked(query, cards):
        raise FetchError("blocked", "HTTP 403")

    monkeypatch.setattr(discovery, "get", get)
    monkeypatch.setattr(discovery, "_api", blocked)
    result = discovery.discover()

    assert [item.platform_product_id for item in result.candidates] == [
        "HBCV0000D3AULB"
    ]
    assert result.candidates[0].storage_gb == 128
    assert result.candidates[0].color == "Siyah"
    assert result.candidates[0].url.endswith(
        "apple-iphone-15-siyah-128gb-p-HBCV0000D3AULB"
    )
    assert [issue.reason for issue in result.issues] == ["search_api"]
    assert any("-pm-HBC0000D3AULA" in url for url in requested)
    discovery.close()


def test_hepsiburada_variant_identity(monkeypatch):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    items = fixture("hepsiburada_variants.json")["allVariantCombinations"]
    state = {
        "sku": "HBCV00004X9ZCK",
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": items,
    }
    html = (
        "<html><h1>Apple iPhone 15 128 GB Mavi</h1><script>"
        f"window.DATA = {json.dumps(state)};"
        "</script></html>"
    )
    monkeypatch.setattr(discovery, "get", lambda url: html)
    candidate, found = discovery._product(
        "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
        "HBCV00004X9ZCK",
    )
    assert candidate.storage_gb == 128
    assert candidate.color == "Mavi"
    assert len(found) == 3
    with pytest.raises(FetchError):
        discovery._product(candidate.url, "HBCVWRONG")

    # Canlı S24 verisindeki gibi SKU'su boş bir varyant kaydı taramayı çökertmez.
    state["allVariantCombinations"] = [{"sku": None, "Renk": None}, *items]
    html = (
        "<html><h1>Apple iPhone 15 128 GB Mavi</h1><script>"
        f"window.DATA = {json.dumps(state)};"
        "</script></html>"
    )
    candidate, _ = discovery._product(candidate.url, "HBCV00004X9ZCK")
    assert candidate.color == "Mavi"
    discovery.close()


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


def test_run_writes_report_and_valid_link_despite_conflict(tmp_path, monkeypatch):
    # Gerçek run(): kilitli/atomik katalog yazımı ve rapor, geçici klasörde.
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_text(
        json.dumps(
            {
                "targets": [
                    {"key": "apple_iphone_15", "brand": "Apple", "model": "iPhone 15"}
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CATALOG_PATH", str(catalog_file))
    monkeypatch.setenv("DISCOVERY_PATH", str(discovery_file))
    monkeypatch.setenv("RUNTIME_PATH", str(CATALOG.parent / "runtime.json"))
    monkeypatch.chdir(tmp_path)
    conflicting, valid = conflict_candidates()

    def adapter(platform, found):
        class Fixed(BaseDiscovery):
            hosts = ["www.example.com"]

            def discover(self):
                return DiscoveryResult(
                    platform=platform,
                    target_key=self.target.key,
                    candidates=found,
                    complete=True,
                )

        Fixed.platform = platform
        return Fixed

    report = run(
        adapters={
            "trendyol": adapter("trendyol", [conflicting]),
            "hepsiburada": adapter("hepsiburada", [valid]),
        }
    )

    assert not report.complete
    assert [issue.reason for issue in report.rejected] == ["catalog_conflict"]
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    saved = Catalog.model_validate_json(catalog_file.read_text(encoding="utf-8"))
    original = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    assert len(saved.listings) == len(original.listings) + 1
    assert saved.products == original.products
    written = json.loads(
        (tmp_path / "data" / "discovery_report.json").read_text("utf-8")
    )
    assert written["rejected"][0]["reason"] == "catalog_conflict"


def test_catalog_merge_preserves_listings_missing_from_current_search():
    catalog = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    updated, products, listings, existing, _ = merge_catalog(catalog, [])
    assert updated == catalog
    assert not products and not listings and not existing


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


def test_hepsiburada_keeps_html_cards_when_api_is_blocked(monkeypatch):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    html = (
        '<a href="/iphone-15-iphone-ios-telefonlar-xc-60005202-t3">'
        "iPhone 15</a>"
        '<a title="Apple iPhone 15 128 GB" '
        'href="/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK">Ürün</a>'
    )
    monkeypatch.setattr(discovery, "get", lambda url: html)

    def blocked(query, cards):
        raise FetchError("blocked", "HTTP 403")

    monkeypatch.setattr(discovery, "_api", blocked)
    cards = discovery._search()
    assert list(cards) == ["HBCV00004X9ZCK"]
    assert discovery.issues[0].reason == "search_api"

    # API engellenmek yerine bozuk yanıt dönerse de HTML kartları korunur.
    monkeypatch.undo()
    monkeypatch.setattr(discovery, "get", lambda url: html)
    malformed = {
        "currentPage": 1,
        "products": [
            {
                "brand": "Apple",
                "mainCategory": {"name": "Cep Telefonu"},
                "variantList": ["bozuk kayıt"],
            }
        ],
    }
    monkeypatch.setattr(discovery, "get_json", lambda url, headers=None: malformed)
    discovery.issues = []
    cards = discovery._search()
    assert list(cards) == ["HBCV00004X9ZCK"]
    assert [(i.reason, i.detail) for i in discovery.issues] == [
        ("search_api", "AttributeError")
    ]
    discovery.close()


def test_trendyol_malformed_search_response_is_reported(monkeypatch):
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    # Marka kaydında "key" alanı eksik: eskiden bütün keşif raporsuz çöküyordu.
    malformed = {"products": [], "canonicalFilters": {"brands": [{"name": "Apple"}]}}
    monkeypatch.setattr(discovery, "get", lambda url, headers=None: "")
    monkeypatch.setattr(discovery, "get_json", lambda url, headers=None: malformed)

    result = discovery.discover()

    assert not result.candidates and not result.complete
    assert [(i.reason, i.detail) for i in result.issues] == [
        ("search_fetch", "KeyError")
    ]
    discovery.close()


def test_hepsiburada_canonical_url_must_stay_on_platform(monkeypatch):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    state = {
        "sku": "HBCV00004X9ZCK",
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": fixture("hepsiburada_variants.json")[
            "allVariantCombinations"
        ],
    }
    url = "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK"

    def page(canonical):
        return (
            f'<html><link rel="canonical" href="{canonical}">'
            "<h1>Apple iPhone 15 128 GB Mavi</h1>"
            f"<script>window.DATA = {json.dumps(state)};</script></html>"
        )

    foreign = "https://m.hepsiburada.com/iphone-15-mavi-p-HBCV00004X9ZCK"
    monkeypatch.setattr(discovery, "get", lambda link: page(foreign))
    candidate, _ = discovery._product(url, "HBCV00004X9ZCK")
    assert candidate.url == url

    same_site = "https://www.hepsiburada.com/iphone-15-mavi-p-HBCV00004X9ZCK"
    monkeypatch.setattr(discovery, "get", lambda link: page(same_site))
    candidate, _ = discovery._product(url, "HBCV00004X9ZCK")
    assert candidate.url == same_site
    discovery.close()


class Response:
    status_code = 418
    headers = {}
    content = b""


class Session:
    def request(self, *args, **kwargs):
        return Response()

    def close(self):
        pass


def test_http_418_is_blocked():
    client = PageClient(
        ["www.trendyol.com"], Runtime(request_interval_seconds=0), client=Session()
    )
    with pytest.raises(FetchError) as error:
        client.get("https://www.trendyol.com/")
    assert error.value.code == "blocked"


def test_discovery_budget_is_enforced_by_http_layer():
    # Keşifte ayrı sayaç yok; bütçe PageClient'a keşif ayarından verilir.
    discovery = TrendyolDiscovery(
        target(),
        DiscoveryConfig(targets=[], max_requests=1),
        Runtime(request_interval_seconds=0, request_attempts=1),
    )
    discovery.pages.client = Session()
    with pytest.raises(FetchError) as first:
        discovery.get("https://www.trendyol.com/")
    assert first.value.code == "blocked"
    with pytest.raises(FetchError) as second:
        discovery.get("https://www.trendyol.com/")
    assert second.value.code == "limit"
    assert discovery.pages.request_count == 1
    discovery.close()


def test_http_budget_counts_actual_attempts():
    client = PageClient(
        ["www.trendyol.com"],
        Runtime(request_interval_seconds=0),
        client=Session(),
        request_budget=1,
    )
    with pytest.raises(FetchError) as first:
        client.get("https://www.trendyol.com/")
    assert first.value.code == "blocked"
    assert client.request_count == 1
    with pytest.raises(FetchError) as second:
        client.get("https://www.trendyol.com/")
    assert second.value.code == "limit"
    assert client.request_count == 1
