import json
from urllib.parse import urljoin

import pytest

from app.contracts import DiscoveryConfig, DiscoveryTarget
from app.discovery.hepsiburada import _card_id
from app.discovery.service import _url_identity
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.hepsiburada_scraper import _sku_from_url
from app.scraper.http import FetchError
from app.scraper.trendyol_scraper import _product_id
from app.settings import Runtime


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.trendyol.com/apple/phone-p-123", "123"),
        ("https://www.trendyol.com/apple/phone-p-123?merchantId=9", "123"),
        ("https://www.trendyol.com/apple/phone-p-123/", "123"),
        ("https://www.trendyol.com/apple/phone-p-123/?merchantId=9", "123"),
        ("/apple/phone-p-123", "123"),
        ("https://www.trendyol.com/apple/phone-p-00123", "00123"),
        ("https://www.trendyol.com/apple/phone", None),
        ("https://www.trendyol.com/apple/phone-p-123abc", None),
        ("https://www.trendyol.com/apple/phone?ref=other-p-123", None),
        ("https://other-p-123/phone", None),
        ("https://www.trendyol.com/apple/phone-P-123", None),
        ("https://[invalid/phone-p-123", None),
    ],
)
def test_trendyol_url_identity_agrees_across_consumers(monkeypatch, url, expected):
    assert _product_id(url) == expected
    assert _url_identity("trendyol", url) == expected
    discovery = TrendyolDiscovery(
        DiscoveryTarget(key="apple_iphone_16", brand="Apple", model="iPhone 16"),
        DiscoveryConfig(targets=[]),
        Runtime(request_interval_seconds=0),
    )
    opened = []

    def get(address):
        opened.append(address)
        product = {
            "id": expected or "123",
            "name": "iPhone 16 128 GB",
            "brand": {"name": "Apple"},
            "category": {"name": "Cep Telefonu"},
        }
        return (
            '<script>window["__envoy__SHARED_PROPS"] = '
            f"{json.dumps({'product': product})};</script>"
        )

    monkeypatch.setattr(discovery, "get", get)
    address = urljoin("https://www.trendyol.com/", url) if url.startswith("/") else url
    try:
        if expected is None:
            with pytest.raises(FetchError) as error:
                discovery._candidate(address, "123")
            assert error.value.code == "identity"
            assert opened == []
        else:
            candidate = discovery._candidate(address, expected)
            assert candidate.platform_product_id == expected
            assert candidate.url == address
            assert opened == [address]
    finally:
        discovery.close()


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.hepsiburada.com/phone-p-HBCV000123", "HBCV000123"),
        ("https://www.hepsiburada.com/phone-p-HBCV000123?ref=9", "HBCV000123"),
        ("https://www.hepsiburada.com/phone-p-HBCV000123/", "HBCV000123"),
        ("https://www.hepsiburada.com/phone-p-HBCV000123/?ref=9", "HBCV000123"),
        ("/phone-p-HBCV000123", "HBCV000123"),
        ("https://www.hepsiburada.com/phone-p-hbcv000123", "HBCV000123"),
        ("https://www.hepsiburada.com/phone-p-HBCV000123X", "HBCV000123X"),
        ("https://www.hepsiburada.com/phone", None),
        ("https://www.hepsiburada.com/phone-p-HBCV000123-bad", None),
        ("https://www.hepsiburada.com/phone?ref=other-p-HBCV000123", None),
        ("https://other-p-HBCV000123/phone", None),
        ("https://[invalid/phone-p-HBCV000123", None),
    ],
)
def test_hepsiburada_url_identity_agrees_across_consumers(url, expected):
    if expected is None:
        with pytest.raises(FetchError) as error:
            _sku_from_url(url)
        assert error.value.code == "identity"
    else:
        assert _sku_from_url(url) == expected
    assert _url_identity("hepsiburada", url) == expected
    assert _card_id(url) == expected


@pytest.mark.parametrize("url", ["/phone-pm-HBC000123", "/phone-pm-hbc000123?ref=9"])
def test_hepsiburada_group_identity_stays_discovery_only(url):
    assert _card_id(url) == "HBC000123"
    assert _url_identity("hepsiburada", url) is None
    with pytest.raises(FetchError) as error:
        _sku_from_url(url)
    assert error.value.code == "identity"


@pytest.mark.parametrize("platform", ["other", "TRendyol"])
def test_unknown_platform_has_no_url_identity(platform):
    assert _url_identity(platform, "https://www.trendyol.com/phone-p-123") is None
