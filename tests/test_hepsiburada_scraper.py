import json

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
        self.text = text
        self.content = text.encode() if data is None else json.dumps(data).encode()
        self.headers = {}
        self.data = data

    def json(self):
        if self.data is None:
            raise ValueError("JSON değil")
        return self.data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.cookies = {"hbus_anonymousId": "test-user"}

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

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
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
        platform_name="Hepsiburada",
        hosts=["www.hepsiburada.com"],
        coverage_version="test",
    )


def page_html():
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
        "name": "Apple iPhone 15 128 GB Mavi",
        "sku": SKU,
    }
    return (
        "<html><body>"
        f'<script type="application/ld+json">{json.dumps(identity)}</script>'
        f'<script type="application/json">{json.dumps(context)}</script>'
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


def response_offer(listing_id, seller, price, *, discounted=None):
    price_data = {"price": price}
    if discounted is not None:
        price_data["discountedPrice"] = discounted
    return {
        "listingId": listing_id,
        "merchantName": seller,
        "campaigns": [],
        "priceData": price_data,
    }


def scraper_with(listings, offers):
    responses = [
        FakeResponse(text=page_html()),
        FakeResponse(data={"statusCode": 200, "data": {"listings": listings}}),
        FakeResponse(data=api_response(offers)),
    ]
    session = FakeSession(responses)
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    return Scraper(["www.hepsiburada.com"], runtime, client=session), session


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


@pytest.mark.parametrize("status", [403, 429])
def test_http_client_classifies_blocked_responses(status):
    session = FakeSession([FakeResponse(status=status)])
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    client = PageClient(["www.hepsiburada.com"], runtime, client=session)

    with pytest.raises(FetchError) as error:
        client.get(URL)

    assert error.value.code == "blocked"
