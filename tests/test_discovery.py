"""Keşfin kimlik, sayfalama ve katalog sürekliliği kontrolleri."""

import codecs
import io
import json
import sys
import types
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from app.contracts import (
    Catalog,
    DiscoveryCandidate,
    DiscoveryConfig,
    DiscoveryReport,
    DiscoveryResult,
    DiscoveryTarget,
)
from app.discovery.__main__ import main as discovery_main
from app.discovery.base import BaseDiscovery
from app.discovery.hepsiburada import Discovery as HepsiburadaDiscovery
from app.discovery.matching import phone_category
from app.discovery.service import (
    _adapter,
    merge_catalog,
    observed_colors,
    retained_unobserved_listings,
    run,
)
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.http import FetchError
from app.scraper.parsing import (
    excluded_term,
    identify,
    matches_model,
    network_type,
    storage_gb,
    title_storage,
    verify_identity,
)
from app.settings import Runtime, Settings

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


def test_trendyol_search_uses_response_cursor(monkeypatch):
    discovery = TrendyolDiscovery(
        target(), DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    first = fixture("trendyol_search.json")
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
    # Kart adresindeki sorgu dizesi (boutiqueId, merchantId) atılır.
    assert cards == {"11": "https://www.trendyol.com/apple/iphone-16-128-gb-siyah-p-11"}
    assert "offsetParameters=Product_3" in calls[0]
    assert complete
    discovery.close()


def test_trendyol_opens_each_variant_once_and_keeps_unlisted_search_card(
    monkeypatch,
):
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
    opened = []

    def candidate(url, product_id, variant_color=None):
        opened.append(product_id)
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
    # "11" hem renk hem kapasite ekseninde görünür; sayfası yine bir kez açılır.
    assert sorted(opened) == ["11", "14", "762254849"]
    # Varyant listesindeki renk adı adaya taşınır; listede olmayan kart kendi rengini
    # kullanır.
    assert {item.platform_product_id: item.color for item in result.candidates} == {
        "11": "Black",
        "14": "Black",
        "762254849": "Sarı",
    }
    assert result.complete
    discovery.close()


def trendyol_discovery(**config):
    """Ağa çıkmayan testler için iPhone 15 hedefli Trendyol keşfi."""
    return TrendyolDiscovery(
        DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15"),
        DiscoveryConfig(targets=[], **config),
        Runtime(request_interval_seconds=0),
    )


def search_page(ids, *, total=None, next_url=None, page_index=1):
    """Trendyol arama API'si yanıtı biçiminde, kabul edilen kartlardan bir sayfa."""
    return {
        "products": [
            {
                "id": item,
                "name": "Apple iPhone 15 128 GB Siyah",
                "brand": "Apple",
                "category": {"name": "iPhone IOS Cep Telefonları"},
                "groupId": item,
                "url": f"/apple/iphone-15-128-gb-siyah-p-{item}?boutiqueId=61",
            }
            for item in ids
        ],
        "pageIndex": page_index,
        "total": total,
        "_links": {"next": next_url},
    }


def test_trendyol_search_reports_count_mismatch_when_cards_are_missing(monkeypatch):
    # Canlıda reklam kartları sayfaları kaydırır; toplamın gerisinde kalan kart
    # sayısı taramayı kısmi yapar, bulunan kartlar yine kullanılır.
    discovery = trendyol_discovery()
    first = search_page([1, 2, 3], total=5)
    monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
    _, cards, complete = discovery._search_candidates()
    assert complete is False
    assert [(i.reason, i.detail) for i in discovery.issues] == [
        ("count_mismatch", "3 / 5")
    ]
    assert sorted(cards) == ["1", "2", "3"]
    discovery.close()


def test_trendyol_search_stops_when_next_page_repeats_same_cards(monkeypatch):
    discovery = trendyol_discovery()
    first = search_page(
        [1, 2], total=4, next_url="https://apigw.trendyol.com/search?pi=2"
    )
    calls = []

    def get_json(url, headers=None):
        calls.append(url)
        return search_page(
            [1, 2],
            total=4,
            next_url="https://apigw.trendyol.com/search?pi=3",
            page_index=2,
        )

    monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
    monkeypatch.setattr(discovery, "get_json", get_json)
    _, _, complete = discovery._search_candidates()
    assert complete is False
    assert [(i.reason, i.detail) for i in discovery.issues] == [
        ("repeated_page", "Sayfa 2")
    ]
    assert len(calls) == 1  # tekrarlanan sayfada durdu, üçüncü sayfaya gitmedi
    discovery.close()


def test_trendyol_search_rejects_foreign_or_repeated_next_link(monkeypatch):
    # Başka alan adına giden "sonraki" bağlantısı hiç açılmaz.
    discovery = trendyol_discovery()
    first = search_page([1], next_url="https://www.example.com/search?pi=2")
    opened = []
    monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
    monkeypatch.setattr(
        discovery, "get_json", lambda url, headers=None: opened.append(url)
    )
    _, _, complete = discovery._search_candidates()
    assert complete is False
    assert [i.reason for i in discovery.issues] == ["repeated_page"]
    assert opened == []
    discovery.close()

    # Yeni kart getirse de aynı "sonraki" bağlantısını tekrar veren sayfada durulur.
    discovery = trendyol_discovery()
    same_next = "https://apigw.trendyol.com/search?pi=2"
    first = search_page([1], next_url=same_next)
    calls = []

    def get_json(url, headers=None):
        calls.append(url)
        return search_page([2], next_url=same_next, page_index=2)

    monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
    monkeypatch.setattr(discovery, "get_json", get_json)
    _, cards, complete = discovery._search_candidates()
    assert complete is False
    assert [i.reason for i in discovery.issues] == ["repeated_page"]
    assert len(calls) == 1
    assert sorted(cards) == ["1", "2"]
    discovery.close()


def test_trendyol_search_reports_page_limit_without_fetching_extra_page(
    monkeypatch,
):
    # Sınır N ise N sayfa çekilir; N+1. sayfa işlenmeyeceği için hiç istenmez.
    def run_search(limit, second_next):
        discovery = trendyol_discovery(max_search_pages=limit)
        first = search_page([1], next_url="https://apigw.trendyol.com/search?pi=2")
        calls = []

        def get_json(url, headers=None):
            calls.append(url)
            return search_page([2], next_url=second_next, page_index=2)

        monkeypatch.setattr(discovery, "_search", lambda: (first, {}))
        monkeypatch.setattr(discovery, "get_json", get_json)
        _, cards, complete = discovery._search_candidates()
        discovery.close()
        return discovery, calls, cards, complete

    # İlk sayfa _search'ten gelir; sınır 1 iken başka sayfa istenmez.
    discovery, calls, cards, complete = run_search(1, None)
    assert calls == []
    assert discovery.search_pages == 1 and sorted(cards) == ["1"]
    assert complete is False
    assert [i.reason for i in discovery.issues] == ["search_limit"]

    discovery, calls, cards, complete = run_search(
        2, "https://apigw.trendyol.com/search?pi=3"
    )
    assert len(calls) == 1  # yalnız 2. sayfa; 3. sayfa istenmedi
    assert discovery.search_pages == 2 and sorted(cards) == ["1", "2"]
    assert complete is False
    assert [i.reason for i in discovery.issues] == ["search_limit"]

    # Son sayfa tam sınırda biterse (sonraki bağlantı yok) tarama tamdır.
    discovery, calls, cards, complete = run_search(2, None)
    assert len(calls) == 1 and sorted(cards) == ["1", "2"]
    assert complete is True and discovery.issues == []


def fixed_candidate(product_id, url):
    return DiscoveryCandidate(
        target_key="apple_iphone_15",
        platform="trendyol",
        platform_product_id=product_id,
        url=url,
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
        color="Siyah",
    )


CARD_URL = "https://www.trendyol.com/apple/iphone-15-128-gb-siyah-p-762254881"


@pytest.mark.parametrize(
    "variants, detail",
    [
        # Grup için hiç seçenek dönmedi: kardeş sayfalar bilinmiyor.
        ({"isSuccess": True, "statusCode": 200, "result": []}, None),
        (
            {"isSuccess": False, "statusCode": 500},
            "7: parse: Trendyol seçenek yanıtı başarısız",
        ),
        (
            FetchError("blocked", "Kaynak HTTP 429 döndürdü"),
            "7: blocked: Kaynak HTTP 429 döndürdü",
        ),
    ],
)
def test_trendyol_variant_problem_is_partial_but_keeps_search_card(
    monkeypatch, variants, detail
):
    discovery = trendyol_discovery()
    monkeypatch.setattr(
        discovery,
        "_search_candidates",
        lambda: ({"7": "762254881"}, {"762254881": CARD_URL}, True),
    )

    def get_json(url):
        if isinstance(variants, Exception):
            raise variants
        return variants

    monkeypatch.setattr(discovery, "get_json", get_json)
    monkeypatch.setattr(
        discovery,
        "_candidate",
        lambda url, product_id, variant_color=None: fixed_candidate(product_id, url),
    )
    result = discovery.discover()
    assert [item.platform_product_id for item in result.candidates] == ["762254881"]
    expected = (
        ("missing_variants", "7") if detail is None else ("variant_fetch", detail)
    )
    assert [(i.reason, i.detail) for i in result.issues] == [expected]
    assert result.complete is False
    discovery.close()


def test_trendyol_product_page_limit_stops_opening_pages(monkeypatch):
    discovery = trendyol_discovery(max_product_pages=1)
    second_url = CARD_URL.replace("762254881", "762254862")
    monkeypatch.setattr(
        discovery,
        "_search_candidates",
        lambda: ({}, {"762254881": CARD_URL, "762254862": second_url}, True),
    )

    def candidate(url, product_id, variant_color=None):
        discovery.product_pages += 1  # gerçek _candidate gibi açılan sayfayı sayar
        return fixed_candidate(product_id, url)

    monkeypatch.setattr(discovery, "_candidate", candidate)
    result = discovery.discover()
    assert [item.platform_product_id for item in result.candidates] == ["762254881"]
    assert [i.reason for i in result.issues] == ["product_limit"]
    assert result.complete is False
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
    groups, cards, complete = discovery._search_candidates()
    decisions = {
        entry["id"]: entry["decision"]
        for entry in discovery.trace
        if entry["kind"] == "search_card"
    }
    assert decisions == {11: "accepted", 12: "other_model", 13: "excluded_word"}
    assert groups == {"7": "11"}
    # Yalnız kabul edilen kart aday adresi olur; sorgu dizesi atılır.
    assert cards == {"11": "https://www.trendyol.com/apple/iphone-16-128-gb-siyah-p-11"}
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


def fixed_adapter(platform, found):
    """Ağa çıkmayan keşif adaptörü: verilen adayları tam tarama olarak döndürür."""

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


def conflict_adapters():
    conflicting, valid = conflict_candidates()
    return {
        "trendyol": fixed_adapter("trendyol", [conflicting]),
        "hepsiburada": fixed_adapter("hepsiburada", [valid]),
    }


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    """Gerçek run() için geçici katalog, discovery.json ve çalışma klasörü.

    Rapor tmp_path/data altına yazılır; gerçek config ve data klasörüne dokunulmaz.
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_text(
        json.dumps(
            {
                "targets": [
                    {"key": "apple_iphone_15", "brand": "Apple", "model": "iPhone 15"},
                    {
                        "key": "poco_x5_pro",
                        "brand": "POCO",
                        "model": "X5 Pro",
                        "active": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CATALOG_PATH", str(catalog_file))
    monkeypatch.setenv("DISCOVERY_PATH", str(discovery_file))
    monkeypatch.setenv("RUNTIME_PATH", str(CONFIG / "runtime.json"))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(tmp_path / "scrape.lock"))
    monkeypatch.chdir(tmp_path)
    return catalog_file


def test_run_writes_report_and_valid_link_despite_conflict(run_env, tmp_path):
    # Gerçek run(): kilitli/atomik katalog yazımı ve rapor, geçici klasörde.
    report = run(adapters=conflict_adapters())

    assert not report.complete
    assert [issue.reason for issue in report.rejected] == ["catalog_conflict"]
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    saved = Catalog.model_validate_json(run_env.read_text(encoding="utf-8"))
    original = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    assert len(saved.listings) == len(original.listings) + 1
    assert saved.products == original.products
    written = json.loads(
        (tmp_path / "data" / "discovery_report.json").read_text("utf-8")
    )
    assert written["rejected"][0]["reason"] == "catalog_conflict"


def test_run_writes_catalog_with_lf_line_endings(run_env):
    # Windows'ta metin kipi "\n"yi CRLF'ye çevirir; katalog her yazımda LF kalmalı
    # ki bütün satırlar Git'te değişmiş görünmesin. (Başlangıç dosyası Windows'ta
    # write_text ile CRLF yazılmıştır; yeniden yazım onu LF'ye çevirir.)
    run(adapters=conflict_adapters())
    written = run_env.read_bytes()
    assert b"\r\n" not in written
    assert written.endswith(b"}\n")


def test_dry_run_writes_report_but_not_catalog(run_env, tmp_path):
    before = run_env.read_bytes()
    report = run(dry_run=True, adapters=conflict_adapters())

    assert run_env.read_bytes() == before
    assert not (tmp_path / "catalog.json.lock").exists()  # katalog kilidi alınmadı
    # Önizleme yine ne ekleneceğini ve çakışmayı gösterir.
    assert report.dry_run is True
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    assert not report.complete
    written = json.loads(
        (tmp_path / "data" / "discovery_report.json").read_text("utf-8")
    )
    assert written["dry_run"] is True


def test_run_reads_catalog_and_config_saved_with_bom(run_env, tmp_path):
    # Windows'ta bazı düzenleyiciler UTF-8 dosyanın başına BOM koyar; json bunu
    # geçersiz sayardı. Hem önizleme hem kilit altındaki ikinci okuma kabul etmeli.
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_bytes(codecs.BOM_UTF8 + discovery_file.read_bytes())
    run_env.write_bytes(codecs.BOM_UTF8 + CATALOG.read_bytes())

    report = run(dry_run=True, adapters=conflict_adapters())
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    assert run_env.read_bytes().startswith(codecs.BOM_UTF8)  # önizleme yazmadı

    report = run(adapters=conflict_adapters())
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    saved = Catalog.model_validate_json(run_env.read_text(encoding="utf-8"))
    assert "hepsiburada_hbcv0000test01" in {item.listing_id for item in saved.listings}


def test_settings_read_runtime_and_discovery_saved_with_bom(tmp_path, monkeypatch):
    runtime_file = tmp_path / "runtime.json"
    runtime_file.write_bytes(
        codecs.BOM_UTF8 + json.dumps({"request_interval_seconds": 5}).encode()
    )
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_bytes(
        codecs.BOM_UTF8
        + json.dumps(
            {"targets": [{"key": "apple_iphone_15", "brand": "Apple", "model": "Ç"}]},
            ensure_ascii=False,
        ).encode("utf-8")
    )
    monkeypatch.setenv("RUNTIME_PATH", str(runtime_file))
    monkeypatch.setenv("DISCOVERY_PATH", str(discovery_file))
    settings = Settings()
    assert settings.runtime().request_interval_seconds == 5
    assert settings.discovery().targets[0].model == "Ç"


def test_run_rejects_unknown_or_inactive_target(run_env):
    # adapters={}: hedef süzgeci bozulsa bile test siteye gidemez (KeyError olur).
    for key in ("olmayan_hedef", "poco_x5_pro"):
        with pytest.raises(ValueError, match="bulunamadı"):
            run(dry_run=True, target_key=key, adapters={})


def test_adapter_loads_only_valid_platform_modules(monkeypatch):
    assert _adapter("trendyol") is TrendyolDiscovery
    assert _adapter("hepsiburada") is HepsiburadaDiscovery
    for key in ("../x", "Trendyol", "app.discovery.trendyol"):
        with pytest.raises(ValueError, match="Geçersiz"):
            _adapter(key)
    with pytest.raises(ImportError):
        _adapter("yok_platform")
    # Discovery adı olmayan modül de (ör. ortak taban) sözleşme hatasıdır; komut
    # bunu çıkış 1'e çevirir, traceback basmaz.
    for key in ("base", "matching"):
        with pytest.raises(ValueError, match="sözleşmeye uymuyor"):
            _adapter(key)
    # Discovery adı olan ama sözleşmeye uymayan (sınıf değil / soyut) modül.
    for implementation in (object(), BaseDiscovery):
        monkeypatch.setitem(
            sys.modules,
            "app.discovery.sahte",
            types.SimpleNamespace(Discovery=implementation),
        )
        with pytest.raises(ValueError, match="sözleşmeye uymuyor"):
            _adapter("sahte")


@pytest.mark.parametrize("complete, code", [(True, 0), (False, 2)])
def test_discovery_cli_exits_0_when_complete_and_2_when_partial(
    run_env, monkeypatch, capsys, complete, code
):
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return DiscoveryReport(complete=complete, dry_run=kwargs["dry_run"], results=[])

    monkeypatch.setattr("app.discovery.__main__.run", fake_run)
    assert discovery_main(["--dry-run", "--target", "apple_iphone_15"]) == code
    assert calls == [{"dry_run": True, "target_key": "apple_iphone_15"}]
    printed = json.loads(capsys.readouterr().out)
    assert printed["complete"] is complete and printed["dry_run"] is True


class RecordingStream(io.StringIO):
    """reconfigure çağrılarını kaydeden sahte stdout/stderr."""

    def __init__(self):
        super().__init__()
        self.reconfigured = []

    def reconfigure(self, **kwargs):
        self.reconfigured.append(kwargs)


def test_discovery_cli_switches_output_to_utf8(run_env, monkeypatch):
    # Çıktı dosyaya yönlendirildiğinde Windows kod sayfası Türkçe karakterleri
    # bozardı; hata çıktısı da dahil iki akış UTF-8'e ayarlanır.
    monkeypatch.setattr(
        "app.discovery.__main__.run",
        lambda **kwargs: DiscoveryReport(complete=True, dry_run=True, results=[]),
    )
    out, err = RecordingStream(), RecordingStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert discovery_main(["--dry-run"]) == 0
    expected = [{"encoding": "utf-8", "errors": "backslashreplace"}]
    assert out.reconfigured == expected and err.reconfigured == expected
    assert json.loads(out.getvalue())["complete"] is True

    # pythonw.exe altında akışlar hiç yoktur (None); komut yine çalışır.
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert discovery_main(["--dry-run"]) == 0


def test_discovery_cli_exits_1_for_unknown_target(run_env, capsys):
    # Gerçek run(): hedef bulunamayınca hiçbir adaptör kurulmadan hata verir.
    assert discovery_main(["--target", "olmayan_hedef", "--dry-run"]) == 1
    error = capsys.readouterr().err
    assert "Keşif başlatılamadı" in error and "olmayan_hedef" in error


def test_real_config_files_match_contracts():
    # Kullanıcı discovery.json'u elle düzenler: JSON yazım hatası, tekrarlanan hedef
    # anahtarı veya geçersiz network değeri canlı keşiften önce burada yakalanır.
    # Yalnız okunur; gerçek katalog keşifle büyüdüğü için sayılar denetlenmez.
    config = DiscoveryConfig.model_validate_json(
        (CONFIG / "discovery.json").read_text(encoding="utf-8")
    )
    catalog = Catalog.model_validate_json(
        (CONFIG / "catalog.json").read_text(encoding="utf-8")
    )
    assert config.targets and catalog.products and catalog.listings
    # Her etkin platformun keşif modülü vardır (yalnız içe aktarılır, istek yok).
    for platform in catalog.platforms:
        if platform.active:
            assert issubclass(_adapter(platform.key), BaseDiscovery)


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


def hepsiburada_discovery(**config):
    return HepsiburadaDiscovery(
        target("iPhone 15"),
        DiscoveryConfig(targets=[], **config),
        Runtime(request_interval_seconds=0),
    )


def api_blocked(query, cards):
    raise FetchError("blocked", "HTTP 403")


HB_MODEL_LINK = (
    '<a href="/iphone-15-iphone-ios-telefonlar-xc-60005202-t3">iPhone 15</a>'
)
HB_CARD = (
    '<a title="Apple iPhone 15 128 GB" '
    'href="/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK">Ürün</a>'
)


def test_hepsiburada_without_model_filter_uses_search_page_cards(monkeypatch):
    discovery = hepsiburada_discovery()
    opened = []
    monkeypatch.setattr(discovery, "get", lambda url: opened.append(url) or HB_CARD)
    monkeypatch.setattr(discovery, "_api", api_blocked)
    cards = discovery._search()
    assert list(cards) == ["HBCV00004X9ZCK"]
    assert [i.reason for i in discovery.issues] == [
        "model_filter_missing",
        "search_api",
    ]
    assert discovery.search_pages == 1 and len(opened) == 1
    discovery.close()


def test_hepsiburada_reports_html_partial_when_cards_fall_short_of_total(
    monkeypatch,
):
    # Canlı örnek: Galaxy S25 model sayfası 140 üründen yalnız ilk 36 kartı gösterir.
    def model_page(total):
        state = json.dumps({"data": {"totalProductCount": total}})
        return f"{HB_CARD}<script>window.STATE = {state};</script>"

    for total, expected in (
        (140, [("html_partial", "HTML: 1 / 140")]),
        (1, []),  # bütün kartlar görünüyorsa uyarı yok
    ):
        discovery = hepsiburada_discovery()
        pages = {"ara?": HB_MODEL_LINK, "-xc-": model_page(total)}
        monkeypatch.setattr(
            discovery,
            "get",
            lambda url: next(html for key, html in pages.items() if key in url),
        )
        monkeypatch.setattr(discovery, "_api", api_blocked)
        cards = discovery._search()
        assert list(cards) == ["HBCV00004X9ZCK"]
        assert [(i.reason, i.detail) for i in discovery.issues] == expected + [
            ("search_api", "blocked: HTTP 403")
        ]
        assert discovery.search_pages == 2
        discovery.close()


def api_product(brand, category, *variants):
    return {"brand": brand, "mainCategory": {"name": category}, "variantList": variants}


def api_variant(name, sku, url):
    return {"name": name, "sku": sku, "url": url}


def api_pages(pages, calls):
    """Sayfa numarasına göre kayıtlı arama API'si yanıtı döndüren sahte get_json."""

    def get_json(url, headers=None):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        calls.append(page)
        return pages[page]

    return get_json


def test_hepsiburada_search_api_collects_variants_until_last_page(monkeypatch):
    # Arama API'si canlıda engelli (HTTP 403); bir gün açılırsa bu yol ilk kez
    # çalışacağı için kayıtlı biçimde bir yanıtla sınanır.
    pages = {
        1: {
            "currentPage": 1,
            "lastPage": 2,
            "products": [
                api_product(
                    "Apple",
                    "Cep Telefonu",
                    api_variant(
                        "Apple iPhone 15 128 GB Mavi",
                        "hbcv00004x9zck",
                        "/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK?magaza=x",
                    ),
                    api_variant(
                        "Apple iPhone 15 Siyah",
                        "HBCV0000D3AULB",
                        "/iphone-15-siyah-128gb-pm-HBC0000D3AULA",
                    ),
                    api_variant(
                        "Apple iPhone 15 Pro 128 GB",
                        "HBCV0000PRO001",
                        "/apple-iphone-15-pro-128-gb-p-HBCV0000PRO001",
                    ),
                ),
                # Adı telefona benzese de aksesuar kategorisindeki ürün elenir.
                api_product(
                    "Apple",
                    "Cep Telefonu Aksesuarları",
                    api_variant(
                        "Apple iPhone 15 128 GB Siyah",
                        "HBCV0000AKSES1",
                        "/apple-iphone-15-128-gb-siyah-p-HBCV0000AKSES1",
                    ),
                ),
                api_product(
                    "Samsung",
                    "Cep Telefonu",
                    api_variant(
                        "iPhone 15 128 GB",
                        "HBCV0000SAMS01",
                        "/iphone-15-128-gb-p-HBCV0000SAMS01",
                    ),
                ),
            ],
        },
        2: {
            "currentPage": 2,
            "lastPage": 2,
            "products": [
                api_product(
                    "Apple",
                    "Cep Telefonu",
                    api_variant(
                        "Apple iPhone 15 512 GB Pembe",
                        "HBCV0000PEMBE1",
                        "/apple-iphone-15-512-gb-pembe-p-HBCV0000PEMBE1",
                    ),
                ),
            ],
        },
    }
    discovery = hepsiburada_discovery()
    html = {"ara?": HB_MODEL_LINK, "-xc-": "<html>kart yok</html>"}
    monkeypatch.setattr(
        discovery,
        "get",
        lambda url: next(page for key, page in html.items() if key in url),
    )
    calls = []
    monkeypatch.setattr(discovery, "get_json", api_pages(pages, calls))
    cards = discovery._search()

    # Başka model (Pro), aksesuar kategorisi ve başka marka elenir; -pm- kartı grup
    # kimliğiyle girer, SKU büyük harfe çevrilir ve adresin sorgu dizesi atılır.
    assert cards == {
        "HBCV00004X9ZCK": (
            "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK"
        ),
        "HBC0000D3AULA": (
            "https://www.hepsiburada.com/iphone-15-siyah-128gb-pm-HBC0000D3AULA"
        ),
        "HBCV0000PEMBE1": (
            "https://www.hepsiburada.com/apple-iphone-15-512-gb-pembe-p-HBCV0000PEMBE1"
        ),
    }
    assert discovery.issues == []
    assert calls == [1, 2]  # lastPage'de durdu
    assert discovery.search_pages == 4  # arama + model sayfası + 2 API sayfası
    discovery.close()


def test_hepsiburada_search_api_stops_on_repeated_page_or_limit(monkeypatch):
    first = {
        "currentPage": 1,
        "products": [
            api_product(
                "Apple",
                "Cep Telefonu",
                api_variant(
                    "Apple iPhone 15 128 GB Mavi",
                    "HBCV00004X9ZCK",
                    "/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK",
                ),
                # Ne -p- ne -pm- biçiminde: aday olmaz, raporlanır.
                api_variant(
                    "Apple iPhone 15 256 GB Mavi",
                    "HBCV0000GARIP1",
                    "/apple-iphone-15-256-gb-mavi",
                ),
            )
        ],
    }
    # lastPage yok ve ikinci sayfa aynı ürünleri döndürüyor.
    pages = {1: first, 2: {**first, "currentPage": 2}}
    discovery = hepsiburada_discovery()
    calls, cards = [], {}
    monkeypatch.setattr(discovery, "get_json", api_pages(pages, calls))
    discovery._api("Apple iPhone 15", cards)
    assert list(cards) == ["HBCV00004X9ZCK"]
    assert [(i.reason, i.detail) for i in discovery.issues] == [
        ("group_url_pending", "HBCV0000GARIP1"),
        ("repeated_page", "2"),
    ]
    assert calls == [1, 2]
    discovery.close()

    discovery = hepsiburada_discovery(max_search_pages=1)
    calls, cards = [], {}
    monkeypatch.setattr(discovery, "get_json", api_pages(pages, calls))
    discovery._api("Apple iPhone 15", cards)
    assert calls == [1]
    assert [i.reason for i in discovery.issues][-1] == "search_limit"
    discovery.close()


def test_hepsiburada_product_page_limit_stops_queue(monkeypatch):
    discovery = hepsiburada_discovery(max_product_pages=1)
    skus = ("HBCV00004X9ZCK", "HBCV00004X9ZCP")
    monkeypatch.setattr(
        discovery,
        "_search",
        lambda: {sku: f"https://www.hepsiburada.com/iphone-15-p-{sku}" for sku in skus},
    )

    def product(url, sku):
        discovery.product_pages += 1  # gerçek _product gibi açılan sayfayı sayar
        candidate = DiscoveryCandidate(
            target_key="apple_iphone_16",
            platform="hepsiburada",
            platform_product_id=sku,
            url=url,
            brand="Apple",
            model="iPhone 15",
            storage_gb=128,
        )
        return candidate, []

    monkeypatch.setattr(discovery, "_product", product)
    result = discovery.discover()
    assert len(result.candidates) == 1
    assert [i.reason for i in result.issues] == ["product_limit"]
    assert result.complete is False
    discovery.close()


@pytest.mark.parametrize(
    "category",
    [
        "Cep Telefonu",
        "iPhone IOS Cep Telefonları",
        "Android Cep Telefonu",
        "Smartphone",
        "Mobile Phone",
    ],
)
def test_phone_category_accepts_new_phone_categories(category):
    assert phone_category(category)


@pytest.mark.parametrize(
    "category",
    [
        # Her biri "cep telefon" içerir; hariç tutma listesinin her terimi sınanır.
        "Cep Telefonu Aksesuarları",
        "Cep Telefonu Kılıfı",
        "Cep Telefonu Şarj Aleti",
        "Cep Telefonu Arka Kapak",
        "Yenilenmiş Cep Telefonu",
        "İkinci El Cep Telefonu",
        "Refurbished Mobile Phone",
        # Telefon kategorisi değil.
        "Tablet",
        "",
    ],
)
def test_phone_category_rejects_accessory_used_and_other_categories(category):
    assert not phone_category(category)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Bulgu: 'kapak' terimi Türkçe çekimli 'Kapağı'yı yakalamıyor (normalize "
        "'kapagi' üretir); 'Cep Telefonu Kapağı' telefon kategorisi sayılıyor."
    ),
)
def test_phone_category_rejects_inflected_cover_category():
    assert not phone_category("Cep Telefonu Kapağı")


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
