"""Kendi fiyat geçmişinden kapsamı ve yeterliliği açıklanan göstergeler."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import log
from statistics import stdev
from typing import Literal
from zoneinfo import ZoneInfo

from app.database.read import ProductRun, ProductSnapshot

Reason = Literal[
    "no_history",
    "incomplete_scope",
    "insufficient_period",
    "no_prices",
    "insufficient_transitions",
    "insufficient_days",
]


@dataclass(frozen=True)
class Statistic[T]:
    value: T | None
    reasons: tuple[Reason, ...]
    period_started_at: datetime | None
    period_ended_at: datetime | None
    observations: int


@dataclass(frozen=True)
class VolatilityStatistic(Statistic[float]):
    transitions: int
    days: int


@dataclass(frozen=True)
class ProductStatistics:
    source_run_id: int | None
    scope_started_at: datetime | None
    scope_ended_at: datetime | None
    scope_runs: int
    planned_listing_ids: tuple[str, ...]
    low_30d: Statistic[int]
    high_in_scope: Statistic[int]
    volatility_30d: VolatilityStatistic


def _empty_statistics(current: ProductRun | None, reason: Reason) -> ProductStatistics:
    missing = Statistic[int](None, (reason,), None, None, 0)
    return ProductStatistics(
        source_run_id=current.run_id if current else None,
        scope_started_at=None,
        scope_ended_at=None,
        scope_runs=0,
        planned_listing_ids=(
            tuple(sorted(current.planned_listing_ids)) if current else ()
        ),
        low_30d=missing,
        high_in_scope=missing,
        volatility_30d=VolatilityStatistic(None, (reason,), None, None, 0, 0, 0),
    )


def _volatility(
    scope: tuple[ProductRun, ...],
    window: tuple[ProductRun, ...],
    start: datetime,
    end: datetime,
) -> VolatilityStatistic:
    window_ids = {run.run_id for run in window}
    changes = []
    used_runs = set()
    days = set()
    istanbul = ZoneInfo("Europe/Istanbul")
    # Fiyatları önce süzmek, fiyatsız turun üzerinden sahte geçiş üretir.
    for before, after in zip(scope, scope[1:]):
        if before.run_id not in window_ids or after.run_id not in window_ids:
            continue
        if before.best_price is None or after.best_price is None:
            continue
        if before.best_checked_at is None or after.best_checked_at is None:
            continue
        gap = after.best_checked_at - before.best_checked_at
        if not timedelta(0) < gap <= timedelta(hours=18):
            continue
        changes.append(log(after.best_price / before.best_price))
        used_runs.update((before.run_id, after.run_id))
        days.update(
            (
                before.best_checked_at.astimezone(istanbul).date(),
                after.best_checked_at.astimezone(istanbul).date(),
            )
        )
    reasons: list[Reason] = []
    if not any(run.best_price is not None for run in window):
        reasons.append("no_prices")
    if len(changes) < 14:
        reasons.append("insufficient_transitions")
    if len(days) < 7:
        reasons.append("insufficient_days")
    return VolatilityStatistic(
        value=None if reasons else stdev(changes) * 100,
        reasons=tuple(reasons),
        period_started_at=start,
        period_ended_at=end,
        observations=len(used_runs),
        transitions=len(changes),
        days=len(days),
    )


def calculate_statistics(snapshot: ProductSnapshot) -> ProductStatistics:
    history = snapshot.all_history
    if not history:
        return _empty_statistics(None, "no_history")
    current = history[-1]
    if current.partial:
        return _empty_statistics(current, "incomplete_scope")
    pages = frozenset(current.planned_listing_ids)
    backwards = []
    for run in reversed(history):
        if run.partial or frozenset(run.planned_listing_ids) != pages:
            break
        backwards.append(run)
    scope = tuple(reversed(backwards))
    start = scope[0].run_started_at
    end = current.run_started_at
    window_start = end - timedelta(days=30)
    window = tuple(run for run in scope if window_start <= run.run_started_at <= end)
    prices = tuple(run.best_price for run in scope if run.best_price is not None)
    window_prices = tuple(
        run.best_price for run in window if run.best_price is not None
    )
    low_reasons: list[Reason] = []
    if end - start < timedelta(days=30):
        low_reasons.append("insufficient_period")
    if not window_prices:
        low_reasons.append("no_prices")
    period_start = max(start, window_start)
    return ProductStatistics(
        source_run_id=current.run_id,
        scope_started_at=start,
        scope_ended_at=end,
        scope_runs=len(scope),
        planned_listing_ids=tuple(sorted(pages)),
        low_30d=Statistic[int](
            value=None if low_reasons else min(window_prices),
            reasons=tuple(low_reasons),
            period_started_at=period_start,
            period_ended_at=end,
            observations=len(window_prices),
        ),
        high_in_scope=Statistic[int](
            value=max(prices) if prices else None,
            reasons=() if prices else ("no_prices",),
            period_started_at=start,
            period_ended_at=end,
            observations=len(prices),
        ),
        volatility_30d=_volatility(scope, window, period_start, end),
    )
