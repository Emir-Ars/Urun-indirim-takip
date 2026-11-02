"""Eksik ölçümlerde simetrik etiket ve sabit sayfa kapsamı kuralları."""

from datetime import date, timedelta

import pytest

from app.ml.labels import analyze_labels
from tests.support.ml import (
    add_label_page,
    label_snapshot,
    label_tables,
    remove_label_run,
)

FIRST = date(2026, 1, 1)
ANCHOR = FIRST + timedelta(days=29)


def anchor_result(snapshot, source="own", offset=29):
    return next(
        row
        for row in analyze_labels(snapshot)[2]
        if row["source"] == source
        and row["anchor_day"] == FIRST + timedelta(days=offset)
    )


def set_check(tables, run_id, outcome, price=None, listing="hepsiburada_a"):
    row = next(
        row
        for row in tables["listing_checks"]
        if row["run_id"] == run_id and row["listing_id"] == listing
    )
    row.update(outcome=outcome, current_price=price)
    if outcome is None:
        row["checked_at"] = None


@pytest.mark.parametrize("source", ["own", "cimri"])
@pytest.mark.parametrize("price,label", [(9500, 1), (9501, 0), (9499, 1), (10000, 0)])
def test_integer_threshold(source, price, label):
    row = anchor_result(label_snapshot(prices=[10000] * 36 + [price]), source)
    assert row["primary"]["label"] == label


@pytest.mark.parametrize("source", ["own", "cimri"])
@pytest.mark.parametrize("missing,label", [(0, 1), (1, 1), (2, None)])
def test_six_of_seven_even_if_drop_already_seen(source, missing, label):
    prices = [10000] * 30 + [9000] + [10000] * (6 - missing) + [None] * missing
    row = anchor_result(label_snapshot(prices=prices), source)
    assert row["primary"]["future_observed_days"] == 7 - missing
    assert row["primary"]["label"] == label


@pytest.mark.parametrize("source", ["own", "cimri"])
def test_missing_history_does_not_remove_relaxed_sample(source):
    prices = [10000] * 37
    prices[10] = None
    snapshot = label_snapshot(prices=prices)
    row = anchor_result(snapshot, source)
    assert row["primary"]["label"] == 0
    assert row["history_missing_days"] == 1
    assert row["history_missing_ratio"] == 1 / 30
    strict = next(
        row
        for row in analyze_labels(snapshot)[3]
        if row["source"] == source and row["anchor_day"] == ANCHOR
    )
    assert strict["label"] is None


@pytest.mark.parametrize("source", ["own", "cimri"])
def test_calendar_boundaries_and_unclosed_seventh_day(source):
    result = analyze_labels(label_snapshot(count=36))
    row = next(
        row
        for row in result[2]
        if row["source"] == source and row["anchor_day"] == ANCHOR
    )
    assert row["history_start"] == FIRST
    assert row["target_end"] == FIRST + timedelta(days=36)
    assert row["primary"]["future_observed_days"] == 6
    assert row["primary"]["label"] is None
    assert "future_not_available" in row["primary"]["reasons"]
    early = next(
        row
        for row in result[2]
        if row["source"] == source and row["anchor_day"] == FIRST + timedelta(days=28)
    )
    assert "insufficient_history_period" in early["primary"]["reasons"]


def test_evening_required_and_morning_not_a_reference():
    tables = label_tables()
    set_check(tables, 60, "sold_out")
    result = analyze_labels(label_snapshot(tables))
    assert not any(
        row["source"] == "own" and row["anchor_day"] == ANCHOR for row in result[2]
    )
    daily = next(
        row for row in result[1] if row["source"] == "own" and row["day"] == ANCHOR
    )
    assert daily["minimum_price"] == 10000
    assert daily["anchor_reasons"] == ["all_sold_out_evening"]


def test_missing_other_slot_is_allowed():
    tables = label_tables()
    remove_label_run(tables, 73)
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["label"] == 0
    assert row["primary"]["future_observed_days"] == 7


def test_error_in_completed_slot_blocks_day_despite_good_other_slot():
    tables = label_tables()
    set_check(tables, 73, "error")
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["future_observed_days"] == 6
    assert row["primary"]["future_days"][-1]["reasons"] == ["incomplete_answers"]


def test_partial_anchor_and_pending_check_are_not_reference_prices():
    tables = label_tables()
    add_label_page(tables)
    set_check(tables, 60, None, listing="new_page")
    result = analyze_labels(label_snapshot(tables))
    assert not any(
        row["source"] == "own" and row["anchor_day"] == ANCHOR for row in result[2]
    )


def test_other_product_error_does_not_block_anchor():
    tables = label_tables()
    other = {**tables["products"][0], "product_id": 2, "product_key": "other_phone"}
    tables["products"].append(other)
    add_label_page(tables, product_id=2)
    set_check(tables, 60, "error", listing="new_page")
    assert anchor_result(label_snapshot(tables))["primary"]["label"] == 0


def test_new_cheap_page_only_changes_tracked_label():
    tables = label_tables()
    add_label_page(tables, start_offset=30, price=9000)
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["label"] == 0
    assert row["tracked"]["label"] == 1
    assert len(row["future_scope_change_days"]) == 7
    assert row["scope"] == ["hepsiburada_a"]


def test_error_in_new_page_does_not_poison_fixed_target():
    tables = label_tables()
    add_label_page(tables, start_offset=30, price=9000)
    for run_id in range(61, 75):
        set_check(tables, run_id, "error", listing="new_page")
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["label"] == 0
    assert row["tracked"]["label"] is None
    assert row["tracked"]["future_observed_days"] == 0


def test_removed_page_is_not_carried_forward():
    tables = label_tables()
    add_label_page(tables, end_offset=29, price=9000)
    row = anchor_result(label_snapshot(tables))
    assert row["reference_price"] == 9000
    assert row["primary"]["future_minimum_price"] == 10000
    assert row["primary"]["label"] == 0
    assert all(
        day["planned_scope"] == ["hepsiburada_a"]
        for day in row["primary"]["future_days"]
    )


def test_no_remaining_baseline_pages_is_unobserved():
    tables = label_tables()
    add_label_page(tables, start_offset=30, price=9000)
    for run in tables["collection_runs"]:
        if run["run_id"] >= 61:
            run["planned_count"] -= 1
    tables["listing_checks"] = [
        row
        for row in tables["listing_checks"]
        if row["run_id"] < 61 or row["listing_id"] == "new_page"
    ]
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["label"] is None
    assert row["primary"]["future_observed_days"] == 0
    assert row["tracked"]["label"] == 1


def test_cross_day_evening_not_reassigned_and_morning_still_usable():
    tables = label_tables()
    run = tables["collection_runs"][-1]
    run["finished_at"] += timedelta(hours=2)
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["future_observed_days"] == 7
    daily = [
        row
        for row in analyze_labels(label_snapshot(tables))[1]
        if row["source"] == "own"
    ]
    assert daily[-1]["reference_price"] is None
    assert "late_completion" in daily[-1]["reasons"]


def test_late_only_slot_does_not_supply_daily_price():
    tables = label_tables()
    tables["collection_runs"][-1]["finished_at"] += timedelta(hours=2)
    remove_label_run(tables, 73)
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["future_observed_days"] == 6


def test_duplicate_slot_is_not_chosen_by_price():
    tables = label_tables()
    run = {**tables["collection_runs"][-1], "run_id": 75}
    check = {**tables["listing_checks"][-1], "run_id": 75, "current_price": 1}
    tables["collection_runs"].append(run)
    tables["listing_checks"].append(check)
    row = anchor_result(label_snapshot(tables))
    assert row["primary"]["label"] == 0
    assert row["primary"]["future_minimum_price"] == 10000


def test_manual_tours_are_ignored():
    tables = label_tables()
    tables["collection_runs"][-1]["trigger"] = "manual"
    tables["listing_checks"][-1]["current_price"] = 1
    assert anchor_result(label_snapshot(tables))["primary"]["label"] == 0


def test_error_only_first_day_does_not_start_history():
    tables = label_tables()
    for run_id in (1, 2):
        set_check(tables, run_id, "error")
    row = anchor_result(label_snapshot(tables))
    assert "insufficient_history_period" in row["primary"]["reasons"]


def test_current_active_flags_do_not_erase_history():
    tables = label_tables()
    tables["listings"][0]["active"] = False
    tables["products"][0]["active"] = False
    tables["platforms"][0]["active"] = False
    assert anchor_result(label_snapshot(tables))["primary"]["label"] == 0


def test_cimri_half_day_stays_missing_in_later_snapshot():
    tables = label_tables()
    row = tables["market_history"][-1]
    row["captured_at"] = tables["collection_runs"][-1]["started_at"]
    row["price_kurus"] = 1
    snapshot = label_snapshot(tables)
    row = anchor_result(snapshot, "cimri")
    assert row["primary"]["future_observed_days"] == 6
    assert row["primary"]["label"] == 0
    assert row["primary"]["future_days"][-1]["reasons"] == ["half_day"]
    assert anchor_result(snapshot)["primary"]["future_observed_days"] == 7


def test_cimri_identity_change_eliminates_window():
    tables = label_tables()
    tables["market_history"][-1]["source_product_id"] = "987654"
    row = anchor_result(label_snapshot(tables), "cimri")
    assert row["primary"]["label"] is None
    assert "source_identity_change" in row["primary"]["reasons"]


def test_missing_cimri_record_is_not_filled():
    tables = label_tables()
    tables["market_history"].pop(33)
    row = anchor_result(label_snapshot(tables), "cimri")
    assert row["primary"]["future_observed_days"] == 6
    assert row["primary"]["label"] == 0


def test_report_counts_match_labels_and_scope_pairing():
    tables = label_tables()
    add_label_page(tables, start_offset=30, price=9000)
    report, _, windows, _ = analyze_labels(label_snapshot(tables))
    own = next(row for row in report["products"] if row["source"] == "own")
    assert own["paired_labels"] == 1
    assert own["scope_label_differences"] == own["tracked_only_drops"] == 1
    assert own["primary"]["usable"] == 1
    assert report["sources"]["own"]["primary"]["candidates"] == len(
        [row for row in windows if row["source"] == "own"]
    )
