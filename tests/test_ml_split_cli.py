"""Ağsız bölme komutu, giriş eşleşmesi ve saklı test içermeyen kanıtlar."""

import hashlib
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.ml.__main__ import main
from app.ml.dataset import write_snapshot
from app.ml.features import analyze_features
from app.ml.labels import analyze_labels
from app.ml.reporting import (
    SPLIT_OUTPUT_FILES,
    json_bytes,
    verify_split_outputs,
    write_feature_outputs,
    write_outputs,
)
from app.ml.splitting import load_split_inputs
from tests.support.ml import label_snapshot

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp_path, count=100):
    snapshot = label_snapshot(
        prices=[10000 if index % 2 == 0 else 9000 for index in range(count)]
    )
    digest = write_snapshot(snapshot, tmp_path / "source")
    labels, features = tmp_path / "labels", tmp_path / "features"
    write_outputs(labels, digest, analyze_labels(snapshot))
    write_feature_outputs(features, digest, analyze_features(snapshot))
    return labels, features, digest


def run(labels, features, target):
    return main(
        [
            "split",
            "--labels-dir",
            str(labels),
            "--features-dir",
            str(features),
            "--output-dir",
            str(target),
        ]
    )


def rehash(directory, name):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    manifest["files"][name] = hashlib.sha256(
        (directory / name).read_bytes()
    ).hexdigest()
    (directory / "manifest.json").write_bytes(json_bytes(manifest))


def test_cli_complete_reproducible_evidence_has_no_test_labels_or_scores(
    tmp_path, capsys
):
    labels, features, digest = prepare(tmp_path, 365)
    inputs = load_split_inputs(labels, features)
    first, second = tmp_path / "first", tmp_path / "second"
    assert run(labels, features, first) == 0
    verify_split_outputs(first, digest, inputs.input_manifests)
    assert "Saklı test açılmadı" in capsys.readouterr().out
    assert run(labels, features, second) == 0
    for name in (*SPLIT_OUTPUT_FILES, "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    report = json.loads((first / "report.json").read_bytes())
    assert report["status"] == "ready"
    assert len(report["folds"]) == 4
    assert set(report["partitions"]["test_reserved"]) == {
        "first_anchor",
        "last_anchor",
        "rows",
    }
    assert report["test_opened"] is report["real_prediction_scores_computed"] is False
    assignments = [
        json.loads(line)
        for line in (first / "assignments.jsonl").read_bytes().splitlines()
    ]
    assert all(
        set(row) == {"product_id", "source", "anchor_day", "role"}
        for row in assignments
    )
    assert len(assignments) == len(inputs.samples)
    # İlk günlerin NULL girdileri satırların aktarımını engellemez.
    assert any(sample.anchor.label is None for sample in inputs.samples)


def test_limited_data_still_returns_zero(tmp_path):
    labels, features, _ = prepare(tmp_path, 10)
    target = tmp_path / "out"
    assert run(labels, features, target) == 0
    assert json.loads((target / "report.json").read_bytes())["status"] == "limited"


def test_existing_directory_not_changed_or_inputs_read(tmp_path):
    target = tmp_path / "keep"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"keep")
    assert run(tmp_path / "missing", tmp_path / "missing", target) == 1
    assert list(target.iterdir()) == [target / "keep.txt"]


@pytest.mark.parametrize(
    "problem", ["snapshot", "rules", "hash", "missing_manifest", "manifest_not_object"]
)
def test_invalid_input_manifests_do_not_create_output(tmp_path, problem):
    labels, features, _ = prepare(tmp_path)
    path = features / "manifest.json"
    manifest = json.loads(path.read_bytes())
    if problem == "snapshot":
        manifest["snapshot_sha256"] = "0" * 64
    elif problem == "rules":
        manifest["feature_rules"]["version"] = 999
    elif problem == "hash":
        (features / "features.jsonl").write_bytes(b"changed")
    elif problem == "missing_manifest":
        path.unlink()
    elif problem == "manifest_not_object":
        manifest = []
    if problem != "missing_manifest":
        path.write_bytes(json_bytes(manifest))
    target = tmp_path / "out"
    assert run(labels, features, target) == 1
    assert not target.exists()


@pytest.mark.parametrize(
    "problem", ["duplicate", "missing", "horizon", "label", "unsorted"]
)
def test_rehashed_invalid_window_records_rejected(tmp_path, problem):
    labels, features, _ = prepare(tmp_path)
    path = labels / "windows.jsonl"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    if problem == "duplicate":
        rows.insert(1, rows[0])
    elif problem == "missing":
        rows.pop()
    elif problem == "horizon":
        rows[0]["target_end"] = (
            date.fromisoformat(rows[0]["target_end"]) + timedelta(days=1)
        ).isoformat()
    elif problem == "label":
        rows[0]["primary"]["label"] = True
    elif problem == "unsorted":
        rows.reverse()
    path.write_bytes(b"".join(json_bytes(row) + b"\n" for row in rows))
    rehash(labels, path.name)
    target = tmp_path / "out"
    assert run(labels, features, target) == 1
    assert not target.exists()


def test_changed_output_and_missing_completion_marker_rejected(tmp_path):
    labels, features, digest = prepare(tmp_path)
    inputs = load_split_inputs(labels, features)
    target = tmp_path / "out"
    assert run(labels, features, target) == 0
    (target / "report.md").write_bytes(b"changed")
    with pytest.raises(ValueError, match="parmak izi"):
        verify_split_outputs(target, digest, inputs.input_manifests)
    (target / "manifest.json").unlink()
    with pytest.raises(OSError):
        verify_split_outputs(target, digest, inputs.input_manifests)


def test_rehashed_test_class_statistics_still_rejected(tmp_path):
    labels, features, digest = prepare(tmp_path)
    inputs = load_split_inputs(labels, features)
    target = tmp_path / "out"
    assert run(labels, features, target) == 0
    path = target / "report.json"
    report = json.loads(path.read_bytes())
    report["partitions"]["test_reserved"]["positive"] = 999
    path.write_bytes(json_bytes(report))
    rehash(target, path.name)
    with pytest.raises(ValueError, match="Saklı test"):
        verify_split_outputs(target, digest, inputs.input_manifests)


def test_rehashed_test_key_in_fold_still_rejected(tmp_path):
    labels, features, digest = prepare(tmp_path, 365)
    inputs = load_split_inputs(labels, features)
    target = tmp_path / "out"
    assert run(labels, features, target) == 0
    assignments = [
        json.loads(line)
        for line in (target / "assignments.jsonl").read_bytes().splitlines()
    ]
    reserved = next(row for row in assignments if row["role"] == "test_reserved")
    path = target / "folds.json"
    folds = json.loads(path.read_bytes())
    folds["folds"][0]["members"]["validation"].append(
        {name: reserved[name] for name in ("product_id", "source", "anchor_day")}
    )
    path.write_bytes(json_bytes(folds))
    rehash(target, path.name)
    with pytest.raises(ValueError, match="saklı test"):
        verify_split_outputs(target, digest, inputs.input_manifests)


def test_interrupted_write_does_not_complete_output(tmp_path, monkeypatch):
    labels, features, _ = prepare(tmp_path)
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.json":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "out"
    assert run(labels, features, target) == 130
    assert not (target / "manifest.json").exists()


def test_split_command_does_not_load_database_network_or_training(tmp_path):
    labels, features, _ = prepare(tmp_path)
    code = r"""
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('psycopg', 'psycopg_pool', 'curl_cffi', 'httpx', 'requests',
                     'app.database', 'app.collection', 'app.discovery',
                     'app.market_history', 'app.api', 'app.ui', 'tools',
                     'numpy', 'sklearn', 'lightgbm')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Ag baglantisi')
sys.meta_path.insert(0, Guard())
socket.create_connection = blocked
socket.socket = blocked
from app.ml.__main__ import main
args = ['split', '--labels-dir', sys.argv[1], '--features-dir', sys.argv[2],
        '--output-dir', sys.argv[3]]
raise SystemExit(main(args))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(labels), str(features), str(tmp_path / "out")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_test_unlock_argument_does_not_exist():
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "split",
                "--labels-dir",
                "labels",
                "--features-dir",
                "features",
                "--output-dir",
                "out",
                "--open-test",
            ]
        )
    assert exc.value.code == 2
