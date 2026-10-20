"""ML denetiminde eksik verinin etiketlenmediğini ve okuma sınırlarını sınar."""

import copy
import json
import os
from datetime import date, datetime, timedelta, timezone

import psycopg
import pytest

from tools import ml_data_check as audit
from test_database_read import world as _world, add_run, add_market, START

world = _world
DAY = date(2026, 1, 1)


def sample_snapshot(count=37, *, prices=None, own=True, market=True):
    prices = prices if prices is not None else [10000] * count
    payload = dict(
        version=1,
        captured_at=datetime.combine(
            DAY + timedelta(days=count), datetime.min.time(), audit.ISTANBUL
        ),
        commit="a" * 40,
        verifier_sha256="0" * 64,
        catalog_sha256="1" * 64,
        mapping_sha256="2" * 64,
        source_sha256={name: "3" * 64 for name in audit.reader.RELATIONS},
        source_unchanged=True,
        products=[
            dict(
                product_id=1,
                product_key="phone_256gb",
                brand="Marka",
                model="Telefon",
                storage_gb=256,
                active=True,
            )
        ],
        platforms=[dict(key="trendyol", active=True)],
        listings=[dict(listing_id="a", product_id=1, platform="trendyol", active=True)],
        collection_runs=[],
        listing_checks=[],
        market_history=[],
    )
    for offset, price in enumerate(prices):
        day = DAY + timedelta(days=offset)
        if own:
            for hour in (10, 22):
                run_id = offset * 2 + (1 if hour == 10 else 2)
                at = datetime.combine(day, datetime.min.time(), audit.ISTANBUL).replace(
                    hour=hour
                )
                payload["collection_runs"].append(
                    dict(
                        run_id=run_id,
                        trigger="scheduled",
                        status="completed",
                        started_at=at,
                        finished_at=at + timedelta(minutes=30),
                        planned_count=1,
                    )
                )
                payload["listing_checks"].append(
                    dict(
                        run_id=run_id,
                        listing_id="a",
                        product_id=1,
                        checked_at=at + timedelta(minutes=1),
                        outcome="offer" if price else "sold_out",
                        current_price=price,
                    )
                )
        if market:
            payload["market_history"].append(
                dict(
                    product_id=1,
                    source="cimri",
                    source_product_id="12345",
                    source_url="https://www.cimri.com/cep-telefonlari/telefon,a12345",
                    day=day,
                    price_kurus=price,
                    captured_at=payload["captured_at"],
                )
            )
    return audit.Snapshot.model_validate(payload)


def result_for(snapshot, source="own"):
    result, windows, daily = audit.analyze(snapshot)
    return (
        result["products"][0][source],
        [row for row in windows if row["source"] == source],
        daily,
    )


def change_check(snapshot, day, hour, **changes):
    run_id = day * 2 + (1 if hour == 10 else 2)
    return snapshot.model_copy(
        update={
            "listing_checks": [
                row.model_copy(update=changes) if row.run_id == run_id else row
                for row in snapshot.listing_checks
            ]
        }
    )


def change_run(snapshot, run_id, **changes):
    return snapshot.model_copy(
        update={
            "collection_runs": [
                row.model_copy(update=changes) if row.run_id == run_id else row
                for row in snapshot.collection_runs
            ]
        }
    )


@pytest.mark.parametrize("source", ["own", "cimri"])
@pytest.mark.parametrize(
    "count,expected", [(29, 0), (30, 0), (36, 0), (37, 1), (38, 2)]
)
def test_exact_calendar_window_boundaries(source, count, expected):
    summary, windows, _ = result_for(sample_snapshot(count), source)
    assert summary["windows"] == expected
    assert len(windows) == count
    if expected:
        first = next(row for row in windows if row["label"] is not None)
        assert first["anchor_day"] == DAY + timedelta(days=29)
        assert first["history_start"] == DAY
        assert first["target_end"] == DAY + timedelta(days=36)


@pytest.mark.parametrize("source", ["own", "cimri"])
@pytest.mark.parametrize("price,label", [(9500, 1), (9501, 0), (9499, 1), (10000, 0)])
def test_five_percent_is_inclusive_and_integer_exact(source, price, label):
    summary, windows, _ = result_for(
        sample_snapshot(prices=[10000] * 36 + [price]), source
    )
    assert summary["windows"] == 1
    assert next(row for row in windows if row["label"] is not None)["label"] == label


def test_drop_outside_seven_days_is_not_used():
    _, windows, _ = result_for(sample_snapshot(38, prices=[10000] * 37 + [1]))
    assert windows[29]["label"] == 0
    assert windows[30]["label"] == 1


def test_reference_is_evening_price_but_future_uses_intraday_minimum():
    snapshot = change_check(sample_snapshot(), 29, 10, current_price=100)
    snapshot = change_check(snapshot, 36, 10, current_price=9500)
    _, windows, daily = result_for(snapshot)
    assert windows[29]["reference_price"] == 10000
    assert windows[29]["future_minimum_price"] == 9500
    assert windows[29]["label"] == 1
    own_day = next(
        row
        for row in daily
        if row["source"] == "own" and row["day"] == DAY + timedelta(days=29)
    )
    assert own_day["minimum_price"] == 100 and own_day["reference_price"] == 10000


def test_missing_evening_price_never_falls_back_to_morning():
    snapshot = change_check(
        sample_snapshot(), 29, 22, outcome="sold_out", current_price=None
    )
    summary, windows, _ = result_for(snapshot)
    assert windows[29]["label"] is None
    assert "history_missing_price" in windows[29]["reasons"]
    assert summary["missing_reference_prices"] == 1


def test_future_sold_out_evening_can_keep_observed_morning_minimum():
    snapshot = change_check(
        sample_snapshot(), 36, 22, outcome="sold_out", current_price=None
    )
    _, windows, _ = result_for(snapshot)
    assert windows[29]["label"] == 0
    snapshot = change_check(snapshot, 36, 10, outcome="sold_out", current_price=None)
    _, windows, _ = result_for(snapshot)
    assert windows[29]["label"] is None
    assert "future_missing_price" in windows[29]["reasons"]


@pytest.mark.parametrize("source", ["own", "cimri"])
@pytest.mark.parametrize(
    "offset,reason", [(0, "history_missing_price"), (36, "future_missing_price")]
)
def test_null_prices_never_become_negative_labels(source, offset, reason):
    prices = [10000] * 37
    prices[offset] = None
    _, windows, _ = result_for(sample_snapshot(prices=prices), source)
    assert windows[29]["label"] is None and reason in windows[29]["reasons"]


def test_missing_cimri_date_is_detected_without_interpolation():
    snapshot = sample_snapshot()
    snapshot = snapshot.model_copy(
        update={
            "market_history": [
                row
                for row in snapshot.market_history
                if row.day != DAY + timedelta(days=32)
            ]
        }
    )
    summary, windows, _ = result_for(snapshot, "cimri")
    assert summary["missing_calendar_days"] == 1
    assert windows[29]["label"] is None
    assert "future_missing_day" in windows[29]["reasons"]


@pytest.mark.parametrize("planned", [True, False])
def test_empty_own_day_is_not_counted_as_observed(planned):
    snapshot = sample_snapshot()
    if planned:
        for hour in (10, 22):
            snapshot = change_check(
                snapshot, 36, hour, outcome=None, checked_at=None, current_price=None
            )
    else:
        snapshot = snapshot.model_copy(
            update={
                "collection_runs": [
                    row for row in snapshot.collection_runs if row.run_id < 73
                ],
                "listing_checks": [
                    row for row in snapshot.listing_checks if row.run_id < 73
                ],
            }
        )
    summary, windows, daily = result_for(snapshot)
    assert summary["calendar_days"] == 37
    assert summary["observed_days"] == 36
    assert summary["missing_calendar_days"] == 1
    assert windows[29]["label"] is None
    assert "future_missing_day" in windows[29]["reasons"]
    assert (
        next(
            row
            for row in daily
            if row["source"] == "own" and row["day"] == DAY + timedelta(days=36)
        )["observed"]
        is False
    )


@pytest.mark.parametrize(
    "kind", ["missing", "duplicate", "interrupted", "late", "error", "pending"]
)
def test_incomplete_scheduled_day_is_excluded(kind):
    snapshot = sample_snapshot()
    if kind == "missing":
        snapshot = snapshot.model_copy(
            update={
                "collection_runs": [
                    row for row in snapshot.collection_runs if row.run_id != 74
                ],
                "listing_checks": [
                    row for row in snapshot.listing_checks if row.run_id != 74
                ],
            }
        )
    elif kind == "duplicate":
        extra = snapshot.collection_runs[-1].model_copy(update={"run_id": 75})
        extra_check = snapshot.listing_checks[-1].model_copy(update={"run_id": 75})
        snapshot = snapshot.model_copy(
            update={
                "collection_runs": [*snapshot.collection_runs, extra],
                "listing_checks": [*snapshot.listing_checks, extra_check],
            }
        )
    elif kind == "interrupted":
        snapshot = change_run(snapshot, 74, status="interrupted")
    elif kind == "late":
        snapshot = change_run(
            snapshot,
            74,
            finished_at=snapshot.collection_runs[-1].finished_at + timedelta(hours=3),
        )
    else:
        snapshot = change_check(
            snapshot,
            36,
            22,
            outcome="error" if kind == "error" else None,
            current_price=None,
            **({"checked_at": None} if kind == "pending" else {}),
        )
    summary, windows, _ = result_for(snapshot)
    assert windows[29]["label"] is None
    assert "future_day_quality" in windows[29]["reasons"]
    assert summary["day_quality_counts"]


@pytest.mark.parametrize(
    "hour,day_offset,expected_hour",
    [(0, -1, 22), (9, -1, 22), (10, 0, 10), (21, 0, 10), (22, 0, 22), (23, 0, 22)],
)
def test_slot_uses_istanbul_and_preceding_schedule(hour, day_offset, expected_hour):
    local = datetime(2026, 1, 1, hour, tzinfo=audit.ISTANBUL)
    assert audit.scheduled_slot(local.astimezone(timezone.utc)) == (
        DAY + timedelta(days=day_offset),
        expected_hour,
    )


def test_scope_change_rejects_window_even_with_all_prices():
    snapshot = sample_snapshot()
    snapshot = snapshot.model_copy(
        update={
            "listings": [
                *snapshot.listings,
                snapshot.listings[0].model_copy(update={"listing_id": "b"}),
            ],
            "listing_checks": [
                row.model_copy(update={"listing_id": "b"}) if row.run_id >= 61 else row
                for row in snapshot.listing_checks
            ],
        }
    )
    summary, windows, _ = result_for(snapshot)
    assert summary["scope_changes"] == 1
    assert windows[29]["label"] is None and "scope_change" in windows[29]["reasons"]


def test_other_product_and_manual_run_do_not_change_valid_window():
    snapshot = sample_snapshot()
    product = snapshot.products[0].model_copy(
        update={"product_id": 2, "product_key": "other"}
    )
    listing = snapshot.listings[0].model_copy(
        update={"product_id": 2, "listing_id": "b"}
    )
    manual = snapshot.collection_runs[-1].model_copy(
        update={"run_id": 75, "trigger": "manual"}
    )
    own_check = snapshot.listing_checks[-1].model_copy(
        update={"run_id": 75, "current_price": 1}
    )
    other = own_check.model_copy(
        update={"run_id": 74, "product_id": 2, "listing_id": "b"}
    )
    snapshot = snapshot.model_copy(
        update={
            "products": [*snapshot.products, product],
            "listings": [*snapshot.listings, listing],
            "collection_runs": [*snapshot.collection_runs, manual],
            "listing_checks": [*snapshot.listing_checks, own_check, other],
        }
    )
    snapshot = change_run(snapshot, 74, planned_count=2)
    summary, windows, _ = result_for(snapshot)
    assert windows[29]["label"] == 0
    assert summary["runs_by_trigger"]["manual"] == 1


def test_cimri_identity_change_rejects_but_two_sources_stay_separate():
    snapshot = sample_snapshot()
    snapshot = snapshot.model_copy(
        update={
            "market_history": [
                (
                    row.model_copy(
                        update={"source_product_id": "99999", "price_kurus": 1}
                    )
                    if row.day == DAY + timedelta(days=36)
                    else row
                )
                for row in snapshot.market_history
            ]
        }
    )
    _, windows, _ = result_for(snapshot, "cimri")
    assert "source_identity_change" in windows[29]["reasons"]
    own, windows, _ = result_for(snapshot)
    assert own["windows"] == 1 and windows[29]["label"] == 0


def test_current_day_is_excluded_and_replay_does_not_use_wall_clock(monkeypatch):
    snapshot = sample_snapshot()
    snapshot = snapshot.model_copy(
        update={"captured_at": snapshot.captured_at - timedelta(hours=1)}
    )
    result, windows, _ = audit.analyze(snapshot)
    assert result["sources"]["own"]["windows"] == 0
    assert result["sources"]["cimri"]["windows"] == 0
    assert all(row["anchor_day"] <= DAY + timedelta(days=35) for row in windows)
    monkeypatch.setattr(audit, "now", lambda: datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert audit.analyze(snapshot)[0] == result


def test_conditional_wait_date_uses_current_valid_scope_and_stops_without_pages():
    snapshot = sample_snapshot(20)
    summary, _, _ = result_for(snapshot)
    assert summary["earliest_conditional_window_end"] == DAY + timedelta(days=36)
    assert summary["earliest_conditional_audit_day"] == DAY + timedelta(days=37)
    snapshot = snapshot.model_copy(
        update={
            "listings": [
                row.model_copy(update={"active": False}) for row in snapshot.listings
            ]
        }
    )
    summary, _, _ = result_for(snapshot)
    assert summary["earliest_conditional_window_end"] is None
    assert summary["no_active_tracking_pages"]


def test_empty_history_and_single_class_are_explicit():
    empty, _, _ = audit.analyze(sample_snapshot(0))
    assert "no_usable_windows" in empty["sources"]["own"]["split"]["limitations"]
    result, _, _ = audit.analyze(sample_snapshot(100))
    assert "single_class" in result["sources"]["own"]["split"]["limitations"]
    assert not result["model_trained"] and not result["production_prediction_enabled"]
    assert result["sources"]["cimri"]["training_permission"] == "unverified"


def test_wait_forecast_does_not_assume_old_scope_will_continue():
    snapshot = sample_snapshot(20)
    snapshot = snapshot.model_copy(
        update={
            "listings": [
                *snapshot.listings,
                snapshot.listings[0].model_copy(update={"listing_id": "new"}),
            ]
        }
    )
    summary, _, _ = result_for(snapshot)
    assert summary["earliest_conditional_window_end"] == DAY + timedelta(days=56)


def test_inactive_product_keeps_history_without_forecasting_collection():
    snapshot = sample_snapshot(20)
    snapshot = snapshot.model_copy(
        update={"products": [snapshot.products[0].model_copy(update={"active": False})]}
    )
    summary, _, _ = result_for(snapshot)
    assert summary["observed_days"] == 20
    assert summary["earliest_conditional_window_end"] is None
    assert not summary["no_active_tracking_pages"]
    assert not summary["collection_available"]


def test_random_series_matches_independent_complete_calendar_calculation():
    import random

    randomizer = random.Random(5)
    prices = [
        (
            randomizer.choice([None, 9000, 9500, 10000, 11000])
            if day % 41 == 0
            else randomizer.choice([9000, 9500, 10000, 11000])
        )
        for day in range(150)
    ]
    snapshot = sample_snapshot(150, prices=prices)
    for source in ("own", "cimri"):
        _, windows, _ = result_for(snapshot, source)
        for offset, row in enumerate(windows):
            complete = offset >= 29 and offset + 7 < len(prices)
            period = prices[max(0, offset - 29) : offset + 8]
            complete = complete and all(value is not None for value in period)
            expected = (
                int(min(prices[offset + 1 : offset + 8]) * 100 <= prices[offset] * 95)
                if complete
                else None
            )
            assert row["label"] == expected


def test_temporal_split_uses_global_dates_and_purges_target_overlap():
    rows = []
    for offset in range(100):
        for product_id in (1, 2):
            rows.append(
                dict(
                    product_id=product_id,
                    anchor_day=DAY + timedelta(days=offset),
                    target_end=DAY + timedelta(days=offset + 7),
                    label=offset % 2,
                    partition=None,
                )
            )
    result = audit.split_windows(rows)
    assert result["train"]["windows"] == 126
    assert result["validation"]["windows"] == 16
    assert result["test"]["windows"] == 30
    assert result["purged"]["windows"] == 28
    assert result["limitations"] == []
    for row in rows:
        siblings = {
            other["partition"]
            for other in rows
            if other["anchor_day"] == row["anchor_day"]
        }
        assert len(siblings) == 1
        if row["partition"] == "train":
            assert row["target_end"] < result["validation"]["first_anchor"]
        if row["partition"] == "validation":
            assert row["target_end"] < result["test"]["first_anchor"]


def test_nonoverlapping_windows_and_input_preservation():
    snapshot = sample_snapshot(100)
    before = snapshot.model_dump()
    summary, _, _ = result_for(snapshot)
    assert summary["windows"] == 64
    assert summary["nonoverlapping_37_day_windows"] == 2
    assert snapshot.model_dump() == before


def save_snapshot(path, snapshot):
    payload = snapshot.model_dump(mode="json")
    audit.write_json(
        path, dict(payload=payload, sha256=audit.reader.fingerprint(payload))
    )


def test_offline_cli_repeats_live_analysis_without_database(tmp_path, monkeypatch):
    snapshot = sample_snapshot()
    source = tmp_path / "source.json"
    save_snapshot(source, snapshot)

    def forbidden(*args, **kwargs):
        pytest.fail("Ağsız tekrar DB veya ortama erişti")

    monkeypatch.setattr(audit.reader, "configured_url", forbidden)
    monkeypatch.setattr(audit.psycopg, "connect", forbidden)
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output in outputs:
        assert audit.main(["--snapshot", str(source), "--output-dir", str(output)]) == 0
    assert (outputs[0] / "report.json").read_bytes() == (
        outputs[1] / "report.json"
    ).read_bytes()
    assert (outputs[0] / "windows.jsonl").read_bytes() == (
        outputs[1] / "windows.jsonl"
    ).read_bytes()
    assert audit.load_snapshot(outputs[0] / "snapshot.json") == snapshot
    manifest = json.loads((outputs[0] / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {
        "snapshot.json",
        "rules.json",
        "report.json",
        "source_check.json",
        "windows.jsonl",
        "daily.jsonl",
        "report.md",
    }
    assert all(
        audit.hashlib.sha256((outputs[0] / name).read_bytes()).hexdigest() == value
        for name, value in manifest.items()
    )


@pytest.mark.parametrize(
    "mutation",
    ["hash", "extra_field", "duplicate", "orphan", "invalid_price", "missing_hash"],
)
def test_offline_snapshot_rejects_corruption(tmp_path, mutation):
    snapshot = sample_snapshot()
    payload = snapshot.model_dump(mode="json")
    if mutation == "extra_field":
        payload["collection_runs"][0]["note"] = "private-note"
    elif mutation == "duplicate":
        payload["market_history"].append(copy.deepcopy(payload["market_history"][0]))
    elif mutation == "orphan":
        payload["listing_checks"][0]["product_id"] = 999
    elif mutation == "invalid_price":
        payload["listing_checks"][0]["current_price"] = None
    elif mutation == "missing_hash":
        del payload["source_sha256"]["products"]
    source = tmp_path / "source.json"
    audit.write_json(
        source,
        dict(
            payload=payload,
            sha256=(
                "0" * 64 if mutation == "hash" else audit.reader.fingerprint(payload)
            ),
        ),
    )
    output = tmp_path / "out"
    assert audit.main(["--snapshot", str(source), "--output-dir", str(output)]) == 1
    assert (
        json.loads((output / "report.json").read_text(encoding="utf-8"))["status"]
        == "failed"
    )


def test_cli_never_overwrites_existing_output(tmp_path):
    report = tmp_path / "report.json"
    report.write_text("koru", encoding="utf-8")
    assert audit.main(["--output-dir", str(tmp_path)]) == 1
    assert report.read_text(encoding="utf-8") == "koru"


@pytest.mark.parametrize(
    "url",
    [
        None,
        "invalid",
        "postgresql://fiyat_takip@localhost/fiyat_takip",
        "postgresql://fiyat_takip_api@localhost/unknown",
    ],
)
def test_cli_refuses_writer_or_missing_reader_without_connecting(
    tmp_path, monkeypatch, url
):
    monkeypatch.setenv("DATABASE_URL", "private-writer")
    if url is not None:
        monkeypatch.setenv("API_DATABASE_URL", url)
    monkeypatch.setattr(
        audit.psycopg,
        "connect",
        lambda *a, **kw: pytest.fail("Yanlış hesapla bağlandı"),
    )
    assert audit.main(["--output-dir", str(tmp_path / "out")]) == 1


def test_actual_reader_snapshot_is_read_only_and_sanitized(world, api_db):
    add_run(world, START, {"a": ("offer", 10001), "b": "error"})
    add_market(world, START.date(), None)
    _, data = audit.reader.read_dataset(api_db)
    snapshot = audit.make_snapshot(data, datetime.now(timezone.utc))
    text = snapshot.model_dump_json()
    assert "error_message" not in text and '"note"' not in text
    assert '"seller_name"' not in text and "postgresql://" not in text
    with pytest.raises(audit.reader.CheckError, match="Okuma hesabı"):
        audit.reader.read_dataset(world)


def test_cli_real_test_database_preserves_all_objects(
    world, api_db, tmp_path, monkeypatch
):
    add_run(world, START, {"a": ("offer", 10001), "b": "sold_out"})
    add_market(world, START.date(), 10000)
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    output = tmp_path / "out"
    assert audit.main(["--output-dir", str(output)]) == 0
    result = json.loads((output / "report.json").read_text(encoding="utf-8"))
    proof = json.loads((output / "source_check.json").read_text(encoding="utf-8"))
    assert proof["before"] == proof["after"] and len(proof["before"]) == 8
    assert len(result["products"]) == 3
    assert result["sources"]["own"]["windows"] == 0


def test_source_change_is_inconclusive_including_offline_replay(
    world, api_db, tmp_path, monkeypatch
):
    add_run(world, START, {"a": ("offer", 10001)})
    original = audit.analyze

    def change_source(snapshot):
        result = original(snapshot)
        world.execute("UPDATE listings SET color='Mavi' WHERE listing_id='a'")
        return result

    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    monkeypatch.setattr(audit, "analyze", change_source)
    output = tmp_path / "out"
    assert audit.main(["--output-dir", str(output)]) == 2
    proof = json.loads((output / "source_check.json").read_text(encoding="utf-8"))
    assert proof["changed_relations"] == ["listings"]
    monkeypatch.setattr(audit, "analyze", original)
    assert (
        audit.main(
            [
                "--snapshot",
                str(output / "snapshot.json"),
                "--output-dir",
                str(tmp_path / "replay"),
            ]
        )
        == 2
    )


def test_running_collection_prevents_audit(world, api_db, tmp_path, monkeypatch):
    add_run(world, START, {"a": "planned"}, status="running")
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    output = tmp_path / "out"
    assert audit.main(["--output-dir", str(output)]) == 1
    assert not (output / "snapshot.json").exists()


@pytest.mark.parametrize(
    "failure,code,error",
    [
        (KeyboardInterrupt(), 130, "interrupted"),
        (psycopg.OperationalError("private password"), 1, "database_error"),
        (RuntimeError("private password"), 1, "check_error"),
    ],
)
def test_failure_is_safe_and_closes_connection(
    tmp_path, monkeypatch, capsys, failure, code, error
):
    events = []

    class Connection:
        def __enter__(self):
            events.append("opened")
            return self

        def __exit__(self, *args):
            events.append("closed")

    monkeypatch.setattr(audit.reader, "configured_url", lambda: "unused")
    monkeypatch.setattr(audit.psycopg, "connect", lambda *a, **kw: Connection())

    def fail(*args):
        raise failure

    monkeypatch.setattr(audit.reader, "read_dataset", fail)
    output = tmp_path / "out"
    assert audit.main(["--output-dir", str(output)]) == code
    report = (output / "report.json").read_text(encoding="utf-8")
    assert json.loads(report)["error_code"] == error
    assert "private" not in report + capsys.readouterr().out
    assert events == ["opened", "closed"]
