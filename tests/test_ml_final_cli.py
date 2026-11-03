"""freeze komutu: kanıt zinciri, çıktı bütünlüğü ve kapalı saklı test."""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.ml import final
from app.ml.__main__ import main
from app.ml.experiment import load_experiment_inputs
from app.ml.final import load_frozen_model
from app.ml.metrics import METRIC_RULES
from app.ml.reporting import (
    FINAL_TEST_OUTPUT_FILES,
    MODEL_OUTPUT_FILES,
    verify_final_test_outputs,
)
from tests.support.ml import write_experiment_evidence

ROOT = Path(__file__).resolve().parents[1]


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
    return write_experiment_evidence(tmp_path_factory.mktemp("evidence"))


@pytest.fixture(scope="module")
def limited(tmp_path_factory):
    return write_experiment_evidence(tmp_path_factory.mktemp("limited"), count=10)


@pytest.fixture(scope="module")
def first(evidence, tmp_path_factory):
    target = tmp_path_factory.mktemp("runs") / "first"
    assert freeze(evidence, target) == 0
    return target


def freeze(evidence, target, experiment=None):
    return main(
        [
            "freeze",
            "--labels-dir",
            str(evidence["labels"]),
            "--features-dir",
            str(evidence["features"]),
            "--split-dir",
            str(evidence["split"]),
            "--experiment-dir",
            str(experiment or evidence["experiment"]),
            "--output-dir",
            str(target),
        ]
    )


def test_complete_run_writes_a_loadable_model_and_keeps_the_test_closed(
    evidence, first
):
    assert {path.name for path in first.iterdir()} == {
        *MODEL_OUTPUT_FILES,
        "manifest.json",
    }
    inputs = load_experiment_inputs(
        evidence["labels"], evidence["features"], evidence["split"]
    )
    digest = hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest()
    loaded = load_frozen_model(first, inputs, digest)
    manifest = loaded.manifest
    assert manifest["test_opened"] is False
    assert set(manifest["input_manifests"]) == {"labels", "features", "split"}
    assert manifest["snapshot_sha256"] == evidence["digest"]
    assert set(manifest["libraries"]) == {"python", "numpy", "scikit_learn", "lightgbm"}
    report = (first / "report.md").read_text(encoding="utf-8")
    assert "saklı test açılmadı" in report


def test_second_run_reproduces_every_byte_and_prints_the_registration_values(
    evidence, first, tmp_path, capsys
):
    second = tmp_path / "second"
    assert freeze(evidence, second) == 0
    for name in (*MODEL_OUTPUT_FILES, "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    output = capsys.readouterr().out
    digest = hashlib.sha256((second / "manifest.json").read_bytes()).hexdigest()
    assert f"Model manifest SHA-256 (ön kayıt için): {digest}" in output
    assert "Dondurulan model:" in output
    assert "Platt sıralamayı koruyor:" in output
    assert "Saklı test açılmadı" in output
    assert "kendi serimiz puanlanmadı" in output


def test_existing_output_directory_is_not_touched_or_inputs_read(tmp_path, capsys):
    target = tmp_path / "keep"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"keep")
    missing = dict(
        labels=tmp_path / "x",
        features=tmp_path / "y",
        split=tmp_path / "z",
        experiment=tmp_path / "w",
    )
    assert freeze(missing, target) == 1
    assert list(target.iterdir()) == [target / "keep.txt"]
    assert "klasör zaten var" in capsys.readouterr().err


def test_experiment_made_from_other_inputs_is_rejected_and_nothing_is_written(
    evidence, limited, tmp_path
):
    target = tmp_path / "out"
    assert freeze(evidence, target, experiment=limited["experiment"]) == 1
    assert not target.exists()


def test_not_evaluable_experiment_is_not_frozen(limited, tmp_path, capsys):
    target = tmp_path / "out"
    assert freeze(limited, target) == 1
    assert not target.exists()
    assert "değerlendirilemedi" in capsys.readouterr().err


def test_missing_experiment_argument_and_test_unlock_argument_do_not_exist():
    base = ["freeze", "--labels-dir", "l", "--features-dir", "f", "--split-dir", "s"]
    with pytest.raises(SystemExit) as missing:
        main([*base, "--output-dir", "o"])
    assert missing.value.code == 2
    with pytest.raises(SystemExit) as unlock:
        main([*base, "--experiment-dir", "e", "--output-dir", "o", "--open-test"])
    assert unlock.value.code == 2


def test_interrupted_write_leaves_no_completion_marker(evidence, tmp_path, monkeypatch):
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.md":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "out"
    assert freeze(evidence, target) == 130
    assert not (target / "manifest.json").exists()


def test_freeze_command_does_not_load_database_or_network_layers(evidence, tmp_path):
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
# Bölme ve deney klasörleri bu tekrar sayısıyla üretildi (modül başındaki hızlandırma).
METRIC_RULES['bootstrap_repeats'] = 100
METRIC_RULES['bootstrap_minimum_valid'] = 90
from app.ml.__main__ import main
args = ['freeze', '--labels-dir', sys.argv[1], '--features-dir', sys.argv[2],
        '--split-dir', sys.argv[3], '--experiment-dir', sys.argv[4],
        '--output-dir', sys.argv[5]]
raise SystemExit(main(args))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(evidence["labels"]),
            str(evidence["features"]),
            str(evidence["split"]),
            str(evidence["experiment"]),
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "out" / "manifest.json").read_bytes())["status"] == (
        "complete"
    )


# --- final-test: saklı testin tek açılışı ---------------------------------------


def model_sha(model):
    return hashlib.sha256((model / "manifest.json").read_bytes()).hexdigest()


def final_test(evidence, model, sha, target):
    return main(
        [
            "final-test",
            "--labels-dir",
            str(evidence["labels"]),
            "--features-dir",
            str(evidence["features"]),
            "--split-dir",
            str(evidence["split"]),
            "--model-dir",
            str(model),
            "--expected-model-sha256",
            sha,
            "--output-dir",
            str(target),
        ]
    )


@pytest.fixture(scope="module")
def opened(evidence, first, tmp_path_factory):
    target = tmp_path_factory.mktemp("final") / "opened"
    assert final_test(evidence, first, model_sha(first), target) == 0
    return target


@pytest.fixture
def reserved_guard(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Model doğrulanmadan saklı test satırlarına gelindi")

    monkeypatch.setattr(final, "reserved_test_samples", forbidden)


def test_final_test_run_writes_verified_files_for_exactly_the_reserved_rows(
    evidence, first, opened
):
    assert {path.name for path in opened.iterdir()} == {
        *FINAL_TEST_OUTPUT_FILES,
        "manifest.json",
    }
    inputs = load_experiment_inputs(
        evidence["labels"], evidence["features"], evidence["split"]
    )
    manifest = verify_final_test_outputs(opened, inputs, model_sha(first))
    assert manifest["test_opened"] is True
    assert manifest["model_manifest_sha256"] == model_sha(first)
    reserved = sum(row["role"] == "test_reserved" for row in inputs.plan.assignments)
    rows = (opened / "predictions.jsonl").read_bytes().splitlines()
    assert len(rows) == reserved > 0
    report = json.loads((opened / "report.json").read_bytes())
    assert report["model_changed"] is False and report["own_source_scored"] is False
    assert "Saklı test (tek açılış)" in (opened / "report.md").read_text("utf-8")


def test_second_final_test_run_reproduces_every_byte_and_prints_the_summary(
    evidence, first, opened, tmp_path, capsys
):
    second = tmp_path / "second"
    assert final_test(evidence, first, model_sha(first), second) == 0
    for name in (*FINAL_TEST_OUTPUT_FILES, "manifest.json"):
        assert (opened / name).read_bytes() == (second / name).read_bytes(), name
    output = capsys.readouterr().out
    assert f"Model manifest SHA-256: {model_sha(first)}" in output
    assert "AP farkı (model − R0)" in output
    assert "Okuma koşulları:" in output
    assert "Saklı test bu komutla açıldı; model değişmedi" in output
    assert "Kendi serimiz puanlanmadı" in output


@pytest.mark.parametrize("wrong", ["0" * 64, "abc", "G" * 64, ""])
def test_unexpected_model_sha_never_reaches_the_reserved_rows(
    evidence, first, tmp_path, capsys, reserved_guard, wrong
):
    target = tmp_path / "out"
    assert final_test(evidence, first, wrong, target) == 1
    assert not target.exists()
    assert "SHA-256" in capsys.readouterr().err


def test_changed_model_file_never_reaches_the_reserved_rows(
    evidence, first, tmp_path, capsys, reserved_guard
):
    model = tmp_path / "model"
    shutil.copytree(first, model)
    (model / "model.pkl").write_bytes(b"other model")
    target = tmp_path / "out"
    # Manifest değişmedi (beklenen SHA tutar); dosya parmak izi tutmaz.
    assert final_test(evidence, model, model_sha(model), target) == 1
    assert not target.exists()
    assert "parmak izi" in capsys.readouterr().err


def test_model_made_from_other_inputs_never_reaches_the_reserved_rows(
    limited, first, tmp_path, reserved_guard
):
    target = tmp_path / "out"
    assert final_test(limited, first, model_sha(first), target) == 1
    assert not target.exists()


def test_existing_final_test_directory_is_not_touched_or_inputs_read(tmp_path, capsys):
    target = tmp_path / "keep"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"keep")
    missing = dict(labels=tmp_path / "x", features=tmp_path / "y", split=tmp_path / "z")
    assert final_test(missing, tmp_path / "m", "0" * 64, target) == 1
    assert list(target.iterdir()) == [target / "keep.txt"]
    assert "klasör zaten var" in capsys.readouterr().err


def test_expected_sha_argument_is_required():
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "final-test",
                "--labels-dir",
                "l",
                "--features-dir",
                "f",
                "--split-dir",
                "s",
                "--model-dir",
                "m",
                "--output-dir",
                "o",
            ]
        )
    assert exc.value.code == 2


def test_interrupted_final_test_write_leaves_no_completion_marker(
    evidence, first, tmp_path, monkeypatch
):
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.json":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "out"
    assert final_test(evidence, first, model_sha(first), target) == 130
    assert not (target / "manifest.json").exists()


def test_final_test_command_does_not_load_database_or_network_layers(
    evidence, first, tmp_path
):
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
socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
from app.ml.metrics import METRIC_RULES
METRIC_RULES['bootstrap_repeats'] = 100
METRIC_RULES['bootstrap_minimum_valid'] = 90
from app.ml.__main__ import main
args = ['final-test', '--labels-dir', sys.argv[1], '--features-dir', sys.argv[2],
        '--split-dir', sys.argv[3], '--model-dir', sys.argv[4],
        '--expected-model-sha256', sys.argv[5], '--output-dir', sys.argv[6]]
raise SystemExit(main(args))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(evidence["labels"]),
            str(evidence["features"]),
            str(evidence["split"]),
            str(first),
            model_sha(first),
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "out" / "manifest.json").read_bytes())["status"] == (
        "complete"
    )


def test_freeze_never_calls_the_reserved_test_entry_points(
    evidence, tmp_path, monkeypatch
):
    # Dondurma saklı test satırlarını almamalı; giriş noktası çağrılırsa test düşer.
    def forbidden(*args, **kwargs):
        pytest.fail("freeze saklı test giriş noktasını çağırdı")

    monkeypatch.setattr(final, "reserved_test_samples", forbidden)
    monkeypatch.setattr(final, "reserved_test_targets", forbidden)
    assert freeze(evidence, tmp_path / "out") == 0
