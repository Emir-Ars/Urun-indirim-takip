"""Günlük serilerden simetrik 6/7 etiketleri ve sıkı karşılaştırma."""

from collections import Counter
from datetime import timedelta

from app.ml.series import build_series, dates, own_minimum

RULES = {
    "version": 2,
    "timezone": "Europe/Istanbul",
    "past_days_including_anchor": 30,
    "future_days": 7,
    "minimum_observed_future_days": 6,
    "drop_percent": 5,
    "own_primary_scope": "anchor_evening_planned_pages",
    "missing_other_slot_allowed": True,
    "cross_day_run_allowed": False,
    "cimri_half_day_allowed": False,
    "imputation": False,
}

REASONS = {
    "insufficient_history_period": "30 günlük geçmiş henüz yok",
    "future_not_available": "Yedinci gelecek gün henüz kapanmadı",
    "insufficient_future_prices": "Gelecek yedi günün altısında güvenilir fiyat yok",
    "source_identity_change": "Pencerede Cimri ürün kimliği değişti",
    "missing_slot": "Zaman dilimi eksik",
    "duplicate_slot": "Zaman diliminde birden fazla tur var",
    "product_not_planned": "Turda ürün planlanmadı",
    "unfinished_run": "Tur tamamlanmadı",
    "late_completion": "Tur kendi gününde tamamlanmadı",
    "incomplete_answers": "İlgili sayfa cevapları eksik veya hatalı",
    "intraday_scope_change": "Gün içindeki sayfa kapsamı değişti",
    "no_usable_planned_pages": "Kullanılabilir turda ilgili sayfa planlanmadı",
    "all_sold_out": "İlgili sayfaların tamamı stoksuz",
    "missing_evening": "Akşam dilimi eksik",
    "duplicate_evening": "Akşam diliminde birden fazla tur var",
    "unusable_evening": "Akşam turu tamamlanmadı veya günü aştı",
    "incomplete_evening_answers": "Akşam turunda ürünün cevapları eksik veya hatalı",
    "all_sold_out_evening": "Akşam turunda ürünün bütün sayfaları stoksuz",
    "missing_record": "Günlük kaynak kaydı yok",
    "half_day": "Cimri alım günü yarım gün",
    "missing_price": "Kaynak kaydında fiyat yok",
    "history_missing_day": "Sıkı geçmişte gözlenmemiş gün var",
    "future_missing_day": "Sıkı gelecekte gözlenmemiş gün var",
    "history_missing_price": "Sıkı geçmişte başlangıç fiyatı eksik",
    "future_missing_price": "Sıkı gelecekte günlük minimum eksik",
    "history_day_quality": "Sıkı geçmişte kusurlu gün var",
    "future_day_quality": "Sıkı gelecekte kusurlu gün var",
    "scope_change": "Sıkı pencerede sayfa kapsamı değişti",
}


def _target(base, future, common_reasons):
    prices = [row["price"] for row in future if row["price"] is not None]
    reasons = set(common_reasons)
    if len(prices) < 6:
        reasons.add("insufficient_future_prices")
    minimum = min(prices, default=None)
    return dict(
        label=int(100 * minimum <= 95 * base) if not reasons else None,
        future_observed_days=len(prices),
        future_minimum_price=minimum,
        reasons=sorted(reasons),
        future_days=future,
    )


def relaxed_windows(series, closed_day):
    result = []
    for day, row in series.days.items():
        base = row["reference_price"]
        if base is None:
            continue
        start, end = day - timedelta(days=29), day + timedelta(days=7)
        reasons = set()
        if series.first_observation is None or start < series.first_observation:
            reasons.add("insufficient_history_period")
        if end > closed_day:
            reasons.add("future_not_available")
        history = [series.days.get(at) for at in dates(start, day)]
        if series.source == "cimri":
            identities = {
                value["source_product_id"]
                for at in dates(start, end)
                if (value := series.days.get(at)) is not None
                and value["source_product_id"] is not None
            }
            if len(identities) > 1:
                reasons.add("source_identity_change")
        fixed, tracked, scope_changes = [], [], []
        scope = set(row["scope"])
        for at in dates(day + timedelta(days=1), end):
            value = series.days.get(at)
            if series.source == "own":
                views = series.runs.get(at, ())
                fixed_day = own_minimum(at, views, scope)
                tracked_day = own_minimum(at, views)
                fixed.append(fixed_day)
                tracked.append(tracked_day)
                planned = {check.listing_id for view in views for check in view.checks}
                if value is not None and planned != scope:
                    scope_changes.append(at)
            else:
                fixed.append(
                    dict(
                        day=at,
                        price=value["minimum_price"] if value else None,
                        reasons=value["reasons"] if value else ["missing_record"],
                    )
                )
        missing = sum(
            value is None or value["reference_price"] is None for value in history
        )
        result.append(
            dict(
                product_id=series.product_id,
                source=series.source,
                anchor_day=day,
                history_start=start,
                target_end=end,
                anchor_at=row["anchor_at"],
                reference_price=base,
                scope=row["scope"],
                history_calendar_days=min(
                    30, max(0, (day - series.first_observation).days + 1)
                ),
                history_missing_days=missing,
                history_missing_ratio=missing / 30,
                history_scope_change_days=_history_scope_changes(series, start, day),
                future_scope_change_days=scope_changes,
                primary=_target(base, fixed, reasons),
                tracked=(
                    _target(base, tracked, reasons) if series.source == "own" else None
                ),
            )
        )
    return result


def _history_scope_changes(series, start, end):
    previous, changes = None, []
    for at in dates(start, end):
        row = series.days.get(at)
        if row is None or not row["scope"]:
            continue
        current = tuple(row["scope"])
        if previous is not None and previous != current:
            changes.append(at)
        previous = current
    return changes


def strict_windows(product_id, source, days):
    """Eski sıkı sözleşme; yarım gün maskesi seri oluşturulurken uygulanır."""
    if not days:
        return []
    by_day = {row["day"]: row for row in days}
    start, end = days[0]["day"], days[-1]["day"]
    result = []
    for anchor in dates(start, end):
        past = list(dates(anchor - timedelta(days=29), anchor))
        future = list(dates(anchor + timedelta(days=1), anchor + timedelta(days=7)))
        reasons = set()
        if past[0] < start:
            reasons.add("insufficient_history_period")
        if future[-1] > end:
            reasons.add("future_not_available")
        for prefix, period, field in (
            ("history", past, "reference_price"),
            ("future", future, "minimum_price"),
        ):
            present = [by_day[at] for at in period if at in by_day]
            if any(
                start <= at <= end and (at not in by_day or not by_day[at]["observed"])
                for at in period
            ):
                reasons.add(f"{prefix}_missing_day")
            if any(row[field] is None for row in present):
                reasons.add(f"{prefix}_missing_price")
            if any(row["reasons"] for row in present):
                reasons.add(f"{prefix}_day_quality")
        scopes = {
            tuple(by_day[at]["scope"])
            for at in past + future
            if at in by_day and by_day[at]["scope"] is not None
        }
        if len(scopes) > 1:
            reasons.add("scope_change" if source == "own" else "source_identity_change")
        base = by_day.get(anchor, {}).get("reference_price")
        minimum = min(
            (
                by_day[at]["minimum_price"]
                for at in future
                if at in by_day and by_day[at]["minimum_price"] is not None
            ),
            default=None,
        )
        result.append(
            dict(
                product_id=product_id,
                source=source,
                anchor_day=anchor,
                history_start=past[0],
                target_end=future[-1],
                reference_price=base,
                future_minimum_price=minimum,
                label=int(100 * minimum <= 95 * base) if not reasons else None,
                reasons=sorted(reasons),
            )
        )
    return result


def counts(rows, target="primary"):
    labels = [row[target]["label"] if target else row["label"] for row in rows]
    return dict(
        candidates=len(labels),
        positive=labels.count(1),
        negative=labels.count(0),
        unknown=labels.count(None),
        usable=sum(value is not None for value in labels),
    )


def reason_counts(rows, target):
    return dict(
        sorted(
            Counter(reason for row in rows for reason in row[target]["reasons"]).items()
        )
    )


def analyze_labels(snapshot):
    closed_day, series_list = build_series(snapshot)
    daily, windows, strict, summaries = [], [], [], []
    products = {product.product_id: product for product in snapshot.products}
    for series in series_list:
        samples = relaxed_windows(series, closed_day)
        comparison = strict_windows(
            series.product_id, series.source, series.strict_days
        )
        daily.extend(
            dict(product_id=series.product_id, source=series.source, **row)
            for row in series.days.values()
        )
        windows.extend(samples)
        strict.extend(comparison)
        paired = [
            row
            for row in samples
            if row["tracked"] is not None
            and row["primary"]["label"] is not None
            and row["tracked"]["label"] is not None
        ]
        differences = sum(
            row["primary"]["label"] != row["tracked"]["label"] for row in paired
        )
        tracked_drops = sum(
            row["primary"]["label"] == 0 and row["tracked"]["label"] == 1
            for row in paired
        )
        summaries.append(
            dict(
                product_id=series.product_id,
                product_name=products[series.product_id].name,
                source=series.source,
                first_observation=series.first_observation,
                daily_rows=len(series.days),
                missing_reference_days=sum(
                    row["reference_price"] is None for row in series.days.values()
                ),
                primary=counts(samples),
                tracked=counts(samples, "tracked") if series.source == "own" else None,
                strict=counts(comparison, None),
                exclusion_reasons=reason_counts(samples, "primary"),
                tracked_exclusion_reasons=(
                    reason_counts(samples, "tracked")
                    if series.source == "own"
                    else None
                ),
                daily_reasons=dict(
                    sorted(
                        Counter(
                            reason
                            for row in series.days.values()
                            for reason in set(row["reasons"])
                            | set(row["anchor_reasons"])
                        ).items()
                    )
                ),
                paired_labels=len(paired),
                scope_label_differences=differences,
                scope_label_difference_ratio=(
                    differences / len(paired) if paired else None
                ),
                tracked_only_drops=tracked_drops,
                tracked_only_drop_ratio=tracked_drops / len(paired) if paired else None,
                future_scope_changed_windows=sum(
                    bool(row["future_scope_change_days"]) for row in samples
                ),
            )
        )

    def order(row):
        return (row["product_id"], row["source"], row.get("day", row.get("anchor_day")))

    report = dict(
        snapshot_at=snapshot.captured_at,
        last_closed_day=closed_day,
        rules=RULES,
        reason_labels=REASONS,
        targets={
            "own_primary": "y_sabit",
            "own_secondary": "y_izlenen",
            "cimri_primary": "daily_minimum",
        },
        products=summaries,
        sources={
            source: dict(
                primary=counts([row for row in windows if row["source"] == source]),
                tracked=(
                    counts(
                        [row for row in windows if row["source"] == source], "tracked"
                    )
                    if source == "own"
                    else None
                ),
                strict=counts([row for row in strict if row["source"] == source], None),
            )
            for source in ("own", "cimri")
        },
        label_only_fields=[
            "primary",
            "tracked",
            "future_scope_change_days",
            "target_end",
        ],
        model_trained=False,
        production_prediction_enabled=False,
    )
    return (
        report,
        sorted(daily, key=order),
        sorted(windows, key=order),
        sorted(strict, key=order),
    )
