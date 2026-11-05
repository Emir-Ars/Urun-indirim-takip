"""shadow-evaluate: komut, dosya güvenliği ve DB/ağ/model çalıştırma sınırı."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app.ml import __main__ as cli
from app.ml import shadow, shadow_evaluation as evaluation
from app.ml.metrics import METRIC_RULES
from tests.support.ml import write_evaluation_evidence, write_shadow_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    return write_evaluation_evidence(tmp_path_factory.mktemp("evaluation_cli"))


@pytest.fixture
def config(evidence, tmp_path):
    folder = tmp_path / "records" / "tahmin_01"
    shutil.copytree(evidence["record"], folder)
    return write_shadow_config(tmp_path / "shadow.json", evidence, folder.parent)


def run(evidence, config, target, source=None):
    return cli.main(
        [
            "shadow-evaluate",
            "--snapshot",
            str(source or evidence["source"]),
            "--config",
            str(config),
            "--output-dir",
            str(target),
        ]
    )


def test_real_command_writes_verified_report_and_keeps_original_records(
    evidence, config, tmp_path, capsys
):
    folder = tmp_path / "records" / "tahmin_01"
    before = {path.name: path.read_bytes() for path in folder.iterdir()}
    target = tmp_path / "report"
    assert run(evidence, config, target) == 0
    report, rows = evaluation.read_outputs(target)
    assert rows and report["summary"]["rows"] == len(rows)
    assert before == {path.name: path.read_bytes() for path in folder.iterdir()}
    assert "DB/ağ kullanılmadı" in capsys.readouterr().out
    assert report["opens_display"] is False


@pytest.mark.parametrize("failure", ["sha", "config", "snapshot"])
def test_bad_inputs_never_write_a_complete_report(
    evidence, config, tmp_path, capsys, failure
):
    source = evidence["source"]
    settings = json.loads(config.read_bytes())
    if failure == "sha":
        settings["model_manifest_sha256"] = "a" * 64
    elif failure == "config":
        settings["extra"] = True
    else:
        source = tmp_path / "missing"
    config.write_bytes(json.dumps(settings).encode("utf-8"))
    target = tmp_path / "report"
    assert run(evidence, config, target, source) == 1
    assert "Değerlendirme yazılmadı" in capsys.readouterr().err
    assert not target.exists()


def test_existing_folder_is_untouched_before_any_evaluation(
    evidence, config, tmp_path, monkeypatch
):
    target = tmp_path / "report"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"keep")
    monkeypatch.setattr(
        evaluation,
        "evaluate_snapshot",
        lambda *args: pytest.fail("Eski klasöre değerlendirme"),
    )
    assert run(evidence, config, target) == 1
    assert list(target.iterdir()) == [target / "keep.txt"]


def test_busy_prediction_writer_is_3_with_no_report(evidence, config, tmp_path):
    with shadow.record_lock(tmp_path / "records"):
        assert run(evidence, config, tmp_path / "report") == 3
    assert not (tmp_path / "report").exists()


def test_interrupted_output_has_no_completed_manifest(
    evidence, config, tmp_path, monkeypatch
):
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.md":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "report"
    assert run(evidence, config, target) == 130
    assert target.exists() and not (target / "manifest.json").exists()


def test_empty_record_directory_is_a_successful_insufficient_report(evidence, tmp_path):
    config = write_shadow_config(tmp_path / "shadow.json", evidence, tmp_path / "empty")
    target = tmp_path / "report"
    assert run(evidence, config, target) == 0
    report, rows = evaluation.read_outputs(target)
    assert not rows and report["gate"]["status"] == "not_evaluable"


def test_command_never_connects_deserializes_trains_or_predicts(
    evidence, config, tmp_path
):
    code = r"""
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('psycopg', 'psycopg_pool', 'curl_cffi', 'httpx', 'requests',
                     'app.database', 'app.api', 'app.ui', 'app.collection',
                     'app.discovery', 'app.market_history', 'tools')
        if any(fullname == name or fullname.startswith(name + '.')
               for name in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Yasak model/ag islemi')
sys.meta_path.insert(0, Guard())
socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
from app.ml.metrics import METRIC_RULES
METRIC_RULES['bootstrap_repeats'] = 100
METRIC_RULES['bootstrap_minimum_valid'] = 90
from app.ml import final, models, shadow
final.pickle.loads = blocked
final.load_frozen_model = blocked
shadow.load_frozen_model = blocked
shadow.load_model = blocked
shadow.predict_frozen = blocked
for name in ('fit_frozen', 'predict_frozen', 'fit_fold', 'evaluate_frozen'):
    if hasattr(models, name):
        setattr(models, name, blocked)
from app.ml.__main__ import main
raise SystemExit(main(sys.argv[1:]))
"""
    target = tmp_path / "report"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            "shadow-evaluate",
            "--snapshot",
            str(evidence["source"]),
            "--config",
            str(config),
            "--output-dir",
            str(target),
        ],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((target / "manifest.json").read_bytes())["status"] == "complete"
