import json

import pytest

from app.contracts import ProductListing
from app.scraper.http import FetchError
from app.scraper.trendyol_scraper import Scraper
from app.settings import Runtime

URL = "https://www.trendyol.com/apple/iphone-15-128-gb-mavi-p-762254881"


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
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
        platform_name="Trendyol",
        hosts=["www.trendyol.com"],
        coverage_version="test",
    )


def product_html(
    *, name="Apple iPhone 15 128 GB Mavi", product_id=762254881, others=None
):
    state = {
        "product": {
            "id": product_id,
            "name": name,
            "inStock": True,
            "merchantListing": {
                "winnerVariant": {
                    "inStock": True,
                    "isRunningOut": False,
                    "price": {
                        "currency": "TRY",
                        "sellingPrice": {"value": 57_249},
                        "originalPrice": {"value": 59_999},
                    },
                },
                "merchant": {
                    "name": "Trendyol",
                    "sellerScore": {"value": 9.3},
                },
                "otherMerchants": others or [],
            },
        }
    }
    return (
        "<html><body><script>"
        f"window['__envoy__SHARED_PROPS'] = {json.dumps(state)};"
        "</script></body></html>"
    )


def test_parses_winner_offer(listing):
    scraper = Scraper(["www.trendyol.com"], Runtime())

    observation = scraper.parse(product_html(), listing)

    assert observation.current_price == 5_724_900
    assert observation.original_price == 5_999_900
    assert observation.seller_name == "Trendyol"
    assert observation.seller_rating == 9.3
    assert observation.seller_rating_scale == 10.0
    assert observation.stock_status == "Stokta Var"


def test_checks_other_merchants_and_keeps_other_color_out(listing):
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
    scraper = Scraper(["www.trendyol.com"], Runtime())

    observation = scraper.parse(product_html(others=others), listing)

    assert observation.current_price == 5_699_900
    assert observation.seller_name == "Aynı Ürün Satıcısı"
    assert len(scraper._last_offers) == 3
    other_color = next(
        offer for offer in scraper._last_offers if offer["listing_id"] == "other-color"
    )
    assert other_color["eligible"] is False
    assert other_color["rejection_reason"] == "different_product_page"


@pytest.mark.parametrize(
    ("name", "product_id"),
    [
        ("Apple iPhone 15 Pro 128 GB", 762254881),
        ("Apple iPhone 15 128 GB", 999999999),
    ],
)
def test_rejects_wrong_product_identity(listing, name, product_id):
    scraper = Scraper(["www.trendyol.com"], Runtime())

    with pytest.raises(FetchError) as error:
        scraper.parse(product_html(name=name, product_id=product_id), listing)

    assert error.value.code == "identity"
