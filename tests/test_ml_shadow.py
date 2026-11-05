"""Gölge mod tahmin kaydı: sızıntı, kural, değişmezlik ve bütünlük (yapay veri)."""

import json
import shutil
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.ml import final, shadow
from app.ml.dataset import read_snapshot
from app.ml.features import analyze_features
from app.ml.metrics import METRIC_RULES
from app.ml.models import design_matrix, predict_frozen
from app.ml.reporting import json_bytes
from app.ml.shadow import (
    FAMILY_REASON,
    HISTORY_REASON,
    MISSING_REASON,
    ShadowConfig,
    ShadowEvidence,
    build_shadow_predictions,
    read_shadow_outputs,
    recorded_keys,
    write_shadow_outputs,
)
from tests.support.ml import (
    label_snapshot,
    label_tables,
    remove_label_run,
    walk_prices,
    write_model_evidence,
)

FIRST_DAY = date(2026, 1, 1)
START_DAY = date(2026, 1, 20)
NO_DIGEST = "0" * 64


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    # Yalnız tekrar sayısı düşer; gerçek sayı ve yöntem tests/test_ml_metrics.py'de.
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    return write_model_evidence(tmp_path_factory.mktemp("evidence"))


def make_config(evidence, records, sha=None):
    return ShadowConfig(
        start_day=START_DAY,
        model_manifest_sha256=sha or evidence["model_sha256"],
        evidence=ShadowEvidence(
            labels=str(evidence["labels"]),
            features=str(evidence["features"]),
            split=str(evidence["split"]),
            model=str(evidence["model"]),
        ),
        records_dir=str(records),
    )


@pytest.fixture(scope="module")
def model(evidence, tmp_path_factory):
    return shadow.load_model(make_config(evidence, tmp_path_factory.mktemp("kayit")))


@pytest.fixture(scope="module")
def source(evidence):
    return read_snapshot(evidence["source"])


@pytest.fixture(scope="module")
def result(source, model):
    snapshot, digest = source
    return build_shadow_predictions(snapshot, digest, model, START_DAY, set())


def build(snapshot, model, recorded=frozenset()):
    return build_shadow_predictions(snapshot, NO_DIGEST, model, START_DAY, recorded)


def offset(row):
    return (date.fromisoformat(row["anchor_day"]) - FIRST_DAY).days


def written(tmp_path, result, model, name="tahmin_01"):
    directory = tmp_path / "kayit" / name
    write_shadow_outputs(directory, result, model, START_DAY)
    return directory


def retamper(directory, rows=None, **manifest_changes):
    """Satırları ve manifest alanlarını değiştirir; parmak izlerini yeniler."""
    import hashlib

    manifest = json.loads((directory / "manifest.json").read_bytes())
    if rows is not None:
        content = b"".join(json_bytes(row) + b"\n" for row in rows)
        (directory / "predictions.jsonl").write_bytes(content)
        manifest["files"]["predictions.jsonl"] = hashlib.sha256(content).hexdigest()
    manifest.update(manifest_changes)
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def test_rows_are_the_own_feature_rows_from_the_start_day(source, result):
    snapshot, _ = source
    expected = [
        row
        for row in analyze_features(snapshot)[1]
        if row.metadata.source == "own" and row.metadata.anchor_day >= START_DAY
    ]
    assert [
        (row["product_id"], row["anchor_day"], row["features"]) for row in result.rows
    ] == [
        (
            row.metadata.product_id,
            row.metadata.anchor_day.isoformat(),
            row.features.model_dump(mode="json"),
        )
        for row in expected
    ]
    assert result.rows and all(row["source"] == "own" for row in result.rows)
    assert all(row["anchor_at"].endswith("Z") for row in result.rows)


def test_probabilities_are_the_frozen_models_for_rows_with_enough_history(
    source, model, result
):
    snapshot, _ = source
    rows = [row for row in result.rows if row["probabilities"] is not None]
    features = {
        row.metadata.anchor_day.isoformat(): row.features
        for row in analyze_features(snapshot)[1]
        if row.metadata.source == "own"
    }
    predicted = predict_frozen(
        model.loaded.frozen,
        design_matrix([features[row["anchor_day"]] for row in rows]),
    )
    assert set(rows[0]["probabilities"]) == {"r0", model.loaded.frozen.choice}
    for name, values in predicted.items():
        assert [row["probabilities"][name] for row in rows] == pytest.approx(
            list(values), rel=1e-12
        )
        assert all(0 < row["probabilities"][name] < 1 for row in rows)


def test_rows_with_less_than_thirty_days_of_history_get_no_probability(result):
    short = [row for row in result.rows if row["features"]["history_days"] < 30]
    enough = [row for row in result.rows if row["features"]["history_days"] >= 30]
    assert len(short) == 10 and enough
    for row in short:
        assert row["probabilities"] is None
        assert HISTORY_REASON in row["reasons"] and row["showable"] is False
    for row in enough:
        assert row["probabilities"] is not None
        assert HISTORY_REASON not in row["reasons"]
    assert min(row["features"]["history_days"] for row in enough) == 30


def test_future_data_never_changes_an_earlier_prediction(source, model, result):
    prices = walk_prices(365)
    altered = prices[:300] + [price // 2 for price in prices[300:]]
    variant = build(label_snapshot(prices=altered), model)
    before = [row for row in result.rows if offset(row) < 300]
    assert before and before == [row for row in variant.rows if offset(row) < 300]
    # Olumlu kontrol: fiyatı yarıya inen ilk gün (300) gerçekten başka girdi üretir;
    # sonraki günlerde pencerenin tamamı yarılanınca oranlar benzer kalabilir.
    after = {offset(row): row for row in result.rows if offset(row) >= 300}
    changed = {offset(row): row for row in variant.rows if offset(row) >= 300}
    assert after[300]["features"]["log_return_1d"] != (
        changed[300]["features"]["log_return_1d"]
    )
    assert after[300]["probabilities"] != changed[300]["probabilities"]


def test_recent_missing_days_make_a_row_not_showable_at_the_exact_threshold(model):
    tables = label_tables(prices=walk_prices(365))
    for day in range(100, 106):
        remove_label_run(tables, 2 * day + 2)
    rows = {offset(row): row for row in build(label_snapshot(tables), model).rows}
    assert not any(day in rows for day in range(100, 106))
    flagged = {day for day, row in rows.items() if MISSING_REASON in row["reasons"]}
    assert flagged == set(range(106, 115))
    assert rows[106]["missing_days_14"] == 6
    assert rows[114]["missing_days_14"] == 5
    assert rows[115]["missing_days_14"] == 4 and rows[115]["showable"] is True
    assert rows[110]["probabilities"] is not None and rows[110]["showable"] is False


def test_family_missing_from_training_is_flagged_but_still_predicted(
    source, model, result
):
    snapshot, _ = source
    unseen = build(snapshot, replace(model, training_families=frozenset()))
    assert all(FAMILY_REASON in row["reasons"] for row in unseen.rows)
    assert all(not row["showable"] for row in unseen.rows)
    assert [row["probabilities"] for row in unseen.rows] == [
        row["probabilities"] for row in result.rows
    ]
    assert not any(FAMILY_REASON in row["reasons"] for row in result.rows)
    assert any(row["showable"] for row in result.rows)


def test_recorded_after_days_counts_from_the_snapshot_day(source, result):
    snapshot, _ = source
    captured = date(2027, 1, 1)
    assert snapshot.captured_at.date() == captured
    assert all(
        row["recorded_after_days"]
        == (captured - date.fromisoformat(row["anchor_day"])).days
        for row in result.rows
    )
    last = result.rows[-1]
    assert last["anchor_day"] == "2026-12-31" and last["recorded_after_days"] == 1


def test_written_records_read_back_and_summarise_the_rows(tmp_path, model, result):
    directory = written(tmp_path, result, model)
    manifest, rows = read_shadow_outputs(directory)
    assert rows == json.loads(json.dumps(result.rows))
    summary = manifest["summary"]
    assert summary["rows"] == len(rows)
    assert summary["predicted"] == sum(row["probabilities"] is not None for row in rows)
    assert summary["on_time"] == 1 and summary["late"] == len(rows) - 1
    assert summary["reasons"] == {HISTORY_REASON: 10}
    assert manifest["model_manifest_sha256"] == model.loaded.manifest_sha256
    assert manifest["last_closed_day"] == "2026-12-31"
    assert "Bu olasılıklar ekranda gösterilmez" in (directory / "report.md").read_text(
        encoding="utf-8"
    )


def test_same_inputs_write_byte_identical_records(tmp_path, source, model, result):
    first = written(tmp_path, result, model, "tahmin_01")
    snapshot, digest = source
    again = build_shadow_predictions(snapshot, digest, model, START_DAY, set())
    second = written(tmp_path, again, model, "tahmin_02")
    for name in ("predictions.jsonl", "report.md", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_a_recorded_day_is_never_predicted_again(tmp_path, source, model, result):
    early = build(label_snapshot(prices=walk_prices(365)[:340]), model)
    assert early.rows and early.rows[-1]["anchor_day"] == "2026-12-06"
    written(tmp_path, early, model, "tahmin_01")
    recorded = recorded_keys(tmp_path / "kayit", model.loaded.manifest_sha256)
    assert recorded == {
        (row["product_id"], date.fromisoformat(row["anchor_day"])) for row in early.rows
    }
    snapshot, digest = source
    later = build_shadow_predictions(snapshot, digest, model, START_DAY, recorded)
    assert later.skipped_recorded == len(early.rows)
    assert [row["anchor_day"] for row in later.rows][0] == "2026-12-07"
    assert len(later.rows) + len(early.rows) == len(result.rows)
    # Aynı gün sonraki çalışmada hâlâ aynı: yeni görüntüde kayıtlı gün yoktur.
    nothing = build_shadow_predictions(
        snapshot,
        digest,
        model,
        START_DAY,
        recorded
        | {
            (row["product_id"], date.fromisoformat(row["anchor_day"]))
            for row in later.rows
        },
    )
    assert nothing.rows == [] and nothing.skipped_recorded == len(result.rows)


def test_a_folder_without_a_manifest_is_not_a_record(tmp_path, model, result):
    directory = written(tmp_path, result, model)
    half = tmp_path / "kayit" / "tahmin_02"
    shutil.copytree(directory, half)
    (half / "manifest.json").unlink()
    assert len(recorded_keys(tmp_path / "kayit", model.loaded.manifest_sha256)) == len(
        result.rows
    )
    assert recorded_keys(tmp_path / "yok", model.loaded.manifest_sha256) == set()


def test_a_damaged_foreign_or_duplicated_record_is_an_error_not_skipped(
    tmp_path, model, result
):
    directory = written(tmp_path, result, model)
    sha = model.loaded.manifest_sha256
    with pytest.raises(ValueError, match="başka bir modelle"):
        recorded_keys(tmp_path / "kayit", NO_DIGEST)
    shutil.copytree(directory, tmp_path / "kayit" / "tahmin_02")
    with pytest.raises(ValueError, match="iki kayıt klasöründe"):
        recorded_keys(tmp_path / "kayit", sha)
    shutil.rmtree(tmp_path / "kayit" / "tahmin_02")
    (directory / "predictions.jsonl").write_bytes(b"{}\n")
    with pytest.raises(ValueError, match="parmak izi"):
        recorded_keys(tmp_path / "kayit", sha)


def test_records_must_follow_the_row_contract_even_with_fresh_fingerprints(
    tmp_path, model, result
):
    directory = written(tmp_path, result, model)
    rows = json.loads(json.dumps(result.rows))
    with_probability = next(i for i, row in enumerate(rows) if row["probabilities"])
    short = next(i for i, row in enumerate(rows) if row["probabilities"] is None)
    choice = model.loaded.frozen.choice
    cases = [
        (
            "olasılıkları geçerli değil",
            lambda rs: rs[with_probability]["probabilities"].update(r0=1.5),
        ),
        (
            "olasılıkları geçerli değil",
            lambda rs: rs[short].update(probabilities={"r0": 0.1, choice: 0.1}),
        ),
        (
            "gerekçeleri tutarsız",
            lambda rs: rs[with_probability].update(showable=False),
        ),
        ("sıralı ve tekil", lambda rs: rs.reverse()),
        ("alanları sözleşmeye uymuyor", lambda rs: rs[0].update(extra=1)),
    ]
    for message, change in cases:
        broken = json.loads(json.dumps(rows))
        change(broken)
        retamper(directory, broken)
        with pytest.raises(ValueError, match=message):
            read_shadow_outputs(directory)
    retamper(directory, rows)
    read_shadow_outputs(directory)
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["summary"]["rows"] += 1
    retamper(directory, summary=manifest["summary"])
    with pytest.raises(ValueError, match="özeti satırlarla"):
        read_shadow_outputs(directory)


def test_a_changed_report_or_manifest_rule_is_rejected(tmp_path, model, result):
    directory = written(tmp_path, result, model)
    (directory / "report.md").write_bytes(b"degisti")
    with pytest.raises(ValueError, match="parmak izi tutmuyor: report.md"):
        read_shadow_outputs(directory)
    other = written(tmp_path, result, model, "tahmin_03")
    retamper(other, shadow_rules={"version": 2})
    with pytest.raises(ValueError, match="manifesti sözleşmeye uymuyor"):
        read_shadow_outputs(other)


def test_wrong_model_sha_never_opens_the_pickle(evidence, tmp_path, monkeypatch):
    def forbidden(data):
        pytest.fail("Denetimlerden önce pickle açıldı")

    monkeypatch.setattr(final.pickle, "loads", forbidden)
    with pytest.raises(ValueError, match="SHA-256"):
        shadow.load_model(make_config(evidence, tmp_path, sha="1" * 64))


def test_official_records_are_only_those_under_the_records_folder(tmp_path):
    records = tmp_path / "kayit"
    assert shadow.is_official(records / "tahmin_01", records)
    assert not shadow.is_official(tmp_path / "deneme" / "tahmin_01", records)
    assert not shadow.is_official(records, records)
    assert not shadow.is_official(records / "deneme", records)
    assert not shadow.is_official(records / "alt" / "tahmin_01", records)


def test_the_committed_config_is_valid_and_names_the_preregistered_model():
    config = shadow.load_config()
    assert config.start_day == date(2026, 10, 27)
    assert config.model_manifest_sha256 == (
        "89c819ed7c9f5eaf0dcc11c8f403a4439f53cfad2527d973646b71474fba4cf2"
    )
    assert (
        shadow.resolve_path(config.records_dir) == Path(shadow.ROOT) / "data/ml/golge"
    )
    for text in config.evidence.model_dump().values():
        assert text.startswith("data/ml/golge/kanitlar/")
    with pytest.raises(ValueError):
        ShadowConfig.model_validate_json(b'{"start_day": "2026-10-27"}')
