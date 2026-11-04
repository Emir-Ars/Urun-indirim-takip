"""shadow-predict komutu: kanıt zinciri, resmi/deneme ayrımı ve katman sınırı."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.ml.__main__ import main
from app.ml.metrics import METRIC_RULES
from app.ml.shadow import read_shadow_outputs
from tests.support.ml import write_model_evidence

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
    return write_model_evidence(tmp_path_factory.mktemp("evidence"))


def write_config(path, evidence, records, sha=None, **extra):
    path.write_text(
        json.dumps(
            dict(
                start_day="2026-01-20",
                model_manifest_sha256=sha or evidence["model_sha256"],
                evidence={
                    name: str(evidence[name])
                    for name in ("labels", "features", "split", "model")
                },
                records_dir=str(records),
                **extra,
            )
        ),
        encoding="utf-8",
    )
    return path


def predict(evidence, config, target, *extra):
    return main(
        [
            "shadow-predict",
            "--snapshot",
            str(evidence["source"]),
            "--output-dir",
            str(target),
            "--config",
            str(config),
            *extra,
        ]
    )


@pytest.fixture
def config(evidence, tmp_path):
    return write_config(tmp_path / "shadow.json", evidence, tmp_path / "kayit")


def test_trial_run_writes_a_verified_folder_and_says_it_is_not_a_record(
    evidence, config, tmp_path, capsys
):
    target = tmp_path / "deneme"
    assert predict(evidence, config, target) == 0
    out = capsys.readouterr().out
    manifest, rows = read_shadow_outputs(target)
    assert rows and manifest["summary"]["rows"] == len(rows)
    assert "Deneme çıktısı" in out and "kayıt sayılmaz" in out
    assert "Model manifest SHA-256: " + evidence["model_sha256"] in out
    assert "Ekranda tahmin yok; veritabanı ve ağ kullanılmadı" in out


def test_official_folder_is_reported_and_its_days_are_not_predicted_again(
    evidence, config, tmp_path, capsys
):
    official = tmp_path / "kayit" / "tahmin_20270101"
    assert predict(evidence, config, official) == 0
    assert "Resmi kayıt klasörüne yazıldı" in capsys.readouterr().out
    again = tmp_path / "kayit" / "tahmin_20270102"
    assert predict(evidence, config, again) == 0
    assert "Yeni tahmin yok" in capsys.readouterr().out
    assert not again.exists()


def test_records_dir_option_overrides_the_config(evidence, config, tmp_path, capsys):
    other = tmp_path / "baska"
    assert (
        predict(evidence, config, other / "tahmin_1", "--records-dir", str(other)) == 0
    )
    assert "Resmi kayıt klasörüne yazıldı" in capsys.readouterr().out
    target = tmp_path / "ikinci"
    assert predict(evidence, config, target, "--records-dir", str(other)) == 0
    assert "Yeni tahmin yok" in capsys.readouterr().out
    assert not target.exists()


def test_existing_output_folder_is_never_touched(evidence, config, tmp_path, capsys):
    target = tmp_path / "var"
    target.mkdir()
    (target / "x.txt").write_text("kalmali", encoding="utf-8")
    assert predict(evidence, config, target) == 1
    assert "klasör zaten var" in capsys.readouterr().err
    assert [path.name for path in target.iterdir()] == ["x.txt"]


def test_missing_or_unknown_config_is_a_clear_error(evidence, config, tmp_path, capsys):
    target = tmp_path / "out"
    assert predict(evidence, tmp_path / "yok.json", target) == 1
    broken = write_config(
        tmp_path / "fazla.json", evidence, tmp_path / "kayit", ekstra=1
    )
    assert predict(evidence, broken, target) == 1
    assert capsys.readouterr().err.count("Tahmin yazılmadı") == 2
    assert not target.exists()


def test_model_with_another_sha_is_rejected_before_any_prediction(
    evidence, tmp_path, capsys
):
    wrong = write_config(
        tmp_path / "yanlis.json", evidence, tmp_path / "kayit", sha="2" * 64
    )
    target = tmp_path / "out"
    assert predict(evidence, wrong, target) == 1
    assert "SHA-256" in capsys.readouterr().err
    assert not target.exists()


def test_missing_snapshot_is_a_clear_error(evidence, config, tmp_path, capsys):
    target = tmp_path / "out"
    missing = dict(evidence, source=tmp_path / "yok")
    assert predict(missing, config, target) == 1
    assert "Tahmin yazılmadı" in capsys.readouterr().err
    assert not target.exists()


def test_interrupted_write_leaves_no_manifest_and_is_not_a_record(
    evidence, config, tmp_path, monkeypatch
):
    original = Path.write_bytes

    def interrupted(path, data):
        if path.name == "report.md":
            raise KeyboardInterrupt
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    target = tmp_path / "kayit" / "tahmin_yarim"
    assert predict(evidence, config, target) == 130
    assert not (target / "manifest.json").exists()
    monkeypatch.undo()
    assert predict(evidence, config, tmp_path / "kayit" / "tahmin_tam") == 0


def test_command_does_not_load_database_or_network_layers(evidence, config, tmp_path):
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
raise SystemExit(main(['shadow-predict', '--snapshot', sys.argv[1],
                       '--config', sys.argv[2], '--output-dir', sys.argv[3]]))
"""
    target = tmp_path / "out"
    result = subprocess.run(
        [sys.executable, "-c", code, str(evidence["source"]), str(config), str(target)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((target / "manifest.json").read_bytes())["status"] == "complete"
