"""Başlangıç anına kadarki günlük fiyatlardan model girdileri; etiket okumaz."""

import re
from collections import Counter
from datetime import date, timedelta
from math import log
from statistics import mean, stdev
from typing import Annotated, Literal

from pydantic import Field

from app.contracts import Contract, Product
from app.ml.dataset import UtcDatetime
from app.ml.series import build_series, dates

Finite = Annotated[float, Field(allow_inf_nan=False)]
FEATURE_RULES = {
    "version": 1,
    "timezone": "Europe/Istanbul",
    "lag_days": [1, 7, 14, 30],
    "level_windows_including_anchor": [7, 30],
    "transitions": "adjacent_calendar_days_inside_30_day_window",
    "volatility": "sample_std_of_log_returns_minimum_two_transitions",
    "drop_percent": 5,
    "no_observed_drop_sentinel": 31,
    "cimri_history": "same_source_product_id_as_anchor",
    "imputation": False,
}


class FeatureValues(Contract):
    log_return_1d: Finite | None = Field(
        description="ln(p(d)/p(d−1)); tam tarih yoksa NULL"
    )
    log_return_7d: Finite | None = Field(
        description="ln(p(d)/p(d−7)); tam tarih yoksa NULL"
    )
    log_return_14d: Finite | None = Field(
        description="ln(p(d)/p(d−14)); tam tarih yoksa NULL"
    )
    log_return_30d: Finite | None = Field(
        description="ln(p(d)/p(d−30)); tam tarih yoksa NULL"
    )
    ratio_min_7d: Finite = Field(
        gt=0, description="p(d)/min(p(d−6…d)); mevcut fiyatlarla"
    )
    ratio_min_30d: Finite = Field(
        gt=0, description="p(d)/min(p(d−29…d)); mevcut fiyatlarla"
    )
    ratio_mean_30d: Finite = Field(
        gt=0, description="p(d)/ortalama(p(d−29…d)); mevcut fiyatlarla"
    )
    volatility_30d: Finite | None = Field(
        description=(
            "İki ucu d−29…d içinde fiyatlı ardışık günlerin "
            "log değişimlerinin örnek std sapması; en az 2 geçiş"
        )
    )
    change_count_30d: int | None = Field(
        ge=0,
        le=29,
        description=(
            "Geçerli ardışık gün geçişlerindeki fiyat değişimi sayısı; "
            "geçiş yoksa NULL"
        ),
    )
    days_since_drop_30d: int | None = Field(
        ge=0,
        le=31,
        description=(
            "Son günlük ≥%5 düşüşün bitişinden itibaren gün; "
            "geçiş var/düşüş yoksa 31, geçiş yoksa NULL"
        ),
    )
    drop_observed_30d: bool | None = Field(
        description="Geçerli geçişlerde ≥%5 düşüş görüldü mü; geçiş yoksa NULL"
    )
    history_days: int = Field(
        ge=1,
        description=(
            "İlk kaynak gözleminden d'ye kadar takvim günleri, "
            "d dahil; 30'a kırpılmaz"
        ),
    )
    missing_ratio_30d: Finite = Field(
        ge=0,
        le=1,
        description="d−29…d içinde eksik/başka Cimri kimliğine ait fiyat sayısı / 30",
    )
    weekday: Literal["0", "1", "2", "3", "4", "5", "6"] = Field(
        description="Kategori: Pazartesi 0, Pazar 6"
    )
    brand: str = Field(min_length=1, description="Marka kategorisi")
    family: str = Field(
        min_length=1, description="Nesil ailesi; tanınmayan modelde marka + tam model"
    )
    segment: str = Field(
        min_length=1,
        description=(
            "Sürüm kategorisi: standard/pro/pro_max/ultra/fe vb.; "
            "tanınmıyorsa unknown"
        ),
    )
    capacity: str = Field(
        min_length=1,
        description="GB kapasitesi kategori dizgisi; sayısal model girdisi değildir",
    )


class FeatureMetadata(Contract):
    product_id: int = Field(gt=0)
    product_key: str = Field(min_length=1)
    source: Literal["own", "cimri"]
    anchor_day: date
    anchor_at: UtcDatetime | None
    month: int = Field(ge=1, le=12)


class FeatureRow(Contract):
    metadata: FeatureMetadata
    features: FeatureValues


def model_family(product: Product):
    model = " ".join(product.model.split())
    patterns = {
        "Apple": r"(iPhone \d+)(?: (Pro Max|Pro|Plus|mini|Air))?",
        "Samsung": r"(Galaxy [SA]\d+)(?: (Ultra|FE|Plus|Edge))?",
        "Xiaomi": r"(\d+T|Redmi Note \d+)(?: (Pro Plus|Pro))?(?: (?:4G|5G))?",
        "POCO": r"(X\d+)(?: (Pro))?",
    }
    pattern = patterns.get(product.brand)
    match = re.fullmatch(pattern, model) if pattern else None
    if match is None:
        return f"{product.brand} {model}", "unknown"
    segment = (match.group(2) or "standard").lower().replace(" ", "_")
    return f"{product.brand} {match.group(1)}", segment


def calculate_features(product, day, first_observation, history):
    """Fiyat sözlüğünde gelecek bulunsa bile yalnız d−30…d okunur."""
    current = history[day]
    past = list(dates(day - timedelta(days=29), day))
    prices = [history.get(at) for at in past]
    present = [price for price in prices if price is not None]
    last_seven = [price for price in prices[-7:] if price is not None]
    transitions = [
        (after_day, before, after)
        for after_day, before, after in zip(past[1:], prices, prices[1:])
        if before is not None and after is not None
    ]
    returns = [log(after / before) for _, before, after in transitions]
    drops = [at for at, before, after in transitions if 100 * after <= 95 * before]
    changes = sum(before != after for _, before, after in transitions)
    family, segment = model_family(product)
    lag_returns = {}
    for lag in FEATURE_RULES["lag_days"]:
        previous = history.get(day - timedelta(days=lag))
        lag_returns[f"log_return_{lag}d"] = (
            log(current / previous) if previous is not None else None
        )
    return FeatureValues(
        **lag_returns,
        ratio_min_7d=current / min(last_seven),
        ratio_min_30d=current / min(present),
        ratio_mean_30d=current / mean(present),
        volatility_30d=stdev(returns) if len(returns) >= 2 else None,
        change_count_30d=changes if transitions else None,
        days_since_drop_30d=(
            (day - drops[-1]).days if drops else 31 if transitions else None
        ),
        drop_observed_30d=bool(drops) if transitions else None,
        history_days=(day - first_observation).days + 1,
        missing_ratio_30d=(30 - len(present)) / 30,
        weekday=str(day.weekday()),
        brand=product.brand,
        family=family,
        segment=segment,
        capacity=str(product.storage_gb),
    )


def feature_rows(series, product):
    rows = []
    for day, anchor in series.days.items():
        if anchor["reference_price"] is None:
            continue
        history = {}
        for at in dates(day - timedelta(days=30), day):
            value = series.days.get(at)
            price = value["reference_price"] if value else None
            if value is not None:
                if (
                    series.source == "cimri"
                    and value["source_product_id"] != anchor["source_product_id"]
                ):
                    price = None
                if (
                    series.source == "own"
                    and value["anchor_at"] is not None
                    and value["anchor_at"] > anchor["anchor_at"]
                ):
                    price = None
            history[at] = price
        rows.append(
            FeatureRow(
                metadata=FeatureMetadata(
                    product_id=product.product_id,
                    product_key=product.product_key,
                    source=series.source,
                    anchor_day=day,
                    anchor_at=anchor["anchor_at"],
                    month=day.month,
                ),
                features=calculate_features(
                    product, day, series.first_observation, history
                ),
            )
        )
    return rows


def feature_schema():
    return dict(
        format_version=1,
        rules=FEATURE_RULES,
        core_features=list(FeatureValues.model_fields),
        categorical_features=["weekday", "brand", "family", "segment", "capacity"],
        ablation_metadata=["month", "product_key"],
        row_schema=FeatureRow.model_json_schema(),
    )


def _summary(rows):
    return dict(
        rows=len(rows),
        missing={
            name: sum(getattr(row.features, name) is None for row in rows)
            for name in FeatureValues.model_fields
        },
    )


def analyze_features(snapshot):
    closed_day, series_list = build_series(snapshot)
    products = {product.product_id: product for product in snapshot.products}
    rows, summaries = [], []
    for series in series_list:
        product = products[series.product_id]
        samples = feature_rows(series, product)
        rows.extend(samples)
        summaries.append(
            dict(
                product_id=product.product_id,
                product_name=product.name,
                source=series.source,
                first_observation=series.first_observation,
                **_summary(samples),
                unknown_segment_rows=sum(
                    row.features.segment == "unknown" for row in samples
                ),
            )
        )
    rows.sort(
        key=lambda row: (
            row.metadata.product_id,
            row.metadata.source,
            row.metadata.anchor_day,
        )
    )
    unknown = [
        dict(product_id=product.product_id, brand=product.brand, model=product.model)
        for product in snapshot.products
        if model_family(product)[1] == "unknown"
    ]
    report = dict(
        snapshot_at=snapshot.captured_at,
        last_closed_day=closed_day,
        feature_rules=FEATURE_RULES,
        products=summaries,
        sources={
            source: _summary([row for row in rows if row.metadata.source == source])
            for source in ("own", "cimri")
        },
        unknown_models=unknown,
        category_counts={
            name: dict(
                sorted(Counter(getattr(row.features, name) for row in rows).items())
            )
            for name in ("weekday", "brand", "family", "segment", "capacity")
        },
        model_trained=False,
        production_prediction_enabled=False,
        labels_read=False,
    )
    return report, rows
