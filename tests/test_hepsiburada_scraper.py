import json
from uuid import UUID

import pytest

from app.contracts import ProductListing
from app.scraper.hepsiburada_scraper import API_URL, LISTINGS_URL, Scraper
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime

URL = "https://www.hepsiburada.com/apple-iphone-15-128-gb-mavi-p-HBCV00004X9ZCK"
SKU = "HBCV00004X9ZCK"


class FakeResponse:
    def __init__(self, *, status=200, text="", data=None):
        self.status_code = status
        self.content = text.encode() if data is None else json.dumps(data).encode()
        self.headers = {}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = {"hbus_anonymousId": "test-user"}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        kwargs["content_callback"](response.content)
        return response

    def close(self):
        pass


@pytest.fixture
def listing():
    return ProductListing(
        listing_id="hepsiburada_iphone_15_128gb_mavi",
        product_id=1,
        platform="hepsiburada",
        url=URL,
        color="Mavi",
        active=True,
        product_name="Apple iPhone 15 128 GB",
        model="iPhone 15",
        storage_gb=128,
    )


def page_html(*, name="Apple iPhone 15 128 GB Mavi", variants=None):
    context = {
        "productTags": [],
        "sku": SKU,
        "productId": "HBC00004X9ZCG",
        "brand": "Apple",
        "rootCategoryList": [60005202],
        "rootBuyingCategoryList": [60005202],
        "definitionName": "Cep Telefonu",
        "definitionId": "60",
        "taxVatRate": 20,
        "campaignIds": [],
        "otherMerchants": [],
    }
    identity = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "sku": SKU,
    }
    variant_state = {"allVariantCombinations": variants or []}
    return (
        "<html><body>"
        f'<script type="application/ld+json">{json.dumps(identity)}</script>'
        f'<script type="application/json">{json.dumps(context)}</script>'
        f'<script type="application/json">{json.dumps(variant_state)}</script>'
        "</body></html>"
    )


def redux_page_html():
    """Canlı stoksuz sayfadaki gibi: ana satıcının fiyatı yok, stok dışı."""
    context = {
        "sku": SKU,
        "productId": "HBC00004X9ZCG",
        "brand": "Apple",
        "definitionName": "Cep Telefonu",
        "definitionId": 60,
        "taxVatRate": 20,
        "campaignIds": [],
        "mainProductTagList": [],
        "rootCategoryList": [{"categoryId": 60005202}],
        "listings": [],
        "merchantId": "Hepsiburada",
        "merchantName": "Hepsiburada",
        "listingId": "",
        "prices": None,
        "isInStock": False,
    }
    identity = {"@type": "Product", "name": "Apple  iPhone 15 128", "sku": SKU}
    variants = {"allVariantCombinations": [{"sku": SKU, "Kapasite": "128 GB"}]}
    return (
        "<html><body>"
        f'<script type="application/ld+json">{json.dumps(identity)}</script>'
        f"<script>window.STATE = {json.dumps(context)};</script>"
        f'<script type="application/json">{json.dumps(variants)}</script>'
        "</body></html>"
    )


def full_listing(listing_id, seller, price, *, salable=True, tags=None, rating=9.5):
    return {
        "listingId": listing_id,
        "merchantId": f"merchant-{listing_id}",
        "merchantName": seller,
        "isSalable": salable,
        "price": {"value": price},
        "originalPrice": {"value": price},
        "minimumPrice": {"value": price},
        "campaignIds": [],
        "tagList": [{"tagId": tag} for tag in (tags or [])],
        "ratingSummary": {"lifetimeRating": rating, "ratingQuantity": 5},
    }


def api_response(offers, *, sku=SKU):
    return {
        "statusCode": 200,
        "data": {"result": {"products": {"sku": sku, "otherMerchants": offers}}},
    }


def response_offer(listing_id, seller, price, *, discounted=None, campaigns=None):
    price_data = {"price": price}
    if discounted is not None:
        price_data["discountedPrice"] = discounted
    return {
        "listingId": listing_id,
        "merchantName": seller,
        "campaigns": campaigns or [],
        "priceData": price_data,
    }


def scraper_with(listings, offers, *, html=None):
    responses = [
        FakeResponse(text=html or page_html()),
        FakeResponse(data={"statusCode": 200, "data": {"listings": listings}}),
        FakeResponse(data=api_response(offers)),
    ]
    session = FakeSession(responses)
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    return Scraper(["www.hepsiburada.com"], runtime, client=session), session


def variant_page_html(variant_lists, *, name="Apple iPhone 15"):
    html = page_html(name=name, variants=variant_lists[0])
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
def test_variant_lists_reject_conflicting_identity(
    listing, capacity, color, reverse, same_list
):
    variants = [
        {"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"},
        {"sku": SKU, "Kapasite": capacity, "Renk": color},
    ]
    if reverse:
        variants.reverse()
    variant_lists = [variants] if same_list else [[item] for item in variants]
    expected_capacity = int(variants[0]["Kapasite"].split()[0])
    listing = listing.model_copy(
        update={
            "storage_gb": expected_capacity,
            "product_name": f"Apple iPhone 15 {expected_capacity} GB",
        }
    )
    scraper, session = scraper_with(
        [full_listing("hb", "Hepsiburada", 50_000)],
        [response_offer("hb", "Hepsiburada", 50_000)],
        html=variant_page_html(variant_lists),
    )

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "identity"
    assert len(session.calls) == 1


@pytest.mark.parametrize(
    ("variant_lists", "capacity", "name"),
    [
        (
            [[{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}]] * 2,
            128,
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": SKU, "Kapasite": "1 TB", "Renk": "Yeşil"}],
                [{"sku": SKU.lower(), "Kapasite": "1024 GB", "Renk": " YESIL "}],
            ],
            1024,
            "Apple iPhone 15",
        ),
        (
            [[{"sku": SKU}], [{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}]],
            128,
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": SKU, "Kapasite": "belirsiz", "Renk": " "}],
                [{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}],
            ],
            128,
            "Apple iPhone 15",
        ),
        ([[{"sku": SKU}], [{"sku": SKU, "Renk": None}]], 128, "Apple iPhone 15 128 GB"),
        (
            [
                [
                    {"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"},
                    {"sku": "HBCVOTHER", "Kapasite": "128 GB", "Renk": "Siyah"},
                ],
                [
                    {"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"},
                    {"sku": "HBCVOTHER", "Kapasite": "256 GB", "Renk": "Mavi"},
                ],
            ],
            128,
            "Apple iPhone 15",
        ),
        (
            [
                [{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}],
                [{"sku": "HBCVOTHER"}],
            ],
            128,
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
def test_variant_lists_accept_consistent_identity(
    listing, variant_lists, capacity, name
):
    listing = listing.model_copy(
        update={
            "storage_gb": capacity,
            "product_name": f"Apple iPhone 15 {capacity} GB",
        }
    )
    scraper, session = scraper_with(
        [full_listing("hb", "Hepsiburada", 50_000)],
        [response_offer("hb", "Hepsiburada", 50_000)],
        html=variant_page_html(variant_lists, name=name),
    )

    observation = scraper.fetch(listing)

    assert observation.current_price == 5_000_000
    assert observation.stock_status == "Stokta Var"
    assert len(session.calls) == 3


def test_fetches_all_listings_and_selects_cheapest(listing):
    listings = [
        full_listing("hb", "Hepsiburada", 57_249.01, rating=0),
        full_listing("other", "Diğer Satıcı", 62_000, rating=9.8),
    ]
    offers = [
        response_offer("hb", "Hepsiburada", 57_249.01),
        response_offer("other", "Diğer Satıcı", 62_000),
    ]
    scraper, session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.current_price == 5_724_901
    # Liste fiyatı satış fiyatına eşit: sayfada üstü çizili fiyat görünmez.
    assert observation.original_price is None
    assert observation.seller_name == "Hepsiburada"
    assert observation.stock_status == "Stokta Var"
    assert [call[:2] for call in session.calls] == [
        ("GET", URL),
        ("GET", LISTINGS_URL.format(sku=SKU)),
        ("POST", API_URL),
    ]
    assert len(session.calls[2][2]["json"]["product"]["otherMerchants"]) == 2
    assert len(scraper._last_offers) == 2
    assert sum(offer["selected"] for offer in scraper._last_offers) == 1


def test_title_without_capacity_uses_variant_capacity(listing):
    # Canlı sayfadaki gibi: JSON-LD adı kapasite birimi içermiyor.
    html = page_html(
        name="Apple  iPhone 15 128",
        variants=[{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}],
    )
    listings = [full_listing("hb", "Hepsiburada", 56_999)]
    offers = [response_offer("hb", "Hepsiburada", 56_999)]
    scraper, _session = scraper_with(listings, offers, html=html)

    observation = scraper.fetch(listing)

    assert observation.current_price == 5_699_900
    assert observation.stock_status == "Stokta Var"


def test_conflicting_page_capacity_is_rejected(listing):
    html = page_html(
        name="Apple iPhone 15 256 GB Mavi",
        variants=[{"sku": SKU, "Kapasite": "128 GB", "Renk": "Mavi"}],
    )
    scraper, session = scraper_with([], [], html=html)

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "identity"
    assert len(session.calls) == 1


def test_filters_conditions_and_uses_discounted_price(listing):
    listings = [
        full_listing("used", "İkinci El Dünyası", 40_000),
        full_listing("display", "Vitrin", 41_000, tags=["teshir-urun"]),
        full_listing("valid", "Geçerli Satıcı", 50_000, rating=9.7),
    ]
    offers = [
        response_offer("used", "İkinci El Dünyası", 40_000),
        response_offer("display", "Vitrin", 41_000),
        response_offer("valid", "Geçerli Satıcı", 50_000, discounted=49_500),
    ]
    scraper, _session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.current_price == 4_950_000
    assert observation.original_price == 5_000_000
    assert observation.seller_name == "Geçerli Satıcı"
    assert observation.seller_rating == 9.7
    assert len(scraper._last_offers) == 3
    assert sum(offer["eligible"] for offer in scraper._last_offers) == 1


def offer_by_id(scraper, listing_id):
    return next(o for o in scraper._last_offers if o["listing_id"] == listing_id)


def test_price_response_campaign_text_rejects_refurbished_offer(listing):
    # Satıcı adı ve etiketleri temiz; "yenilenmiş" yalnız fiyat yanıtındaki kampanya
    # metninde geçiyor. Daha pahalı temiz satıcının seçilmesi, seçimin en ucuz
    # kuralıyla değil ret nedeniyle değiştiğini gösterir.
    listings = [
        full_listing("valid", "Geçerli Satıcı", 50_000),
        full_listing("other", "Diğer Satıcı", 52_000),
    ]
    offers = [
        response_offer(
            "valid",
            "Geçerli Satıcı",
            50_000,
            campaigns=[{"text": "Yenilenmiş ürün"}],
        ),
        response_offer("other", "Diğer Satıcı", 52_000),
    ]
    scraper, session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.seller_name == "Diğer Satıcı"
    assert observation.current_price == 5_200_000
    assert len(session.calls) == 3
    rejected = offer_by_id(scraper, "valid")
    assert rejected["eligible"] is False
    assert rejected["rejection_reason"] == "disallowed_condition"


def test_equal_prices_select_seller_by_name(listing):
    # Kimlik sırası ad sırasının tersi: seçim listingId'ye veya sıraya göre olsaydı
    # Zeta kazanırdı.
    listings = [
        full_listing("1", "Zeta Satıcı", 50_000),
        full_listing("2", "Alfa Satıcı", 50_000),
    ]
    offers = [
        response_offer("1", "Zeta Satıcı", 50_000),
        response_offer("2", "Alfa Satıcı", 50_000),
    ]
    scraper, _session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.seller_name == "Alfa Satıcı"
    assert offer_by_id(scraper, "2")["selected"] is True
    assert offer_by_id(scraper, "1")["selected"] is False


def test_selected_diagnostic_is_marked_when_listing_id_is_integer(listing):
    # API listingId'yi sayı olarak döndürürse de kazanan tanılama kaydı bulunmalı.
    listings = [
        full_listing(12345, "Hepsiburada", 56_999),
        full_listing(67890, "Diğer Satıcı", 58_000),
    ]
    offers = [
        response_offer(12345, "Hepsiburada", 56_999),
        response_offer(67890, "Diğer Satıcı", 58_000),
    ]
    scraper, _session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.seller_name == "Hepsiburada"
    assert offer_by_id(scraper, "12345")["selected"] is True
    assert offer_by_id(scraper, "67890")["selected"] is False


@pytest.mark.parametrize(
    ("seller", "price", "reason"),
    [
        ("Eksik Satıcı", None, "missing_price"),
        (None, 40_000, "missing_seller"),
    ],
    ids=["missing_price", "missing_seller"],
)
def test_price_response_offer_without_price_or_seller_is_diagnosed(
    listing, seller, price, reason
):
    listings = [
        full_listing("broken", "Eksik Satıcı", 40_000),
        full_listing("valid", "Geçerli Satıcı", 50_000),
    ]
    valid_offer = response_offer("valid", "Geçerli Satıcı", 50_000)
    scraper, _session = scraper_with(
        listings, [response_offer("broken", seller, price), valid_offer]
    )
    baseline, _baseline_session = scraper_with(listings, [valid_offer])

    observation = scraper.fetch(listing)

    # Üretim sonucu, bozuk teklif yanıtta hiç yokmuş gibi aynı kalır.
    expected = baseline.fetch(listing)
    assert observation.model_dump(exclude={"timestamp"}) == expected.model_dump(
        exclude={"timestamp"}
    )
    rejected = offer_by_id(scraper, "broken")
    assert rejected["eligible"] is False
    assert rejected["rejection_reason"] == reason
    assert rejected["selected"] is False
    assert offer_by_id(scraper, "valid")["selected"] is True


def test_only_disallowed_salable_seller_is_no_eligible_offer(listing):
    listings = [full_listing("used", "İkinci El Dünyası", 40_000)]
    scraper, session = scraper_with(listings, [])

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "no_eligible_offer"
    assert len(session.calls) == 2  # fiyat isteği gönderilmez
    assert scraper._last_offers[0]["rejection_reason"] == "disallowed_condition"


@pytest.mark.parametrize(
    "missing_fields",
    [["merchantId"], ["price", "originalPrice", "minimumPrice"]],
    ids=["merchant_id", "all_prices"],
)
def test_seller_record_missing_field_is_skipped_as_invalid_offer(
    listing, missing_fields
):
    broken = full_listing("broken", "Eksik Satıcı", 40_000)
    for field in missing_fields:
        del broken[field]
    listings = [broken, full_listing("valid", "Geçerli Satıcı", 50_000)]
    offers = [response_offer("valid", "Geçerli Satıcı", 50_000)]
    scraper, session = scraper_with(listings, offers)

    observation = scraper.fetch(listing)

    assert observation.seller_name == "Geçerli Satıcı"
    sent = session.calls[2][2]["json"]["product"]["otherMerchants"]
    assert [item["listingId"] for item in sent] == ["valid"]
    rejected = offer_by_id(scraper, "broken")
    assert rejected["eligible"] is False
    assert rejected["rejection_reason"] == "invalid_offer"


def test_empty_full_listing_response_is_out_of_stock(listing):
    session = FakeSession(
        [
            FakeResponse(text=page_html()),
            FakeResponse(data={"statusCode": 200, "data": {"listings": []}}),
        ]
    )
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    scraper = Scraper(["www.hepsiburada.com"], runtime, client=session)

    observation = scraper.fetch(listing)

    assert observation.current_price is None
    assert observation.stock_status == "Tükendi"
    assert len(session.calls) == 2


@pytest.mark.parametrize(
    "records",
    [
        [None],
        ["bozuk kayıt"],
        [42],
        [False],
        [[]],
        [full_listing("hb", "Hepsiburada", 56_999, salable=False), None],
        [full_listing("hb", "Hepsiburada", 56_999), None],
    ],
    ids=["null", "text", "number", "bool", "list", "mixed_sold_out", "mixed_salable"],
)
def test_malformed_seller_records_are_parse_errors(listing, records):
    scraper, session = scraper_with(
        records, [response_offer("hb", "Hepsiburada", 56_999)]
    )
    try:
        with pytest.raises(FetchError) as error:
            scraper.fetch(listing)

        assert error.value.code == "parse"
        assert len(session.calls) == 2
    finally:
        scraper.close()


def test_sold_out_page_without_main_price_is_out_of_stock(listing):
    scraper, session = scraper_with([], [], html=redux_page_html())

    observation = scraper.fetch(listing)

    assert observation.stock_status == "Tükendi"
    assert observation.current_price is None
    assert len(session.calls) == 2


def test_other_seller_is_priced_when_main_merchant_is_sold_out(listing):
    listings = [full_listing("other", "Diğer Satıcı", 58_500)]
    offers = [response_offer("other", "Diğer Satıcı", 58_500)]
    scraper, session = scraper_with(listings, offers, html=redux_page_html())

    observation = scraper.fetch(listing)

    assert observation.current_price == 5_850_000
    assert observation.seller_name == "Diğer Satıcı"
    assert len(session.calls[2][2]["json"]["product"]["otherMerchants"]) == 1


def test_empty_price_response_for_salable_listing_is_not_sold_out(listing):
    listings = [full_listing("hb", "Hepsiburada", 56_999)]
    scraper, _session = scraper_with(listings, [])

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "api_error"


def test_missing_stock_signal_is_an_error_not_sold_out(listing):
    # "isSalable" alanı kalkar veya adı değişirse sayfalar sessizce Tükendi olmamalı.
    item = full_listing("hb", "Hepsiburada", 56_999)
    del item["isSalable"]
    scraper, _session = scraper_with([item], [])

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "parse"


def test_every_seller_explicitly_unsalable_is_out_of_stock(listing):
    listings = [full_listing("hb", "Hepsiburada", 56_999, salable=False)]
    scraper, session = scraper_with(listings, [])

    observation = scraper.fetch(listing)

    assert observation.stock_status == "Tükendi"
    assert len(session.calls) == 2  # fiyat isteği gönderilmez


def test_rejects_response_sku_mismatch(listing):
    listings = [full_listing("hb", "Hepsiburada", 57_249.01)]
    scraper, session = scraper_with(
        listings, [response_offer("hb", "Hepsiburada", 57_249.01)]
    )
    session.responses[-1] = FakeResponse(
        data=api_response(
            [response_offer("hb", "Hepsiburada", 57_249.01)],
            sku="HBCV0000000000",
        )
    )

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "identity"


@pytest.mark.parametrize("failing_call", [2, 3], ids=["listings_api", "price_api"])
def test_unsuccessful_api_status_code_is_api_error(listing, failing_call):
    listings = [full_listing("hb", "Hepsiburada", 56_999)]
    scraper, session = scraper_with(
        listings, [response_offer("hb", "Hepsiburada", 56_999)]
    )
    # HTTP 200 dönse de gövdedeki statusCode başarısızlık bildiriyor.
    session.responses[failing_call - 1] = FakeResponse(data={"statusCode": 500})

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "api_error"
    assert len(session.calls) == failing_call


def test_price_request_sends_anonymous_cookie_as_user_id(listing):
    listings = [full_listing("hb", "Hepsiburada", 56_999)]
    scraper, session = scraper_with(
        listings, [response_offer("hb", "Hepsiburada", 56_999)]
    )

    scraper.fetch(listing)

    assert session.calls[2][2]["json"]["userId"] == "test-user"


def test_user_id_without_cookie_is_random_uuid_reused_across_fetches(listing):
    listings = [full_listing("hb", "Hepsiburada", 56_999)]
    offers = [response_offer("hb", "Hepsiburada", 56_999)]
    scraper, session = scraper_with(listings, offers)
    _unused, second_round = scraper_with(listings, offers)
    session.responses.extend(second_round.responses)
    session.cookies = {}

    scraper.fetch(listing)
    scraper.fetch(listing)

    first_id = session.calls[2][2]["json"]["userId"]
    assert str(UUID(first_id)) == first_id
    assert session.calls[5][2]["json"]["userId"] == first_id


@pytest.mark.parametrize("status", [403, 429])
def test_http_client_classifies_blocked_responses(status):
    session = FakeSession([FakeResponse(status=status)])
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    client = PageClient(["www.hepsiburada.com"], runtime, client=session)

    with pytest.raises(FetchError) as error:
        client.get(URL)

    assert error.value.code == "blocked"
