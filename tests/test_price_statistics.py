"""İstatistikler: sentetik geçmişler ve bağımsız sayısal beklentiler."""

from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.contracts import Product
from app.database.read import MarketPoint, ProductRun, ProductSnapshot
from app.price_statistics import calculate_statistics

START = datetime(2024, 11, 1, 7, tzinfo=timezone.utc)
PRODUCT = Product(
    product_id=1,
    product_key="apple_iphone_15_128gb",
    brand="Apple",
    model="iPhone 15",
    storage_gb=128,
    active=True,
)
CIMRI = (
    MarketPoint(
        date(2024, 11, 1),
        1,
        "cimri",
        "123456",
        "https://www.cimri.com/cep-telefonlari/test,a123456",
        START,
    ),
)


def run(run_id, at, price=10000, pages=("a", "b"), answered=None):
    answered = len(pages) if answered is None else answered
    offers = int(price is not None)
    checked = at + timedelta(minutes=1)
    return ProductRun(
        run_id=run_id,
        product_id=1,
        run_started_at=at,
        run_finished_at=at + timedelta(minutes=30),
        planned_pages=len(pages),
        answered_pages=answered,
        offer_pages=offers,
        sold_out_pages=answered - offers,
        error_pages=len(pages) - answered,
        best_price=price,
        best_listing_id="a" if offers else None,
        best_checked_at=checked if offers else None,
        last_checked_at=checked,
        previous_run_id=run_id - 1 if run_id > 1 else None,
        previous_best_price=None,
        hours_since_previous=Decimal("12") if run_id > 1 else None,
        comparable_with_previous=run_id > 1,
        planned_listing_ids=pages,
    )


def snapshot(*runs, history=None, cimri=()):
    return ProductSnapshot(
        product=PRODUCT,
        current=runs[-1] if runs else None,
        checks=(),
        best_offer=None,
        last_successful_offer=None,
        history=tuple(runs) if history is None else history,
        all_history=tuple(runs),
        cimri_history=cimri,
    )


def series(count=15, step=timedelta(hours=12), prices=None):
    return tuple(
        run(index + 1, START + index * step, prices[index] if prices else 10000)
        for index in range(count)
    )


@pytest.mark.parametrize("cimri", [(), CIMRI])
def test_no_own_history_has_no_statistics_even_with_cimri(cimri):
    result = calculate_statistics(snapshot(cimri=cimri))
    assert result.source_run_id is None
    assert result.scope_started_at is result.scope_ended_at is None
    assert result.scope_runs == 0
    assert result.planned_listing_ids == ()
    for metric in (result.low_30d, result.high_in_scope, result.volatility_30d):
        assert metric.value is None
        assert metric.reasons == ("no_history",)
        assert metric.period_started_at is metric.period_ended_at is None
        assert metric.observations == 0
    assert result.volatility_30d.transitions == result.volatility_30d.days == 0


@pytest.mark.parametrize("price,answered", [(10000, 1), (None, 1), (None, 0)])
def test_incomplete_latest_run_does_not_fall_back_to_an_older_period(price, answered):
    past = run(1, START, 90000)
    latest = run(2, START + timedelta(days=40), price, answered=answered)
    result = calculate_statistics(snapshot(past, latest))
    assert result.source_run_id == 2
    assert result.scope_runs == 0
    assert result.scope_started_at is result.scope_ended_at is None
    for metric in (result.low_30d, result.high_in_scope, result.volatility_30d):
        assert metric.value is None
        assert metric.reasons == ("incomplete_scope",)
        assert metric.observations == 0


@pytest.mark.parametrize("price", [12345, 2**60 + 7])
def test_single_offer_has_an_integer_peak_and_explained_missing_metrics(price):
    result = calculate_statistics(snapshot(run(1, START, price)))
    assert result.scope_runs == 1
    assert result.scope_started_at == result.scope_ended_at == START
    assert result.high_in_scope.value == price
    assert type(result.high_in_scope.value) is int
    assert result.high_in_scope.reasons == ()
    assert result.high_in_scope.observations == 1
    assert result.low_30d.value is None
    assert result.low_30d.reasons == ("insufficient_period",)
    assert result.low_30d.observations == 1
    assert result.volatility_30d.reasons == (
        "insufficient_transitions",
        "insufficient_days",
    )
    assert result.volatility_30d.observations == 0


@pytest.mark.parametrize(
    "days,low_reasons",
    [(5, ("insufficient_period", "no_prices")), (30, ("no_prices",))],
)
def test_all_sold_out_runs_keep_the_scope_but_do_not_invent_prices(days, low_reasons):
    result = calculate_statistics(
        snapshot(run(1, START, None), run(2, START + timedelta(days=days), None))
    )
    assert result.scope_runs == 2
    assert result.high_in_scope.value is result.low_30d.value is None
    assert result.low_30d.reasons == low_reasons
    assert result.high_in_scope.reasons == ("no_prices",)
    assert result.high_in_scope.observations == 0
    assert result.volatility_30d.reasons == (
        "no_prices",
        "insufficient_transitions",
        "insufficient_days",
    )


def test_an_older_incomplete_run_is_a_boundary_even_if_the_view_is_comparable():
    runs = (
        run(1, START, 90000),
        run(2, START + timedelta(days=1), 80000, answered=1),
        run(3, START + timedelta(days=2), 10000),
        run(4, START + timedelta(days=3), 9000),
    )
    result = calculate_statistics(snapshot(*runs))
    assert runs[1].comparable_with_previous is True
    assert result.scope_runs == 2
    assert result.scope_started_at == START + timedelta(days=2)
    assert result.high_in_scope.value == 10000
    assert result.high_in_scope.observations == 2


@pytest.mark.parametrize("old_pages", [("a",), ("a", "b", "c"), ("a", "c")])
def test_a_different_planned_page_set_is_not_part_of_the_current_scope(old_pages):
    result = calculate_statistics(
        snapshot(
            run(1, START, 90000, pages=old_pages),
            run(2, START + timedelta(days=1), 10000),
            run(3, START + timedelta(days=2), 9000),
        )
    )
    assert result.scope_runs == 2
    assert result.scope_started_at == START + timedelta(days=1)
    assert result.planned_listing_ids == ("a", "b")
    assert result.high_in_scope.value == 10000


def test_page_order_does_not_change_the_scope():
    result = calculate_statistics(
        snapshot(
            run(1, START, 12000, pages=("b", "a")),
            run(2, START + timedelta(days=30), 10000),
        )
    )
    assert result.scope_runs == 2
    assert result.planned_listing_ids == ("a", "b")
    assert result.low_30d.value == 10000
    assert result.high_in_scope.value == 12000


def test_sold_out_run_stays_in_scope_and_breaks_price_adjacency():
    result = calculate_statistics(
        snapshot(
            run(1, START, 10000),
            run(2, START + timedelta(hours=12), None),
            run(3, START + timedelta(hours=24), 12000),
        )
    )
    assert result.scope_runs == 3
    assert result.high_in_scope.value == 12000
    assert result.high_in_scope.observations == 2
    assert result.volatility_30d.transitions == 0
    assert result.volatility_30d.days == 0


def test_long_gaps_keep_the_peak_period_but_not_volatility_transitions():
    result = calculate_statistics(
        snapshot(
            run(1, START, 50000),
            run(2, START + timedelta(days=31), 12345),
            run(3, START + timedelta(days=40), 9000),
        )
    )
    assert result.scope_runs == 3
    assert result.scope_started_at == START
    assert result.low_30d.value == 9000
    assert result.low_30d.observations == 2
    assert result.low_30d.period_started_at == START + timedelta(days=10)
    assert result.high_in_scope.value == 50000
    assert result.high_in_scope.observations == 3
    assert result.high_in_scope.period_started_at == START
    assert result.volatility_30d.transitions == 0


@pytest.mark.parametrize(
    "offset,expected",
    [
        (timedelta(microseconds=-1), None),
        (timedelta(0), 10000),
        (timedelta(microseconds=1), 12000),
    ],
)
def test_thirty_day_duration_and_window_edges_are_exact(offset, expected):
    at = START + timedelta(days=30) + offset
    result = calculate_statistics(snapshot(run(1, START), run(2, at, 12000)))
    assert result.low_30d.value == expected
    assert result.low_30d.reasons == (
        ("insufficient_period",) if expected is None else ()
    )
    assert result.low_30d.period_ended_at == at


def test_low_excludes_an_older_price_and_includes_both_window_boundaries():
    end = START + timedelta(days=30)
    result = calculate_statistics(
        snapshot(
            run(1, START - timedelta(microseconds=1), 1000),
            run(2, START, 9000),
            run(3, START + timedelta(days=1), 50000),
            run(4, end, 12000),
        )
    )
    assert result.low_30d.value == 9000
    assert result.low_30d.period_started_at == START
    assert result.low_30d.period_ended_at == end
    assert result.low_30d.observations == 3
    assert result.high_in_scope.observations == 4


def test_a_price_outside_the_window_does_not_replace_a_missing_window_price():
    result = calculate_statistics(
        snapshot(run(1, START, 9000), run(2, START + timedelta(days=40), None))
    )
    assert result.low_30d.value is None
    assert result.low_30d.reasons == ("no_prices",)
    assert result.high_in_scope.value == 9000


@pytest.mark.parametrize("count,transitions,days", [(14, 13, 7), (15, 14, 8)])
def test_transition_threshold_is_fourteen(count, transitions, days):
    metric = calculate_statistics(snapshot(*series(count))).volatility_30d
    assert metric.transitions == transitions
    assert metric.days == days
    assert metric.observations == count
    assert metric.value == (0.0 if transitions == 14 else None)
    assert metric.reasons == (
        () if transitions == 14 else ("insufficient_transitions",)
    )


@pytest.mark.parametrize("hours,days", [(9, 6), (10, 7)])
def test_day_threshold_is_seven_even_with_fourteen_transitions(hours, days):
    metric = calculate_statistics(
        snapshot(*series(step=timedelta(hours=hours)))
    ).volatility_30d
    assert metric.transitions == 14
    assert metric.days == days
    assert metric.value == (0.0 if days == 7 else None)
    assert metric.reasons == (() if days == 7 else ("insufficient_days",))


def test_isolated_price_days_do_not_help_the_seven_day_threshold():
    runs = series(step=timedelta(hours=2)) + (
        run(16, START + timedelta(days=5)),
        run(17, START + timedelta(days=10)),
    )
    metric = calculate_statistics(snapshot(*runs)).volatility_30d
    assert metric.transitions == 14
    assert metric.observations == 15
    assert metric.days == 2
    assert metric.value is None
    assert metric.reasons == ("insufficient_days",)


@pytest.mark.parametrize(
    "shift,days",
    [
        (-timedelta(hours=6, seconds=1), 7),
        (timedelta(hours=13, minutes=59, seconds=59), 6),
    ],
)
def test_istanbul_days_come_from_price_checks_including_both_transition_ends(
    shift, days
):
    runs = series(step=timedelta(hours=10))
    shifted = tuple(
        replace(
            item,
            run_started_at=item.run_started_at + shift,
            run_finished_at=item.run_finished_at + shift,
            best_checked_at=item.best_checked_at + shift,
        )
        for item in runs
    )
    metric = calculate_statistics(snapshot(*shifted)).volatility_30d
    assert metric.transitions == 14
    assert metric.days == days
    assert metric.value == (0.0 if days == 7 else None)
    assert metric.reasons == (() if days == 7 else ("insufficient_days",))


@pytest.mark.parametrize(
    "offset,transitions",
    [
        (timedelta(microseconds=-1), 14),
        (timedelta(0), 14),
        (timedelta(microseconds=1), 13),
    ],
)
def test_eighteen_hours_is_inclusive_and_not_rounded(offset, transitions):
    runs = series(step=timedelta(hours=18))
    last = replace(
        runs[-1],
        best_checked_at=runs[-1].best_checked_at + offset,
        hours_since_previous=Decimal("18.00"),
    )
    metric = calculate_statistics(snapshot(*runs[:-1], last)).volatility_30d
    assert metric.transitions == transitions
    assert metric.value == (0.0 if transitions == 14 else None)
    assert metric.reasons == (
        () if transitions == 14 else ("insufficient_transitions",)
    )


@pytest.mark.parametrize("gap", [timedelta(0), timedelta(seconds=-1)])
def test_equal_or_backwards_check_times_do_not_form_a_transition(gap):
    runs = series()
    last = replace(runs[-1], best_checked_at=runs[-2].best_checked_at + gap)
    metric = calculate_statistics(snapshot(*runs[:-1], last)).volatility_30d
    assert metric.transitions == 13
    assert metric.value is None
    assert metric.reasons == ("insufficient_transitions",)


@pytest.mark.parametrize("index,transitions", [(-1, 15), (8, 14)])
def test_a_missing_check_time_is_not_a_valid_transition(index, transitions):
    runs = list(series(17))
    runs[index] = replace(runs[index], best_checked_at=None)
    metric = calculate_statistics(snapshot(*runs)).volatility_30d
    assert metric.transitions == transitions
    assert metric.value == 0.0


def test_no_transition_skips_a_missing_middle_price():
    runs = list(series(16))
    runs[7] = run(8, runs[7].run_started_at, None)
    result = calculate_statistics(snapshot(*runs))
    assert result.scope_runs == 16
    assert result.volatility_30d.transitions == 13
    assert result.volatility_30d.observations == 15
    assert result.volatility_30d.value is None
    assert result.volatility_30d.reasons == ("insufficient_transitions",)


@pytest.mark.parametrize("index", [0, -1])
def test_a_missing_edge_price_does_not_discard_other_valid_transitions(index):
    runs = list(series(17))
    runs[index] = run(runs[index].run_id, runs[index].run_started_at, None)
    metric = calculate_statistics(snapshot(*runs)).volatility_30d
    assert metric.transitions == 15
    assert metric.observations == 16
    assert metric.value == 0.0


def test_an_internal_long_gap_excludes_only_its_transition():
    runs = series()
    shifted = tuple(
        (
            replace(
                item,
                run_started_at=item.run_started_at + timedelta(days=2),
                run_finished_at=item.run_finished_at + timedelta(days=2),
                best_checked_at=item.best_checked_at + timedelta(days=2),
            )
            if index >= 8
            else item
        )
        for index, item in enumerate(runs)
    )
    result = calculate_statistics(snapshot(*shifted))
    assert result.scope_runs == 15
    assert result.volatility_30d.transitions == 13
    assert result.volatility_30d.observations == 15
    assert result.volatility_30d.value is None


def test_both_ends_of_a_transition_must_be_inside_the_thirty_day_window():
    recent = series(14)
    boundary = recent[-1].run_started_at - timedelta(days=30)
    runs = (
        run(-1, boundary - timedelta(hours=12)),
        run(0, boundary),
    ) + recent
    result = calculate_statistics(snapshot(*runs))
    assert result.low_30d.reasons == ()
    assert result.volatility_30d.transitions == 13
    assert result.volatility_30d.observations == 14
    assert result.volatility_30d.value is None


@pytest.mark.parametrize("scale", [1, 100, 2**40])
def test_log_sample_deviation_matches_an_independent_analytical_result(scale):
    prices = tuple(price * scale for price in ([10000, 20000] * 7 + [10000]))
    result = calculate_statistics(
        snapshot(*series(step=timedelta(hours=10), prices=prices))
    )
    metric = result.volatility_30d
    # Yedi +ln(2), yedi -ln(2): 100 * ln(2) * sqrt(14/13).
    assert metric.value == pytest.approx(71.93128235098797, rel=1e-12)
    assert metric.transitions == 14
    assert metric.days == 7
    assert metric.observations == 15
    assert metric.reasons == ()
    assert type(metric.value) is float


@pytest.mark.parametrize("prices", [None, tuple(10000 * 2**i for i in range(15))])
def test_zero_deviation_is_a_real_value_when_the_returns_are_constant(prices):
    metric = calculate_statistics(
        snapshot(*series(step=timedelta(hours=10), prices=prices))
    ).volatility_30d
    assert metric.value == 0.0
    assert metric.reasons == ()


@pytest.mark.parametrize("visible_count", [1, 3, 15])
def test_graph_window_cimri_and_product_activity_do_not_change_statistics(
    visible_count,
):
    complete = snapshot(*series(step=timedelta(hours=10)))
    changed = replace(
        complete,
        product=PRODUCT.model_copy(update={"active": False}),
        history=complete.all_history[-visible_count:],
        cimri_history=CIMRI,
    )
    assert calculate_statistics(changed) == calculate_statistics(complete)


def test_result_is_frozen_input_is_unchanged_and_calculation_is_repeatable():
    original = snapshot(*series(step=timedelta(hours=10)))
    before = replace(original)
    result = calculate_statistics(original)
    assert original == before
    assert calculate_statistics(original) == result
    assert result.source_run_id == 15
    assert result.low_30d.observations == result.high_in_scope.observations == 15
    with pytest.raises(FrozenInstanceError):
        result.scope_runs = 0
    with pytest.raises(FrozenInstanceError):
        result.high_in_scope.value = 0
    with pytest.raises(FrozenInstanceError):
        result.volatility_30d.transitions = 0
