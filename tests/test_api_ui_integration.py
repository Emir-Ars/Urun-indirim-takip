"""Gerçek test DB'si → API → istemci → Streamlit zincirini birlikte sınar."""

from datetime import timedelta
from pathlib import Path
import pickle
import shutil

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.ui import api_client
from app.ui.api_client import ApiClient
from app.contracts import PriceObservation
from app.collection.service import to_result
from app.database import runs
from app.ml import models, shadow_display, shadow_records
from app.ml.__main__ import main as ml_main
from tests.support.ml import label_snapshot
from tests.support.shadow_display import (
    NOW,
    append_daily_record,
    display_case,
)
from tests.support.read_world import KEY, START, add_market, add_run, close_run
from tests.support.ui_samples import APP_TEST_TIMEOUT, messages, sample_prediction

SCREEN = Path(__file__).resolve().parents[1] / "app/ui/main.py"


@pytest.fixture
def prediction_store(tmp_path, monkeypatch, request):
    kind = getattr(request, "param", "available")
    options = {
        "available": {},
        "short": {"short": True},
        "missing": {"prices": [10000] * 363 + [None] * 5 + [10000]},
        "unseen": {"unseen": True},
    }[kind]
    case = display_case(tmp_path, **options)
    case.clock = {"now": NOW}
    monkeypatch.setattr(shadow_records, "load_config", lambda path=None: case.config)
    monkeypatch.setattr(shadow_display, "utc_now", lambda: case.clock["now"])
    return case


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
        if request.url.path.startswith(
            "/api/v1/products/"
        ) and not request.url.path.endswith("/prediction"):
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
        f"/api/v1/products/{KEY}/prediction",
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
    assert calls[-2].url.params["history_days"] == "7"
    assert calls[-1].url.path.endswith("/prediction") and not calls[-1].url.query
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


def test_prediction_503_is_isolated_from_real_price_api_and_can_recover(
    world, integrated_screen, monkeypatch
):
    outcome = {"broken": False}

    def prediction(product):
        if outcome["broken"]:
            raise ValueError("private: bozuk kayıt")
        return sample_prediction("available").model_dump()

    monkeypatch.setattr(shadow_display, "prediction_for", prediction)
    add_run(world, START, {"a": ("offer", 20001)})
    app, _, calls = integrated_screen
    app.run()
    assert not app.exception
    assert any(item.value == "%12,3" for item in app.metric)
    outcome["broken"] = True
    app.button(key="refresh").click().run()
    assert not app.exception and not app.error
    assert "Tahmin kaydı şu anda doğrulanamıyor." in messages(app)
    assert "private" not in messages(app)
    assert all(item.value != "%12,3" for item in app.metric)
    assert any(item.value == "200,01 TL" for item in app.metric)
    assert len(app.get("vega_lite_chart")) == 1 and app.dataframe
    assert calls[-1].url.path == f"/api/v1/products/{KEY}/prediction"
    outcome["broken"] = False
    app.button(key="refresh").click().run()
    assert not app.exception
    assert any(item.value == "%12,3" for item in app.metric)


def test_stored_record_and_source_reach_real_api_client_and_card_without_model(
    world, integrated_screen, prediction_store, client, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("İstek sırasında model, eğitim veya yeni tahmin kullanıldı")

    for name in ("fit_models", "fit_frozen", "predict_frozen", "design_matrix"):
        monkeypatch.setattr(models, name, forbidden)
    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    add_run(world, START, {"a": ("offer", 20001)})
    case = prediction_store
    before = {
        path: path.read_bytes() for path in case.root.rglob("*") if path.is_file()
    }
    app, _, calls = integrated_screen
    app.run()
    assert not app.exception and not app.error
    metrics = {item.label: item.value for item in app.metric}
    assert metrics["Belirtilen dönemde en az %5 düşüş olasılığı"] == "%37,0"
    assert metrics["Takip edilen en ucuz teklif"] == "200,01 TL"
    for value in (
        "Başlangıç fiyatı: 100,00 TL",
        "Başlangıç günü: 04.01.2027",
        "Akşam turu: 04.01.2027 22:30:00 · İstanbul",
        "Tahmin dönemi: 05.01.2027 — 11.01.2027",
        "Başlangıç kapsamı: 1 sayfa",
    ):
        assert value in messages(app)
    response = client.get(f"/api/v1/products/{KEY}/prediction")
    assert (
        response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    )
    payload = response.json()
    assert payload["state"] == "available"
    assert payload["forecast"]["probability"] == case.row["probabilities"]["r2_platt"]
    assert payload["forecast"]["reference_price_kurus"] == 10000
    assert "features" not in payload and "probabilities" not in payload
    assert calls[-1].url.path.endswith("/prediction")
    after = {path: path.read_bytes() for path in case.root.rglob("*") if path.is_file()}
    assert before == after


@pytest.mark.parametrize(
    "prediction_store,reason_text",
    [
        ("short", "fiyat geçmişi henüz 30 güne ulaşmadı"),
        ("missing", "eksik günlük fiyat oranı %30'dan fazla"),
        ("unseen", "telefon ailesi modelin eğitim verisinde bulunmuyor"),
    ],
    indirect=["prediction_store"],
)
def test_real_record_eligibility_hides_probability_through_the_whole_screen(
    world, integrated_screen, prediction_store, client, reason_text
):
    add_run(world, START, {"a": ("offer", 20001)})
    app, _, _ = integrated_screen
    app.run()
    assert not app.exception and not app.error
    assert reason_text in messages(app)
    assert all(item.value != "%37,0" for item in app.metric)
    assert any(item.value == "200,01 TL" for item in app.metric)
    payload = client.get(f"/api/v1/products/{KEY}/prediction").json()
    assert payload["state"] == "insufficient_data" and payload["forecast"] is None
    assert "probability" not in str(payload)


def test_midnight_missing_record_and_next_daily_record_replace_the_card(
    world, integrated_screen, prediction_store
):
    case = prediction_store
    add_run(world, START, {"a": ("offer", 20001), "d": ("offer", 30001)})
    app, _, calls = integrated_screen
    app.run()
    assert any(item.value == "%37,0" for item in app.metric)
    app.selectbox(key="_product").select("samsung_s24_256gb").run()
    assert "Güncel tahmin kaydı bekleniyor." in messages(app)
    assert all(item.value != "%37,0" for item in app.metric)
    assert any(item.value == "300,01 TL" for item in app.metric)
    app.selectbox(key="_product").select(KEY).run()
    app.selectbox(key="_history_days").select(7).run()
    assert "Tahmin dönemi: 05.01.2027 — 11.01.2027" in messages(app)
    assert not calls[-1].url.query
    # 21 UTC, İstanbul takviminde yeni günün başlangıcıdır.
    case.clock["now"] = NOW + timedelta(hours=9)
    app.button(key="refresh").click().run()
    assert not app.exception
    assert "Güncel tahmin kaydı bekleniyor." in messages(app)
    assert all(item.value != "%37,0" for item in app.metric)
    old_files = {path: path.read_bytes() for path in case.folder.iterdir()}
    snapshot = label_snapshot(count=370, prices=[10000] * 369 + [15000])
    append_daily_record(case, snapshot)
    case.clock["now"] = NOW + timedelta(days=1)
    app.button(key="refresh").click().run()
    assert not app.exception and not app.error
    assert any(item.value == "%42,0" for item in app.metric)
    assert all(item.value != "%37,0" for item in app.metric)
    assert "Başlangıç fiyatı: 150,00 TL" in messages(app)
    assert "Tahmin dönemi: 06.01.2027 — 12.01.2027" in messages(app)
    assert app.selectbox(key="_history_days").value == 7
    assert all(path.read_bytes() == content for path, content in old_files.items())


@pytest.mark.parametrize("failure", ["hash", "duplicate", "missing_source"])
def test_broken_stored_evidence_clears_card_and_recovery_reads_original_files(
    world, integrated_screen, prediction_store, failure
):
    case = prediction_store
    add_run(world, START, {"a": ("offer", 20001)})
    app, _, _ = integrated_screen
    app.run()
    assert any(item.value == "%37,0" for item in app.metric)
    restore = None
    if failure == "hash":
        path = case.folder / "predictions.jsonl"
        restore = path.read_bytes()
        path.write_bytes(b"private: bozuk kayit")
    elif failure == "missing_source":
        path = case.root / "goruntuler" / "veri_01" / "snapshot.json"
        restore = path.read_bytes()
        path.unlink()
    else:
        duplicate = case.root / "tahmin_duplicate"
        shutil.copytree(case.folder, duplicate)
    app.button(key="refresh").click().run()
    assert not app.exception and not app.error
    assert "Tahmin kaydı şu anda doğrulanamıyor." in messages(app)
    assert "private" not in messages(app)
    assert all(item.value != "%37,0" for item in app.metric)
    assert any(item.value == "200,01 TL" for item in app.metric)
    if restore is not None:
        path.write_bytes(restore)
    else:
        (duplicate / "manifest.json").unlink()
    app.button(key="refresh").click().run()
    assert not app.exception and not app.error
    assert any(item.value == "%37,0" for item in app.metric)


def test_cli_disable_and_rejected_opening_affect_the_real_card(
    world, integrated_screen, prediction_store, client
):
    case = prediction_store
    add_run(world, START, {"a": ("offer", 20001)})
    app, _, _ = integrated_screen
    app.run()
    assert any(item.value == "%37,0" for item in app.metric)
    immutable = {path: path.read_bytes() for path in case.folder.iterdir()}
    assert ml_main(["shadow-display", "--disable", "--config", str(case.path)]) == 0
    app.button(key="refresh").click().run()
    assert "Tahmin gösterimi kapalı." in messages(app)
    assert all(item.value != "%37,0" for item in app.metric)
    payload = client.get(f"/api/v1/products/{KEY}/prediction").json()
    assert payload["state"] == "closed" and payload["forecast"] is None
    assert "probability" not in str(payload)
    approval = (case.root / shadow_display.APPROVAL_FILE).read_bytes()
    case.clock["now"] = NOW - timedelta(days=1)
    assert (
        ml_main(
            [
                "shadow-display",
                "--evaluation",
                str(case.evaluation),
                "--config",
                str(case.path),
            ]
        )
        == 1
    )
    assert (case.root / shadow_display.APPROVAL_FILE).read_bytes() == approval
    case.clock["now"] = NOW
    app.button(key="refresh").click().run()
    assert "Tahmin gösterimi kapalı." in messages(app)
    assert all(path.read_bytes() == content for path, content in immutable.items())
