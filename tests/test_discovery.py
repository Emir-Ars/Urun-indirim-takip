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
from app.discovery.base import BaseDiscovery, error_code
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
    network_type,
    storage_gb,
    title_storage,
    verify_identity,
)
from app.settings import Runtime

FIXTURES = Path(__file__).parent / "fixtures" / "discovery"
CONFIG = Path(__file__).parents[1] / "config"
# Gerçek katalog keşifle değişir; testler 25 Eylül 2026 tarihli sabit kopyayı okur.
CATALOG = FIXTURES / "catalog.json"


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
    # "RAM" etiketli değer hafıza sayılmaz; canlı örnek: Galaxy S25 128 GB.
    assert title_storage("iPhone 16 8 GB RAM 256 GB") == 256
    assert title_storage("Samsung Galaxy S25 128 GB 12 GB Ram (Türkiye)") == 128
    assert title_storage("Redmi Note 14 Pro 12GB+512GB Siyah") is None  # etiketsiz
    assert matches_model("Samsung Galaxy S24 8 GB RAM 256 GB", "Galaxy S24")
    assert not matches_model("Samsung Galaxy S24 Ultra 256 GB", "Galaxy S24")


def test_variant_words_separate_models():
    # Katalog hedeflerindeki kardeş modeller birbirine karışmamalı.
    for title, model in (
        ("Samsung Galaxy S25 Edge 256 GB", "Galaxy S25"),
        ("Apple iPhone 17 Air 256 GB", "iPhone 17"),
        ("Samsung Galaxy S24 FE 128 GB", "Galaxy S24"),
        ("Samsung Galaxy S24+ 256 GB", "Galaxy S24"),
        ("Samsung Galaxy S24 Ultra 256 GB", "Galaxy S24"),
        ("Xiaomi Redmi Note 14 Pro+ 5G 512 GB", "Redmi Note 14 Pro 5G"),
        ("Xiaomi Redmi Note 14 Pro 5G 256 GB", "Redmi Note 14 Pro 4G"),
        ("Xiaomi 14T 512 GB", "14T Pro"),
        ("Xiaomi 14T Pro 512 GB", "14T"),
    ):
        assert not matches_model(title, model), (title, model)
    for title, model in (
        ("Samsung Galaxy S25 Edge 256 GB", "Galaxy S25 Edge"),
        ("Apple iPhone Air 256 GB", "iPhone Air"),
        ("Samsung Galaxy S24FE 128 GB", "Galaxy S24 FE"),
        ("Xiaomi Redmi Note 14 Pro 5G 256 GB", "Redmi Note 14 Pro 5G"),
        ("Xiaomi Redmi Note 13 Pro 4G 256 GB", "Redmi Note 13 Pro 4G"),
        ("Xiaomi 14T Pro 12 GB 512 GB", "14T Pro"),
        ("Xiaomi POCO X6 Pro 5G 256 GB", "POCO X6 Pro"),
    ):
        assert matches_model(title, model), (title, model)


def test_underscore_separated_titles():
    # Canlı Trendyol adı: "_" regex'te harf sayıldığı için "Ultra" görülmüyor ve
    # sayfa hem S25 hem S25 Ultra hedefine giriyordu (catalog_conflict).
    title = "Galaxy S25 Ultra_12GB_256GB Gri"
    assert not matches_model(title, "Galaxy S25")
    assert matches_model(title, "Galaxy S25 Ultra")
    assert identify([title], "Galaxy S25 Ultra", 256) == 256
    assert not matches_model("Galaxy S25 Kılıf_Şeffaf", "Galaxy S25")


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
    # Canlı Hepsiburada başlığı: 4G telefon "4.5G Mobil Bağlantı" diye yazılır.
    assert (
        excluded_term(["Redmi Note 14 Pro 256 GB 4.5G Mobil Bağlantı"], ["5G"]) is None
    )
    assert excluded_term(["Redmi Note 14 Pro 5G 512 GB"], ["5G"]) == "5G"

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

    def candidate(url, product_id, variant_color=None):
        return DiscoveryCandidate(
            target_key=iphone_15.key,
            platform="trendyol",
            platform_product_id=product_id,
            url=url,
            brand="Apple",
            model="iPhone 15",
            storage_gb=256,
            color=variant_color or "Sarı",
        )

    monkeypatch.setattr(discovery, "_candidate", candidate)
    result = discovery.discover()
    # Varyant listesindeki renk adı adaya taşınır; listede olmayan kart kendi rengini
    # kullanır.
    assert {item.platform_product_id: item.color for item in result.candidates} == {
        "11": "Black",
        "14": "Black",
        "762254849": "Sarı",
    }
    discovery.close()


def test_trendyol_color_prefers_page_color_selector(monkeypatch):
    # Canlı örnek: sayfanın renk seçicisinde "Abis", ürün özelliğinde "Çok Renkli".
    discovery = TrendyolDiscovery(
        DiscoveryTarget(
            key="apple_iphone_17_pro_max", brand="Apple", model="iPhone 17 Pro Max"
        ),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    product = {
        "id": 985256830,
        "name": "iPhone 17 Pro Max 256GB Abis",
        "brand": {"name": "Apple"},
        "category": {"name": "iPhone IOS Cep Telefonları"},
        "attributes": [
            {"key": {"name": "Renk"}, "value": {"name": "Çok Renkli"}},
            {"key": {"name": "Dahili Hafıza"}, "value": {"name": "256 GB"}},
        ],
    }
    html = (
        "<html><body><script>"
        f"window['__envoy__SHARED_PROPS'] = {json.dumps({'product': product})};"
        "</script></body></html>"
    )
    monkeypatch.setattr(discovery, "get", lambda url: html)
    url = "https://www.trendyol.com/apple/iphone-17-pro-max-256gb-abis-p-985256830"

    assert discovery._candidate(url, "985256830", "Abis").color == "Abis"
    assert discovery._candidate(url, "985256830").color == "Çok Renkli"
    discovery.close()


def test_network_type_values():
    assert network_type("4G") == "4G"
    assert network_type("4.5G") == "4G"  # Hepsiburada 4G telefonları böyle yazar
    assert network_type("5G") == "5G"
    for value in ("5G+", "5G NR", "4G/5G"):  # 5G desteği söyleyen her değer
        assert network_type(value) == "5G", value
    assert network_type(None) is None and network_type("3G") is None


def test_foreign_version_pages_are_out_of_scope():
    # Canlı örnek: trendyol_991304922, iPhone 16 128 GB karşılaştırmasına giriyordu.
    for title in (
        "iPhone 16 128GB Teal 5G with FaceTime International Version",
        "Xiaomi 14T Pro 512 GB Global Version",
        "Redmi Note 14 Pro 256 GB Yurt Dışı Sürüm",
    ):
        with pytest.raises(FetchError, match="yurt dışı"):
            identify([title], "iPhone 16")  # kapsam kontrolü modelden önce yapılır
    assert identify(["Apple iPhone 16 128 GB Deniz Mavisi"], "iPhone 16") == 128


def network_target():
    return DiscoveryTarget(
        key="xiaomi_redmi_note_14_pro_4g",
        brand="Xiaomi",
        model="Redmi Note 14 Pro",
        network="4G",
        exclude_terms=["5G"],
    )


def test_trendyol_network_target_checks_page_attribute(monkeypatch):
    # Canlı örnek: başlıkta 4G yok; "Mobil Bağlantı Hızı" özelliği 4G / 5G diyor.
    discovery = TrendyolDiscovery(
        network_target(),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )

    def page(network):
        attributes = [{"key": {"name": "Dahili Hafıza"}, "value": {"name": "256 GB"}}]
        if network:
            attributes.append(
                {"key": {"name": "Mobil Bağlantı Hızı"}, "value": {"name": network}}
            )
        product = {
            "id": 891692674,
            "name": "Redmi Note 14 Pro 8+256 Siyah (Xiaomi Türkiye Garantili)",
            "brand": {"name": "Xiaomi"},
            "category": {"name": "Android Cep Telefonu"},
            "attributes": attributes,
        }
        state = json.dumps({"product": product})
        return f"<script>window['__envoy__SHARED_PROPS'] = {state};</script>"

    url = "https://www.trendyol.com/xiaomi/redmi-note-14-pro-8-256-siyah-p-891692674"
    monkeypatch.setattr(discovery, "get", lambda url: page("4G"))
    assert discovery._candidate(url, "891692674").storage_gb == 256
    # Satıcılar alanı çoğu zaman boş bırakır: alanı olmayan sayfa 4G sayılır.
    monkeypatch.setattr(discovery, "get", lambda url: page(None))
    assert discovery._candidate(url, "891692674").storage_gb == 256
    # Yalnız açıkça 5G yazan özellik reddedilir.
    monkeypatch.setattr(discovery, "get", lambda url: page("5G"))
    with pytest.raises(FetchError, match="Ağ türü"):
        discovery._candidate(url, "891692674")
    # Başlıkta "5G" varsa özellik boş olsa da exclude_terms ile reddedilir.
    monkeypatch.setattr(
        discovery,
        "get",
        lambda url: page(None).replace("Pro 8+256", "Pro 5G 8+256"),
    )
    with pytest.raises(FetchError, match="5G"):
        discovery._candidate(url, "891692674")
    discovery.close()


def test_hepsiburada_network_target_reads_page_property(monkeypatch):
    # Canlı örnek: Hepsiburada özellik kaydı {"name": "Mobil Bağlantı Hızı",
    # "property": "4.5G"}; başlıktaki "4.5G" değil, bu kayıt kullanılır.
    discovery = HepsiburadaDiscovery(
        network_target(),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    sku = "HBCV00008KX994"

    def page(network):
        state = {
            "sku": sku,
            "definitionName": "Cep Telefonu",
            "brand": "Xiaomi",
            "allVariantCombinations": [
                {"sku": sku, "Kapasite": "256 GB", "Renk": "Siyah"}
            ],
            "properties": [{"name": "Mobil Bağlantı Hızı", "property": network}],
        }
        return (
            "<html><h1>Xiaomi Redmi Note 14 Pro Akıllı Telefon 8 GB RAM 256 GB Siyah"
            " 4.5G Mobil Bağlantı Hızı</h1><script>"
            f"window.DATA = {json.dumps(state)};</script></html>"
        )

    url = f"https://www.hepsiburada.com/xiaomi-redmi-note-14-pro-p-{sku}"
    monkeypatch.setattr(discovery, "get", lambda url: page("4.5G"))
    candidate, _ = discovery._product(url, sku)
    assert candidate.storage_gb == 256
    monkeypatch.setattr(discovery, "get", lambda url: page("5G"))
    with pytest.raises(FetchError, match="Ağ türü"):
        discovery._product(url, sku)
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

    def gone(url, product_id, variant_color=None):
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
    monkeypatch.setenv("RUNTIME_PATH", str(CONFIG / "runtime.json"))
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


def test_trendyol_search_skips_html_search_page(monkeypatch):
    # Canlıda www.trendyol.com/sr HTTP 403 ile engelleniyordu; içeriği kullanılmaz.
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    opened, api_headers = [], []
    first = {"products": [], "_links": {"aggregation": "https://apigw.trendyol.com/a"}}
    aggregations = {
        "aggregation": [
            {"filterKey": "WebBrand", "values": [{"id": 101470, "text": "Apple"}]},
            {
                "filterKey": "LeafCategory",
                "values": [{"id": 164462, "text": "iPhone IOS Cep Telefonları"}],
            },
        ]
    }

    def get_json(url, headers=None):
        api_headers.append(headers["Referer"])
        return aggregations if url.endswith("/a") else first

    monkeypatch.setattr(
        discovery, "get", lambda url, headers=None: opened.append(url) or ""
    )
    monkeypatch.setattr(discovery, "get_json", get_json)
    discovery._search()

    assert opened == ["https://www.trendyol.com/"]
    assert "lc=164462" in api_headers[-1]  # filtreli istek yine Referer taşır
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


def test_request_interval_is_shared_between_clients(monkeypatch):
    # Canlı kontrol her bağlantı için yeni istemci açıyor; aynı siteye iki istek
    # arasında bekleme yine uygulanmalı, başka siteye geçerken beklenmemeli.
    import app.scraper.http as http

    slept = []
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    monkeypatch.setattr(http.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(http.time, "sleep", slept.append)

    class Ok:
        status_code = 200
        headers = {}
        content = b"ok"

    class Quiet(Session):
        def request(self, *args, **kwargs):
            return Ok()

    runtime = Runtime(request_interval_seconds=3)
    for host in ("www.trendyol.com", "www.trendyol.com", "www.hepsiburada.com"):
        PageClient([host], runtime, client=Quiet()).get(f"https://{host}/")
    assert slept == [3.0]


def test_cookie_conflict_is_treated_as_missing():
    # curl_cffi, aynı adlı çerez iki alt alan adında farklıysa hata verir.
    from curl_cffi.requests.cookies import CookieConflict

    class Jar:
        def get(self, name):
            raise CookieConflict("iki alan adında aynı çerez")

    class WithCookies(Session):
        cookies = Jar()

    client = PageClient(
        ["www.hepsiburada.com"], Runtime(request_interval_seconds=0), WithCookies()
    )
    assert client.cookie("hbus_anonymousId") is None


def test_http_418_is_blocked():
    client = PageClient(
        ["www.trendyol.com"], Runtime(request_interval_seconds=0), client=Session()
    )
    with pytest.raises(FetchError) as error:
        client.get("https://www.trendyol.com/sr?q=iphone")
    assert error.value.code == "blocked"
    # Raporda engelin türü ve yeri görünür: 429 hız sınırı, 403 erişim reddi.
    assert error_code(error.value) == (
        "blocked: Kaynak HTTP 418 döndürdü (www.trendyol.com/sr)"
    )
    assert error_code(KeyError("key")) == "KeyError"


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
