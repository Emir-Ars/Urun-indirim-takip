"""experiment komutu: kanıt zinciri, çıktı bütünlüğü ve kapalı saklı test."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.ml.__main__ import main
from app.ml.experiment import load_experiment_inputs
from app.ml.metrics import METRIC_RULES
from app.ml.reporting import (
    EXPERIMENT_OUTPUT_FILES,
    json_bytes,
    verify_experiment_outputs,
)
from tests.support.ml import write_ml_evidence

ROOT = Path(__file__).resolve().parents[1]
KEY_FIELDS = ("product_id", "source", "anchor_day")


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
    return write_ml_evidence(tmp_path_factory.mktemp("evidence"))


@pytest.fixture(scope="module")
def limited(tmp_path_factory):
    root = tmp_path_factory.mktemp("limited")
    return write_ml_evidence(root, count=10)


@pytest.fixture(scope="module")
def first(evidence, tmp_path_factory):
    target = tmp_path_factory.mktemp("runs") / "first"
    assert run(evidence, target) == 0
    return target


def run(evidence, target, split=None):
    return main(
        [
            "experiment",
            "--labels-dir",
            str(evidence["labels"]),
            "--features-dir",
            str(evidence["features"]),
            "--split-dir",
            str(split or evidence["split"]),
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


def test_complete_run_writes_verified_files_and_keeps_the_test_closed(evidence, first):
    assert {path.name for path in first.iterdir()} == {
        *EXPERIMENT_OUTPUT_FILES,
        "manifest.json",
    }
    inputs = load_experiment_inputs(
        evidence["labels"], evidence["features"], evidence["split"]
    )
    manifest = verify_experiment_outputs(first, inputs)
    assert set(manifest["input_manifests"]) == {"labels", "features", "split"}
    assert manifest["snapshot_sha256"] == evidence["digest"]
    assert set(manifest["libraries"]) == {"python", "numpy", "scikit_learn", "lightgbm"}
    report = json.loads((first / "report.json").read_bytes())
    assert (
        report["test_opened"]
        is report["own_source_scored"]
        is report["model_frozen"]
        is False
    )
    folds = json.loads((evidence["split"] / "folds.json").read_bytes())["folds"]
    validation = {
        tuple(member[name] for name in KEY_FIELDS)
        for fold in folds
        for member in fold["members"]["validation"]
    }
    rows = [
        json.loads(line)
        for line in (first / "predictions.jsonl").read_bytes().splitlines()
    ]
    predicted = [tuple(row[name] for name in KEY_FIELDS) for row in rows]
    assert len(predicted) == len(set(predicted)) and set(predicted) == validation
    assignments = [
        json.loads(line)
        for line in (evidence["split"] / "assignments.jsonl").read_bytes().splitlines()
    ]
    reserved = {
        tuple(row[name] for name in KEY_FIELDS)
        for row in assignments
        if row["role"] == "test_reserved"
    }
    assert reserved and reserved.isdisjoint(predicted)
    assert all(row["source"] == "cimri" for row in rows)


def test_second_run_reproduces_every_byte_and_prints_the_summary(
    evidence, first, tmp_path, capsys
):
    second = tmp_path / "second"
    assert run(evidence, second) == 0
    for name in (*EXPERIMENT_OUTPUT_FILES, "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    output = capsys.readouterr().out
    assert "LightGBM seçim ölçütü" in output
    assert "Saklı test açılmadı" in output
    assert "kendi serimiz puanlanmadı" in output


def test_existing_output_directory_is_not_touched_or_inputs_read(tmp_path, capsys):
    target = tmp_path / "keep"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"keep")
    missing = dict(labels=tmp_path / "x", features=tmp_path / "y", split=tmp_path / "z")
    assert run(missing, target) == 1
    assert list(target.iterdir()) == [target / "keep.txt"]
    assert "klasör zaten var" in capsys.readouterr().err


def test_split_that_differs_from_the_rebuilt_split_is_rejected(
    evidence, tmp_path, capsys
):
    split = tmp_path / "split"
    shutil.copytree(evidence["split"], split)
    path = split / "folds.json"
    folds = json.loads(path.read_bytes())
    folds["folds"][0]["purged"]["train"] += 1
    path.write_bytes(json_bytes(folds))
    # Parmak izi yenilense bile içerik yeniden üretilen bölmeyle uyuşmalıdır.
    rehash(split, path.name)
    target = tmp_path / "out"
    assert run(evidence, target, split) == 1
    assert "yeniden üretilen" in capsys.readouterr().err
    assert not target.exists()


def test_split_made_from_other_inputs_is_rejected(evidence, limited, tmp_path):
    target = tmp_path / "out"
    other = dict(evidence, labels=limited["labels"], features=limited["features"])
    assert run(other, target) == 1
    assert not target.exists()


def test_missing_split_manifest_is_rejected(evidence, tmp_path):
    split = tmp_path / "split"
    shutil.copytree(evidence["split"], split)
    (split / "manifest.json").unlink()
    target = tmp_path / "out"
    assert run(evidence, target, split) == 1
    assert not target.exists()


def test_test_unlock_argument_does_not_exist():
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "experiment",
                "--labels-dir",
                "labels",
                "--features-dir",
                "features",
                "--split-dir",
                "split",
                "--output-dir",
                "out",
                "--open-test",
            ]
        )
    assert exc.value.code == 2


def test_interrupted_write_leaves_no_completion_marker(evidence, tmp_path, monkeypatch):
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.json":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "out"
    assert run(evidence, target) == 130
    assert not (target / "manifest.json").exists()


def test_limited_evidence_returns_zero_with_an_unevaluable_selection(
    limited, tmp_path, capsys
):
    target = tmp_path / "out"
    assert run(limited, target) == 0
    assert "değerlendirilemedi" in capsys.readouterr().out
    assert (target / "predictions.jsonl").read_bytes() == b""
    assert "Puanlanacak doğrulama satırı yok" in (target / "report.md").read_text(
        encoding="utf-8"
    )
    report = json.loads((target / "report.json").read_bytes())
    assert report["selection"]["status"] == "not_evaluable"
    inputs = load_experiment_inputs(
        limited["labels"], limited["features"], limited["split"]
    )
    verify_experiment_outputs(target, inputs)


def test_experiment_command_does_not_load_database_or_network_layers(limited, tmp_path):
    code = r"""
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('psycopg', 'psycopg_pool', 'curl_cffi', 'httpx', 'requests',
                     'app.database', 'app.collection', 'app.discovery',
                     'app.market_history', 'app.api', 'app.ui', 'tools')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Ag baglantisi')
sys.meta_path.insert(0, Guard())
# numpy/scikit-learn socket.socket'ten türeyen sınıflar yükler; sınıfın kendisi
# yerine yalnız bağlantı kuran yöntemler engellenir.
socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
from app.ml.metrics import METRIC_RULES
# Bölme klasörü bu tekrar sayısıyla üretildi (modül başındaki hızlandırma).
METRIC_RULES['bootstrap_repeats'] = 100
METRIC_RULES['bootstrap_minimum_valid'] = 90
from app.ml.__main__ import main
args = ['experiment', '--labels-dir', sys.argv[1], '--features-dir', sys.argv[2],
        '--split-dir', sys.argv[3], '--output-dir', sys.argv[4]]
raise SystemExit(main(args))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(limited["labels"]),
            str(limited["features"]),
            str(limited["split"]),
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
