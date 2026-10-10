"""Telefon ekranını, veri boşluklarını ve kaynak bırakmayı ağsız sınar."""

import json
from datetime import date, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.ui import api_client
from app.ui.api_client import ApiClientError
from app.ui.presentation import (
    REASONS,
    format_day,
    format_money,
    format_number,
    format_time,
    history_rows,
    market_rows,
    price_chart,
    reason_text,
)
from ui_samples import (
    AT,
    PRODUCTS,
    SCENARIOS,
    preview_client,
    sample_history,
    sample_market,
    sample_offer,
    sample_product,
    sample_status,
)

ROOT = Path(__file__).resolve().parents[1]
SCREEN = ROOT / "app/ui/main.py"
PREVIEW = ROOT / "tests/manual/ui_preview.py"


@pytest.fixture
def screen(monkeypatch):
    state = SimpleNamespace(
        products=PRODUCTS,
        snapshot=sample_product(),
        status=sample_status(),
        failures={},
        calls=[],
        opened=0,
        closed=0,
    )

    class Client:
        def __enter__(self):
            state.opened += 1
            return self

        def __exit__(self, *args):
            state.closed += 1

        def call(self, method, *args):
            state.calls.append((method, *args))
            if method in state.failures:
                raise state.failures[method]

        def list_products(self):
            self.call("products")
            return state.products

        def get_status(self):
            self.call("status")
            return state.status

        def get_product(self, key, history_days=30, cimri_days=366):
            self.call("product", key, history_days, cimri_days)
            return state.snapshot.model_copy(
                update={
                    "product": next(p for p in state.products if p.product_key == key)
                }
            )

    monkeypatch.setattr(api_client, "ApiClient", Client)
    app = AppTest.from_file(SCREEN)
    return app, state


def messages(app):
    return "\n".join(
        str(element.value)
        for kind in ("caption", "text", "info", "warning", "error")
        for element in app.get(kind)
    )


def chart_specs(app):
    return [json.loads(chart.proto.spec) for chart in app.get("vega_lite_chart")]


@pytest.mark.parametrize(
    "value,signed,expected",
    [
        (None, False, "—"),
        (0, False, "0,00 TL"),
        (1, False, "0,01 TL"),
        (1234567, False, "12.345,67 TL"),
        (-10001, True, "−100,01 TL"),
        (10001, True, "+100,01 TL"),
        (0, True, "0,00 TL"),
        (2**60 + 7, False, "11.529.215.046.068.469,83 TL"),
    ],
)
def test_money_format_preserves_integer_cents(value, signed, expected):
    assert format_money(value, signed=signed) == expected


@pytest.mark.parametrize(
    "value,expected", [(None, "—"), (0.0, "0,00"), (9.25, "9,25"), (1234.5, "1.234,50")]
)
def test_number_format(value, expected):
    assert format_number(value) == expected


def test_istanbul_dates_and_missing_time():
    assert format_time(AT.replace(hour=22)) == "10.10.2026 01:00:00"
    assert (
        format_time(AT.astimezone(timezone(timedelta(hours=-5))))
        == "09.10.2026 12:00:00"
    )
    assert format_time(None) == "—"
    assert format_day(date(2026, 10, 9)) == "09.10.2026"


@pytest.mark.parametrize("reason", tuple(REASONS))
def test_statistics_reasons_have_turkish_explanations(reason):
    assert reason_text((reason,)) == REASONS[reason]


def test_multiple_reasons_are_not_lost():
    text = reason_text(("insufficient_transitions", "insufficient_days"))
    assert "14" in text and "7" in text


@pytest.mark.parametrize(
    "gap,connected",
    [
        (timedelta(seconds=-1), False),
        (timedelta(0), False),
        (timedelta(seconds=1), True),
        (timedelta(hours=18), True),
        (timedelta(hours=18, microseconds=1), False),
    ],
)
def test_history_connections_use_actual_check_time(gap, connected):
    first = sample_history(1, best_checked_at=AT)
    second = sample_history(2, best_checked_at=AT + gap)
    rows = history_rows((first, second))
    assert (rows[0]["segment"] == rows[1]["segment"]) is connected


@pytest.mark.parametrize(
    "changes",
    [
        {"best_price": None},
        {"best_checked_at": None},
        {"partial": True, "answered_pages": 1},
        {"planned_listing_ids": ("a", "c")},
    ],
)
def test_missing_scope_or_price_breaks_both_sides(changes):
    points = (sample_history(1), sample_history(2, **changes), sample_history(3))
    rows = history_rows(points)
    assert [row["segment"] for row in rows] == [0, 1, 2]
    assert rows[1]["price_kurus"] == points[1].best_price


def test_page_order_does_not_change_scope():
    rows = history_rows(
        (sample_history(1), sample_history(2, planned_listing_ids=("b", "a")))
    )
    assert rows[0]["segment"] == rows[1]["segment"]


def test_history_rows_preserve_null_and_input_and_istanbul_clock():
    points = (sample_history(1), sample_history(2, best_price=None))
    original = tuple(point.model_dump_json() for point in points)
    rows = history_rows(points)
    assert rows[0]["istanbul_time"] == "2026-10-06T12:00:00+00:00"
    assert rows[0]["run_text"] == "06.10.2026 12:00:00"
    assert rows[1]["price_tl"] is None
    assert rows[1]["price_text"] == "—"
    assert tuple(point.model_dump_json() for point in points) == original
    assert history_rows(()) == []


@pytest.mark.parametrize(
    "gap,price,segments",
    [
        (1, 10001, [0, 0, 0]),
        (2, 10001, [0, 1, 1]),
        (1, None, [0, 1, 2]),
    ],
)
def test_market_date_gaps_and_null_are_not_bridged(gap, price, segments):
    first = date(2026, 10, 1)
    points = (
        sample_market(first),
        sample_market(first + timedelta(days=gap), price),
        sample_market(first + timedelta(days=gap + 1)),
    )
    original = tuple(p.model_dump_json() for p in points)
    rows = market_rows(points)
    assert [row["segment"] for row in rows] == segments
    assert [row["day"] for row in rows] == [p.day.isoformat() for p in points]
    assert [row["price_kurus"] for row in rows] == [p.price_kurus for p in points]
    assert tuple(p.model_dump_json() for p in points) == original
    assert market_rows(()) == []


@pytest.mark.parametrize("market", [False, True])
def test_chart_spec_breaks_paths_and_preserves_single_or_null_rows(market):
    rows = (
        market_rows((sample_market(), sample_market(date(2026, 10, 9), None)))
        if market
        else history_rows((sample_history(), sample_history(2, best_price=None)))
    )
    spec = price_chart(rows, market=market).to_dict(validate=True)
    assert spec["data"]["values"] == rows
    assert spec["layer"][0]["mark"]["invalid"] == "break-paths-show-domains"
    assert spec["layer"][0]["encoding"]["detail"]["field"] == "segment"
    assert spec["layer"][1]["mark"]["type"] == "point"
    assert spec["layer"][0]["encoding"]["y"]["scale"]["zero"] is False
    assert spec["layer"][0]["encoding"]["x"]["scale"]["type"] == "utc"
    assert "impute" not in json.dumps(spec)


def test_initial_screen_reads_fresh_data_and_separates_global_run(screen):
    app, state = screen
    app.run()
    assert not app.exception
    assert state.calls == [
        ("products",),
        ("status",),
        ("product", PRODUCTS[0].product_key, 30, 366),
    ]
    assert state.opened == state.closed == 1
    assert app.metric[0].value == "29.300,01 TL"
    assert len(chart_specs(app)) == 2
    text = messages(app)
    assert "9,25 / 10,00" in text and "2/2" in text
    assert "global tur: 99" in text and "Ürün turu: 7" in text
    assert "Satıcının belirttiği eski fiyat: 31.500,00 TL" in text
    assert app.dataframe[0].value["Sonuç"].tolist() == ["Teklif", "Teklif"]


def test_selection_ranges_and_manual_refresh_preserve_preferences(screen):
    app, state = screen
    app.run()
    app.selectbox(key="_product").set_value(PRODUCTS[1].product_key).run()
    app.selectbox(key="_history_days").set_value(90).run()
    app.selectbox(key="_cimri_days").set_value(7).run()
    app.button(key="refresh").click().run()
    assert not app.exception
    assert state.calls[-1] == ("product", PRODUCTS[1].product_key, 90, 7)
    assert state.calls.count(("products",)) == 5
    assert state.opened == state.closed == 5
    assert app.session_state["selected_product"] == PRODUCTS[1].product_key
    assert app.session_state["history_days"] == 90
    assert app.session_state["cimri_days"] == 7


def test_removed_product_selects_first_active_and_preserves_order_by_key(screen):
    app, state = screen
    app.run()
    app.selectbox(key="_product").set_value(PRODUCTS[1].product_key).run()
    state.products = tuple(reversed(PRODUCTS))
    app.run()
    assert state.calls[-1][1] == PRODUCTS[1].product_key
    state.products = PRODUCTS[:1]
    app.run()
    assert not app.exception
    assert state.calls[-1][1] == PRODUCTS[0].product_key
    assert "artık etkin listede değil" in messages(app)


def test_no_active_products_and_recovery(screen):
    app, state = screen
    state.products = ()
    app.run()
    assert not app.exception
    assert "Etkin telefon bulunmuyor" in messages(app)
    assert state.calls == [("products",), ("status",)]
    assert not app.metric and not chart_specs(app)
    state.products = PRODUCTS
    app.button(key="refresh").click().run()
    assert not app.exception and len(chart_specs(app)) == 2


@pytest.mark.parametrize(
    "scenario,text",
    [
        ("Bütün sayfalar stoksuz", "bütün sayfalarda stok yok"),
        ("Fiyat doğrulanamadı", "fiyat doğrulanamadı"),
        ("Yalnız Cimri geçmişi", "tamamlanmış toplama turu bulunmuyor"),
        ("Kısmi kapsam", "Kısmi kapsam"),
        ("Eski teklif", "en az 18 saat"),
        ("Cimri geçmişi yok", "Cimri geçmişi bulunmuyor"),
        ("Fiyatların hepsi eksik", "kayıtlı turlar var; fiyat gözlemi bulunmuyor"),
    ],
)
def test_states_remain_distinct_and_old_offer_is_separate(screen, scenario, text):
    app, state = screen
    state.snapshot = sample_product(scenario)
    app.run()
    assert not app.exception
    assert text in messages(app)
    if state.snapshot.best_offer is None:
        assert all(m.label != "Takip edilen en ucuz teklif" for m in app.metric)
        if state.snapshot.last_successful_offer:
            assert app.metric[0].label == "Son başarılı fiyat"
    if scenario == "Yalnız Cimri geçmişi":
        assert len(chart_specs(app)) == 1
    if scenario == "Fiyatların hepsi eksik":
        assert not chart_specs(app)


def test_api_statistics_are_displayed_without_recalculation(screen):
    app, state = screen
    snapshot = state.snapshot
    stats = snapshot.statistics
    stats = stats.model_copy(
        update={
            "low_30d": stats.low_30d.model_copy(
                update={"value": 10001, "reasons": (), "observations": 99}
            ),
            "volatility_30d": stats.volatility_30d.model_copy(
                update={"value": 0.0, "reasons": (), "transitions": 14, "days": 7}
            ),
        }
    )
    state.snapshot = snapshot.model_copy(update={"statistics": stats})
    original = state.snapshot.model_dump_json()
    app.run()
    values = {metric.label: metric.value for metric in app.metric}
    assert values["30 günlük gözlenen dip"] == "100,01 TL"
    assert values["Fiyat değişkenliği"] == "0,00"
    assert "Fiyat gözlemi: 99" in messages(app)
    assert "Geçerli geçiş: 14 · Gün: 7" in messages(app)
    app.selectbox(key="_history_days").set_value(7).run()
    assert state.snapshot.model_dump_json() == original
    assert {m.label: m.value for m in app.metric}[
        "30 günlük gözlenen dip"
    ] == "100,01 TL"


def test_current_success_is_not_repeated_as_old_offer(screen):
    app, state = screen
    app.run()
    assert not app.exception
    assert all(metric.label != "Son başarılı fiyat" for metric in app.metric)


def test_inactive_catalog_metadata_and_unchecked_page_are_preserved(screen):
    app, state = screen
    unchecked = sample_offer(
        listing_id="b",
        color="Mavi",
        listing_active=False,
        platform_active=False,
        url="https://example.com/guncel-adres",
        outcome=None,
        checked_at=None,
        current_price=None,
        original_price=None,
        seller_name=None,
        seller_rating=None,
        seller_rating_scale=None,
        stock_status=None,
    )
    state.snapshot = state.snapshot.model_copy(
        update={"checks": (state.snapshot.best_offer, unchecked)}
    )
    app.run()
    assert not app.exception
    row = app.dataframe[0].value.iloc[1]
    assert row["Sonuç"] == "Kontrol edilmedi"
    assert row["Fiyat"] == "—" and row["Stok"] == "—"
    assert row["Sayfa etkin"] == "Hayır" and row["Platform etkin"] == "Hayır"
    assert row["Renk"] == "Mavi" and row["Adres"] == unchecked.url
    assert "mevcut katalog bilgisidir" in messages(app)


def test_unknown_seller_rating_and_stock_are_not_invented(screen):
    app, state = screen
    best = sample_offer(
        seller_name=None,
        seller_rating=None,
        seller_rating_scale=None,
        stock_status=None,
        original_price=None,
    )
    state.snapshot = state.snapshot.model_copy(update={"best_offer": best})
    app.run()
    assert not app.exception
    text = messages(app)
    assert "Satıcı: Bilinmiyor" in text and "Satıcı puanı: Bilinmiyor" in text
    assert "Stok: Bilinmiyor" in text
    assert "Satıcının belirttiği eski fiyat" not in text


@pytest.mark.parametrize(
    "comparable,previous,expected",
    [
        (True, 3000001, "−700,00 TL"),
        (True, None, None),
        (False, 3000001, None),
    ],
)
def test_price_change_requires_api_comparability(
    screen, comparable, previous, expected
):
    app, state = screen
    state.snapshot = state.snapshot.model_copy(
        update={
            "current": state.snapshot.current.model_copy(
                update={
                    "comparable_with_previous": comparable,
                    "previous_best_price": previous,
                }
            )
        }
    )
    app.run()
    assert not app.exception
    assert app.metric[0].delta == (expected or "")


@pytest.mark.parametrize(
    "stock,warn", [("Kritik Stok", True), ("Stokta Var", False), (None, False)]
)
def test_stock_warning_only_uses_recorded_stock(screen, stock, warn):
    app, state = screen
    state.snapshot = state.snapshot.model_copy(
        update={"best_offer": sample_offer(stock_status=stock)}
    )
    app.run()
    assert ("Kaynak kritik stok" in messages(app)) is warn


@pytest.mark.parametrize("method", ["products", "status", "product"])
def test_api_failure_removes_old_cards_and_recovers_with_same_preferences(
    screen, method
):
    app, state = screen
    app.run()
    app.selectbox(key="_product").set_value(PRODUCTS[1].product_key).run()
    app.selectbox(key="_history_days").set_value(90).run()
    state.failures[method] = ApiClientError(
        "connection_error", "Yerel API'ye erişilemiyor."
    )
    app.button(key="refresh").click().run()
    assert not app.exception
    assert app.error[0].value == "Yerel API'ye erişilemiyor."
    assert not app.metric and not chart_specs(app) and not app.dataframe
    assert state.opened == state.closed
    state.failures.clear()
    app.button(key="refresh").click().run()
    assert not app.exception
    assert state.calls[-1] == ("product", PRODUCTS[1].product_key, 90, 366)
    assert state.opened == state.closed


def test_unexpected_programming_error_is_not_hidden_as_api_failure(screen):
    app, state = screen
    state.failures["product"] = RuntimeError("Sahte kod hatası")
    app.run()
    assert len(app.exception) == 1
    assert not app.error
    assert state.opened == state.closed == 1


def test_refresh_interval_is_registered_as_30_seconds(screen, monkeypatch):
    app, state = screen
    original = st.fragment
    intervals = []

    def fragment(*args, **kwargs):
        intervals.append(kwargs["run_every"])
        return original(*args, **kwargs)

    monkeypatch.setattr(st, "fragment", fragment)
    app.run()
    assert not app.exception and intervals == [30]


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_manual_preview_uses_same_screen_and_displays_test_banner(scenario):
    app = AppTest.from_file(PREVIEW).run()
    app.selectbox(key="preview_scenario").set_value(scenario).run()
    assert not app.exception
    assert app.warning[0].value == "Test verisi — gerçek fiyatlar değildir"
    if scenario in ("API bağlantı hatası", "Bozuk API cevabı"):
        assert app.error and not app.metric and not chart_specs(app)
    else:
        assert not app.error


def test_preview_second_product_and_range_use_validated_client():
    with preview_client("Teklif ve grafik boşlukları") as client:
        products = client.list_products()
        snapshot = client.get_product(products[1].product_key, cimri_days=7)
        assert snapshot.product == products[1]
        assert all(p.product_id == products[1].product_id for p in snapshot.history)
        assert len(snapshot.cimri_history) == 7
