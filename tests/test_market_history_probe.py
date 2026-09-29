"""Piyasa geçmişi araştırma aracının ağsız denetimleri."""

import json
from copy import deepcopy
from datetime import date, timedelta

import pytest

from app.contracts import Product
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime
from tests.manual.market_history_probe import (
    CIMRI_API_URL,
    cimri_history,
    cimri_page_data,
    probe,
    summarize_html,
)

PRODUCT = Product(
    product_id=1,
    product_key="apple_iphone_16_128gb",
    brand="Apple",
    model="iPhone 16",
    storage_gb=128,
)
XIAOMI = Product(
    product_id=2,
    product_key="xiaomi_14t_pro_256gb",
    brand="Xiaomi",
    model="14T Pro",
    storage_gb=256,
)
XIAOMI_URL = (
    "https://www.cimri.com/cep-telefonlari/"
    "en-ucuz-xiaomi-14t-pro-fiyatlari%2Ca2372365900"
)


def synthetic_xiaomi():
    last_day = date(2026, 9, 29)
    prices = [50000.25 + (index // 7 % 5) * 100 for index in range(365)]
    prices[-1] = 44000.5
    table_rows = [
        {
            "date": (last_day - timedelta(days=index)).strftime("%d/%m/%Y"),
            "minPrice": prices[index],
        }
        for index in range(90)
    ]
    page_data = {
        "props": {
            "pageProps": {
                "data": {
                    "product": {"id": "2372365900"},
                    "priceHistoryTablePrices": table_rows,
                }
            }
        }
    }
    response = {
        "data": {
            "priceHistoryV2": {
                "productId": 2372365900,
                "lastDay": last_day.isoformat(),
                "prices": prices,
            }
        }
    }
    return page_data, response


def xiaomi_html(page_data, heading="Xiaomi 14T Pro 256 GB 12 GB Ram"):
    return (
        f"<title>{heading} Fiyatları | Cimri</title><h1>{heading}</h1>"
        '<script id="__OCTOPUS_DATA__" type="application/json">'
        f"{json.dumps(page_data, ensure_ascii=False)}</script>"
    )


def test_history_table_rows_are_candidates_not_confirmed_history():
    html = """
    <title>Apple iPhone 16 128 GB fiyatları</title>
    <h1>Apple iPhone 16 128 GB</h1>
    <h2>Fiyat Geçmişi</h2>
    <table><tr><th>Tarih</th><th>Fiyat</th></tr>
      <tr><td>01.09.2026</td><td>52.999,00 TL</td></tr>
      <tr><td>02.09.2026</td><td>51.999,00 TL</td></tr>
      <tr><td>bozuk</td><td>50.000 TL</td></tr>
    </table>
    <table><tr><th>Satıcı</th><th>Fiyat</th></tr>
      <tr><td>Bir mağaza</td><td>51.999 TL</td></tr></table>
    """
    report = summarize_html(html, PRODUCT)
    assert report["identity"]["status"] == "matched"
    assert report["table_count"] == 2
    assert report["candidate_tables"][0]["candidate_rows"] == 2
    assert report["candidate_tables"][0]["oldest_day"] == "2026-09-01"
    assert report["candidate_tables"][0]["newest_day"] == "2026-09-02"
    assert report["has_history_label"]
    assert "manuel doğrulama" in report["interpretation"]


def test_wrong_capacity_is_not_reported_as_matched():
    report = summarize_html("<h1>Apple iPhone 16 256 GB</h1>", PRODUCT)
    assert report["identity"]["status"] == "unverified"
    assert report["candidate_tables"] == []


def test_other_site_url_is_rejected_before_network_request():
    class NoRequest:
        def request(self, *args, **kwargs):
            raise AssertionError("İzinsiz adrese istek gitmemeli")

    def client_class(hosts, runtime, request_budget):
        assert request_budget == 4
        return PageClient(hosts, runtime, client=NoRequest(), request_budget=4)

    report = probe(
        "akakce",
        "https://example.com/iphone-16",
        PRODUCT,
        Runtime(),
        client_class=client_class,
    )
    assert report["result"] == "error"
    assert report["error"]["code"] == "invalid_host"
    assert report["request_count"] == 0


def test_year_with_365_points_matches_page_table():
    page_data, response = synthetic_xiaomi()
    product_id, table_rows = cimri_page_data(xiaomi_html(page_data))
    history = cimri_history(response, product_id, table_rows)
    assert product_id == "2372365900"
    assert history["summary"]["point_count"] == 365
    assert history["summary"]["oldest_day"] == "2025-09-30"
    assert history["summary"]["newest_day"] == "2026-09-29"
    assert history["summary"]["missing_price_count"] == 0
    assert history["summary"]["table_compared_rows"] == 90
    assert history["summary"]["table_comparison"] == "matched"
    assert history["points"][0] == {"day": "2025-09-30", "price_tl": 44000.5}
    assert history["points"][-1] == {"day": "2026-09-29", "price_tl": 50000.25}


def test_cimri_probe_uses_page_id_and_same_client_for_post():
    page_data, response = synthetic_xiaomi()

    class Client:
        def __init__(self, hosts, runtime, request_budget):
            assert "www.cimri.com" in hosts
            assert request_budget == 4
            self.request_count = 0

        def get(self, url):
            assert url == XIAOMI_URL
            self.request_count += 1
            return xiaomi_html(page_data)

        def post_json(self, url, payload, *, headers):
            assert url == CIMRI_API_URL
            assert payload == {
                "queryName": "priceHistoryV2Query",
                "variables": {"productId": "2372365900"},
                "platform": "CIMRI_DESKTOP_V2",
            }
            assert headers == {"Referer": XIAOMI_URL}
            self.request_count += 1
            return response

        def close(self):
            pass

    report = probe("cimri", XIAOMI_URL, XIAOMI, Runtime(), client_class=Client)
    assert report["result"] == "inspection_needed"
    assert report["request_count"] == 2
    assert len(report["history"]["points"]) == 365


def test_wrong_capacity_stops_before_cimri_api_call():
    page_data, _ = synthetic_xiaomi()

    class Client:
        request_count = 1

        def __init__(self, hosts, runtime, request_budget):
            pass

        def get(self, url):
            return xiaomi_html(page_data, heading="Xiaomi 14T Pro 512 GB")

        def post_json(self, *args, **kwargs):
            raise AssertionError("Yanlış ürüne API isteği gitmemeli")

        def close(self):
            pass

    report = probe("cimri", XIAOMI_URL, XIAOMI, Runtime(), client_class=Client)
    assert report["result"] == "error"
    assert report["error"]["code"] == "identity"
    assert "history" not in report


def test_wrong_response_product_id_is_rejected():
    page_data, response = synthetic_xiaomi()
    _, table_rows = cimri_page_data(xiaomi_html(page_data))
    response["data"]["priceHistoryV2"]["productId"] = 111
    with pytest.raises(FetchError) as error:
        cimri_history(response, "2372365900", table_rows)
    assert error.value.code == "identity"


def test_missing_price_keeps_day_without_inventing_price():
    page_data, response = synthetic_xiaomi()
    _, table_rows = cimri_page_data(xiaomi_html(page_data))
    response["data"]["priceHistoryV2"]["prices"][200] = None
    history = cimri_history(response, "2372365900", table_rows)
    assert history["summary"]["missing_price_count"] == 1
    assert history["points"][164]["price_tl"] is None


@pytest.mark.parametrize(
    "change",
    [
        lambda h: h.update(lastDay="29/09/2026"),
        lambda h: h.update(prices=[]),
        lambda h: h["prices"].__setitem__(0, "46549,05"),
    ],
)
def test_invalid_history_response_is_rejected(change):
    _, response = synthetic_xiaomi()
    change(response["data"]["priceHistoryV2"])
    with pytest.raises(FetchError) as error:
        cimri_history(response, "2372365900", [])
    assert error.value.code == "parse"


def test_table_price_mismatch_is_rejected():
    page_data, response = synthetic_xiaomi()
    _, table_rows = cimri_page_data(xiaomi_html(page_data))
    changed_rows = deepcopy(table_rows)
    changed_rows[0]["minPrice"] += 1
    with pytest.raises(FetchError) as error:
        cimri_history(response, "2372365900", changed_rows)
    assert error.value.code == "parse"
    assert "uyuşmuyor" in str(error.value)
