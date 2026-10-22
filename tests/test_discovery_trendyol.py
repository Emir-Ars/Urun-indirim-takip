"""Trendyol keşif adaptörü: arama, sayfalama, varyantlar, gerçek örnekler."""

import json
from copy import deepcopy

import pytest

from app.contracts import DiscoveryCandidate, DiscoveryConfig, DiscoveryTarget
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.http import FetchError
from app.scraper.parsing import identify, title_storage, verify_identity
from app.settings import Runtime
from tests.support.discovery import fixture, network_target, target


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


def test_trendyol_failed_aggregation_reports_filter_unavailable_once(monkeypatch):
    # Filtre isteği hata verince kategori de bulunamaz; aynı uyarı iki kez yazılmaz
    # ve ayrıntılı olan (hata kodu ve mesajı) kalır.
    discovery = trendyol_discovery()
    first = {
        "products": [],
        "_links": {"aggregation": "https://apigw.trendyol.com/aggregation"},
    }

    def get_json(url, headers=None):
        if "aggregation" in url:
            raise FetchError("network", "bağlantı koptu")
        return first

    monkeypatch.setattr(discovery, "get", lambda url, headers=None: "")
    monkeypatch.setattr(discovery, "get_json", get_json)
    discovery._search()
    assert [(issue.reason, issue.detail) for issue in discovery.issues] == [
        ("filter_unavailable", "network: bağlantı koptu")
    ]
    discovery.close()


def test_trendyol_without_aggregation_link_reports_missing_category_filter(
    monkeypatch,
):
    discovery = trendyol_discovery()
    monkeypatch.setattr(discovery, "get", lambda url, headers=None: "")
    monkeypatch.setattr(
        discovery, "get_json", lambda url, headers=None: {"products": []}
    )
    discovery._search()
    assert [(issue.reason, issue.detail) for issue in discovery.issues] == [
        ("filter_unavailable", "Telefon kategori filtresi bulunamadı")
    ]
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


TRENDYOL_IDENTITY_EXAMPLES = fixture("trendyol_identity_examples.json")


def trendyol_identity_html(product):
    return (
        '<script>window["__envoy__SHARED_PROPS"] = '
        f"{json.dumps({'product': product})};</script>"
    )


TRENDYOL_SCOPE_EXAMPLES = fixture("trendyol_scope_examples.json")
TRENDYOL_NETWORK_EXAMPLES = fixture("trendyol_network_examples.json")


def test_trendyol_saved_network_conflict_rejects_candidate(monkeypatch):
    example = TRENDYOL_NETWORK_EXAMPLES["conflicting_product"]
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_NETWORK_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: trendyol_identity_html(example["product"])
    )
    try:
        assert discovery.target.network is None
        with pytest.raises(FetchError, match="Ağ türü") as error:
            discovery._candidate(example["url"], str(example["product"]["id"]))
        assert error.value.code == "identity"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "example",
    TRENDYOL_NETWORK_EXAMPLES["consistent_products"],
    ids=lambda example: str(example["product"]["id"]),
)
def test_trendyol_saved_network_preserves_candidate(monkeypatch, example):
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_NETWORK_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: trendyol_identity_html(example["product"])
    )
    try:
        candidate = discovery._candidate(example["url"], str(example["product"]["id"]))
        assert candidate.model_dump(mode="json") == example["expected_candidate"]
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "value, accepted",
    [
        (None, True),
        ("", True),
        ("3G", True),
        ("5G", True),
        ("5G+", True),
        ("5G NR", True),
        ("4G/5G", True),
        ("4G", False),
        ("4.5G", False),
        ("4,5G", False),
        ("LTE", False),
        ("4G LTE", False),
    ],
)
def test_trendyol_derived_network_values_control_candidate(
    monkeypatch, value, accepted
):
    example = TRENDYOL_NETWORK_EXAMPLES["consistent_products"][0]
    product = deepcopy(example["product"])
    product["attributes"] = [
        item
        for item in product["attributes"]
        if item["key"]["name"] != "Mobil Bağlantı Hızı"
    ]
    if value is not None:
        product["attributes"].append(
            {"key": {"name": "Mobil Bağlantı Hızı"}, "value": {"name": value}}
        )
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_NETWORK_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(discovery, "get", lambda url: trendyol_identity_html(product))
    try:
        if accepted:
            candidate = discovery._candidate(example["url"], str(product["id"]))
            assert candidate.model_dump(mode="json") == example["expected_candidate"]
        else:
            with pytest.raises(FetchError, match="Ağ türü") as error:
                discovery._candidate(example["url"], str(product["id"]))
            assert error.value.code == "identity"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "example",
    TRENDYOL_SCOPE_EXAMPLES["graded_cards"],
    ids=lambda example: str(example["card"]["id"]),
)
def test_saved_yenilio_grade_titles_reject_identity(example):
    name = example["card"]["name"]
    capacity = title_storage(name)
    assert capacity in (128, 256)
    with pytest.raises(FetchError, match="kapsam dışında") as discovery_error:
        identify([name], "iPhone 15 Pro", capacity)
    with pytest.raises(FetchError, match="kapsam dışında") as scraper_error:
        verify_identity([name], "iPhone 15 Pro", capacity, capacity)
    assert discovery_error.value.code == scraper_error.value.code == "identity"


@pytest.mark.parametrize(
    "example",
    TRENDYOL_SCOPE_EXAMPLES["graded_cards"],
    ids=lambda example: str(example["card"]["id"]),
)
def test_trendyol_saved_yenilio_grade_cards_are_excluded(example):
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_SCOPE_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    try:
        assert discovery._card_reason(example["card"]) == "excluded_word"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "example",
    TRENDYOL_SCOPE_EXAMPLES["graded_products"],
    ids=lambda example: str(example["product"]["id"]),
)
def test_trendyol_saved_yenilio_grade_product_is_rejected(monkeypatch, example):
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_SCOPE_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: trendyol_identity_html(example["product"])
    )
    try:
        with pytest.raises(FetchError, match="kapsam dışında") as error:
            discovery._candidate(example["url"], str(example["product"]["id"]))
        assert error.value.code == "identity"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "example",
    TRENDYOL_SCOPE_EXAMPLES["new_products"],
    ids=lambda example: str(example["product"]["id"]),
)
def test_trendyol_saved_new_phone_scope_preserves_candidate(monkeypatch, example):
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(TRENDYOL_SCOPE_EXAMPLES["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: trendyol_identity_html(example["product"])
    )
    try:
        candidate = discovery._candidate(example["url"], str(example["product"]["id"]))
        assert candidate.platform_product_id == str(example["product"]["id"])
        assert candidate.model == example["listing"]["model"]
        assert candidate.storage_gb == example["listing"]["storage_gb"]
        assert candidate.warranty_text == "Apple Türkiye Garantili"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "example",
    TRENDYOL_IDENTITY_EXAMPLES,
    ids=lambda example: str(example["product"]["id"]),
)
def test_trendyol_saved_address_identity_preserves_candidate(monkeypatch, example):
    discovery = TrendyolDiscovery(
        DiscoveryTarget.model_validate(example["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: trendyol_identity_html(example["product"])
    )
    try:
        candidate = discovery._candidate(
            example["url"], str(example["product"]["id"]), example["variant_color"]
        )
        assert candidate.model_dump(mode="json") == example["expected_candidate"]
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "path",
    [
        "/apple/iphone-15",
        "/apple/iphone-15-p-999",
        "/apple/iphone-15-p-762254881abc",
        "/apple/iphone-15?redirect=other-p-762254881",
        "/apple/iphone-15-p-999?redirect=other-p-762254881",
    ],
)
def test_trendyol_candidate_rejects_wrong_address_before_request(monkeypatch, path):
    discovery = trendyol_discovery()
    opened = []

    def get(url):
        opened.append(url)
        return trendyol_identity_html(TRENDYOL_IDENTITY_EXAMPLES[0]["product"])

    monkeypatch.setattr(discovery, "get", get)
    try:
        with pytest.raises(FetchError) as error:
            discovery._candidate("https://www.trendyol.com" + path, "762254881")
        assert error.value.code == "identity"
        assert "adres" in str(error.value)
        assert opened == []
        assert discovery.product_pages == 1
    finally:
        discovery.close()


@pytest.mark.parametrize("suffix", ["", "?merchantId=1", "/", "/?merchantId=1"])
def test_trendyol_candidate_accepts_matching_address(monkeypatch, suffix):
    discovery = trendyol_discovery()
    example = TRENDYOL_IDENTITY_EXAMPLES[0]
    opened = []

    def get(url):
        opened.append(url)
        return trendyol_identity_html(example["product"])

    monkeypatch.setattr(discovery, "get", get)
    url = example["url"] + suffix
    try:
        candidate = discovery._candidate(url, "762254881", example["variant_color"])
        expected = {**example["expected_candidate"], "url": url}
        assert candidate.model_dump(mode="json") == expected
        assert opened == [url]
    finally:
        discovery.close()


def test_trendyol_matching_address_still_checks_opened_page_id(monkeypatch):
    discovery = trendyol_discovery()
    example = TRENDYOL_IDENTITY_EXAMPLES[0]
    product = {**example["product"], "id": 999}
    monkeypatch.setattr(discovery, "get", lambda url: trendyol_identity_html(product))
    try:
        with pytest.raises(FetchError, match="ürün kimliği uyuşmuyor") as error:
            discovery._candidate(example["url"], "762254881")
        assert error.value.code == "identity"
    finally:
        discovery.close()


@pytest.mark.parametrize("path", ["/apple/iphone-15", "/apple/iphone-15-p-999"])
def test_trendyol_wrong_variant_address_keeps_other_candidates(monkeypatch, path):
    discovery = trendyol_discovery()
    example = TRENDYOL_IDENTITY_EXAMPLES[0]
    monkeypatch.setattr(
        discovery,
        "_search_candidates",
        lambda: ({"7": "762254881"}, {"762254881": example["url"]}, True),
    )
    variants = {
        "isSuccess": True,
        "statusCode": 200,
        "result": [{"values": [{"products": [{"id": 123, "pageUrl": path}]}]}],
    }
    monkeypatch.setattr(discovery, "get_json", lambda url: variants)
    opened = []

    def get(url):
        opened.append(url)
        product = {
            **example["product"],
            "id": 762254881 if url == example["url"] else 123,
        }
        return trendyol_identity_html(product)

    monkeypatch.setattr(discovery, "get", get)
    try:
        result = discovery.discover()
        assert [item.platform_product_id for item in result.candidates] == ["762254881"]
        assert opened == [example["url"]]
        assert [issue.reason for issue in result.issues] == ["candidate_rejected"]
        assert (
            result.issues[0].detail == "123: Trendyol adres kimliği kaynakla uyuşmuyor"
        )
        assert discovery.product_pages == 2 and not result.complete
    finally:
        discovery.close()
