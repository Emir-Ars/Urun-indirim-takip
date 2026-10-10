"""Gerçek test DB'si → API → istemci → Streamlit zincirini birlikte sınar."""

from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.ui import api_client
from app.ui.api_client import ApiClient
from test_api import client as _client, world as _world
from test_database_read import KEY, START, add_market, add_run
from test_ui import messages

client = _client
world = _world
SCREEN = Path(__file__).resolve().parents[1] / "app/ui/main.py"


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
    yield AppTest.from_file(SCREEN), failures, calls
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
