"""Elle açılış: kesin tarih, gerçek kapı hesabı, model zinciri ve kapatma."""

import hashlib
import json
import pickle
from datetime import date, datetime, timedelta, timezone

import pytest
from filelock import FileLock

from app.ml import final, models, shadow_evaluation as evaluation
from app.ml import shadow_display as display, shadow_records as records
from app.ml.__main__ import main
from app.ml.dataset import write_snapshot
from app.ml.metrics import METRIC_RULES
from app.ml.reporting import json_bytes
from tests.support.ml import (
    feature_values,
    label_snapshot,
    write_model_evidence,
    write_shadow_config,
)
from tests.support.shadow_display import NOW, seal_files, write_json


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    root = tmp_path_factory.mktemp("display_model")
    result = write_model_evidence(root)
    yield result
    patch.undo()


@pytest.fixture
def case(tmp_path, evidence):
    root = tmp_path / "records"
    snapshot = label_snapshot(count=369)
    digest = write_snapshot(snapshot, root / "goruntuler" / "veri_final")
    path = write_shadow_config(tmp_path / "shadow.json", evidence, root)
    config = records.load_config(path)
    model = evaluation.load_evaluation_model(config)
    result = evaluation.build_evaluation(snapshot, digest, config, model, [], [], [])
    report = result.report
    rows = []
    # Yapay 60 günlük puan gerçekten hesaplanır; kapı bayrağı taklit edilmez.
    for offset in range(60):
        day = date(2026, 10, 15) + timedelta(days=offset)
        for label in (0, 1):
            pid = 2 * offset + label + 1
            anchor = datetime.combine(day, datetime.min.time(), timezone.utc).replace(
                hour=19, minute=30
            )
            target = dict(label=label, reasons=[])
            rows.append(
                dict(
                    product_id=pid,
                    product_key=f"phone_{pid}",
                    source="own",
                    anchor_day=day.isoformat(),
                    anchor_at=anchor.isoformat(),
                    recorded_after_days=1,
                    features=feature_values(history_days=100).model_dump(mode="json"),
                    missing_days_14=0,
                    reasons=[],
                    showable=True,
                    probabilities={
                        "r0": model.reference_rate,
                        model.choice: 0.9 if label else 0.1,
                    },
                    role="own_evaluation",
                    record_folder=f"tahmin_{offset}",
                    recorded_at=(anchor + timedelta(hours=13)).isoformat(),
                    timing="on_time",
                    target_end=(day + timedelta(days=7)).isoformat(),
                    primary=target,
                    tracked=target,
                )
            )
    groups = evaluation._selections(rows)
    report["scores"] = {
        name: evaluation._score_rows(group, target, model.choice)
        for name, (group, target) in groups.items()
    }
    targets, _, _ = evaluation._vectors(rows, "primary", model.choice)
    report["summary"] = evaluation._summary(rows)
    report["gate"] = evaluation.evaluate_gate(
        targets, report["scores"]["main"][model.choice]
    )
    assert report["gate"]["status"] == "met"
    report = json.loads(json_bytes(report))
    folder = tmp_path / "evaluation"
    evaluation.write_outputs(folder, evaluation.EvaluationResult(report, rows))
    evaluation.read_outputs(folder)
    return dict(
        root=root, path=path, config=config, folder=folder, report=report, rows=rows
    )


def rewrite_report(case):
    folder, report = case["folder"], case["report"]
    write_json(folder / "report.json", report)
    (folder / "report.md").write_text(
        evaluation.markdown_report(report), encoding="utf-8"
    )
    manifest = json.loads((folder / "manifest.json").read_bytes())
    manifest["input"] = report["input"]
    seal_files(folder, manifest)


def invoke(case, monkeypatch, *args, now=NOW):
    monkeypatch.setattr(display, "utc_now", lambda: now)
    return main(["shadow-display", "--config", str(case["path"]), *args])


def test_success_binds_real_validated_report_and_model_without_pickle_or_prediction(
    case, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Gösterim onayında model açıldı veya tahmin üretildi")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    monkeypatch.setattr(final, "load_frozen_model", forbidden)
    monkeypatch.setattr(models, "predict_frozen", forbidden)
    before = {path: path.read_bytes() for path in case["folder"].iterdir()}
    assert invoke(case, monkeypatch, "--evaluation", str(case["folder"])) == 0
    path = case["root"] / display.APPROVAL_FILE
    approval = display.DisplayApproval.model_validate_json(path.read_bytes())
    assert approval.enabled
    assert approval.model_manifest_sha256 == case["config"].model_manifest_sha256
    assert (
        approval.evaluation_manifest_sha256
        == hashlib.sha256((case["folder"] / "manifest.json").read_bytes()).hexdigest()
    )
    assert approval.approved_at == NOW
    original = path.read_bytes()
    assert invoke(case, monkeypatch, "--evaluation", str(case["folder"])) == 0
    assert path.read_bytes() == original
    assert all(path.read_bytes() == content for path, content in before.items())


@pytest.mark.parametrize(
    "failure",
    [
        "early",
        "wrong_day",
        "not_met",
        "foreign_model",
        "hash",
        "source_missing",
        "false_gate",
        "model_changed",
        "forged_scores",
        "future_report",
    ],
)
def test_unsuitable_report_never_creates_approval(case, monkeypatch, failure):
    now = NOW
    if failure == "early":
        now = NOW - timedelta(days=1)
    elif failure == "future_report":
        now = NOW.replace(hour=0) - timedelta(minutes=1)
    elif failure == "hash":
        (case["folder"] / "report.md").write_bytes(b"bozuk")
    elif failure == "source_missing":
        (case["root"] / "goruntuler" / "veri_final" / "snapshot.json").unlink()
    elif failure == "model_changed":
        case["config"] = case["config"].model_copy(
            update=dict(model_manifest_sha256="b" * 64)
        )
        write_json(case["path"], case["config"].model_dump(mode="json"))
    else:
        if failure == "wrong_day":
            case["report"]["input"]["snapshot_captured_at"] = "2027-01-06T00:00:00Z"
        elif failure == "not_met":
            for row in case["rows"]:
                row["probabilities"][case["report"]["input"]["choice"]] = (
                    0.1 if row["primary"]["label"] else 0.9
                )
            choice = case["report"]["input"]["choice"]
            groups = evaluation._selections(case["rows"])
            case["report"]["scores"] = {
                name: evaluation._score_rows(group, target, choice)
                for name, (group, target) in groups.items()
            }
            targets, _, _ = evaluation._vectors(case["rows"], "primary", choice)
            case["report"]["gate"] = evaluation.evaluate_gate(
                targets, case["report"]["scores"]["main"][choice]
            )
            (case["folder"] / "evaluations.jsonl").write_bytes(
                b"".join(json_bytes(row) + b"\n" for row in case["rows"])
            )
            assert case["report"]["gate"]["status"] == "not_met"
        elif failure == "foreign_model":
            case["report"]["input"]["model_manifest_sha256"] = "c" * 64
        elif failure == "false_gate":
            case["report"]["gate"]["labelled_distinct_days"] = 999
        else:
            # Dosyalar yeniden hash'lense de kapı puanı kayıttan hesaplanmalıdır.
            case["report"]["scores"]["main"][case["report"]["input"]["choice"]][
                "brier"
            ] = 0.001
        rewrite_report(case)
    assert invoke(case, monkeypatch, "--evaluation", str(case["folder"]), now=now) == 1
    assert not (case["root"] / display.APPROVAL_FILE).exists()


def test_disable_reenable_same_report_and_reject_different_report(case, monkeypatch):
    assert invoke(case, monkeypatch, "--evaluation", str(case["folder"])) == 0
    path = case["root"] / display.APPROVAL_FILE
    original = json.loads(path.read_bytes())
    assert invoke(case, monkeypatch, "--disable", now=NOW + timedelta(hours=1)) == 0
    disabled = json.loads(path.read_bytes())
    assert disabled["enabled"] is False
    assert disabled["approved_at"] == original["approved_at"]
    assert (
        invoke(
            case,
            monkeypatch,
            "--evaluation",
            str(case["folder"]),
            now=NOW + timedelta(hours=2),
        )
        == 0
    )
    assert json.loads(path.read_bytes())["enabled"] is True
    before = path.read_bytes()
    case["report"]["health"]["incomplete_folders"] = ["tahmin_yarim"]
    rewrite_report(case)
    assert invoke(case, monkeypatch, "--evaluation", str(case["folder"])) == 1
    assert path.read_bytes() == before


def test_disable_is_idempotent_without_an_approval(case, monkeypatch):
    assert invoke(case, monkeypatch, "--disable") == 0
    assert not (case["root"] / display.APPROVAL_FILE).exists()


def test_busy_lock_returns_three_and_keeps_approval(case, monkeypatch):
    with FileLock(str(case["root"] / "gosterim_onayi.lock"), timeout=0):
        assert invoke(case, monkeypatch, "--evaluation", str(case["folder"])) == 3
    assert not (case["root"] / display.APPROVAL_FILE).exists()


@pytest.mark.parametrize("args", [[], ["--disable", "--evaluation", "x"]])
def test_cli_requires_exactly_one_action(args):
    with pytest.raises(SystemExit) as error:
        main(["shadow-display", *args])
    assert error.value.code == 2


def test_istanbul_date_allows_january_fifth_before_utc_midnight(case):
    # İstanbul'da 00.30 olduğunda UTC hâlâ 4 Ocak'tır; rapor gelecekteyse reddedilir.
    now = datetime(2027, 1, 4, 21, 30, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="gelecekte"):
        display.set_display(case["config"], case["folder"], now=now)
