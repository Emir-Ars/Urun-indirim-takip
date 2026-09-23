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


def product_html(*, name="Apple iPhone 15 128 GB Mavi", product_id=762254881):
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
