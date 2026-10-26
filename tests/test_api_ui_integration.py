"""Gerçek test DB'si → API → istemci → Streamlit zincirini birlikte sınar."""

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.ui import api_client
from app.ui.api_client import ApiClient
from app.contracts import PriceObservation
from app.collection.service import to_result
from app.database import runs
from tests.support.read_world import KEY, START, add_market, add_run, close_run
from tests.support.ui_samples import APP_TEST_TIMEOUT, messages

SCREEN = Path(__file__).resolve().parents[1] / "app/ui/main.py"


def test_selected_link_survives_collection_database_api_and_screen(
    world, integrated_screen, client
):
    add_run(world, START, {"a": ("offer", 30000)})
    app, _, _ = integrated_screen
    app.run()
    assert app.get("link_button")[0].proto.label == "Ürün sayfasını aç"
    run_id = add_run(
        world,
        START + timedelta(hours=12),
        {"a": "planned", "b": "planned"},
        status="running",
    )
    urls = {}
    for page, price, merchant in [("a", 20000, 9), ("b", 10000, 11)]:
        product_url = f"https://www.trendyol.com/phone-p-{merchant}"
        urls[page] = product_url + f"?merchantId={merchant}"
        world.execute(
            "UPDATE listings SET url=%s WHERE listing_id=%s", (product_url, page)
        )
        observation = PriceObservation(
            listing_id=page,
            product_id=1,
            platform="trendyol",
            product_name="Apple iPhone 15 128 GB",
            product_url=product_url,
            offer_url=urls[page],
            current_price=price,
            seller_name=f"Satıcı {page}",
            stock_status="Stokta Var",
            timestamp=START + timedelta(hours=12, minutes=1),
        )
        runs.record_result(world, run_id, page, to_result(observation))
    close_run(world, run_id, START + timedelta(hours=12))
    response = client.get(f"/api/v1/products/{KEY}")
    assert response.status_code == 200
    result = response.json()
    assert result["best_offer"]["listing_id"] == "b"
    assert result["best_offer"]["offer_url"] == urls["b"]
    assert {row["listing_id"]: row["offer_url"] for row in result["checks"]} == urls
    app.button(key="refresh").click().run()
    assert not app.exception
    button = app.get("link_button")[0].proto
    assert button.label == "Satıcı teklifini aç" and button.url == urls["b"]


@pytest.fixture
def integrated_screen(client, monkeypatch):
    calls, opened, closed = [], [], []
    failures = {"enabled": False}

    def send(request):
        calls.append(request)
        if failures["enabled"]:
            raise httpx.ConnectError("Yerel test kesintisi", request=request)
        response = client.get(str(request.url))
        if request.url.path.startswith("/api/v1/products/"):
            failures["last_product"] = response.json()
        return httpx.Response(response.status_code, content=response.content)

    class Reader(ApiClient):
        def __init__(self):
            super().__init__(transport=httpx.MockTransport(send))
            opened.append(self)

        def close(self):
            super().close()
            closed.append(self)

    monkeypatch.setattr(api_client, "ApiClient", Reader)
    yield AppTest.from_file(SCREEN, default_timeout=APP_TEST_TIMEOUT), failures, calls
    assert opened == closed
    assert all(reader._client.is_closed for reader in closed)


@pytest.mark.parametrize(
    "outcome,text,partial",
    [
        (("offer", 1234567), "Satıcı a", False),
        ("sold_out", "Takip edilen bütün sayfalarda stok yok.", False),
        ("error", "Son tamamlanmış turda fiyat doğrulanamadı.", True),
        ("planned", "Son tamamlanmış turda fiyat doğrulanamadı.", True),
    ],
)
def test_real_result_and_previous_success_reach_the_screen(
    world, integrated_screen, outcome, text, partial
):
    add_run(world, START, {"a": ("offer", 2000001)})
    add_run(world, START + timedelta(hours=12), {"a": outcome})
    add_market(world, START.date(), None)
    app, _, calls = integrated_screen
    app.run()
    assert not app.exception
    assert text in messages(app)
    if not isinstance(outcome, tuple):
        assert any(
            "Son başarılı fiyat" == item.label and item.value == "20.000,01 TL"
            for item in app.metric
        )
    else:
        assert not any(item.label == "Son başarılı fiyat" for item in app.metric)
    assert any("Kısmi kapsam:" in item.value for item in app.warning) is partial
    assert "Seçilen Cimri aralığında fiyatlar eksik." in messages(app)
    if isinstance(outcome, tuple):
        assert any(
            item.label == "Takip edilen en ucuz teklif" and item.value == "12.345,67 TL"
            for item in app.metric
        )
    else:
        assert not any(
            item.label == "Takip edilen en ucuz teklif" for item in app.metric
        )
    assert [request.url.path for request in calls] == [
        "/api/v1/products",
        "/api/v1/status",
        f"/api/v1/products/{KEY}",
    ]


def test_selection_ranges_error_and_recovery_use_real_api(world, integrated_screen):
    add_run(world, START, {"a": ("offer", 20001), "d": ("offer", 30001)})
    add_run(
        world,
        START + timedelta(days=10),
        {"a": ("offer", 19901), "d": ("offer", 29901)},
    )
    add_market(world, START.date(), 21001)
    add_market(world, START.date() + timedelta(days=10), None)
    app, failures, calls = integrated_screen
    app.run()
    assert not app.exception
    app.selectbox(key="_product").select("samsung_s24_256gb").run()
    app.selectbox(key="_history_days").select(7).run()
    app.selectbox(key="_cimri_days").select(7).run()
    assert any(item.value == "299,01 TL" for item in app.metric)
    assert "Cimri geçmişi bulunmuyor" in messages(app)
    assert len(app.get("vega_lite_chart")) == 1
    assert len(failures["last_product"]["history"]) == 1
    failures["enabled"] = True
    app.button(key="refresh").click().run()
    assert "Yerel API'ye erişilemiyor." in messages(app)
    assert not app.metric and not app.get("vega_lite_chart")
    failures["enabled"] = False
    app.button(key="refresh").click().run()
    assert not app.exception and not app.error
    assert app.selectbox(key="_product").value == "samsung_s24_256gb"
    assert (
        app.selectbox(key="_history_days").value
        == app.selectbox(key="_cimri_days").value
        == 7
    )
    assert calls[-1].url.params["history_days"] == "7"
    assert any(item.value == "299,01 TL" for item in app.metric)


def test_no_completed_history_is_not_substituted_with_cimri(world, integrated_screen):
    add_market(world, START.date(), 21001)
    app, _, _ = integrated_screen
    app.run()
    assert not app.exception
    assert "Bu telefon için tamamlanmış toplama turu bulunmuyor." in messages(app)
    assert "Kendi fiyat geçmişimiz bulunmuyor." in messages(app)
    assert all(item.value == "—" for item in app.metric)
    assert len(app.get("vega_lite_chart")) == 1
