"""Günlük gölge akışı: bekleme, salt okunur görüntü, kayıt ve işletim hataları."""

import json
import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from filelock import FileLock

from app.ml import __main__ as cli
from app.ml import daily, shadow
from app.ml.dataset import read_snapshot
from app.ml.metrics import METRIC_RULES
from app.scrape_lock import ScrapeBusy, scrape_lock
from tests.support.ml import write_model_evidence, write_shadow_config


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    # Tam tekrar sayısı ölçüt testlerinde denetlenir; burada akış sınanır.
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    return write_model_evidence(tmp_path_factory.mktemp("daily_evidence"))


@pytest.fixture
def config(evidence, tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "loglar"))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(tmp_path / "scrape.lock"))
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://reader@localhost/example_test")
    return write_shadow_config(tmp_path / "shadow.json", evidence, tmp_path / "kayit")


@pytest.fixture
def capture(evidence, monkeypatch):
    calls = []

    def work(directory):
        # Üretimdeki snapshot komutunun yerine yalnız bu sınır taklit edilir;
        # tahmin ve dosya doğrulaması gerçek koddan geçer.
        with pytest.raises(ScrapeBusy):
            with scrape_lock():
                pass
        calls.append(directory)
        shutil.copytree(evidence["source"], directory)
        return 0

    monkeypatch.setattr(cli, "run_snapshot", work)
    return calls


@pytest.fixture
def clock(monkeypatch):
    elapsed, sleeps = [0.0], []
    monkeypatch.setattr(daily, "monotonic", lambda: elapsed[0])

    def sleep(seconds):
        sleeps.append(seconds)
        elapsed[0] += seconds

    monkeypatch.setattr(daily, "sleep", sleep)
    return elapsed, sleeps


def run(config, scheduled=False):
    return cli.main(
        ["shadow-daily", "--config", str(config)]
        + (["--scheduled"] if scheduled else [])
    )


def logs(tmp_path):
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((tmp_path / "loglar").glob("golge_*.log"))
    )


@pytest.mark.parametrize("scheduled", [False, True])
def test_daily_records_are_verified_and_second_run_preserves_them(
    config, capture, tmp_path, scheduled
):
    assert run(config, scheduled) == 0
    folders = list((tmp_path / "kayit").glob("tahmin_*"))
    assert len(folders) == 1
    manifest, rows = shadow.read_shadow_outputs(folders[0])
    assert rows and manifest["summary"]["predicted"] > 0
    _, digest = read_snapshot(capture[0])
    assert manifest["snapshot_sha256"] == digest
    before = {path.name: path.read_bytes() for path in folders[0].iterdir()}
    assert run(config, scheduled) == 0
    assert list((tmp_path / "kayit").glob("tahmin_*")) == folders
    assert {path.name: path.read_bytes() for path in folders[0].iterdir()} == before
    assert len(capture) == 2
    text = logs(tmp_path)
    assert "Yeni tahmin yok" in text and "Çıkış kodu: 0" in text
    assert ("zamanlanmış" if scheduled else "elle") in text
    with scrape_lock():
        pass


def test_windowless_daily_run_still_logs(config, capture, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert run(config, scheduled=True) == 0
    assert "Resmi kayıt klasörüne yazıldı" in logs(tmp_path)
    assert "Çıkış kodu: 0" in logs(tmp_path)


def test_missing_api_address_does_not_start_snapshot(
    config, capture, tmp_path, monkeypatch
):
    monkeypatch.delenv("API_DATABASE_URL")
    assert run(config) == 1
    assert not capture and not (tmp_path / "kayit").exists()
    assert "API_DATABASE_URL tanımlı değil" in logs(tmp_path)


@pytest.mark.parametrize("failure", ["sha", "model", "labels", "config"])
def test_invalid_evidence_never_produces_an_official_record(
    config, capture, tmp_path, failure
):
    settings = json.loads(config.read_bytes())
    if failure == "sha":
        settings["model_manifest_sha256"] = "2" * 64
    elif failure == "config":
        settings["unknown"] = True
    else:
        settings["evidence"][failure] = str(tmp_path / "yok")
    config.write_text(json.dumps(settings), encoding="utf-8")
    assert run(config) == 1
    assert not list((tmp_path / "kayit").glob("tahmin_*/manifest.json"))
    assert "Çıkış kodu: 1" in logs(tmp_path)


def test_log_failure_does_not_start_work(config, capture, tmp_path, monkeypatch):
    blocked = tmp_path / "dosya"
    blocked.write_text("koru", encoding="utf-8")
    monkeypatch.setenv("LOG_DIR", str(blocked))
    assert run(config) == 1
    assert not capture and blocked.read_text(encoding="utf-8") == "koru"


def test_snapshot_error_is_not_retried(config, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_snapshot", lambda path: calls.append(path) or 1)
    assert run(config) == 1
    assert len(calls) == 1
    assert not list((tmp_path / "kayit").glob("tahmin_*"))
    assert "Çıkış kodu: 1" in logs(tmp_path)


def test_db_running_status_waits_then_continues(tmp_path, monkeypatch, clock):
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(tmp_path / "scrape.lock"))
    statuses = iter([3, 0])
    assert daily.snapshot_when_idle(tmp_path / "veri", lambda _: next(statuses)) == 0
    assert clock[1] == [300]


def test_real_scrape_lock_is_waited_for_and_released(tmp_path, monkeypatch, clock):
    path = tmp_path / "scrape.lock"
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(path))
    lock = FileLock(str(path), timeout=0)
    lock.acquire()
    original_sleep = daily.sleep

    def release(seconds):
        original_sleep(seconds)
        lock.release()

    monkeypatch.setattr(daily, "sleep", release)
    try:
        assert daily.snapshot_when_idle(tmp_path / "veri", lambda _: 0) == 0
    finally:
        lock.release()
    assert clock[1] == [300]
    with scrape_lock(path):
        pass


@pytest.mark.parametrize("busy", ["scrape", "database"])
def test_wait_limit_is_90_minutes_and_never_starts_predictions(
    config, tmp_path, monkeypatch, clock, busy
):
    @contextmanager
    def blocked():
        raise ScrapeBusy("meşgul")
        yield

    if busy == "scrape":
        monkeypatch.setattr(daily, "scrape_lock", blocked)
    monkeypatch.setattr(cli, "run_snapshot", lambda _: 3)
    monkeypatch.setattr(
        cli, "run_shadow_predict", lambda *args: pytest.fail("Beklemeden sonra tahmin")
    )
    assert run(config) == 3
    assert sum(clock[1]) == 5400 and all(delay == 300 for delay in clock[1])
    assert not list((tmp_path / "kayit").glob("tahmin_*"))
    assert "90 dakikalık bekleme sınırı" in logs(tmp_path)
    assert "Çıkış kodu: 3" in logs(tmp_path)


def test_interrupt_while_waiting_is_logged_as_130(config, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "run_snapshot", lambda _: 3)

    def stop(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(daily, "sleep", stop)
    assert run(config) == 130
    assert "Çıkış kodu: 130" in logs(tmp_path)
    with scrape_lock():
        pass


def test_daily_and_manual_predict_share_the_entire_record_critical_section(
    evidence, config, capture, tmp_path, monkeypatch
):
    original = shadow.write_shadow_outputs
    competitor = tmp_path / "kayit" / "tahmin_rakip"
    codes = []

    def racing_write(*args):
        codes.append(
            cli.main(
                [
                    "shadow-predict",
                    "--snapshot",
                    str(evidence["source"]),
                    "--config",
                    str(config),
                    "--output-dir",
                    str(competitor),
                ]
            )
        )
        return original(*args)

    monkeypatch.setattr(shadow, "write_shadow_outputs", racing_write)
    assert run(config) == 0
    assert codes == [3] and not competitor.exists()
    assert len(list((tmp_path / "kayit").glob("tahmin_*/manifest.json"))) == 1
    monkeypatch.setattr(shadow, "write_shadow_outputs", original)
    assert run(config) == 0
    assert len(list((tmp_path / "kayit").glob("tahmin_*/manifest.json"))) == 1


def test_busy_record_writer_returns_3_and_can_be_retried(config, capture, tmp_path):
    with shadow.record_lock(tmp_path / "kayit"):
        assert run(config) == 3
    assert not list((tmp_path / "kayit").glob("tahmin_*"))
    assert "başka bir gölge tahmin kaydı" in logs(tmp_path)
    assert run(config) == 0


def test_daily_uses_actual_snapshot_command_with_test_read_role(
    world, api_db, config, tmp_path, monkeypatch
):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    before = world.execute("SELECT count(*) FROM collection_runs").fetchone()[0]
    assert run(config) == 0
    sources = list((tmp_path / "kayit" / "goruntuler").glob("veri_*"))
    assert len(sources) == 1
    snapshot, _ = read_snapshot(sources[0])
    assert len(snapshot.products) == 3
    assert world.execute("SELECT count(*) FROM collection_runs").fetchone()[0] == before


def test_daily_refuses_the_test_owner_account(world, config, tmp_path, monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    assert run(config) == 1
    assert "okuma hesabı değil" in logs(tmp_path)
    assert not list((tmp_path / "kayit").glob("goruntuler/veri_*"))


def test_task_installer_keeps_windowless_reversible_and_catchup_contract():
    path = Path(__file__).resolve().parents[1] / "scripts/golge_zamanlayici_kur.ps1"
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    text = path.read_text(encoding="utf-8-sig")
    assert "'.venv\\Scripts\\pythonw.exe'" in text
    assert "'-m app.ml shadow-daily --scheduled'" in text
    assert "-WorkingDirectory $root" in text
    assert "-Daily -At '11:00'" in text and "-StartWhenAvailable" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "-LogonType Interactive -RunLevel Limited" in text
    assert "'\\FiyatTakip\\'" in text and "'GolgeTahmin'" in text
    assert text.index("if ($Kaldir)") < text.index("'API_DATABASE_URL', 'User'")
    assert text.index("'API_DATABASE_URL', 'User'") < text.index(
        "\nRegister-ScheduledTask"
    )
