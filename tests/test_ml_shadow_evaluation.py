"""Gölge değerlendirmesi: gerçek etiket, girdi eşleşmesi, kapı ve dosya kanıtı."""

import copy
import hashlib
import json
import shutil
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from filelock import Timeout

from app.ml import final, shadow, shadow_evaluation as evaluation
from app.ml.dataset import read_snapshot
from app.ml.metrics import METRIC_RULES, Probability, Target, score_predictions
from app.ml.reporting import json_bytes
from tests.support.ml import (
    label_snapshot,
    label_tables,
    remove_label_run,
    walk_prices,
    write_evaluation_evidence,
    write_shadow_config,
)


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    return write_evaluation_evidence(tmp_path_factory.mktemp("evaluation"))


@pytest.fixture(scope="module")
def model(evidence):
    return evaluation.load_evaluation_model(shadow.load_config(evidence["config"]))


@pytest.fixture
def case(evidence, model, tmp_path):
    folder = tmp_path / "records" / "tahmin_01"
    shutil.copytree(evidence["record"], folder)
    path = write_shadow_config(tmp_path / "config.json", evidence, folder.parent)
    config = shadow.load_config(path)
    snapshot, digest = read_snapshot(evidence["source"])
    origins, records, incomplete = evaluation.read_inventory(
        config, snapshot.captured_at
    )
    return SimpleNamespace(
        snapshot=snapshot,
        digest=digest,
        config=config,
        model=model,
        origins=origins,
        records=records,
        incomplete=incomplete,
        folder=folder,
        path=path,
    )


def build(case, snapshot=None, records=None):
    return evaluation.build_evaluation(
        snapshot or case.snapshot,
        case.digest,
        case.config,
        case.model,
        case.origins,
        case.records if records is None else records,
        case.incomplete,
    )


def rewrite_record(folder, rows=None, **updates):
    manifest = json.loads((folder / "manifest.json").read_bytes())
    if rows is not None:
        data = b"".join(json_bytes(row) + b"\n" for row in rows)
        (folder / "predictions.jsonl").write_bytes(data)
        manifest["files"]["predictions.jsonl"] = hashlib.sha256(data).hexdigest()
    manifest.update(updates)
    (folder / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def test_labels_are_not_zero_filled_and_main_population_is_exact(case):
    result = build(case)
    primary = [row for row in result.rows if evaluation._eligible(row, "primary")]
    assert primary and any(row["primary"]["label"] is None for row in result.rows)
    assert result.report["summary"]["groups"]["main"] == sum(
        row["showable"] for row in primary
    )
    short = [row for row in result.rows if row["features"]["history_days"] < 30]
    boundary = [row for row in result.rows if row["features"]["history_days"] == 30]
    assert short and boundary
    assert all(row["probabilities"] is None for row in short)
    assert all(row["probabilities"] is not None for row in boundary)
    assert all(not evaluation._eligible(row, "primary") for row in short)
    assert (
        result.report["model_trained"]
        is result.report["predictions_generated"]
        is False
    )
    assert result.report["opens_display"] is False


def test_stored_probabilities_not_new_predictions_determine_hand_calculated_score(case):
    for row in case.records:
        if row["probabilities"] is not None:
            row["probabilities"][case.model.choice] = 0.25
    result = build(case)
    main = [
        row
        for row in result.rows
        if row["showable"] and evaluation._eligible(row, "primary")
    ]
    expected = sum((0.25 - row["primary"]["label"]) ** 2 for row in main) / len(main)
    assert result.report["scores"]["main"][case.model.choice]["brier"] == pytest.approx(
        expected
    )


def test_future_changes_only_labels_and_past_changes_are_rejected(case):
    first = date(2026, 1, 1)
    records = [
        row
        for row in case.records
        if date.fromisoformat(row["anchor_day"]) < first + timedelta(days=300)
    ]
    before = build(case, records=records)
    prices = walk_prices(365)
    changed = label_snapshot(
        prices=prices[:300] + [price // 2 for price in prices[300:]]
    )
    after = build(case, snapshot=changed, records=records)
    assert [row["features"] for row in before.rows] == [
        row["features"] for row in after.rows
    ]
    assert any(
        a["primary"]["label"] != b["primary"]["label"]
        for a, b in zip(before.rows, after.rows)
    )
    prices[295] //= 2
    with pytest.raises(ValueError, match="girdileri"):
        build(case, snapshot=label_snapshot(prices=prices), records=records)


def test_new_future_listing_changes_tracked_label_but_not_primary_gate(case):
    first = date(2026, 1, 1)
    records = [
        row
        for row in case.records
        if date.fromisoformat(row["anchor_day"]) < first + timedelta(days=300)
    ]
    before = build(case, records=records)
    tables = label_tables(prices=walk_prices(365))
    tables["listings"].append(dict(tables["listings"][0], listing_id="extra"))
    for run in tables["collection_runs"]:
        if run["run_id"] >= 601:
            run["planned_count"] += 1
    for row in list(tables["listing_checks"]):
        if row["run_id"] >= 601:
            tables["listing_checks"].append(
                dict(row, listing_id="extra", current_price=1000)
            )
    after = build(case, snapshot=label_snapshot(tables), records=records)
    assert [row["primary"] for row in before.rows] == [
        row["primary"] for row in after.rows
    ]
    assert after.report["summary"]["paired_label_differences"] > 0
    assert before.report["gate"] == after.report["gate"]


@pytest.mark.parametrize(
    "field", ["features", "missing_days_14", "recorded_after_days", "r0"]
)
def test_rehashed_but_factually_wrong_record_is_rejected(case, field):
    _, rows = shadow.read_shadow_outputs(case.folder)
    row = rows[20]
    if field == "features":
        row["features"]["log_return_1d"] += 0.01
    elif field == "r0":
        row["probabilities"]["r0"] += 0.01
    else:
        row[field] += 1
    rewrite_record(case.folder, rows)
    origins, records, incomplete = evaluation.read_inventory(
        case.config, case.snapshot.captured_at
    )
    with pytest.raises(ValueError, match="girdi|yeterlilik|R0"):
        evaluation.build_evaluation(
            case.snapshot,
            case.digest,
            case.config,
            case.model,
            origins,
            records,
            incomplete,
        )


@pytest.mark.parametrize(
    "failure", ["foreign_model", "duplicate", "old_snapshot", "start_day"]
)
def test_inventory_rejects_foreign_duplicate_stale_or_incompatible_records(
    case, failure
):
    captured = case.snapshot.captured_at
    if failure == "foreign_model":
        rewrite_record(case.folder, model_manifest_sha256="f" * 64)
    elif failure == "duplicate":
        shutil.copytree(case.folder, case.folder.parent / "tahmin_02")
    elif failure == "start_day":
        rewrite_record(case.folder, start_day="2026-01-21")
    else:
        captured -= timedelta(seconds=1)
    with pytest.raises(ValueError):
        evaluation.read_inventory(case.config, captured)


def test_inventory_lock_is_short_and_incomplete_folders_are_reported(case, monkeypatch):
    (case.folder.parent / "tahmin_yarim").mkdir()
    _, _, incomplete = evaluation.read_inventory(case.config, case.snapshot.captured_at)
    assert incomplete == ["tahmin_yarim"]
    original = evaluation._score_rows

    def unlocked(*args):
        with shadow.record_lock(case.folder.parent):
            return original(*args)

    monkeypatch.setattr(evaluation, "_score_rows", unlocked)
    assert build(case).rows
    with shadow.record_lock(case.folder.parent), pytest.raises(Timeout):
        evaluation.read_inventory(case.config, case.snapshot.captured_at)


def test_missing_records_and_missing_start_price_are_different(case):
    result = build(case, records=case.records[:-1])
    assert len(result.report["health"]["missing_records"]) == 1
    assert result.report["health"]["per_day"][-1]["missing_records"] == 1
    assert result.report["health"]["per_day"][-1]["no_start_price"] == 0
    assert result.report["health"]["timing"]["initial_backfill"] > 0


def test_no_records_gives_an_explicit_insufficient_report(case):
    result = build(case, records=[])
    assert result.report["gate"]["status"] == "not_evaluable"
    assert result.report["scores"]["main"][case.model.choice]["brier"] is None
    assert result.report["health"]["missing_records"]


def test_no_pickle_training_or_prediction_is_used(case, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Değerlendirme model açmaya/tahmin üretmeye çalıştı")

    monkeypatch.setattr(final.pickle, "loads", forbidden)
    monkeypatch.setattr(shadow, "load_model", forbidden)
    monkeypatch.setattr(shadow, "predict_frozen", forbidden)
    assert evaluation.evaluate_snapshot(case.snapshot, case.digest, case.config).rows


def test_output_roundtrip_is_deterministic_and_records_are_unchanged(case, tmp_path):
    before = {p.name: p.read_bytes() for p in case.folder.iterdir()}
    result = build(case)
    for name in ("a", "b"):
        target = tmp_path / name
        evaluation.write_outputs(target, result)
        report, rows = evaluation.read_outputs(target)
        assert report == result.report and rows == result.rows
    assert {p.name: p.read_bytes() for p in (tmp_path / "a").iterdir()} == {
        p.name: p.read_bytes() for p in (tmp_path / "b").iterdir()
    }
    assert before == {p.name: p.read_bytes() for p in case.folder.iterdir()}
    with pytest.raises(FileExistsError):
        evaluation.write_outputs(tmp_path / "a", result)


@pytest.mark.parametrize("failure", ["file", "summary", "gate", "role"])
def test_output_verifier_detects_corruption_even_when_rehashed(case, tmp_path, failure):
    target = tmp_path / "out"
    evaluation.write_outputs(target, build(case))
    name = "evaluations.jsonl" if failure == "role" else "report.json"
    if failure == "file":
        (target / name).write_bytes(b"{}")
    elif failure == "role":
        rows = [json.loads(line) for line in (target / name).read_bytes().splitlines()]
        rows[0]["role"] = "test_reserved"
        (target / name).write_bytes(b"".join(json_bytes(row) + b"\n" for row in rows))
    else:
        report = json.loads((target / name).read_bytes())
        if failure == "summary":
            report["summary"]["rows"] += 1
        else:
            report["gate"]["status"] = "invalid"
        (target / name).write_bytes(json_bytes(report))
    if failure != "file":
        manifest = json.loads((target / "manifest.json").read_bytes())
        manifest["files"][name] = hashlib.sha256(
            (target / name).read_bytes()
        ).hexdigest()
        (target / "manifest.json").write_bytes(json_bytes(manifest))
    with pytest.raises(ValueError):
        evaluation.read_outputs(target)


def gate_data(days=range(60), probabilities=None):
    first = date(2026, 10, 15)
    targets = [
        Target(
            product_id=2 * day + label + 1,
            source="own",
            anchor_day=first + timedelta(days=day),
            label=label,
            role="own_evaluation",
            brand="Apple",
            family="Apple iPhone 15",
        )
        for day in days
        for label in (0, 1)
    ]
    values = probabilities or [0.9 if row.label else 0.1 for row in targets]

    def vector(values):
        return [
            Probability(
                product_id=row.product_id,
                source="own",
                anchor_day=row.anchor_day,
                probability=float(value),
            )
            for row, value in zip(targets, values)
        ]

    score = score_predictions(
        targets, vector(values), vector([0.5] * len(targets)), role="own_evaluation"
    )
    return targets, score


def test_gate_succeeds_with_sufficient_data_and_readiness_precedes_performance():
    targets, score = gate_data()
    assert evaluation.evaluate_gate(targets, score)["status"] == "met"
    score["brier_skill"] = -0.1
    assert evaluation.evaluate_gate(targets, score)["status"] == "not_met"
    short, short_score = gate_data(range(59))
    short_score["brier_skill"] = -0.1
    assert evaluation.evaluate_gate(short, short_score)["status"] == "not_evaluable"


@pytest.mark.parametrize("count,passed", [(13, False), (14, True)])
def test_outside_november_counts_distinct_labelled_days_not_span(count, passed):
    # Sınır günleri aynı kalır; aradaki etiketli dış günlerin sayısı değişir.
    outside = [0, 59] + list(range(1, count - 1))
    days = sorted(set(outside + list(range(17, 47))))
    targets, score = gate_data(days)
    gate = evaluation.evaluate_gate(targets, score)
    condition = next(
        item for item in gate["readiness"] if item["name"] == "outside_november_days"
    )
    assert condition["value"] == count and condition["passed"] is passed
    assert gate["readiness"][0]["value"] == 60


@pytest.mark.parametrize("clusters,passed", [(29, False), (30, True)])
def test_gate_cluster_support_boundary(clusters, passed):
    targets, score = gate_data()
    score["positive_window_clusters"] = clusters
    condition = evaluation.evaluate_gate(targets, score)["readiness"][-1]
    assert condition["passed"] is passed


@pytest.mark.parametrize("gap,passed", [(0.05, True), (0.050001, False)])
def test_gate_mean_gap_boundary(gap, passed):
    targets, score = gate_data(probabilities=[p + gap for p in ([0.1, 0.9] * 60)])
    condition = evaluation.evaluate_gate(targets, score)["performance"][1]
    assert condition["passed"] is passed


@pytest.mark.parametrize("gap,passed", [(0.15, True), (0.150001, False)])
def test_gate_bin_gap_boundary(gap, passed):
    targets, score = gate_data(probabilities=[gap, 1 - gap] * 60)
    condition = evaluation.evaluate_gate(targets, score)["performance"][2]
    assert condition["passed"] is passed


@pytest.mark.parametrize("count,status", [(19, "met"), (20, "not_met")])
def test_small_bin_does_not_become_a_supported_bin_until_twenty(count, status):
    zero_seen = 0
    values = []
    for label in [0, 1] * 60:
        if label:
            values.append(0.9)
        else:
            values.append(0.2 if zero_seen < count else 0.05)
            zero_seen += 1
    targets, score = gate_data(probabilities=values)
    assert evaluation.evaluate_gate(targets, score)["status"] == status


def test_undefined_performance_is_distinct_from_measured_failure():
    targets, score = gate_data()
    for item in score["calibration"]:
        item["low_support"] = True
    assert evaluation.evaluate_gate(targets, score)["status"] == "not_evaluable"
    score["brier_skill"] = 0.0
    assert evaluation.evaluate_gate(targets, score)["status"] == "not_met"


def test_information_slices_and_tracked_metrics_do_not_change_gate(case):
    result = build(case)
    report = copy.deepcopy(result.report)
    report["information_slices"] = {}
    report["scores"]["tracked_all"] = {}
    targets, _, _ = evaluation._vectors(
        evaluation._selections(result.rows)["main"][0], "primary", case.model.choice
    )
    assert report["gate"] == evaluation._json(
        evaluation.evaluate_gate(targets, report["scores"]["main"][case.model.choice])
    )


def test_valid_probability_with_recent_missing_days_is_only_in_secondary(case):
    tables = label_tables(prices=walk_prices(365))
    for day in range(100, 106):
        remove_label_run(tables, 2 * day + 2)
    snapshot = label_snapshot(tables)
    frozen = shadow.load_model(case.config)
    predicted = shadow.build_shadow_predictions(
        snapshot, case.digest, frozen, case.config.start_day, set()
    )
    recorded_at = snapshot.captured_at.isoformat().replace("+00:00", "Z")
    records = [
        dict(row, record_folder="tahmin_01", recorded_at=recorded_at)
        for row in predicted.rows
    ]
    result = build(case, snapshot=snapshot, records=records)
    summary = result.report["summary"]["groups"]
    assert summary["all_eligible"] > summary["main"]
    flagged = [
        row
        for row in result.rows
        if shadow.MISSING_REASON in row["reasons"]
        and evaluation._eligible(row, "primary")
    ]
    assert flagged and all(not row["showable"] for row in flagged)
    assert (
        sum(item["no_start_price"] for item in result.report["health"]["per_day"]) == 6
    )


def test_single_class_primary_keeps_brier_and_reports_undefined_ap(case):
    complete = build(case)
    zero_keys = {
        (row["product_id"], row["anchor_day"])
        for row in complete.rows
        if row["primary"]["label"] == 0
    }
    records = [
        row
        for row in case.records
        if (row["product_id"], row["anchor_day"]) in zero_keys
    ]
    result = build(case, records=records)
    score = result.report["scores"]["main"][case.model.choice]
    assert score["rows"] > 0 and score["brier"] is not None
    assert score["average_precision"] is None and "single_class" in score["reasons"]
    assert result.report["gate"]["status"] == "not_evaluable"


@pytest.mark.parametrize("offset,matches", [(3, False), (4, True), (5, False)])
def test_final_snapshot_date_is_fixed_and_never_opens_display(case, offset, matches):
    snapshot = case.snapshot.model_copy(
        update={"captured_at": case.snapshot.captured_at + timedelta(days=offset)}
    )
    result = build(case, snapshot=snapshot)
    assert result.report["final_date_matches"] is matches
    assert result.report["opens_display"] is False


@pytest.mark.parametrize(
    "field,value", [("last_closed_day", "2026-12-30"), ("snapshot_sha256", "bozuk")]
)
def test_incoherent_record_snapshot_header_is_rejected(case, field, value):
    rewrite_record(case.folder, **{field: value})
    with pytest.raises(ValueError, match="başlık bilgisi"):
        evaluation.read_inventory(case.config, case.snapshot.captured_at)


def test_november_coverage_has_fixed_year():
    targets, score = gate_data()
    later = [
        row.model_copy(update={"anchor_day": row.anchor_day + timedelta(days=365)})
        for row in targets
    ]
    gate = evaluation.evaluate_gate(later, score)
    assert gate["readiness"][1]["passed"] is False
    assert gate["status"] == "not_evaluable"
