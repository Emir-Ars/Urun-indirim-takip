"""Hepsiburada keşif adaptörü: HTML kartları, arama API'si, kimlik."""

import json
from html import escape
from urllib.parse import parse_qs, urlsplit

import pytest

from app.contracts import DiscoveryCandidate, DiscoveryConfig, DiscoveryTarget
from app.discovery.hepsiburada import Discovery as HepsiburadaDiscovery
from app.scraper.http import FetchError
from app.settings import Runtime
from tests.support.discovery import fixture, network_target, target


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


def hepsiburada_variant_html(
    variant_lists, *, sku="HBCV00004X9ZCK", name="Apple iPhone 15"
):
    state = {
        "sku": sku,
        "brand": "Apple",
        "definitionName": "Cep Telefonu",
        "allVariantCombinations": variant_lists[0],
    }
    html = (
        f"<h1>{escape(name)}</h1>"
        f'<script type="application/json">{json.dumps(state)}</script>'
    )
    for variants in variant_lists[1:]:
        state = {"allVariantCombinations": variants}
        html += f'<script type="application/json">{json.dumps(state)}</script>'
    return html


@pytest.mark.parametrize(
    ("capacity", "color"),
    [("256 GB", "Mavi"), ("128 GB", "Siyah"), ("256 GB", "Siyah")],
    ids=["capacity", "color", "both"],
)
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("same_list", [False, True])
def test_hepsiburada_variant_lists_reject_conflicting_identity(
    monkeypatch, capacity, color, reverse, same_list
):
    sku = "HBCV00004X9ZCK"
    variants = [
        {"sku": sku, "Kapasite": "128 GB", "Renk": "Mavi"},
        {"sku": sku, "Kapasite": capacity, "Renk": color},
    ]
    if reverse:
        variants.reverse()
    variant_lists = [variants] if same_list else [[item] for item in variants]
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"), DiscoveryConfig(targets=[]), Runtime()
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: hepsiburada_variant_html(variant_lists)
    )
    try:
        with pytest.raises(FetchError) as error:
            discovery._product(f"https://www.hepsiburada.com/iphone-15-p-{sku}", sku)
        assert error.value.code == "identity"
    finally:
        discovery.close()


@pytest.mark.parametrize(
    ("variant_lists", "capacity", "color", "name"),
    [
        (
            [[{"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"}]] * 2,
            128,
            "Mavi",
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": "HBCV00004X9ZCK", "Kapasite": "1 TB", "Renk": "Yeşil"}],
                [{"sku": "hbcv00004x9zck", "Kapasite": "1024 GB", "Renk": " YESIL "}],
            ],
            1024,
            "Yeşil",
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": "HBCV00004X9ZCK"}],
                [{"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"}],
            ],
            128,
            "Mavi",
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": "HBCV00004X9ZCK", "Kapasite": "belirsiz", "Renk": " "}],
                [{"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"}],
            ],
            128,
            "Mavi",
            "Apple iPhone 15",
        ),
        (
            [[{"sku": "HBCV00004X9ZCK"}], [{"sku": "HBCV00004X9ZCK", "Renk": None}]],
            128,
            "",
            "Apple iPhone 15 128 GB",
        ),
        (
            [
                [
                    {"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"},
                    {"sku": "HBCVOTHER", "Kapasite": "128 GB", "Renk": "Siyah"},
                ],
                [
                    {"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"},
                    {"sku": "HBCVOTHER", "Kapasite": "256 GB", "Renk": "Mavi"},
                ],
            ],
            128,
            "Mavi",
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": "HBCV00004X9ZCK", "Kapasite": "128 GB", "Renk": "Mavi"}],
                [{"sku": "HBCVOTHER"}],
            ],
            128,
            "Mavi",
            "Apple iPhone 15",
        ),
    ],
    ids=[
        "duplicate",
        "equivalent",
        "missing",
        "unreadable",
        "title-fallback",
        "other-sku",
        "earlier-list",
    ],
)
def test_hepsiburada_variant_lists_accept_consistent_identity(
    monkeypatch, variant_lists, capacity, color, name
):
    sku = "HBCV00004X9ZCK"
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"), DiscoveryConfig(targets=[]), Runtime()
    )
    monkeypatch.setattr(
        discovery, "get", lambda url: hepsiburada_variant_html(variant_lists, name=name)
    )
    try:
        candidate, found = discovery._product(
            f"https://www.hepsiburada.com/iphone-15-p-{sku}", sku
        )
        assert (candidate.storage_gb, candidate.color) == (capacity, color)
        assert found == variant_lists[-1]
    finally:
        discovery.close()


def test_hepsiburada_variant_conflict_does_not_stop_other_candidates(monkeypatch):
    bad_sku = "HBCV00004X9ZCK"
    good_sku = "HBCV00004X9ZCN"
    urls = {
        sku: f"https://www.hepsiburada.com/iphone-15-p-{sku}"
        for sku in (good_sku, bad_sku)
    }
    pages = {
        urls[bad_sku]: hepsiburada_variant_html(
            [
                [{"sku": bad_sku, "Kapasite": "128 GB", "Renk": "Mavi"}],
                [{"sku": bad_sku, "Kapasite": "256 GB", "Renk": "Siyah"}],
            ]
        ),
        urls[good_sku]: hepsiburada_variant_html(
            [[{"sku": good_sku, "Kapasite": "128 GB", "Renk": "Mavi"}]], sku=good_sku
        ),
    }
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"), DiscoveryConfig(targets=[]), Runtime()
    )
    monkeypatch.setattr(discovery, "_search", lambda: urls.copy())
    monkeypatch.setattr(discovery, "get", pages.__getitem__)
    try:
        result = discovery.discover()
        assert [c.platform_product_id for c in result.candidates] == [good_sku]
        assert [i.reason for i in result.issues] == ["candidate_rejected"]
        assert bad_sku in result.issues[0].detail
        assert not result.complete
    finally:
        discovery.close()


HEPSIBURADA_IDENTITY_EXAMPLES = fixture("hepsiburada_identity_examples.json")


@pytest.mark.parametrize(
    "example",
    HEPSIBURADA_IDENTITY_EXAMPLES["pages"],
    ids=lambda example: example["sku"],
)
def test_hepsiburada_saved_variant_identity_preserves_candidate(monkeypatch, example):
    html = (
        f'<script type="application/ld+json">{json.dumps(example["json_ld"])}</script>'
    )
    if example["heading"] is not None:
        html += f'<h1>{escape(example["heading"])}</h1>'
    if example["canonical"] is not None:
        html += (
            f'<link rel="canonical" href="{escape(example["canonical"], quote=True)}">'
        )
    html += f'<script type="application/json">{json.dumps(example["details"])}</script>'
    for index in example["variant_list_indexes"]:
        state = {
            "allVariantCombinations": HEPSIBURADA_IDENTITY_EXAMPLES["variant_lists"][
                index
            ]
        }
        html += f'<script type="application/json">{json.dumps(state)}</script>'
    discovery = HepsiburadaDiscovery(
        DiscoveryTarget.model_validate(example["target"]),
        DiscoveryConfig(targets=[]),
        Runtime(),
    )
    monkeypatch.setattr(discovery, "get", lambda url: html)
    try:
        if example["expected_error"]:
            with pytest.raises(FetchError) as error:
                discovery._product(example["url"], example["sku"])
            assert error.value.code == example["expected_error"]
            assert "Sayfadaki model hedefle eşleşmiyor" in str(error.value)
        else:
            candidate, _ = discovery._product(example["url"], example["sku"])
            assert candidate.model_dump(mode="json") == example["expected_candidate"]
    finally:
        discovery.close()


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


@pytest.mark.parametrize(
    "canonical, use_canonical",
    [
        ("https://www.hepsiburada.com/other-p-HBCV00004X9ZCKX", False),
        ("https://www.hepsiburada.com/HBCV00004X9ZCK/other-p-HBCV00000000", False),
        (
            "https://www.hepsiburada.com/other-p-HBCV00000000?ref=HBCV00004X9ZCK",
            False,
        ),
        ("https://www.hepsiburada.com/other?ref=phone-p-HBCV00004X9ZCK", False),
        ("https://www.hepsiburada.com/other-p-HBCV00004X9ZCK", True),
        ("https://www.hepsiburada.com/other-p-HBCV00004X9ZCK?ref=1", True),
        ("https://www.hepsiburada.com/other-p-HBCV00004X9ZCK/", True),
        ("https://www.hepsiburada.com/other-p-hbcv00004x9zck", True),
        ("https://www.hepsiburada.com/other-pm-HBC000123", False),
        ("https://www.hepsiburada.com/apple-iphone-15-cep-telefonlari", False),
        ("https://m.hepsiburada.com/other-p-HBCV00004X9ZCK", False),
        (None, False),
    ],
)
def test_hepsiburada_canonical_requires_exact_path_sku(
    monkeypatch, canonical, use_canonical
):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"), DiscoveryConfig(targets=[]), Runtime()
    )
    sku = "HBCV00004X9ZCK"
    url = "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-" + sku
    state = {
        "sku": sku,
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": fixture("hepsiburada_variants.json")[
            "allVariantCombinations"
        ],
    }
    html = "<h1>Apple iPhone 15 128 GB Mavi</h1>"
    if canonical is not None:
        html += f'<link rel="canonical" href="{escape(canonical, quote=True)}">'
    html += f'<script type="application/json">{json.dumps(state)}</script>'
    monkeypatch.setattr(discovery, "get", lambda link: html)
    try:
        candidate, _ = discovery._product(url, sku)
        assert candidate.url == (canonical if use_canonical else url)
        assert candidate.platform_product_id == sku
        assert (candidate.storage_gb, candidate.color) == (128, "Mavi")
    finally:
        discovery.close()


def test_hepsiburada_wrong_canonical_keeps_discovery_candidate(monkeypatch):
    discovery = HepsiburadaDiscovery(
        target("iPhone 15"), DiscoveryConfig(targets=[]), Runtime()
    )
    sku = "HBCV00004X9ZCK"
    url = "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-" + sku
    canonical = url + "X"
    state = {
        "sku": sku,
        "definitionName": "Cep Telefonu",
        "brand": "Apple",
        "allVariantCombinations": [{"sku": sku, "Kapasite": "128 GB", "Renk": "Mavi"}],
    }
    html = (
        f'<link rel="canonical" href="{canonical}">'
        "<h1>Apple iPhone 15 128 GB Mavi</h1>"
        f'<script type="application/json">{json.dumps(state)}</script>'
    )
    monkeypatch.setattr(discovery, "_search", lambda: {sku: url})
    monkeypatch.setattr(discovery, "get", lambda link: html)
    try:
        result = discovery.discover()
        assert [item.url for item in result.candidates] == [url]
        assert result.complete and result.issues == []
    finally:
        discovery.close()
