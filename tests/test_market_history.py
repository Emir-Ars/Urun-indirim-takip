"""Cimri yerel alımını ağsız sınar; gerçek örnekler yalnız seçilmiş alanlardır."""

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.market_history.__main__ as command
import app.market_history.capture as captures
import app.scraper.http as http
from app.contracts import Catalog
from app.market_history.capture import Mapping, MappingEntry, capture, read_mapping
from app.market_history.cimri import (
    CIMRI_API_URL,
    CIMRI_HOSTS,
    cimri_history,
    history_in_kurus,
    verified_page,
)
from app.scrape_lock import scrape_lock
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime
from tests.test_http import Recorder, Reply

ROOT = Path(__file__).parents[1]
RECORDED = json.loads(
    (ROOT / "tests/fixtures/cimri_recorded_samples.json").read_text(encoding="utf-8")
)
CATALOG = Catalog.model_validate_json(
    (ROOT / "config/catalog.json").read_text(encoding="utf-8-sig")
)
PRODUCTS = {product.product_key: product for product in CATALOG.products}
SAMPLES = RECORDED["samples"]
FRONTEND_SAMPLES = RECORDED["frontend_history"]["samples"]
CHANGED_FRONTEND_KEYS = {
    "apple_iphone_16_pro_max_512gb",
    "samsung_galaxy_s24_256gb",
    "samsung_galaxy_s24_ultra_512gb",
    "samsung_galaxy_s24_ultra_1024gb",
    "xiaomi_redmi_note_13_pro_4g_512gb",
}
MAPPING = Mapping(
    version=1,
    source="cimri",
    entries=[
        MappingEntry(
            product_key=sample["product_key"],
            url=sample["url"],
            cimri_product_id=sample["cimri_product_id"],
        )
        for sample in SAMPLES
    ],
)


def source_pair(sample=SAMPLES[0]):
    """Kaydedilmiş başlık/fiyatla sentetik zarf; tam API yanıtı olduğu iddia edilmez."""
    product = PRODUCTS[sample["product_key"]]
    metadata = {
        "id": sample["cimri_product_id"],
        "title": sample["headings"][0],
        "brand": {"name": product.brand},
        "category": {"slug": "cep-telefonlari"},
    }
    if product.brand == "Xiaomi":
        metadata = deepcopy(RECORDED["xiaomi_product"])
    last = date.fromisoformat(sample["last_day"])
    page = {
        "product": metadata,
        "priceHistoryTablePrices": [
            {
                "date": (last - timedelta(days=index)).strftime("%d/%m/%Y"),
                "minPrice": price,
            }
            for index, price in enumerate(sample["latest_three_prices_tl"])
        ],
    }
    response = {
        "data": {
            "priceHistoryV2": {
                "productId": sample["cimri_product_id"],
                "lastDay": sample["last_day"],
                "prices": list(sample["latest_three_prices_tl"]),
            }
        }
    }
    return page, response


def page_html(page, heading=None):
    data = {"props": {"pageProps": {"data": page}}}
    name = heading if heading is not None else page["product"].get("title", "")
    return (
        f"<h1>{name}</h1><script id='__OCTOPUS_DATA__'>"
        f"{json.dumps(data, ensure_ascii=False)}</script>"
    )


def small_catalog(keys=None):
    keys = keys or [sample["product_key"] for sample in SAMPLES]
    return Catalog(platforms=[], products=[PRODUCTS[key] for key in keys], listings=[])


def fake_clients(*pairs):
    pending = list(pairs)
    created = []

    class Client:
        def __init__(self, hosts, runtime, request_budget):
            assert hosts == CIMRI_HOSTS
            assert request_budget == 4
            self.pair = pending.pop(0)
            self.request_count = 0
            self.calls = []
            self.closed = False
            created.append(self)

        def get(self, url):
            self.request_count += 1
            self.calls.append(("GET", url))
            if isinstance(self.pair[0], BaseException):
                raise self.pair[0]
            return self.pair[0]

        def post_json(self, url, payload, *, headers):
            self.request_count += 1
            self.calls.append(("POST", url, payload, headers))
            if isinstance(self.pair[1], BaseException):
                raise self.pair[1]
            return self.pair[1]

        def close(self):
            self.closed = True

    return Client, created


def good_pair(sample=SAMPLES[0]):
    page, response = source_pair(sample)
    return page_html(page), response


def recorded_zero_gap():
    page, response = source_pair(SAMPLES[2])
    gap = RECORDED["xiaomi_zero_gap"]
    page["priceHistoryTablePrices"] = deepcopy(gap["table_rows"])
    response["data"]["priceHistoryV2"].update(
        productId=gap["cimri_product_id"],
        lastDay=gap["last_day"],
        prices=list(gap["prices"]),
    )
    return page, response


def saved_report(directory):
    return json.loads((directory / "report.json").read_text(encoding="utf-8"))


def test_config_mapping_uses_existing_catalog_and_recorded_source_ids():
    mapping = read_mapping(ROOT / "config/market_history.json", CATALOG)
    entries = {entry.product_key: entry for entry in mapping.entries}
    assert all(entries[entry.product_key] == entry for entry in MAPPING.entries)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda s: s["product_key"])
def test_recorded_headings_and_selected_prices_keep_identity_and_cents(sample):
    page, response = source_pair(sample)
    product = PRODUCTS[sample["product_key"]]
    identity, table = verified_page(
        page_html(page), product, sample["cimri_product_id"]
    )
    result = history_in_kurus(response, identity["product_id"], table)
    assert result["summary"]["table_compared_rows"] == 3
    assert result["summary"]["table_comparison"] == "matched"
    assert result["points"][-1]["day"] == sample["last_day"]
    prices = [
        round(price * 100) for price in reversed(sample["latest_three_prices_tl"])
    ]
    assert [point["price_kurus"] for point in result["points"]] == prices


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p["product"].update(id="111"),
        lambda p: p["product"].update(title="Apple iPhone 16 256 GB"),
        lambda p: p["product"].update(title="Apple iPhone 16 Pro 128 GB"),
        lambda p: p["product"].update(title="Apple iPhone 16 128 GB Kılıfı"),
        lambda p: p["product"].update(title="Apple iPhone 16 128 GB Yenilenmiş"),
        lambda p: p["product"].update(brand={"name": "Samsung"}),
        lambda p: p["product"].update(brand={}),
        lambda p: p["product"].update(category={"slug": "yenilenmis-cep-telefonlari"}),
        lambda p: p["product"].update(category={}),
        lambda p: p["product"].update(title=128),
        lambda p: p["product"].pop("title"),
    ],
)
def test_identity_error_saves_page_and_stops_before_api(tmp_path, change):
    page, response = source_pair()
    change(page)
    client, created = fake_clients((page_html(page), response))
    report = capture(
        small_catalog([SAMPLES[0]["product_key"]]),
        Mapping(version=1, source="cimri", entries=[MAPPING.entries[0]]),
        tmp_path / "capture",
        Runtime(),
        client_class=client,
    )
    record = report["products"][0]
    assert record["status"] == "error" and record["error"]["code"] == "identity"
    assert record["request_count"] == 1 and "api" not in record
    assert len(created[0].calls) == 1 and created[0].closed
    assert (tmp_path / "capture" / record["page"]["file"]).exists()


def test_conflicting_h1_model_is_rejected_even_when_capacity_matches():
    page, _ = source_pair()
    with pytest.raises(FetchError, match="model"):
        verified_page(
            page_html(page, heading="Apple iPhone 16 Pro 128 GB"),
            PRODUCTS[SAMPLES[0]["product_key"]],
            SAMPLES[0]["cimri_product_id"],
        )


@pytest.mark.parametrize(
    "html",
    ["<h1>Apple iPhone 16 128 GB</h1>", "<script id='__OCTOPUS_DATA__'>{}</script>"],
)
def test_unknown_page_format_is_parse_error(html):
    with pytest.raises(FetchError) as error:
        verified_page(html, PRODUCTS[SAMPLES[0]["product_key"]], "2314921069")
    assert error.value.code == "parse"


@pytest.mark.parametrize(
    "price", [True, False, "54999", -1, 1.001, float("nan"), float("inf"), {}, []]
)
def test_invalid_price_is_rejected_without_rounding(price):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] = price
    with pytest.raises(FetchError) as error:
        history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert error.value.code == "parse"


def test_recorded_zero_gap_is_missing_and_raw_prices_are_preserved(tmp_path):
    page, response = recorded_zero_gap()
    original = deepcopy(response)
    client, created = fake_clients((page_html(page), response))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog(),
        MAPPING,
        directory,
        Runtime(),
        [SAMPLES[2]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert report["result"] == "completed" and record["status"] == "captured"
    assert record["history"]["points"] == [
        {"day": "2026-10-01", "price_kurus": 4703904},
        {"day": "2026-10-02", "price_kurus": None},
        {"day": "2026-10-03", "price_kurus": None},
        {"day": "2026-10-04", "price_kurus": None},
        {"day": "2026-10-05", "price_kurus": None},
        {"day": "2026-10-06", "price_kurus": 5437705},
        {"day": "2026-10-07", "price_kurus": 5443404},
        {"day": "2026-10-08", "price_kurus": 5443404},
    ]
    summary = record["history"]["summary"]
    assert summary["missing_price_count"] == 4 and summary["point_count"] == 8
    assert summary["table_compared_rows"] == 4
    assert summary["table_comparison"] == "matched"
    body = (directory / record["api"]["file"]).read_bytes()
    assert json.loads(body) == response == original
    assert hashlib.sha256(body).hexdigest() == record["api"]["sha256"]
    assert created[0].closed and saved_report(directory) == report


@pytest.mark.parametrize("price", [0, 0.0, -0.0])
def test_graph_zero_without_table_price_is_missing(price):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] = price
    original = deepcopy(response)
    history = history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert history["points"][-1] == {"day": "2026-09-29", "price_kurus": None}
    assert history["summary"]["missing_price_count"] == 1
    assert history["summary"]["table_comparison"] == "unavailable"
    assert response == original


@pytest.mark.parametrize("table_price", [50000.25, 0, -1, None])
def test_graph_zero_with_table_price_is_rejected(table_price):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] = 0
    with pytest.raises(FetchError) as error:
        history_in_kurus(
            response,
            SAMPLES[0]["cimri_product_id"],
            [{"date": "29/09/2026", "minPrice": table_price}],
        )
    assert error.value.code == "parse"


@pytest.mark.parametrize("price", [0, 0.0])
def test_legacy_history_keeps_zero_rejection(price):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] = price
    with pytest.raises(FetchError) as error:
        cimri_history(response, SAMPLES[0]["cimri_product_id"], [])
    assert error.value.code == "parse"


def test_mixed_null_and_zero_keep_dates_without_filling_prices():
    _, response = source_pair()
    response["data"]["priceHistoryV2"].update(
        lastDay="2026-10-08", prices=[None, 0, 50000.25]
    )
    history = history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert history["points"] == [
        {"day": "2026-10-06", "price_kurus": 5000025},
        {"day": "2026-10-07", "price_kurus": None},
        {"day": "2026-10-08", "price_kurus": None},
    ]
    assert history["summary"]["missing_price_count"] == 2


@pytest.mark.parametrize("count", [0, 367])
def test_invalid_series_length_is_rejected(count):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"] = [50000] * count
    with pytest.raises(FetchError) as error:
        history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert error.value.code == "parse"


@pytest.mark.parametrize("day", ["2026-02-30", "2026-9-29", "29/09/2026", None])
def test_invalid_day_is_rejected(day):
    _, response = source_pair()
    response["data"]["priceHistoryV2"]["lastDay"] = day
    with pytest.raises(FetchError) as error:
        history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert error.value.code == "parse"


def test_leap_day_missing_price_and_short_series_are_not_filled():
    _, response = source_pair()
    response["data"]["priceHistoryV2"].update(
        lastDay="2024-03-01", prices=[50000.25, None, 50000.25]
    )
    history = history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert history["points"] == [
        {"day": "2024-02-28", "price_kurus": 5000025},
        {"day": "2024-02-29", "price_kurus": None},
        {"day": "2024-03-01", "price_kurus": 5000025},
    ]
    assert history["summary"]["missing_price_count"] == 1
    assert history["summary"]["table_comparison"] == "unavailable"


def test_full_leap_year_accepts_exactly_366_points():
    _, response = source_pair()
    response["data"]["priceHistoryV2"].update(
        lastDay="2024-12-31", prices=[50000] * 366
    )
    history = history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert len(history["points"]) == 366
    assert history["points"][0]["day"] == "2024-01-01"
    assert history["points"][-1]["day"] == "2024-12-31"


def test_wrong_api_identity_keeps_evidence_and_rejects_history(tmp_path):
    page, response = source_pair()
    response["data"]["priceHistoryV2"]["productId"] = "111"
    client, created = fake_clients((page_html(page), response))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog(),
        MAPPING,
        directory,
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert record["error"]["code"] == "identity" and "history" not in record
    assert (directory / record["api"]["file"]).exists() and created[0].closed


@pytest.mark.parametrize(
    "response",
    [
        {},
        {"data": {"priceHistoryV2": None}},
        {"data": {"priceHistoryV2": {"productId": True}}},
        {
            "data": {
                "priceHistoryV2": {
                    "productId": "2314921069",
                    "lastDay": "2026-09-29",
                    "prices": "invalid",
                }
            }
        },
    ],
)
def test_unknown_api_format_is_parse_error(response):
    with pytest.raises(FetchError) as error:
        history_in_kurus(response, SAMPLES[0]["cimri_product_id"], [])
    assert error.value.code == "parse"


@pytest.mark.parametrize("prices", [[None, None, None], [50000.25, None, 50000]])
def test_captured_null_prices_remain_null(tmp_path, prices):
    page, response = source_pair()
    page["priceHistoryTablePrices"] = []
    response["data"]["priceHistoryV2"]["prices"] = prices
    client, _ = fake_clients((page_html(page), response))
    report = capture(
        small_catalog(),
        MAPPING,
        tmp_path / "capture",
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert record["status"] == "captured"
    history = record["history"]
    assert history["summary"]["missing_price_count"] == prices.count(None)
    assert [p["price_kurus"] is None for p in history["points"]] == [
        price is None for price in reversed(prices)
    ]


def test_inactive_catalog_product_is_not_requested(tmp_path):
    product = PRODUCTS[SAMPLES[0]["product_key"]].model_copy(update={"active": False})
    catalog = Catalog(platforms=[], products=[product], listings=[])
    client, created = fake_clients()
    with pytest.raises(ValueError, match="katalog"):
        capture(catalog, MAPPING, tmp_path / "capture", Runtime(), client_class=client)
    assert created == [] and not (tmp_path / "capture").exists()


@pytest.mark.parametrize(
    "code", ["network", "http_error", "too_large", "limit", "redirect", "invalid_host"]
)
def test_fetch_error_codes_and_details_are_preserved(tmp_path, code):
    client, created = fake_clients((FetchError(code, "Yerel hata taklidi"), None))
    report = capture(
        small_catalog(),
        MAPPING,
        tmp_path / "capture",
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert record["error"] == {"code": code, "detail": "Yerel hata taklidi"}
    assert (
        record["status"] == "error" and "page" not in record and "history" not in record
    )
    assert created[0].closed


def test_table_mismatch_does_not_leave_accepted_history(tmp_path):
    page, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] += 1
    client, created = fake_clients((page_html(page), response))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog(),
        MAPPING,
        directory,
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert record["error"]["code"] == "parse" and "history" not in record
    assert (directory / record["api"]["file"]).exists()
    assert created[0].closed


def test_capture_preserves_responses_hashes_utc_times_and_selected_scope(tmp_path):
    client, created = fake_clients(*(good_pair(sample) for sample in SAMPLES))
    directory = tmp_path / "capture"
    extra = PRODUCTS[SAMPLES[0]["product_key"]].model_copy(
        update={
            "product_id": 404,
            "product_key": "another_phone",
            "model": "Other Model",
        }
    )
    catalog = Catalog(
        platforms=[], products=[*small_catalog().products, extra], listings=[]
    )
    report = capture(
        catalog,
        MAPPING,
        directory,
        Runtime(),
        [sample["product_key"] for sample in SAMPLES],
        client_class=client,
    )
    assert report == saved_report(directory)
    assert report["result"] == "completed" and len(report["products"]) == 3
    assert report["catalog_product_count"] == 4
    assert report["unmapped_catalog_product_keys"] == ["another_phone"]
    assert all(client.closed for client in created)
    for record, sample, client in zip(report["products"], SAMPLES, created):
        assert record["status"] == "captured" and record["request_count"] == 2
        assert (
            datetime.fromisoformat(record["captured_at_utc"]).utcoffset() == timedelta()
        )
        for kind in ("page", "api"):
            body = (directory / record[kind]["file"]).read_bytes()
            assert hashlib.sha256(body).hexdigest() == record[kind]["sha256"]
        assert (
            json.loads((directory / record["api"]["file"]).read_text("utf-8"))
            == source_pair(sample)[1]
        )
        assert client.calls[-1] == (
            "POST",
            CIMRI_API_URL,
            {
                "queryName": "priceHistoryV2Query",
                "variables": {"productId": sample["cimri_product_id"]},
                "platform": "CIMRI_DESKTOP_V2",
            },
            {"Referer": sample["url"]},
        )


@pytest.mark.parametrize("stage", ["page", "api"])
def test_blocked_stops_remaining_products_and_closes_client(tmp_path, stage):
    pair = list(good_pair())
    pair[0 if stage == "page" else 1] = FetchError("blocked", "HTTP 403")
    client, created = fake_clients(tuple(pair))
    report = capture(
        small_catalog(), MAPPING, tmp_path / "capture", Runtime(), client_class=client
    )
    assert [r["status"] for r in report["products"]] == [
        "error",
        "not_attempted",
        "not_attempted",
    ]
    assert report["products"][1]["reason"] == "blocked"
    assert len(created) == 1 and created[0].closed
    assert "api" not in report["products"][0]


def test_product_parse_error_allows_next_product_and_unmapped_is_explicit(tmp_path):
    mapping = Mapping(version=1, source="cimri", entries=MAPPING.entries[:2])
    bad, response = source_pair()
    bad["product"]["id"] = "111"
    client, created = fake_clients((page_html(bad), response), good_pair(SAMPLES[1]))
    report = capture(
        small_catalog(), mapping, tmp_path / "capture", Runtime(), client_class=client
    )
    assert [r["status"] for r in report["products"]] == [
        "error",
        "captured",
        "unmapped",
    ]
    assert report["result"] == "partial" and len(created) == 2
    assert all(client.closed for client in created)


@pytest.mark.parametrize("stage", ["page", "api"])
def test_ctrl_c_preserves_previous_product_and_report(tmp_path, stage):
    pair = list(good_pair(SAMPLES[1]))
    pair[0 if stage == "page" else 1] = KeyboardInterrupt()
    client, created = fake_clients(good_pair(), tuple(pair))
    directory = tmp_path / "capture"
    with pytest.raises(KeyboardInterrupt):
        capture(small_catalog(), MAPPING, directory, Runtime(), client_class=client)
    report = saved_report(directory)
    assert report["result"] == "interrupted"
    assert [r["status"] for r in report["products"]] == [
        "captured",
        "interrupted",
        "not_attempted",
    ]
    assert report["products"][2]["reason"] == "interrupted"
    assert report["products"][0]["history"]["summary"]["point_count"] == 3
    assert all(client.closed for client in created)


def test_existing_directory_is_never_overwritten_or_requested(tmp_path):
    sentinel = tmp_path / "report.json"
    sentinel.write_text("old report", encoding="utf-8")
    client, created = fake_clients()
    with pytest.raises(FileExistsError):
        capture(small_catalog(), MAPPING, tmp_path, Runtime(), client_class=client)
    assert sentinel.read_text("utf-8") == "old report" and created == []


@pytest.mark.parametrize("keys", [["unknown"], [], [SAMPLES[0]["product_key"]] * 2])
def test_invalid_selection_fails_before_directory_or_network(tmp_path, keys):
    client, created = fake_clients()
    directory = tmp_path / "capture"
    with pytest.raises(ValueError):
        capture(
            small_catalog(), MAPPING, directory, Runtime(), keys, client_class=client
        )
    assert not directory.exists() and created == []


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/cep-telefonlari/a1",
        "http://www.cimri.com/cep-telefonlari/a1",
        "https://www.cimri.com/yenilenmis-cep-telefonlari/a1",
        "https://user@www.cimri.com/cep-telefonlari/a1",
        "https://www.cimri.com:444/cep-telefonlari/a1",
        "https://www.cimri.com/cep-telefonlari/a1#history",
    ],
)
def test_invalid_mapping_url_is_rejected(url):
    data = MAPPING.entries[0].model_dump()
    data["url"] = url
    with pytest.raises(ValidationError):
        MappingEntry.model_validate(data)


@pytest.mark.parametrize("field", ["product_key", "url", "cimri_product_id"])
def test_duplicate_mapping_identities_are_rejected(field):
    data = MAPPING.model_dump()
    data["entries"][1][field] = data["entries"][0][field]
    with pytest.raises(ValidationError):
        Mapping.model_validate(data)


@pytest.mark.parametrize("source_id", [True, 123, "0", "-1", "abc", "１２３"])
def test_invalid_mapping_source_id_is_rejected(source_id):
    data = MAPPING.entries[0].model_dump()
    data["cimri_product_id"] = source_id
    with pytest.raises(ValidationError):
        MappingEntry.model_validate(data)


def test_mapping_outside_active_catalog_is_rejected(tmp_path):
    data = MAPPING.model_dump()
    data["entries"][0]["product_key"] = "unknown"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="katalog"):
        read_mapping(path, small_catalog())


def test_capture_budget_includes_redirect_retry_get_and_post(tmp_path, monkeypatch):
    html, response = good_pair()
    session = Recorder(
        Reply(status=302, location=SAMPLES[0]["url"]),
        Reply(status=503),
        Reply(content=html.encode("utf-8")),
        Reply(content=json.dumps(response).encode()),
    )
    monkeypatch.setattr(http.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    pages = PageClient(
        CIMRI_HOSTS,
        Runtime(request_interval_seconds=0),
        client=session,
        request_budget=4,
    )
    closed = []
    monkeypatch.setattr(pages, "close", lambda: closed.append(True))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog(),
        MAPPING,
        directory,
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=lambda *a, **k: pages,
    )
    assert report["result"] == "completed" and closed == [True]
    assert report["products"][0]["request_count"] == len(session.calls) == 4
    assert [call[0] for call in session.calls] == ["GET", "GET", "GET", "POST"]


def test_budget_exhaustion_does_not_create_api_response(tmp_path, monkeypatch):
    html, _ = good_pair()
    session = Recorder(
        *(Reply(status=302, location=SAMPLES[0]["url"]) for _ in range(3)),
        Reply(content=html.encode("utf-8")),
    )
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    pages = PageClient(
        CIMRI_HOSTS,
        Runtime(request_interval_seconds=0),
        client=session,
        request_budget=4,
    )
    report = capture(
        small_catalog(),
        MAPPING,
        tmp_path / "capture",
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=lambda *a, **k: pages,
    )
    record = report["products"][0]
    assert record["error"]["code"] == "limit" and record["request_count"] == 4
    assert "page" in record and "api" not in record and "history" not in record


def setup_cli(tmp_path, monkeypatch, pairs):
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(small_catalog().model_dump_json(), encoding="utf-8")
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text("{}", encoding="utf-8")
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(MAPPING.model_dump_json(), encoding="utf-8")
    lock_path = tmp_path / "scrape.lock"
    monkeypatch.setenv("CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("RUNTIME_PATH", str(runtime_path))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(lock_path))
    client, created = fake_clients(*pairs)
    monkeypatch.setattr(captures, "PageClient", client)
    args = [
        "capture",
        "--mapping",
        str(mapping_path),
        "--output-dir",
        str(tmp_path / "capture"),
    ]
    return args, created, lock_path


@pytest.mark.parametrize(
    "failure,expected",
    [(None, 0), (FetchError("blocked", "403"), 2), (KeyboardInterrupt(), 130)],
)
def test_cli_exit_output_and_lock_release(
    tmp_path, monkeypatch, capsys, failure, expected
):
    pair = good_pair() if failure is None else (failure, None)
    args, created, lock_path = setup_cli(tmp_path, monkeypatch, [pair])
    args += ["--product-key", SAMPLES[0]["product_key"]]
    assert command.main(args) == expected
    assert len(created) == 1 and created[0].closed
    with scrape_lock(lock_path):
        pass
    text = capsys.readouterr()
    assert (
        "Veritabanına yazılmadı" in text.out
        if expected != 130
        else "durduruldu" in text.err
    )


def test_cli_busy_creates_no_directory_and_can_retry(tmp_path, monkeypatch):
    args, created, lock_path = setup_cli(tmp_path, monkeypatch, [good_pair()])
    args += ["--product-key", SAMPLES[0]["product_key"]]
    with scrape_lock(lock_path):
        assert command.main(args) == 3
    assert created == [] and not (tmp_path / "capture").exists()
    assert command.main(args) == 0


def test_cli_recorded_zero_gap_is_success_with_explicit_missing_count(
    tmp_path, monkeypatch, capsys
):
    page, response = recorded_zero_gap()
    args, created, lock_path = setup_cli(
        tmp_path,
        monkeypatch,
        [good_pair(SAMPLES[0]), good_pair(SAMPLES[1]), (page_html(page), response)],
    )
    assert command.main(args) == 0
    report = saved_report(tmp_path / "capture")
    assert all(record["status"] == "captured" for record in report["products"])
    assert report["products"][2]["history"]["summary"]["missing_price_count"] == 4
    assert all(client.closed for client in created)
    with scrape_lock(lock_path):
        pass
    text = capsys.readouterr().out
    assert "xiaomi_14t_pro_256gb: kaydedildi" in text
    assert "eksik fiyat: 4; tablo: eşleşti (4)" in text


def test_cli_disk_failure_keeps_saved_page_and_releases_lock(tmp_path, monkeypatch):
    args, created, lock_path = setup_cli(tmp_path, monkeypatch, [good_pair()])
    args += ["--product-key", SAMPLES[0]["product_key"]]
    original = captures._save_response

    def failing_save(directory, name, content):
        if name.endswith(".json"):
            raise OSError("Yerel disk hatası taklidi")
        return original(directory, name, content)

    monkeypatch.setattr(captures, "_save_response", failing_save)
    assert command.main(args) == 1
    report = saved_report(tmp_path / "capture")
    assert report["result"] == "failed"
    assert report["error"]["type"] == "OSError"
    assert report["products"][0]["error"]["code"] == "storage"
    assert (tmp_path / "capture" / report["products"][0]["page"]["file"]).exists()
    assert created[0].closed
    with scrape_lock(lock_path):
        pass


def test_cli_invalid_config_never_requests_or_creates_output(tmp_path, monkeypatch):
    args, created, _ = setup_cli(tmp_path, monkeypatch, [])
    (tmp_path / "mapping.json").write_text("{}", encoding="utf-8")
    assert command.main(args) == 1
    assert created == [] and not (tmp_path / "capture").exists()


def test_cli_existing_directory_preserves_files_and_releases_lock(
    tmp_path, monkeypatch, capsys
):
    args, created, lock_path = setup_cli(tmp_path, monkeypatch, [])
    directory = tmp_path / "capture"
    directory.mkdir()
    sentinel = directory / "report.json"
    sentinel.write_text("onceki rapor", encoding="utf-8")
    assert command.main(args) == 1
    assert "klasör zaten var" in capsys.readouterr().err
    assert sentinel.read_text("utf-8") == "onceki rapor" and created == []
    with scrape_lock(lock_path):
        pass


@pytest.mark.parametrize(
    "sample",
    [s for s in FRONTEND_SAMPLES if s["product_key"] in CHANGED_FRONTEND_KEYS],
    ids=lambda s: s["product_key"],
)
def test_capture_recorded_frontend_prices(tmp_path, monkeypatch, sample):
    page, response = deepcopy(sample["page"]), deepcopy(sample["response"])
    original = deepcopy(response)
    moment = datetime.fromisoformat(sample["captured_at_utc"])
    monkeypatch.setattr(captures, "utc_now", lambda: moment)
    client, created = fake_clients((page_html(page), response))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog([sample["product_key"]]),
        Mapping(version=1, source="cimri", entries=[sample["mapping"]]),
        directory,
        Runtime(),
        client_class=client,
    )
    record = report["products"][0]
    assert record["status"] == "captured", record.get("error")
    offer = int(Decimal(str(page["product"]["offers"][0]["price"])) * 100)
    api = int(Decimal(str(response["data"]["priceHistoryV2"]["prices"][0])) * 100)
    history = record["history"]
    assert history["points"][-1] == {"day": "2026-10-08", "price_kurus": offer}
    assert history["summary"]["latest_price"] == {
        "day": "2026-10-08",
        "rule": "page_first_offer",
        "api_price_kurus": api,
        "first_offer_price_kurus": offer,
        "effective_price_kurus": offer,
        "changed": True,
        "table_comparison": (
            "unavailable"
            if sample["product_key"] == "samsung_galaxy_s24_ultra_1024gb"
            else "matched"
        ),
    }
    for kind in ("page", "api"):
        body = (directory / record[kind]["file"]).read_bytes()
        assert hashlib.sha256(body).hexdigest() == record[kind]["sha256"]
    assert (
        json.loads((directory / record["api"]["file"]).read_text("utf-8")) == original
    )
    assert response == original and sample["page"] == page
    assert record["page_started_at_utc"] == moment.isoformat()
    assert record["captured_at_utc"] == moment.isoformat()
    assert len(created[0].calls) == 2 and created[0].closed
    assert saved_report(directory) == report


def frontend_history(sample, **changes):
    identity, table = verified_page(
        page_html(sample["page"]),
        PRODUCTS[sample["product_key"]],
        sample["mapping"]["cimri_product_id"],
    )
    options = {
        "first_offer_price": identity["first_offer_price"],
        "page_started_at_utc": sample["captured_at_utc"],
        "captured_at_utc": sample["captured_at_utc"],
    }
    options.update(changes)
    return history_in_kurus(
        sample["response"], identity["product_id"], table, **options
    )


@pytest.mark.parametrize("sample", FRONTEND_SAMPLES, ids=lambda s: s["product_key"])
def test_recorded_frontend_keeps_dates_previous_prices_and_missing_values(sample):
    original = deepcopy(sample)
    history = frontend_history(sample)
    api = sample["response"]["data"]["priceHistoryV2"]
    expected = []
    for index, price in enumerate(api["prices"]):
        if index == 0 and sample["page"]["product"]["offers"]:
            price = sample["page"]["product"]["offers"][0]["price"]
        expected.append(
            {
                "day": (
                    date.fromisoformat(api["lastDay"]) - timedelta(days=index)
                ).isoformat(),
                "price_kurus": (
                    None if price in (None, 0) else int(Decimal(str(price)) * 100)
                ),
            }
        )
    assert history["points"] == list(reversed(expected))
    latest = history["summary"]["latest_price"]
    assert latest["changed"] == (sample["product_key"] in CHANGED_FRONTEND_KEYS)
    assert history["summary"]["table_compared_rows"] == len(
        sample["page"]["priceHistoryTablePrices"]
    )
    assert sample == original


@pytest.mark.parametrize(
    "offers",
    [
        None,
        {},
        "invalid",
        [None],
        [{}],
        [{"price": None}],
        [{"price": 0}],
        [{"price": False}],
        [{"price": -1}],
        [{"price": "100"}],
        [{"price": 1.001}],
    ],
)
def test_invalid_first_offer_is_rejected_before_api(tmp_path, offers):
    page, response = source_pair()
    page["product"]["offers"] = offers
    client, created = fake_clients((page_html(page), response))
    report = capture(
        small_catalog(),
        MAPPING,
        tmp_path / "capture",
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    record = report["products"][0]
    assert record["status"] == "error" and record["error"]["code"] == "parse"
    assert "api" not in record and "history" not in record
    assert created[0].request_count == 1 and created[0].closed


@pytest.mark.parametrize(
    "price",
    [True, False, -1, "100", 1.001, float("nan"), float("inf"), {}, [], 0, None],
)
def test_first_offer_does_not_hide_invalid_or_missing_api_latest_price(price):
    sample = deepcopy(FRONTEND_SAMPLES[0])
    sample["response"]["data"]["priceHistoryV2"]["prices"][0] = price
    with pytest.raises(FetchError) as error:
        frontend_history(sample)
    assert error.value.code == "parse"


@pytest.mark.parametrize("index", [0, 1])
def test_first_offer_does_not_hide_real_table_conflicts(index):
    sample = deepcopy(FRONTEND_SAMPLES[0])
    sample["page"]["priceHistoryTablePrices"][index]["minPrice"] += 1
    with pytest.raises(FetchError, match="tablo ve grafik"):
        frontend_history(sample)


def test_first_offer_is_not_replaced_by_cheapest_offer():
    sample = deepcopy(FRONTEND_SAMPLES[0])
    first = sample["page"]["product"]["offers"][0]["price"]
    sample["page"]["product"]["offers"].append({"price": first - 100})
    assert frontend_history(sample)["points"][-1]["price_kurus"] == int(
        Decimal(str(first)) * 100
    )


@pytest.mark.parametrize("present", [True, False])
def test_no_first_offer_keeps_api_prices_and_source(present):
    sample = deepcopy(FRONTEND_SAMPLES[0])
    if present:
        sample["page"]["product"]["offers"] = []
    else:
        sample["page"]["product"].pop("offers")
    history = frontend_history(sample)
    latest = history["summary"]["latest_price"]
    assert latest["rule"] == "api" and not latest["changed"]
    assert latest["first_offer_price_kurus"] is None
    assert latest["effective_price_kurus"] == latest["api_price_kurus"]


@pytest.mark.parametrize(
    "start,end",
    [
        (None, "2026-10-08T10:00:00+00:00"),
        ("invalid", "2026-10-08T10:00:00+00:00"),
        ("2026-10-08T09:00:00", "2026-10-08T10:00:00+00:00"),
        ("2026-10-08T09:00:00+03:00", "2026-10-08T10:00:00+00:00"),
        ("2026-10-08T11:00:00+00:00", "2026-10-08T10:00:00+00:00"),
        ("2026-10-08T20:59:59+00:00", "2026-10-08T21:00:00+00:00"),
        ("2026-10-09T10:00:00+00:00", "2026-10-09T10:00:01+00:00"),
    ],
)
def test_first_offer_rejects_invalid_times_midnight_or_stale_api(start, end):
    with pytest.raises(FetchError) as error:
        frontend_history(
            FRONTEND_SAMPLES[0], page_started_at_utc=start, captured_at_utc=end
        )
    assert error.value.code == "parse"


def test_capture_day_uses_istanbul_and_recorded_time_instead_of_current_clock():
    history = frontend_history(
        FRONTEND_SAMPLES[0],
        page_started_at_utc="2026-10-07T21:00:00+00:00",
        captured_at_utc="2026-10-07T21:00:01+00:00",
    )
    assert history["points"][-1]["day"] == "2026-10-08"


def test_capture_midnight_rejection_keeps_raw_evidence_and_closes_client(
    tmp_path, monkeypatch
):
    sample = FRONTEND_SAMPLES[0]
    start = datetime.fromisoformat("2026-10-08T20:59:59+00:00")
    end = start + timedelta(seconds=1)
    moments = iter([start, start, end, end])
    monkeypatch.setattr(captures, "utc_now", lambda: next(moments))
    client, created = fake_clients((page_html(sample["page"]), sample["response"]))
    directory = tmp_path / "capture"
    report = capture(
        small_catalog([sample["product_key"]]),
        Mapping(version=1, source="cimri", entries=[sample["mapping"]]),
        directory,
        Runtime(),
        client_class=client,
    )
    record = report["products"][0]
    assert record["status"] == "error" and record["error"]["code"] == "parse"
    assert "gün sınırını" in record["error"]["detail"] and "history" not in record
    assert all((directory / record[kind]["file"]).is_file() for kind in ("page", "api"))
    assert created[0].closed and report == saved_report(directory)


def test_cli_latest_table_gap_is_reported_and_lock_is_released(
    tmp_path, monkeypatch, capsys
):
    sample = next(
        s
        for s in FRONTEND_SAMPLES
        if s["product_key"] == "samsung_galaxy_s24_ultra_1024gb"
    )
    args, created, lock_path = setup_cli(
        tmp_path, monkeypatch, [(page_html(sample["page"]), sample["response"])]
    )
    (tmp_path / "catalog.json").write_text(
        small_catalog([sample["product_key"]]).model_dump_json(), encoding="utf-8"
    )
    (tmp_path / "mapping.json").write_text(
        Mapping(
            version=1, source="cimri", entries=[sample["mapping"]]
        ).model_dump_json(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        captures, "utc_now", lambda: datetime.fromisoformat(sample["captured_at_utc"])
    )
    assert command.main(args) == 0
    output = capsys.readouterr().out
    assert "sayfanın ilk teklifinden" in output
    assert "Son gün için tablo satırı yok" in output
    assert created[0].closed
    with scrape_lock(lock_path):
        pass


def test_legacy_tl_history_does_not_apply_frontend_adjustment():
    sample = next(
        s
        for s in FRONTEND_SAMPLES
        if s["product_key"] == "apple_iphone_16_pro_max_512gb"
    )
    with pytest.raises(FetchError, match="tablo ve grafik"):
        cimri_history(
            sample["response"],
            sample["mapping"]["cimri_product_id"],
            sample["page"]["priceHistoryTablePrices"],
        )
