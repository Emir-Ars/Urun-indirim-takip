"""Yerel istemcinin veri, hedef, hata ve kaynak bırakma sözleşmeleri."""

import copy
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.api.schemas import HealthResponse
from app.ui.api_client import ApiClient, ApiClientError, _validate_target
from test_api import stub as _stub

stub = _stub
ROOT = Path(__file__).resolve().parents[1]
KEY = "apple_iphone_15_128gb"
AT = "2026-10-09T15:00:00+03:00"
PRICE = 2**60 + 7
PRODUCT = {
    "product_id": 1,
    "product_key": KEY,
    "brand": "Apple",
    "model": "iPhone 15",
    "storage_gb": 128,
    "active": False,
}


def product_payload():
    offer = {
        "run_id": 2,
        "listing_id": "a",
        "product_id": 1,
        "platform": "hepsiburada",
        "platform_name": "Hepsiburada",
        "platform_active": True,
        "url": "https://www.hepsiburada.com/telefon-p-HBC123",
        "color": "Siyah",
        "listing_active": False,
        "checked_at": AT,
        "outcome": "offer",
        "current_price": PRICE,
        "original_price": None,
        "seller_name": "Ornek",
        "seller_rating": 9.25,
        "seller_rating_scale": 10,
        "stock_status": "Stokta Var",
        "error_code": None,
    }
    point = {
        "run_id": 2,
        "product_id": 1,
        "run_started_at": AT,
        "run_finished_at": AT,
        "planned_pages": 2,
        "answered_pages": 1,
        "offer_pages": 1,
        "sold_out_pages": 0,
        "error_pages": 0,
        "best_price": PRICE,
        "best_listing_id": "a",
        "best_checked_at": AT,
        "last_checked_at": AT,
        "previous_run_id": 1,
        "previous_best_price": None,
        "hours_since_previous": 12.0,
        "comparable_with_previous": False,
        "planned_listing_ids": ["a", "b"],
        "partial": True,
        "unchecked_pages": 1,
    }
    metric = {
        "value": None,
        "reasons": ["incomplete_scope"],
        "period_started_at": None,
        "period_ended_at": None,
        "observations": 0,
    }
    previous = dict(
        point,
        run_id=1,
        best_price=None,
        best_listing_id=None,
        best_checked_at=None,
        offer_pages=0,
        sold_out_pages=1,
        previous_run_id=None,
        hours_since_previous=None,
    )
    market = {
        "day": "2026-10-08",
        "price_kurus": 10001,
        "source": "cimri",
        "source_product_id": "123456",
        "source_url": "https://www.cimri.com/test,a123456",
        "captured_at": AT,
    }
    return {
        "product": copy.deepcopy(PRODUCT),
        "state": "offer",
        "current": point,
        "checks": [copy.deepcopy(offer)],
        "best_offer": offer,
        "last_successful_offer": dict(offer, run_id=1, current_price=9999),
        "history": [previous, copy.deepcopy(point)],
        "cimri_history": [market, dict(market, day="2026-10-09", price_kurus=None)],
        "statistics": {
            "source_run_id": 2,
            "scope_started_at": None,
            "scope_ended_at": None,
            "scope_runs": 0,
            "planned_listing_ids": ["a", "b"],
            "low_30d": copy.deepcopy(metric),
            "high_in_scope": copy.deepcopy(metric),
            "volatility_30d": dict(metric, transitions=0, days=0),
        },
        "generated_at": AT,
        "currency": "TRY",
        "price_age_seconds": 0.0,
        "is_stale": False,
    }


def reply(data, status=200):
    return httpx.Response(status, content=json.dumps(data).encode("utf-8"))


class Recorder(httpx.MockTransport):
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.responses = []
        self.closed = 0
        super().__init__(self.respond)

    def respond(self, request):
        self.calls.append(request)
        assert self.replies, "Beklenmeyen ek HTTP isteği"
        result = self.replies.pop(0)
        if isinstance(result, BaseException):
            raise result
        self.responses.append(result)
        return result

    def close(self):
        self.closed += 1


def assert_error(error, code, status=None):
    assert error.value.code == code
    assert error.value.status_code == status
    assert error.value.message == str(error.value)
    assert "private" not in str(error.value)
    assert "SELECT" not in str(error.value)


def test_four_methods_use_fixed_get_paths_and_typed_data():
    run = {
        "run_id": 2,
        "trigger": "manual",
        "status": "completed",
        "started_at": AT,
        "finished_at": AT,
        "planned_count": 2,
    }
    wire = product_payload()
    recorder = Recorder(
        reply({"ready": True}),
        reply({"running": None, "completed": run}),
        reply([PRODUCT]),
        reply(wire),
    )
    with ApiClient(transport=recorder) as client:
        assert client.get_health().ready is True
        status = client.get_status()
        assert status.running is None and status.completed.run_id == 2
        assert status.completed.started_at == datetime(
            2026, 10, 9, 12, tzinfo=timezone.utc
        )
        products = client.list_products()
        assert isinstance(products, tuple) and products[0].active is False
        result = client.get_product(KEY)
    assert [request.url.path for request in recorder.calls] == [
        "/health",
        "/api/v1/status",
        "/api/v1/products",
        f"/api/v1/products/{KEY}",
    ]
    assert all(
        request.method == "GET"
        and request.url.host == "127.0.0.1"
        and request.url.port == 8000
        for request in recorder.calls
    )
    assert dict(recorder.calls[-1].url.params) == {
        "history_days": "30",
        "cimri_days": "366",
    }
    assert result.best_offer.current_price == PRICE
    assert type(result.best_offer.current_price) is int
    assert result.last_successful_offer.current_price == 9999
    assert result.best_offer.seller_rating == 9.25
    assert result.best_offer.seller_rating_scale == 10
    assert result.current.partial and result.current.unchecked_pages == 1
    assert result.history[0].best_price is None
    assert len(result.history) == len(result.cimri_history) == 2
    assert result.cimri_history[0].day == date(2026, 10, 8)
    assert result.cimri_history[0].price_kurus == 10001
    assert result.cimri_history[1].price_kurus is None
    assert result.statistics.low_30d.reasons == ("incomplete_scope",)
    assert result.statistics.volatility_30d.transitions == 0
    assert result.generated_at.tzinfo == timezone.utc
    assert result.price_age_seconds == 0.0 and result.is_stale is False
    assert recorder.closed == 1 and all(
        response.is_closed for response in recorder.responses
    )
    with pytest.raises(ValidationError):
        result.currency = "USD"


def test_empty_responses_are_valid_and_do_not_invent_data():
    recorder = Recorder(reply([]), reply({"running": None, "completed": None}))
    with ApiClient(transport=recorder) as client:
        assert client.list_products() == ()
        assert client.get_status().completed is None


@pytest.mark.parametrize("days", [1, 366])
def test_day_boundaries_reach_api(days):
    recorder = Recorder(reply(product_payload()))
    with ApiClient(transport=recorder) as client:
        client.get_product(KEY, days, days)
    assert dict(recorder.calls[0].url.params) == {
        "history_days": str(days),
        "cimri_days": str(days),
    }


@pytest.mark.parametrize("name", ["history_days", "cimri_days"])
@pytest.mark.parametrize("value", [0, 367, -1, 1.0, "30", True, None])
def test_invalid_days_are_rejected_before_http(name, value):
    recorder = Recorder()
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_product(KEY, **{name: value})
    assert_error(error, "invalid_request")
    assert not recorder.calls


@pytest.mark.parametrize(
    "key",
    [
        "",
        "../health",
        "a/b",
        "//example.com",
        "http://example.com",
        "a?x=1",
        "a#x",
        "a%2Fb",
        "Apple",
        "a\n",
        1,
        None,
    ],
)
def test_invalid_key_cannot_change_request_target(key):
    recorder = Recorder()
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_product(key)
    assert error.value.code in ("invalid_request", "invalid_target")
    assert not recorder.calls


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8000/health",
        "http://example.com:8000/health",
        "http://localhost:8000/health",
        "http://127.0.0.1:8001/health",
        "http://127.0.0.1/health",
        "http://[::1]:8000/health",
        "http://private@127.0.0.1:8000/health",
        "http://127.0.0.1:8000/health#x",
        "http://127.0.0.1:8000/admin",
        "http://127.0.0.1:8000/api/v1/products/a/b",
        "http://127.0.0.1:8000/health?next=http://example.com",
        "http://127.0.0.1:8000/api/v1/products/a?next=http://example.com",
        "http://127.0.0.1:8000/api/v1/products/a?history_days=0",
        "http://127.0.0.1:8000/api/v1/products/a?history_days=367",
        "http://127.0.0.1:8000/api/v1/products/a?history_days=1.5",
        "http://127.0.0.1:8000/api/v1/products/a?history_days=1&history_days=2",
    ],
)
def test_only_allowed_origin_paths_and_queries_are_accepted(url):
    with pytest.raises(ApiClientError) as error:
        _validate_target(httpx.Request("GET", url))
    assert_error(error, "invalid_target")


def test_post_is_not_an_allowed_request():
    with pytest.raises(ApiClientError) as error:
        _validate_target(httpx.Request("POST", "http://127.0.0.1:8000/health"))
    assert_error(error, "invalid_target")


def test_changed_base_url_is_rejected_before_transport():
    recorder = Recorder()
    with ApiClient(transport=recorder) as client:
        client._client.base_url = "http://example.com:8000"
        with pytest.raises(ApiClientError) as error:
            client.get_health()
    assert_error(error, "invalid_target")
    assert not recorder.calls


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_never_sends_a_second_request(status):
    response = httpx.Response(
        status, headers={"Location": "https://example.com/private"}
    )
    recorder = Recorder(response)
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_health()
    assert_error(error, "redirect_rejected", status)
    assert len(recorder.calls) == 1 and response.is_closed and recorder.closed == 1


@pytest.mark.parametrize(
    "status,code",
    [
        (404, "product_not_found"),
        (404, "not_found"),
        (405, "method_not_allowed"),
        (422, "invalid_request"),
        (500, "internal_error"),
        (503, "pool_unavailable"),
        (503, "database_unavailable"),
        (503, "read_access_denied"),
        (503, "schema_not_ready"),
    ],
)
def test_known_api_errors_keep_code_but_do_not_expose_message(status, code):
    recorder = Recorder(
        reply({"detail": {"code": code, "message": "private SELECT secret"}}, status)
    )
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_product(KEY)
    assert_error(error, code, status)
    assert len(recorder.calls) == 1


@pytest.mark.parametrize(
    "body",
    [
        b"private SELECT",
        b"{}",
        b'{"detail":"private"}',
        b'{"detail":{"code":"unexpected","message":"private"}}',
        b'{"detail":{"code":"internal_error","message":"private"}}',
    ],
)
def test_unknown_malformed_or_mismatched_error_is_safe(body):
    recorder = Recorder(httpx.Response(503, content=body))
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_health()
    assert_error(error, "http_error", 503)


@pytest.mark.parametrize("status", [201, 204, 206])
def test_unexpected_success_status_is_not_a_valid_result(status):
    recorder = Recorder(reply({"ready": True}, status))
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_health()
    assert_error(error, "invalid_response", status)


@pytest.mark.parametrize(
    "body",
    [
        b"private SELECT",
        b"{",
        b"null",
        b"[]",
        b"{}",
        b'{"ready":false}',
        b'{"ready":true,"extra":1}',
    ],
)
def test_bad_successful_response_is_not_empty_success(body):
    recorder = Recorder(httpx.Response(200, content=body))
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_health()
    assert_error(error, "invalid_response", 200)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "float_price",
        "string_price",
        "boolean_price",
        "rating_nan",
        "scale_inf",
        "naive_time",
        "bad_date",
        "reason",
        "currency",
        "missing_currency",
        "missing_active",
    ],
)
def test_bad_product_fields_are_rejected(mutation):
    data = product_payload()
    if mutation == "missing":
        del data["checks"]
    elif mutation == "extra":
        data["all_history"] = []
    elif mutation in ("float_price", "string_price", "boolean_price"):
        data["best_offer"]["current_price"] = {
            "float_price": 100.5,
            "string_price": "100",
            "boolean_price": True,
        }[mutation]
    elif mutation == "rating_nan":
        data["best_offer"]["seller_rating"] = float("nan")
    elif mutation == "scale_inf":
        data["best_offer"]["seller_rating_scale"] = float("inf")
    elif mutation == "naive_time":
        data["generated_at"] = "2026-10-09T12:00:00"
    elif mutation == "bad_date":
        data["cimri_history"][0]["day"] = "2026-02-30"
    elif mutation == "reason":
        data["statistics"]["low_30d"]["reasons"] = ["invented"]
    elif mutation == "currency":
        data["currency"] = "USD"
    elif mutation == "missing_currency":
        del data["currency"]
    elif mutation == "missing_active":
        del data["product"]["active"]
    recorder = Recorder(reply(data))
    with (
        ApiClient(transport=recorder) as client,
        pytest.raises(ApiClientError) as error,
    ):
        client.get_product(KEY)
    assert_error(error, "invalid_response", 200)


@pytest.mark.parametrize(
    "failure,code",
    [
        (httpx.ConnectTimeout, "timeout"),
        (httpx.ReadTimeout, "timeout"),
        (httpx.WriteTimeout, "timeout"),
        (httpx.PoolTimeout, "timeout"),
        (httpx.ConnectError, "connection_error"),
        (httpx.ReadError, "connection_error"),
        (httpx.WriteError, "connection_error"),
        (httpx.RemoteProtocolError, "connection_error"),
        (httpx.DecodingError, "connection_error"),
    ],
)
def test_transport_failure_does_not_retry_and_next_call_recovers(failure, code):
    recorder = Recorder(failure("private SELECT"), reply({"ready": True}))
    with ApiClient(transport=recorder) as client:
        with pytest.raises(ApiClientError) as error:
            client.get_health()
        assert_error(error, code)
        assert len(recorder.calls) == 1
        assert client.get_health().ready
    assert len(recorder.calls) == 2 and recorder.closed == 1


def test_calls_are_not_cached_and_http_error_does_not_replace_data():
    recorder = Recorder(
        reply([PRODUCT]), httpx.Response(503, content=b"private"), reply([])
    )
    with ApiClient(transport=recorder) as client:
        assert len(client.list_products()) == 1
        with pytest.raises(ApiClientError) as error:
            client.list_products()
        assert_error(error, "http_error", 503)
        assert client.list_products() == ()
    assert len(recorder.calls) == 3


def test_proxy_environment_is_ignored_and_timeouts_are_explicit(monkeypatch):
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        monkeypatch.setenv(variable, "http://example.com:8123")
    monkeypatch.setenv("NO_PROXY", "")
    recorder = Recorder(reply({"ready": True}))
    with ApiClient(transport=recorder) as client:
        assert not client._client._trust_env
        assert client._client._mounts == {}
        assert not client._client.follow_redirects
        client.get_health()
    assert recorder.calls[0].extensions["timeout"] == {
        "connect": 3,
        "read": 15,
        "write": 3,
        "pool": 3,
    }


def test_close_is_idempotent_and_closed_client_does_not_send():
    recorder = Recorder()
    client = ApiClient(transport=recorder)
    client.close()
    client.close()
    with pytest.raises(ApiClientError) as error:
        client.get_health()
    assert_error(error, "client_closed")
    assert recorder.closed == 1 and not recorder.calls


def test_keyboard_interrupt_is_not_converted_and_context_closes():
    failure = KeyboardInterrupt()
    recorder = Recorder(failure)
    with pytest.raises(KeyboardInterrupt) as error:
        with ApiClient(transport=recorder) as client:
            client.get_health()
    assert error.value is failure and recorder.closed == 1


def test_unexpected_programming_error_is_not_disguised_as_transport_error():
    recorder = Recorder(ValueError("private"))
    with pytest.raises(ValueError):
        with ApiClient(transport=recorder) as client:
            client.get_health()
    assert recorder.closed == 1


def test_import_and_construction_do_not_load_database_or_open_network():
    source = """
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('app.database', 'app.api.database', 'app.api.main',
                     'app.api.models', 'app.price_statistics', 'psycopg',
                     'psycopg_pool', 'fastapi', 'streamlit', 'curl_cffi')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman yuklendi: ' + fullname)
def no_connection(*args, **kwargs):
    raise AssertionError('Ag baglantisi acildi')
sys.meta_path.insert(0, Guard())
socket.create_connection = no_connection
from app.ui.api_client import ApiClient
with ApiClient():
    pass
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_client_reads_real_fastapi_routes_without_network(stub):
    pool, server = stub
    requests = []

    def bridge(request):
        requests.append(request)
        return server.get(str(request.url))

    with ApiClient(transport=httpx.MockTransport(bridge)) as client:
        assert client.get_health() == HealthResponse()
        assert client.list_products() == ()
        assert client.get_status().running is None
        with pytest.raises(ApiClientError) as error:
            client.get_product(KEY)
        assert_error(error, "product_not_found", 404)
    assert pool.borrowed == pool.returned == len(requests) == 4


def test_real_api_product_conversion_matches_shared_client_contract(stub, monkeypatch):
    from app.api.models import product_response
    from app.api import main
    from test_price_statistics import CIMRI, START, run, snapshot

    _, server = stub
    data = snapshot(
        run(1, START, PRICE), run(2, START.replace(day=2), None), cimri=CIMRI
    )
    monkeypatch.setattr(main.read, "read_product", lambda *args: data)
    monkeypatch.setattr(main, "utc_now", lambda: START)
    with ApiClient(
        transport=httpx.MockTransport(lambda request: server.get(str(request.url)))
    ) as client:
        result = client.get_product(KEY)
    assert result == product_response(data, START)
    assert result.state == "sold_out" and result.best_offer is None
    assert result.history[-1].best_price is None
    assert result.cimri_history[0].price_kurus == 1
    assert result.statistics.high_in_scope.value == PRICE


def test_existing_catalog_keys_can_use_client_validation():
    catalog = json.loads((ROOT / "config/catalog.json").read_text(encoding="utf-8"))
    recorder = Recorder(
        *(
            reply({"detail": {"code": "product_not_found", "message": "none"}}, 404)
            for product in catalog["products"]
        )
    )
    with ApiClient(transport=recorder) as client:
        for product in catalog["products"]:
            with pytest.raises(ApiClientError) as error:
                client.get_product(product["product_key"])
            assert_error(error, "product_not_found", 404)
    assert len(recorder.calls) == len(catalog["products"])
