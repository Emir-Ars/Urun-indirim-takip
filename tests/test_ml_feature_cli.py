"""Girdi komutunun ağsızlığı, çıktı sözleşmesi ve dosya bütünlüğü."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.ml.__main__ import main
from app.ml.dataset import write_snapshot
from app.ml.features import FeatureRow
from app.ml.reporting import FEATURE_OUTPUT_FILES, json_bytes, verify_feature_outputs
from tests.support.ml import label_snapshot

ROOT = Path(__file__).resolve().parents[1]


def run_features(tmp_path, snapshot=None, name="out"):
    source = tmp_path / "source"
    digest = write_snapshot(snapshot or label_snapshot(), source)
    target = tmp_path / name
    code = main(["features", "--snapshot", str(source), "--output-dir", str(target)])
    return source, digest, target, code


def test_cli_writes_typed_reproducible_outputs_without_labels(tmp_path, capsys):
    source, digest, target, code = run_features(tmp_path)
    assert code == 0
    verify_feature_outputs(target, digest)
    report = json.loads((target / "report.json").read_bytes())
    assert report["sources"]["own"]["rows"] == report["sources"]["cimri"]["rows"] == 37
    assert report["labels_read"] is report["model_trained"] is False
    assert all(
        count == 0
        for name, count in report["sources"]["own"]["missing"].items()
        if name in ("brand", "family", "capacity")
    )
    rows = [
        FeatureRow.model_validate_json(line)
        for line in (target / "features.jsonl").read_bytes().splitlines()
    ]
    assert len(rows) == 74
    assert rows[0].metadata.anchor_at is None
    assert rows[1].metadata.month == 1
    assert "Etiket okunmadı" in capsys.readouterr().out
    repeated = tmp_path / "repeated"
    assert (
        main(["features", "--snapshot", str(source), "--output-dir", str(repeated)])
        == 0
    )
    for name in (*FEATURE_OUTPUT_FILES, "manifest.json"):
        assert (target / name).read_bytes() == (repeated / name).read_bytes()


def test_no_price_rows_is_success(tmp_path):
    _, _, target, code = run_features(tmp_path, label_snapshot(prices=[None] * 37))
    assert code == 0
    assert (target / "features.jsonl").read_bytes() == b""
    assert (
        json.loads((target / "report.json").read_bytes())["sources"]["own"]["rows"] == 0
    )


def test_existing_output_untouched_before_reading_input(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep").write_bytes(b"keep")
    assert (
        main(
            [
                "features",
                "--snapshot",
                str(tmp_path / "missing"),
                "--output-dir",
                str(target),
            ]
        )
        == 1
    )
    assert list(target.iterdir()) == [target / "keep"]
    assert (target / "keep").read_bytes() == b"keep"


def test_corrupt_input_no_output(tmp_path):
    source = tmp_path / "source"
    write_snapshot(label_snapshot(), source)
    path = source / "snapshot.json"
    value = json.loads(path.read_bytes())
    value["payload"]["schema_version"] += 1
    path.write_bytes(json_bytes(value))
    target = tmp_path / "out"
    assert (
        main(["features", "--snapshot", str(source), "--output-dir", str(target)]) == 1
    )
    assert not target.exists()


def test_tampered_output_and_missing_manifest_rejected(tmp_path):
    _, digest, target, code = run_features(tmp_path)
    assert code == 0
    (target / "report.md").write_bytes(b"changed")
    with pytest.raises(ValueError, match="parmak izi"):
        verify_feature_outputs(target, digest)
    (target / "manifest.json").unlink()
    with pytest.raises(OSError):
        verify_feature_outputs(target, digest)


def test_wrong_snapshot_digest_rejected(tmp_path):
    _, _, target, _ = run_features(tmp_path)
    with pytest.raises(ValueError, match="manifesti"):
        verify_feature_outputs(target, "0" * 64)


def test_rehashed_forbidden_field_is_still_rejected(tmp_path):
    _, digest, target, _ = run_features(tmp_path)
    path = target / "features.jsonl"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    rows[0]["features"]["future_observed_days"] = 7
    path.write_bytes(b"".join(json_bytes(row) + b"\n" for row in rows))
    manifest = json.loads((target / "manifest.json").read_bytes())
    manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / "manifest.json").write_bytes(json_bytes(manifest))
    with pytest.raises(ValueError, match="Extra inputs"):
        verify_feature_outputs(target, digest)


def test_interruption_does_not_write_success_marker(tmp_path, monkeypatch):
    source = tmp_path / "source"
    write_snapshot(label_snapshot(), source)
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.json":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "out"
    assert (
        main(["features", "--snapshot", str(source), "--output-dir", str(target)])
        == 130
    )
    assert not (target / "manifest.json").exists()


def test_write_failure_returns_one_without_success_marker(tmp_path, monkeypatch):
    source = tmp_path / "source"
    write_snapshot(label_snapshot(), source)
    original = Path.write_bytes

    def failed(path, data):
        if path.name == "feature_schema.json":
            raise OSError("Yapay yazma hatası")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", failed)
    target = tmp_path / "out"
    assert (
        main(["features", "--snapshot", str(source), "--output-dir", str(target)]) == 1
    )
    assert not (target / "manifest.json").exists()


def test_feature_command_does_not_import_labels_database_network_or_training(tmp_path):
    source = tmp_path / "source"
    write_snapshot(label_snapshot(), source)
    code = r"""
import importlib.abc
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('psycopg', 'psycopg_pool', 'curl_cffi', 'httpx', 'requests',
                     'app.database', 'app.collection', 'app.discovery',
                     'app.market_history', 'app.api', 'app.ui', 'tools',
                     'app.ml.labels', 'sklearn', 'lightgbm', 'numpy')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Ag baglantisi')
sys.meta_path.insert(0, Guard())
socket.create_connection = blocked
socket.socket = blocked
from app.ml.__main__ import main
args = ['features', '--snapshot', sys.argv[1], '--output-dir', sys.argv[2]]
raise SystemExit(main(args))
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(source), str(tmp_path / "out")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_missing_required_arguments_return_two():
    with pytest.raises(SystemExit) as exc:
        main(["features"])
    assert exc.value.code == 2
