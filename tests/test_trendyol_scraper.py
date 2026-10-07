import json

import pytest
from pydantic import ValidationError

from app.contracts import ProductListing
from app.scraper.http import FetchError
from app.scraper.trendyol_scraper import Scraper
from app.settings import Runtime

URL = "https://www.trendyol.com/apple/iphone-15-128-gb-mavi-p-762254881"
# product_html() varsayılan olarak ürün stoğunu kazanan varyanta da yazar.
PRODUCT_STOCK = object()


class FakeResponse:
    def __init__(self, text="", status=200):
        self.status_code = status
        self.headers = {}
        self.content = text.encode()


class FakeSession:
    """Yalnız sıraya konan yanıtları döndürür; testler internete çıkmaz."""

    def __init__(self):
        self.responses = []
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url))
        assert self.responses, "Beklenmeyen HTTP isteği"
        response = self.responses.pop(0)
        kwargs["content_callback"](response.content)
        return response

    def close(self):
        pass


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def scraper(session):
    runtime = Runtime(request_interval_seconds=0, request_attempts=1)
    return Scraper(["www.trendyol.com"], runtime, client=session)


@pytest.fixture
def listing():
    return ProductListing(
        listing_id="trendyol_iphone_15_128gb_mavi",
        product_id=1,
        platform="trendyol",
        url=URL,
        color="Mavi",
        active=True,
        product_name="Apple iPhone 15 128 GB",
        model="iPhone 15",
        storage_gb=128,
    )


def _present(**fields):
    """None verilen alanı sayfaya hiç yazmaz; eksik alanlı sayfayı taklit eder."""
    return {key: value for key, value in fields.items() if value is not None}


def product_html(
    *,
    name="Apple iPhone 15 128 GB Mavi",
    product_id=762254881,
    others=None,
    in_stock=True,
    variant_stock=PRODUCT_STOCK,
    running_out=False,
    price=None,
    merchant=None,
    slicing=None,
):
    if variant_stock is PRODUCT_STOCK:
        variant_stock = in_stock
    winner = _present(
        inStock=variant_stock,
        isRunningOut=running_out,
        price=price
        or {
            "currency": "TRY",
            "sellingPrice": {"value": 57_249},
            "originalPrice": {"value": 59_999},
        },
    )
    state = {
        "product": _present(
            id=product_id,
            name=name,
            inStock=in_stock,
            slicingAttributes=slicing or {},
            merchantListing={
                "winnerVariant": winner,
                "merchant": merchant
                or {"name": "Trendyol", "sellerScore": {"value": 9.3}},
                "otherMerchants": others or [],
            },
        )
    }
    return (
        "<html><body><script>"
        f"window['__envoy__SHARED_PROPS'] = {json.dumps(state)};"
        "</script></body></html>"
    )


def other_merchant(name, listing_id, *, page_id=762254881, price=56_999, **variant):
    """Tek varyantlı otherMerchants girdisi; stok alanları `variant` ile verilir."""
    return {
        "name": name,
        "url": f"/apple/iphone-15-128-gb-p-{page_id}?merchantId=9",
        "variants": [
            {
                "listingId": listing_id,
                "price": {"currency": "TRY", "sellingPrice": {"value": price}},
                **variant,
            }
        ],
    }


def test_parses_winner_offer(scraper, listing):
    observation = scraper.parse(product_html(), listing)

    assert observation.current_price == 5_724_900
    assert observation.original_price == 5_999_900
    assert observation.seller_name == "Trendyol"
    assert observation.seller_rating == 9.3
    assert observation.seller_rating_scale == 10.0
    assert observation.stock_status == "Stokta Var"


def test_fetch_downloads_listing_page_once(scraper, session, listing):
    session.responses.append(FakeResponse(product_html()))

    observation = scraper.fetch(listing)

    assert session.calls == [("GET", URL)]
    assert observation.listing_id == listing.listing_id
    assert observation.current_price == 5_724_900


@pytest.mark.parametrize(
    "url",
    [
        "/apple/phone-p-762254881abc",
        "/apple/phone?ref=other-p-762254881",
    ],
)
def test_url_identity_rejects_invalid_cheaper_offer(scraper, listing, url):
    merchant = other_merchant("Ucuz satıcı", "invalid", price=1_000, inStock=True)
    merchant["url"] = url
    observation = scraper.parse(product_html(others=[merchant]), listing)

    assert observation.seller_name == "Trendyol"
    assert observation.current_price == 5_724_900
    rejected = next(
        offer for offer in scraper._last_offers if offer["listing_id"] == "invalid"
    )
    assert rejected["rejection_reason"] == "different_product_page"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.trendyol.com/apple/phone-p-762254881abc",
        "https://www.trendyol.com/apple/phone?ref=other-p-762254881",
    ],
)
def test_url_identity_rejects_invalid_listing_address(scraper, session, listing, url):
    session.responses.append(FakeResponse(product_html()))
    invalid = listing.model_copy(update={"url": url})

    with pytest.raises(FetchError) as error:
        scraper.fetch(invalid)

    assert error.value.code == "identity"
    assert session.calls == [("GET", url)]


@pytest.mark.parametrize(
    ("page", "cause"),
    [
        (product_html(name=None), KeyError),
        (
            product_html(price={"currency": "TRY", "sellingPrice": {"value": "abc"}}),
            ValueError,
        ),
        (
            product_html(merchant={"name": "Trendyol", "sellerScore": {"value": [9]}}),
            TypeError,
        ),
        (
            product_html(merchant={"name": "Trendyol", "sellerScore": 9.3}),
            AttributeError,
        ),
        # Puan ölçeği aşıyor: PriceObservation doğrulaması reddeder.
        (
            product_html(merchant={"name": "Trendyol", "sellerScore": {"value": 11}}),
            ValidationError,
        ),
    ],
    ids=["missing_name", "broken_price", "rating_list", "rating_number", "contract"],
)
def test_fetch_turns_unexpected_page_shape_into_parse_error(
    scraper, session, listing, page, cause
):
    session.responses.append(FakeResponse(page))

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == "parse"
    assert str(error.value).startswith("Teklif doğrulanamadı")
    assert isinstance(error.value.__cause__, cause)


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (FakeResponse(status=403), "blocked"),
        (FakeResponse(product_html(product_id=999999999)), "identity"),
    ],
    ids=["blocked", "identity"],
)
def test_fetch_passes_fetch_errors_through_unchanged(
    scraper, session, listing, response, code
):
    session.responses.append(response)

    with pytest.raises(FetchError) as error:
        scraper.fetch(listing)

    assert error.value.code == code
    assert not str(error.value).startswith("Teklif doğrulanamadı")


def test_running_out_flag_is_critical_stock(scraper, listing):
    observation = scraper.parse(product_html(running_out=True), listing)

    assert observation.stock_status == "Kritik Stok"
    assert observation.current_price == 5_724_900
    assert observation.seller_name == "Trendyol"


@pytest.mark.parametrize(
    "running_out", [None, "true", 1], ids=["missing", "text", "number"]
)
def test_running_out_flag_other_than_true_stays_in_stock(scraper, listing, running_out):
    observation = scraper.parse(product_html(running_out=running_out), listing)

    assert observation.stock_status == "Stokta Var"


def test_critical_stock_comes_from_selected_other_merchant(scraper, listing):
    others = [
        other_merchant("Aynı Ürün Satıcısı", "cheap", inStock=True, isRunningOut=True)
    ]

    observation = scraper.parse(product_html(others=others), listing)

    assert observation.seller_name == "Aynı Ürün Satıcısı"
    assert observation.stock_status == "Kritik Stok"


@pytest.mark.parametrize(
    ("in_stock", "status"), [(True, "Stokta Var"), (False, "Tükendi")]
)
def test_winner_without_stock_field_uses_product_stock(
    scraper, listing, in_stock, status
):
    html = product_html(in_stock=in_stock, variant_stock=None)

    observation = scraper.parse(html, listing)

    assert observation.stock_status == status


def test_explicitly_sold_out_page_returns_sold_out_observation(scraper, listing):
    observation = scraper.parse(product_html(in_stock=False), listing)

    assert observation.stock_status == "Tükendi"
    assert observation.current_price is None
    assert observation.seller_name is None
    assert scraper._last_offers[0]["rejection_reason"] == "out_of_stock"


def test_all_on_page_offers_out_of_stock_is_sold_out(scraper, listing):
    others = [other_merchant("Stoksuz Satıcı", "out", inStock=False)]

    observation = scraper.parse(product_html(in_stock=False, others=others), listing)

    assert observation.stock_status == "Tükendi"


def test_sold_out_needs_every_on_page_offer_explicitly_out_of_stock(scraper, listing):
    # Diğer satıcının stok alanı yok: stoku bilinmediği için sayfa Tükendi olamaz.
    others = [other_merchant("Stoku Belirsiz Satıcı", "unknown")]

    with pytest.raises(FetchError) as error:
        scraper.parse(product_html(in_stock=False, others=others), listing)

    assert error.value.code == "no_eligible_offer"
    assert [offer["rejection_reason"] for offer in scraper._last_offers] == [
        "out_of_stock",
        "unknown_stock",
    ]


def test_other_color_offer_does_not_prevent_sold_out(scraper, listing):
    others = [
        other_merchant("Başka Renk Satıcısı", "other", page_id=762254878, inStock=True)
    ]

    observation = scraper.parse(product_html(in_stock=False, others=others), listing)

    assert observation.stock_status == "Tükendi"


def test_disallowed_condition_is_not_mistaken_for_sold_out(scraper, listing):
    html = product_html(in_stock=False).replace('"Trendyol"', '"Yenilenmiş Trendyol"')

    with pytest.raises(FetchError) as error:
        scraper.parse(html, listing)

    assert error.value.code == "no_eligible_offer"


@pytest.mark.parametrize(
    ("page", "reason"),
    [
        (product_html(in_stock=None), "unknown_stock"),
        (
            product_html(price={"currency": "USD", "sellingPrice": {"value": 57_249}}),
            "invalid_currency",
        ),
        (product_html(merchant={"name": ""}), "missing_seller"),
    ],
    ids=["unknown_stock", "invalid_currency", "missing_seller"],
)
def test_rejected_winner_is_error_not_sold_out(scraper, listing, page, reason):
    with pytest.raises(FetchError) as error:
        scraper.parse(page, listing)

    assert error.value.code == "no_eligible_offer"
    assert scraper._last_offers[0]["rejection_reason"] == reason


def test_checks_other_merchants_and_keeps_other_color_out(scraper, listing):
    others = [
        {
            "name": "Aynı Ürün Satıcısı",
            "sellerScore": {"value": 9.7},
            "url": "/apple/iphone-15-128-gb-mavi-p-762254881?merchantId=2",
            "variants": [
                {
                    "listingId": "same-product",
                    "inStock": True,
                    "sellable": True,
                    "price": {
                        "currency": "TRY",
                        "sellingPrice": {"value": 56_999},
                        "originalPrice": {"value": 58_999},
                    },
                }
            ],
        },
        {
            "name": "Başka Renk Satıcısı",
            "sellerScore": {"value": 9.8},
            "url": "/apple/iphone-15-128-gb-siyah-p-762254878?merchantId=3",
            "variants": [
                {
                    "listingId": "other-color",
                    "inStock": True,
                    "sellable": True,
                    "price": {
                        "currency": "TRY",
                        "sellingPrice": {"value": 50_000},
                        "originalPrice": {"value": 50_000},
                    },
                }
            ],
        },
    ]

    observation = scraper.parse(product_html(others=others), listing)

    assert observation.current_price == 5_699_900
    assert observation.seller_name == "Aynı Ürün Satıcısı"
    assert len(scraper._last_offers) == 3
    other_color = next(
        offer for offer in scraper._last_offers if offer["listing_id"] == "other-color"
    )
    assert other_color["eligible"] is False
    assert other_color["rejection_reason"] == "different_product_page"


def test_equal_prices_pick_seller_by_name(scraper, listing):
    # listing_id sırası ada ters: seçimi listing_id değil satıcı adı belirlemeli.
    others = [
        other_merchant("Zeta", "a", inStock=True),
        other_merchant("Alfa", "b", inStock=True),
    ]

    observation = scraper.parse(product_html(others=others), listing)

    assert observation.seller_name == "Alfa"
    selected = [offer for offer in scraper._last_offers if offer["selected"]]
    assert [offer["listing_id"] for offer in selected] == ["b"]


def test_equal_price_and_seller_pick_smaller_listing_id(scraper, listing):
    others = [
        other_merchant("Alfa", "b", inStock=True),
        other_merchant("Alfa", "a", inStock=True),
    ]

    scraper.parse(product_html(others=others), listing)

    selected = [offer for offer in scraper._last_offers if offer["selected"]]
    assert [offer["listing_id"] for offer in selected] == ["a"]


@pytest.mark.parametrize("listing_id", [None, ""], ids=["null", "empty"])
def test_missing_offer_listing_id_is_none(scraper, listing, listing_id):
    others = [other_merchant("Diğer Satıcı", listing_id, inStock=True)]

    scraper.parse(product_html(others=others), listing)

    winner, other = scraper._last_offers
    # Kazanan varyantta listingId anahtarı hiç yok.
    assert winner["listing_id"] is None
    assert other["listing_id"] is None


def test_numeric_offer_listing_id_is_text(scraper, listing):
    others = [other_merchant("Diğer Satıcı", 12345, inStock=True)]

    scraper.parse(product_html(others=others), listing)

    assert scraper._last_offers[1]["listing_id"] == "12345"


def test_uses_unconditional_discounted_price(scraper, listing):
    # Canlı ALDIMGİTTİ teklifi: sayfada ~~59.999~~ 59.599 ("Net 400 TL İndirim").
    others = [
        {
            "name": "ALDIMGİTTİ",
            "url": "/apple/iphone-15-128-gb-mavi-p-762254881?merchantId=4",
            "variants": [
                {
                    "listingId": "discounted",
                    "inStock": True,
                    "sellable": True,
                    "price": {
                        "currency": "TRY",
                        "sellingPrice": {"value": 59_999},
                        "discountedPrice": {"value": 59_599},
                        "originalPrice": {"value": 59_599},
                    },
                }
            ],
        }
    ]
    scraper.parse(product_html(others=others), listing)

    offer = next(o for o in scraper._last_offers if o["listing_id"] == "discounted")
    assert offer["current_price"] == 5_959_900
    assert offer["original_price"] == 5_999_900


@pytest.mark.parametrize(
    "original", [57_249, 55_000, None], ids=["equal", "lower", "missing"]
)
def test_original_price_not_above_current_is_none(scraper, listing, original):
    price = {"currency": "TRY", "sellingPrice": {"value": 57_249}}
    if original is not None:
        price["originalPrice"] = {"value": original}

    observation = scraper.parse(product_html(price=price), listing)

    assert observation.current_price == 5_724_900
    assert observation.original_price is None


def test_title_without_capacity_uses_slicing_capacity(scraper, listing):
    html = product_html(
        name="Apple iPhone 15 Mavi", slicing={"Internal Memory": "128 GB"}
    )

    observation = scraper.parse(html, listing)

    assert observation.current_price == 5_724_900


@pytest.mark.parametrize(
    ("name", "product_id"),
    [
        ("Apple iPhone 15 Pro 128 GB", 762254881),
        ("Apple iPhone 15 Plus 128 GB", 762254881),
        ("Apple iPhone 15 256 GB", 762254881),
        ("Apple iPhone 15 Mavi", 762254881),
        ("Apple iPhone 15 128 GB", 999999999),
    ],
)
def test_rejects_wrong_product_identity(scraper, listing, name, product_id):
    with pytest.raises(FetchError) as error:
        scraper.parse(product_html(name=name, product_id=product_id), listing)

    assert error.value.code == "identity"
