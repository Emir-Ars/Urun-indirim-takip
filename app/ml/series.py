"""Görüntüden iki ayrı günlük seri; eksik fiyatlar doldurulmaz."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from app.ml.dataset import CheckRow, MlSnapshot, RunRow

ISTANBUL = ZoneInfo("Europe/Istanbul")
ANSWERED = {"offer", "sold_out"}


def dates(start: date, end: date):
    for offset in range(max(0, (end - start).days + 1)):
        yield start + timedelta(days=offset)


def scheduled_slot(at):
    local = at.astimezone(ISTANBUL)
    if local.hour >= 22:
        return local.date(), 22
    if local.hour >= 10:
        return local.date(), 10
    return local.date() - timedelta(days=1), 22


def half_day(row):
    return row.day == row.captured_at.astimezone(ISTANBUL).date()


@dataclass(frozen=True)
class SlotRun:
    hour: int
    run: RunRow
    checks: tuple[CheckRow, ...]
    duplicate: bool

    def usable(self, day):
        return (
            not self.duplicate
            and self.run.status == "completed"
            and self.run.finished_at.astimezone(ISTANBUL).date() == day
        )


@dataclass
class PriceSeries:
    product_id: int
    source: str
    first_observation: date | None
    days: dict[date, dict]
    strict_days: list[dict]
    runs: dict[date, list[SlotRun]] = field(default_factory=dict)


def own_minimum(day, views, scope=None):
    """Sabit kapsamda yalnız o gün planlanan kesişim değerlendirilir.

    Bir dilimin yokluğu diğer sağlam dilimi geçersiz kılmaz. Tamamlanmış,
    kullanılabilir dilimdeki ilgili hata ise ucuz teklifi saklıyor olabilir.
    """
    prices, reasons, planned = [], set(), set()
    for view in views:
        if not view.usable(day):
            continue
        checks = [
            row for row in view.checks if scope is None or row.listing_id in scope
        ]
        planned.update(row.listing_id for row in checks)
        if any(row.outcome not in ANSWERED for row in checks):
            reasons.add("incomplete_answers")
        prices.extend(row.current_price for row in checks if row.outcome == "offer")
    if not planned:
        reasons.add("no_usable_planned_pages")
    elif not prices and not reasons:
        reasons.add("all_sold_out")
    return {
        "day": day,
        "price": min(prices) if prices and not reasons else None,
        "reasons": sorted(reasons),
        "planned_scope": sorted(planned),
    }


def build_series(snapshot: MlSnapshot):
    closed_day = snapshot.captured_at.astimezone(ISTANBUL).date() - timedelta(days=1)
    groups, slots, markets = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in snapshot.listing_checks:
        groups[row.product_id, row.run_id].append(row)
    for run in snapshot.collection_runs:
        if run.trigger == "scheduled":
            slots[scheduled_slot(run.started_at)].append(run)
    for row in snapshot.market_history:
        if row.day <= closed_day:
            markets[row.product_id].append(row)
    result = []
    for product in snapshot.products:
        result.append(_own_series(product.product_id, groups, slots, closed_day))
        result.append(
            _market_series(product.product_id, markets[product.product_id], closed_day)
        )
    return closed_day, result


def _own_series(product_id, groups, slots, closed_day):
    starts, observations = [], []
    for (day, _), runs in slots.items():
        for run in runs:
            checks = groups.get((product_id, run.run_id), ())
            if checks:
                starts.append(day)
            if any(row.outcome in ANSWERED for row in checks):
                observations.append(day)
    first = min(observations, default=None)
    series = PriceSeries(product_id, "own", first, {}, [])
    if not starts:
        return series
    for day in dates(min(starts), closed_day):
        views, reasons, scopes, raw_prices, run_ids = [], set(), [], [], []
        raw_reference, observed = None, False
        for hour in (10, 22):
            assigned = slots.get((day, hour), ())
            if len(assigned) != 1:
                reasons.add("missing_slot" if not assigned else "duplicate_slot")
            for run in assigned:
                checks = tuple(groups.get((product_id, run.run_id), ()))
                views.append(SlotRun(hour, run, checks, len(assigned) != 1))
                run_ids.append(run.run_id)
                if not checks:
                    reasons.add("product_not_planned")
                    continue
                scopes.append(tuple(sorted(row.listing_id for row in checks)))
                observed = observed or any(row.checked_at is not None for row in checks)
                if run.status != "completed":
                    reasons.add("unfinished_run")
                if run.finished_at.astimezone(ISTANBUL).date() != day:
                    reasons.add("late_completion")
                if any(row.outcome not in ANSWERED for row in checks):
                    reasons.add("incomplete_answers")
                offers = [row.current_price for row in checks if row.outcome == "offer"]
                if run.status == "completed":
                    raw_prices.extend(offers)
                    if hour == 22 and len(assigned) == 1:
                        raw_reference = min(offers, default=None)
        scope = scopes[0] if scopes and len(set(scopes)) == 1 else None
        if len(set(scopes)) > 1:
            reasons.add("intraday_scope_change")
        strict = dict(
            day=day,
            observed=observed,
            reference_price=raw_reference,
            minimum_price=min(raw_prices, default=None),
            scope=scope,
            reasons=sorted(reasons),
            run_ids=run_ids,
        )
        series.strict_days.append(strict)
        series.runs[day] = views
        evening = [view for view in views if view.hour == 22]
        anchor, anchor_scope, anchor_at = None, [], None
        anchor_reasons = set()
        if len(evening) != 1:
            anchor_reasons.add(
                "missing_evening" if not evening else "duplicate_evening"
            )
        else:
            view = evening[0]
            if not view.usable(day):
                anchor_reasons.add("unusable_evening")
            elif not view.checks:
                anchor_reasons.add("product_not_planned")
            elif any(row.outcome not in ANSWERED for row in view.checks):
                anchor_reasons.add("incomplete_evening_answers")
            else:
                anchor = min(
                    (
                        row.current_price
                        for row in view.checks
                        if row.outcome == "offer"
                    ),
                    default=None,
                )
                if anchor is None:
                    anchor_reasons.add("all_sold_out_evening")
                else:
                    anchor_scope = sorted(row.listing_id for row in view.checks)
                    anchor_at = view.run.finished_at
        minimum = own_minimum(day, views)
        series.days[day] = dict(
            day=day,
            observed=observed,
            reference_price=anchor,
            minimum_price=minimum["price"],
            scope=anchor_scope,
            anchor_at=anchor_at,
            anchor_reasons=sorted(anchor_reasons),
            reasons=sorted(reasons | set(minimum["reasons"])),
            run_ids=run_ids,
            checks=[
                row.model_dump(mode="json") for view in views for row in view.checks
            ],
            source_product_id=None,
        )
    return series


def _market_series(product_id, rows, closed_day):
    rows = sorted(rows, key=lambda row: row.day)
    series = PriceSeries(product_id, "cimri", rows[0].day if rows else None, {}, [])
    if not rows:
        return series
    by_day = {row.day: row for row in rows}
    for day in dates(rows[0].day, closed_day):
        row = by_day.get(day)
        partial = row is not None and half_day(row)
        price = row.price_kurus if row is not None and not partial else None
        reasons = (
            ["missing_record"]
            if row is None
            else ["half_day"] if partial else ["missing_price"] if price is None else []
        )
        series.days[day] = dict(
            day=day,
            observed=row is not None,
            reference_price=price,
            minimum_price=price,
            scope=[row.source_product_id] if row else [],
            anchor_at=None,
            anchor_reasons=reasons,
            reasons=reasons,
            run_ids=[],
            checks=[],
            source_product_id=row.source_product_id if row else None,
            captured_at=row.captured_at if row else None,
            recorded_price=row.price_kurus if row else None,
        )
        if row is not None:
            # Eski araç da yalnız kayıtlı Cimri günlerinden bir seri kurar.
            series.strict_days.append(
                dict(
                    day=day,
                    observed=True,
                    reference_price=price,
                    minimum_price=price,
                    scope=(row.source_product_id,),
                    reasons=[],
                    run_ids=[],
                )
            )
    return series
