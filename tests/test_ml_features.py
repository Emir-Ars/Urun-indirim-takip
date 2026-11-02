"""Girdi formülleri, eksik geçmiş ve gelecek veriye karşı değişmezlik."""

from copy import deepcopy
from datetime import date, timedelta
from math import log, sqrt

import pytest
from pydantic import ValidationError

from app.contracts import Product
from app.ml.dataset import build_snapshot
from app.ml.features import (
    FeatureValues,
    analyze_features,
    calculate_features,
    feature_schema,
    model_family,
)
from app.ml.labels import analyze_labels
from tests.support.ml import add_label_page, label_snapshot, label_tables

DAY = date(2026, 1, 30)
PRODUCT = Product(
    product_id=1,
    product_key="phone_128gb",
    brand="Apple",
    model="iPhone 16 Pro",
    storage_gb=128,
)


def values(prices, first=None):
    return calculate_features(PRODUCT, DAY, first or min(prices), prices)


def feature_at(snapshot, source="own", offset=29):
    day = date(2026, 1, 1) + timedelta(days=offset)
    return next(
        row
        for row in analyze_features(snapshot)[1]
        if row.metadata.product_id == 1
        and row.metadata.source == source
        and row.metadata.anchor_day == day
    )


def test_hand_calculated_log_ratios_mean_and_sample_volatility():
    history = {
        DAY - timedelta(days=2): 10000,
        DAY - timedelta(days=1): 10000,
        DAY: 9500,
    }
    result = values(history)
    assert result.log_return_1d == pytest.approx(log(0.95))
    assert result.log_return_7d is None
    assert result.ratio_min_7d == result.ratio_min_30d == 1
    assert result.ratio_mean_30d == pytest.approx(57 / 59)
    assert result.volatility_30d == pytest.approx(abs(log(0.95)) / sqrt(2))
    assert result.change_count_30d == 1
    assert result.days_since_drop_30d == 0
    assert result.drop_observed_30d is True
    assert result.history_days == 3
    assert result.missing_ratio_30d == 27 / 30
    assert result.weekday == "4"
    assert result.capacity == "128"


def test_lag_30_reads_extra_day_without_expanding_rolling_window():
    history = {DAY - timedelta(days=n): 10000 for n in range(31)}
    history[DAY - timedelta(days=30)] = 100
    result = values(history)
    assert result.log_return_30d == pytest.approx(log(100))
    assert result.ratio_min_30d == result.ratio_mean_30d == 1
    assert result.volatility_30d == 0
    assert result.change_count_30d == 0
    assert result.history_days == 31


def test_seven_day_window_excludes_d_minus_seven_but_lag_uses_it():
    history = {DAY - timedelta(days=n): 10000 for n in range(30)}
    history[DAY - timedelta(days=7)] = 5000
    result = values(history)
    assert result.ratio_min_7d == 1
    assert result.ratio_min_30d == 2
    assert result.log_return_7d == pytest.approx(log(2))


def test_exact_missing_lag_not_replaced_by_previous_available_day():
    result = values({DAY: 10000, DAY - timedelta(days=8): 5000})
    assert result.log_return_7d is None
    assert result.ratio_min_30d == 2


def test_gap_does_not_create_daily_return_or_drop():
    result = values(
        {DAY - timedelta(days=3): 10000, DAY - timedelta(days=1): 9000, DAY: 9000}
    )
    assert result.change_count_30d == 0
    assert result.volatility_30d is None
    assert result.days_since_drop_30d == 31
    assert result.drop_observed_30d is False


def test_single_price_retained_without_inventing_zero_changes():
    result = values({DAY: 10000})
    assert result.ratio_min_7d == result.ratio_min_30d == result.ratio_mean_30d == 1
    assert result.volatility_30d is None
    assert result.change_count_30d is None
    assert result.days_since_drop_30d is None
    assert result.drop_observed_30d is None
    assert result.missing_ratio_30d == 29 / 30


@pytest.mark.parametrize(
    "price,seen,days", [(9500, True, 0), (9501, False, 31), (9499, True, 0)]
)
def test_integer_inclusive_drop_threshold(price, seen, days):
    result = values({DAY - timedelta(days=1): 10000, DAY: price})
    assert result.drop_observed_30d is seen
    assert result.days_since_drop_30d == days


def test_most_recent_daily_drop_date():
    history = {
        DAY - timedelta(days=n): price
        for n, price in enumerate([9000, 9000, 9600, 9500, 10000])
    }
    assert values(history).days_since_drop_30d == 1


def test_history_age_is_calendar_age_not_valid_count_or_clipped_30():
    result = values({DAY: 10000}, DAY - timedelta(days=100))
    assert result.history_days == 101
    assert result.missing_ratio_30d == 29 / 30


def test_price_scale_does_not_change_dimensionless_features():
    history = {DAY - timedelta(days=n): 10000 + n * 17 for n in range(31)}
    before = values(history).model_dump()
    after = values({at: price * 10 for at, price in history.items()}).model_dump()
    assert after == pytest.approx(before)


@pytest.mark.parametrize(
    "brand,model,family,segment",
    [
        ("Apple", "iPhone 16", "Apple iPhone 16", "standard"),
        ("Apple", "iPhone 16 Pro", "Apple iPhone 16", "pro"),
        ("Apple", "iPhone 16 Pro Max", "Apple iPhone 16", "pro_max"),
        ("Apple", "iPhone 17 Air", "Apple iPhone 17", "air"),
        ("Samsung", "Galaxy S24", "Samsung Galaxy S24", "standard"),
        ("Samsung", "Galaxy S24 Ultra", "Samsung Galaxy S24", "ultra"),
        ("Samsung", "Galaxy S24 FE", "Samsung Galaxy S24", "fe"),
        ("Samsung", "Galaxy A55", "Samsung Galaxy A55", "standard"),
        ("Xiaomi", "14T Pro", "Xiaomi 14T", "pro"),
        ("Xiaomi", "13T Pro", "Xiaomi 13T", "pro"),
        ("Xiaomi", "Redmi Note 14 Pro", "Xiaomi Redmi Note 14", "pro"),
        ("Xiaomi", "Redmi Note 14 Pro 5G", "Xiaomi Redmi Note 14", "pro"),
        ("POCO", "X6 Pro", "POCO X6", "pro"),
        ("Acme", "New Pro", "Acme New Pro", "unknown"),
        ("Apple", "iPhone Special", "Apple iPhone Special", "unknown"),
    ],
)
def test_family_and_segment_without_product_identity_changes(
    brand, model, family, segment
):
    product = PRODUCT.model_copy(update={"brand": brand, "model": model})
    assert model_family(product) == (family, segment)
    assert product.model == model


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "product_id",
        "product_key",
        "reference_price",
        "anchor_day",
        "month",
        "primary",
        "tracked",
        "future_minimum_price",
        "target_end",
        "future_observed_days",
    ],
)
def test_core_schema_rejects_identity_and_future_fields(field):
    payload = values({DAY: 10000}).model_dump()
    payload[field] = 1
    with pytest.raises(ValidationError, match="Extra inputs"):
        FeatureValues.model_validate(payload)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_values_rejected(invalid):
    payload = values({DAY: 10000}).model_dump()
    payload["log_return_1d"] = invalid
    with pytest.raises(ValidationError):
        FeatureValues.model_validate(payload)


@pytest.mark.parametrize("source", ["own", "cimri"])
def test_missing_day_keeps_anchor_row_and_null_lag(source):
    prices = [10000] * 37
    prices[28] = None
    row = feature_at(label_snapshot(prices=prices), source)
    assert row.features.log_return_1d is None
    assert row.features.log_return_30d is None
    assert row.features.missing_ratio_30d == 1 / 30


def test_half_day_and_previous_cimri_identity_not_used_in_features():
    tables = label_tables()
    tables["market_history"][28]["captured_at"] = tables["collection_runs"][56][
        "started_at"
    ]
    tables["market_history"][28]["price_kurus"] = 1
    tables["market_history"][22]["source_product_id"] = "987654"
    tables["market_history"][22]["price_kurus"] = 1
    row = feature_at(label_snapshot(tables), "cimri")
    assert row.features.ratio_min_30d == 1
    assert row.features.log_return_1d is None
    assert row.features.log_return_7d is None
    assert row.features.missing_ratio_30d == 2 / 30


def test_all_valid_anchors_match_labels_independently_of_label_values():
    snapshot = label_snapshot(prices=[10000] * 36 + [9000] + [10000] * 13)
    feature_keys = {
        (row.metadata.product_id, row.metadata.source, row.metadata.anchor_day)
        for row in analyze_features(snapshot)[1]
    }
    windows = analyze_labels(snapshot)[2]
    assert {row["primary"]["label"] for row in windows} == {0, 1, None}
    assert feature_keys == {
        (row["product_id"], row["source"], row["anchor_day"]) for row in windows
    }


def _past_rows(snapshot):
    return [
        row.model_dump(mode="json")
        for row in analyze_features(snapshot)[1]
        if row.metadata.product_id == 1 and row.metadata.anchor_day <= DAY
    ]


def test_future_prices_stock_and_new_pages_do_not_change_past_features():
    tables = label_tables(40)
    before = _past_rows(label_snapshot(tables))
    changed = deepcopy(tables)
    for row in changed["listing_checks"]:
        if row["run_id"] > 60:
            row.update(outcome="sold_out", current_price=None)
    for row in changed["market_history"]:
        if row["day"] > DAY:
            row["price_kurus"] = 1
    add_label_page(changed, start_offset=30, end_offset=39, price=1)
    assert _past_rows(label_snapshot(changed)) == before


def test_truncated_and_extended_future_have_same_shared_feature_rows():
    tables = label_tables(40)
    snapshot = label_snapshot(tables)
    before = _past_rows(snapshot)
    tables["collection_runs"] = [
        row for row in tables["collection_runs"] if row["run_id"] <= 60
    ]
    tables["listing_checks"] = [
        row for row in tables["listing_checks"] if row["run_id"] <= 60
    ]
    tables["market_history"] = [
        row for row in tables["market_history"] if row["day"] <= DAY
    ]
    prefix = build_snapshot(tables, snapshot.captured_at, 5)
    assert _past_rows(prefix) == before


def test_new_future_product_does_not_recode_old_categories():
    tables = label_tables(40)
    before = _past_rows(label_snapshot(tables))
    tables["products"].append(
        dict(
            product_id=2,
            product_key="new_phone",
            brand="Acme",
            model="Future Phone",
            storage_gb=1024,
            active=True,
        )
    )
    add_label_page(tables, start_offset=30, end_offset=39, price=1, product_id=2)
    assert _past_rows(label_snapshot(tables)) == before


def test_changing_past_price_is_a_positive_control():
    tables = label_tables()
    before = feature_at(label_snapshot(tables))
    for row in tables["listing_checks"]:
        if row["run_id"] == 58:
            row["current_price"] = 20000
    after = feature_at(label_snapshot(tables))
    assert before.features.log_return_1d == 0
    assert after.features.log_return_1d == pytest.approx(log(0.5))
    assert after.features != before.features


def test_pure_calculator_does_not_read_future_keys():
    class PastOnly(dict):
        def get(self, key, default=None):
            assert key <= DAY
            return super().get(key, default)

    history = PastOnly({DAY: 10000, DAY + timedelta(days=1): -1})
    assert values(history, DAY).ratio_min_30d == 1


def test_empty_series_and_unknown_models_are_reported():
    tables = label_tables(prices=[None] * 37)
    tables["products"][0]["model"] = "Future Phone"
    report, rows = analyze_features(label_snapshot(tables))
    assert rows == []
    assert report["sources"]["own"]["rows"] == 0
    assert report["unknown_models"][0]["model"] == "Future Phone"


def test_schema_lists_only_core_fields_and_unlearned_categories():
    schema = feature_schema()
    assert schema["core_features"] == list(FeatureValues.model_fields)
    assert set(schema["categorical_features"]) == {
        "weekday",
        "brand",
        "family",
        "segment",
        "capacity",
    }
    assert schema["ablation_metadata"] == ["month", "product_key"]
