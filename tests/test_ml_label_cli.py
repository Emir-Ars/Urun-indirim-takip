"""Ağsız etiket komutu, belirlenimci kanıt dosyaları ve bağımsız eski hesap."""

import hashlib
import json
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from app.ml.__main__ import main
from app.ml.dataset import write_snapshot
from app.ml.labels import analyze_labels
from app.ml.reporting import OUTPUT_FILES, json_bytes, verify_outputs, write_outputs
from tests.support.ml import (
    add_label_page,
    label_snapshot,
    label_tables,
    remove_label_run,
)
from tools.ml_label_check import check_labels, legacy_windows, main as check_main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_writes_reproducible_verified_artifacts(tmp_path, capsys):
    source = tmp_path / "source"
    digest = write_snapshot(label_snapshot(), source)
    outputs = [tmp_path / "first", tmp_path / "second"]
    for target in outputs:
        assert (
            main(["labels", "--snapshot", str(source), "--output-dir", str(target)])
            == 0
        )
        verify_outputs(target, digest)
    assert "veritabanına bağlanılmadı" in capsys.readouterr().out
    for name in (*OUTPUT_FILES, "manifest.json"):
        assert (outputs[0] / name).read_bytes() == (outputs[1] / name).read_bytes()
    assert check_labels(source, outputs[0]) == 74
    assert check_main(["--snapshot", str(source), "--labels-dir", str(outputs[0])]) == 0


@pytest.mark.parametrize(
    "change",
    [
        "gap",
        "error",
        "scope",
        "half_day",
        "late",
        "duplicate",
        "interrupted",
        "identity",
        "no_market",
        "no_own",
    ],
)
def test_strict_variant_matches_independent_old_calculator(change):
    tables = label_tables(40)
    if change == "gap":
        remove_label_run(tables, 20)
        tables["market_history"].pop(10)
    elif change == "error":
        tables["listing_checks"][20].update(outcome="error", current_price=None)
    elif change == "scope":
        add_label_page(tables, start_offset=15, end_offset=39)
    elif change == "half_day":
        tables["market_history"][-1]["captured_at"] = tables["collection_runs"][-1][
            "started_at"
        ]
    elif change == "late":
        tables["collection_runs"][21]["finished_at"] += timedelta(hours=3)
    elif change == "duplicate":
        tables["collection_runs"].append(
            {**tables["collection_runs"][20], "run_id": 81}
        )
        tables["listing_checks"].append({**tables["listing_checks"][20], "run_id": 81})
    elif change == "interrupted":
        tables["collection_runs"][20]["status"] = "interrupted"
        tables["listing_checks"][20].update(
            outcome=None, current_price=None, checked_at=None
        )
    elif change == "identity":
        tables["market_history"][20]["source_product_id"] = "987654"
    elif change == "no_market":
        tables["market_history"] = []
    elif change == "no_own":
        tables["collection_runs"], tables["listing_checks"] = [], []
    snapshot = label_snapshot(tables)
    actual = analyze_labels(snapshot)[3]
    assert json_bytes(actual) == json_bytes(legacy_windows(snapshot))


def test_zero_usable_windows_is_success(tmp_path):
    source, target = tmp_path / "source", tmp_path / "out"
    write_snapshot(label_snapshot(count=5), source)
    assert main(["labels", "--snapshot", str(source), "--output-dir", str(target)]) == 0
    report = json.loads((target / "report.json").read_bytes())
    assert report["sources"]["own"]["primary"]["usable"] == 0


def test_existing_output_directory_is_untouched(tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "keep").write_bytes(b"keep")
    assert (
        main(
            [
                "labels",
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


def test_corrupt_snapshot_does_not_create_output(tmp_path):
    source, target = tmp_path / "source", tmp_path / "out"
    write_snapshot(label_snapshot(), source)
    path = source / "snapshot.json"
    content = json.loads(path.read_bytes())
    content["payload"]["schema_version"] += 1
    path.write_bytes(json_bytes(content))
    assert main(["labels", "--snapshot", str(source), "--output-dir", str(target)]) == 1
    assert not target.exists()


def test_missing_manifest_and_changed_file_are_rejected(tmp_path):
    source, target = tmp_path / "source", tmp_path / "out"
    snapshot = label_snapshot()
    digest = write_snapshot(snapshot, source)
    write_outputs(target, digest, analyze_labels(snapshot))
    path = target / "strict_windows.jsonl"
    path.write_bytes(path.read_bytes() + b"\n")
    assert check_main(["--snapshot", str(source), "--labels-dir", str(target)]) == 1
    (target / "manifest.json").unlink()
    assert check_main(["--snapshot", str(source), "--labels-dir", str(target)]) == 1


def test_rehashed_wrong_label_still_fails_independent_check(tmp_path):
    source, target = tmp_path / "source", tmp_path / "out"
    snapshot = label_snapshot()
    digest = write_snapshot(snapshot, source)
    write_outputs(target, digest, analyze_labels(snapshot))
    path = target / "strict_windows.jsonl"
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]
    next(row for row in rows if row["label"] == 0)["label"] = 1
    path.write_bytes(b"".join(json_bytes(row) + b"\n" for row in rows))
    manifest = json.loads((target / "manifest.json").read_bytes())
    manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (target / "manifest.json").write_bytes(json_bytes(manifest))
    with pytest.raises(ValueError, match="uyuşmuyor"):
        check_labels(source, target)


def test_interrupted_write_has_no_success_manifest(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "out"
    write_snapshot(label_snapshot(), source)
    original = Path.write_bytes

    def interrupted(path, content):
        if path.name == "report.json":
            raise KeyboardInterrupt
        return original(path, content)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    assert (
        main(["labels", "--snapshot", str(source), "--output-dir", str(target)]) == 130
    )
    assert not (target / "manifest.json").exists()


def test_labels_command_never_loads_database_or_network_layers(tmp_path):
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
                     'app.market_history', 'app.api', 'app.ui', 'tools')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman: ' + fullname)
def blocked(*args, **kwargs):
    raise AssertionError('Ag baglantisi')
sys.meta_path.insert(0, Guard())
socket.create_connection = blocked
socket.socket = blocked
from app.ml.__main__ import main
args = ['labels', '--snapshot', sys.argv[1], '--output-dir', sys.argv[2]]
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


def test_checker_uses_no_database_connection(tmp_path, monkeypatch):
    import psycopg
    import socket

    def forbidden(*args, **kwargs):
        pytest.fail("Çapraz kontrol DB/ağ bağlantısı açtı")

    source, target = tmp_path / "source", tmp_path / "out"
    snapshot = label_snapshot()
    digest = write_snapshot(snapshot, source)
    write_outputs(target, digest, analyze_labels(snapshot))
    monkeypatch.setattr(psycopg, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    assert check_labels(source, target) == 74
