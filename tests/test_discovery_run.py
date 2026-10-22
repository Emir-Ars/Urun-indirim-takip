"""Keşfin çalıştırılması ve komut satırı.

Katalog ve rapor yazma, ayar dosyaları, eklenti yükleyici, çıkış kodları,
zamanlanmış keşif ve raporun siteye gitmeden uygulanması.
"""

import codecs
import io
import json
import re
import sys
import types
from pathlib import Path

import pytest

import app.discovery.service as discovery_service
from app.console import open_log
from app.contracts import (
    Catalog,
    DiscoveryConfig,
    DiscoveryEvidence,
    DiscoveryFact,
    DiscoveryReport,
    DiscoveryResult,
    utc_now,
)
from app.discovery.acceptance import decide
from app.discovery.__main__ import main as discovery_main
from app.discovery.base import BaseDiscovery
from app.discovery.hepsiburada import Discovery as HepsiburadaDiscovery
from app.discovery.service import (
    DiscoveryWriteError,
    ReportMismatch,
    _adapter,
    apply_report,
    run,
)
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scrape_lock import scrape_lock
from app.settings import Runtime, Settings
from tests.support.discovery import CATALOG, conflict_candidates, target

CONFIG = Path(__file__).parents[1] / "config"


def fixed_adapter(platform, found):
    """Ağa çıkmayan keşif adaptörü: verilen adayları tam tarama olarak döndürür."""

    class Fixed(BaseDiscovery):
        hosts = ["www.example.com"]

        def discover(self):
            decisions = []
            for candidate in found:
                facts = {
                    "source_id": candidate.platform_product_id,
                    "name": (
                        f"{candidate.brand} {candidate.model} "
                        f"{candidate.storage_gb} GB"
                    ),
                    "brand": candidate.brand,
                    "category": "Cep Telefonu",
                    "color": candidate.color,
                    "condition": "https://schema.org/NewCondition",
                }
                evidence = DiscoveryEvidence(
                    platform=platform,
                    platform_product_id=candidate.platform_product_id,
                    url=candidate.url,
                    captured_at=utc_now(),
                    html_sha256="0" * 64,
                    facts=[
                        DiscoveryFact(
                            field=key,
                            value=value,
                            owner_id=candidate.platform_product_id,
                            source="synthetic_test",
                        )
                        for key, value in facts.items()
                    ],
                )
                decisions.append(decide(evidence, self.target))
            return DiscoveryResult(
                platform=platform,
                target_key=self.target.key,
                candidates=found,
                decisions=decisions,
                complete=True,
            )

    Fixed.platform = platform
    return Fixed


def conflict_adapters():
    conflicting, valid = conflict_candidates()
    return {
        "trendyol": fixed_adapter("trendyol", [conflicting]),
        "hepsiburada": fixed_adapter("hepsiburada", [valid]),
    }


@pytest.fixture
def run_env(tmp_path, monkeypatch):
    """Gerçek run() için geçici katalog, discovery.json ve çalışma klasörü.

    Rapor tmp_path/data altına yazılır; gerçek config ve data klasörüne dokunulmaz.
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(CATALOG.read_text(encoding="utf-8"), encoding="utf-8")
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_text(
        json.dumps(
            {
                "targets": [
                    {"key": "apple_iphone_15", "brand": "Apple", "model": "iPhone 15"},
                    {
                        "key": "poco_x5_pro",
                        "brand": "POCO",
                        "model": "X5 Pro",
                        "active": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CATALOG_PATH", str(catalog_file))
    monkeypatch.setenv("DISCOVERY_PATH", str(discovery_file))
    monkeypatch.setenv("RUNTIME_PATH", str(CONFIG / "runtime.json"))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(tmp_path / "scrape.lock"))
    monkeypatch.chdir(tmp_path)
    return catalog_file


def test_run_writes_report_and_valid_link_despite_conflict(run_env, tmp_path):
    # Gerçek run(): kilitli/atomik katalog yazımı ve rapor, geçici klasörde.
    report = run(adapters=conflict_adapters())

    assert not report.complete
    assert [issue.reason for issue in report.rejected] == ["catalog_conflict"]
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    saved = Catalog.model_validate_json(run_env.read_text(encoding="utf-8"))
    original = Catalog.model_validate_json(CATALOG.read_text(encoding="utf-8"))
    assert len(saved.listings) == len(original.listings) + 1
    assert saved.products == original.products
    written = json.loads(
        (tmp_path / "data" / "discovery_report.json").read_text("utf-8")
    )
    assert written["rejected"][0]["reason"] == "catalog_conflict"


def test_run_writes_catalog_with_lf_line_endings(run_env):
    # Windows'ta metin kipi "\n"yi CRLF'ye çevirir; katalog her yazımda LF kalmalı
    # ki bütün satırlar Git'te değişmiş görünmesin. (Başlangıç dosyası Windows'ta
    # write_text ile CRLF yazılmıştır; yeniden yazım onu LF'ye çevirir.)
    run(adapters=conflict_adapters())
    written = run_env.read_bytes()
    assert b"\r\n" not in written
    assert written.endswith(b"}\n")


def test_dry_run_writes_report_but_not_catalog(run_env, tmp_path):
    before = run_env.read_bytes()
    report = run(dry_run=True, adapters=conflict_adapters())

    assert run_env.read_bytes() == before
    assert not (tmp_path / "catalog.json.lock").exists()  # katalog kilidi alınmadı
    # Önizleme yine ne ekleneceğini ve çakışmayı gösterir.
    assert report.dry_run is True
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    assert not report.complete
    written = json.loads(
        (tmp_path / "data" / "discovery_report.json").read_text("utf-8")
    )
    assert written["dry_run"] is True


def test_run_reads_catalog_and_config_saved_with_bom(run_env, tmp_path):
    # Windows'ta bazı düzenleyiciler UTF-8 dosyanın başına BOM koyar; json bunu
    # geçersiz sayardı. Hem önizleme hem kilit altındaki ikinci okuma kabul etmeli.
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_bytes(codecs.BOM_UTF8 + discovery_file.read_bytes())
    run_env.write_bytes(codecs.BOM_UTF8 + CATALOG.read_bytes())

    report = run(dry_run=True, adapters=conflict_adapters())
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    assert run_env.read_bytes().startswith(codecs.BOM_UTF8)  # önizleme yazmadı

    report = run(adapters=conflict_adapters())
    assert report.added_listings == ["hepsiburada_hbcv0000test01"]
    saved = Catalog.model_validate_json(run_env.read_text(encoding="utf-8"))
    assert "hepsiburada_hbcv0000test01" in {item.listing_id for item in saved.listings}


def test_settings_read_runtime_and_discovery_saved_with_bom(tmp_path, monkeypatch):
    runtime_file = tmp_path / "runtime.json"
    runtime_file.write_bytes(
        codecs.BOM_UTF8 + json.dumps({"request_interval_seconds": 5}).encode()
    )
    discovery_file = tmp_path / "discovery.json"
    discovery_file.write_bytes(
        codecs.BOM_UTF8
        + json.dumps(
            {"targets": [{"key": "apple_iphone_15", "brand": "Apple", "model": "Ç"}]},
            ensure_ascii=False,
        ).encode("utf-8")
    )
    monkeypatch.setenv("RUNTIME_PATH", str(runtime_file))
    monkeypatch.setenv("DISCOVERY_PATH", str(discovery_file))
    settings = Settings()
    assert settings.runtime().request_interval_seconds == 5
    assert settings.discovery().targets[0].model == "Ç"


def test_run_rejects_unknown_or_inactive_target(run_env):
    # adapters={}: hedef süzgeci bozulsa bile test siteye gidemez (KeyError olur).
    for key in ("olmayan_hedef", "poco_x5_pro"):
        with pytest.raises(ValueError, match="bulunamadı"):
            run(dry_run=True, target_key=key, adapters={})


def test_adapter_loads_only_valid_platform_modules(monkeypatch):
    assert _adapter("trendyol") is TrendyolDiscovery
    assert _adapter("hepsiburada") is HepsiburadaDiscovery
    for key in ("../x", "Trendyol", "app.discovery.trendyol"):
        with pytest.raises(ValueError, match="Geçersiz"):
            _adapter(key)
    with pytest.raises(ImportError):
        _adapter("yok_platform")
    # Discovery adı olmayan modül de (ör. ortak taban) sözleşme hatasıdır; komut
    # bunu çıkış 1'e çevirir, traceback basmaz.
    for key in ("base", "matching"):
        with pytest.raises(ValueError, match="sözleşmeye uymuyor"):
            _adapter(key)
    # Discovery adı olan ama sözleşmeye uymayan (sınıf değil / soyut) modül.
    for implementation in (object(), object, BaseDiscovery):
        monkeypatch.setitem(
            sys.modules,
            "app.discovery.sahte",
            types.SimpleNamespace(Discovery=implementation),
        )
        with pytest.raises(ValueError, match="sözleşmeye uymuyor"):
            _adapter("sahte")


def test_adapter_checks_key_before_import(monkeypatch):
    imports = []

    def load(name):
        imports.append(name)
        return types.SimpleNamespace(Discovery=TrendyolDiscovery)

    monkeypatch.setattr(discovery_service.importlib, "import_module", load)
    for key in ("../x", "Trendyol", "app.discovery.trendyol", "", "1trendyol"):
        with pytest.raises(ValueError, match="Geçersiz"):
            _adapter(key)
    assert imports == []


def test_adapter_returns_class_without_calling_constructor(monkeypatch):
    calls = []

    class FailingDiscovery(BaseDiscovery):
        def __init__(self, target, config, runtime):
            calls.append((target, config, runtime))
            raise RuntimeError("Yerel keşif kurulum hata taklidi")

        def discover(self):
            raise AssertionError("Yükleme sırasında keşif başlamamalı")

    monkeypatch.setitem(
        sys.modules,
        "app.discovery.sahte",
        types.SimpleNamespace(Discovery=FailingDiscovery),
    )
    implementation = _adapter("sahte")
    assert implementation is FailingDiscovery
    assert calls == []
    arguments = (target(), DiscoveryConfig(targets=[]), Runtime())
    with pytest.raises(RuntimeError, match="kurulum hata taklidi"):
        implementation(*arguments)
    assert len(calls) == 1
    assert all(actual is expected for actual, expected in zip(calls[0], arguments))


@pytest.mark.parametrize("error_type", [ImportError, RuntimeError, KeyboardInterrupt])
def test_adapter_preserves_import_error_and_ctrl_c(monkeypatch, error_type):
    failure = error_type("Yerel keşif yükleme hata taklidi")
    imports = []

    def load(name):
        imports.append(name)
        raise failure

    monkeypatch.setattr(discovery_service.importlib, "import_module", load)
    with pytest.raises(error_type) as error:
        _adapter("sahte")
    assert error.value is failure
    assert imports == ["app.discovery.sahte"]


@pytest.mark.parametrize("scheduled", [False, True], ids=["manual", "scheduled"])
@pytest.mark.parametrize(
    "failure",
    [
        "missing_module",
        "invalid_class",
        "import_runtime_error",
        "constructor_value_error",
        "constructor_runtime_error",
        "constructor_type_error",
        "constructor_interrupt",
    ],
)
def test_discovery_loader_failure_preserves_files_and_releases_lock(
    run_env, tmp_path, monkeypatch, capsys, scheduled, failure
):
    catalog_before = run_env.read_bytes()
    config_path = tmp_path / "discovery.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["targets"][1]["active"] = True
    config_path.write_text(json.dumps(config), encoding="utf-8")
    previous_report = tmp_path / "data" / "discovery_report.json"
    previous_report.parent.mkdir(parents=True)
    previous_report.write_bytes(b"previous report")
    report_dir = tmp_path / "data" / "discovery"
    log_dir = tmp_path / "data" / "logs"
    monkeypatch.setenv("DISCOVERY_REPORT_DIR", str(report_dir))
    monkeypatch.setenv("LOG_DIR", str(log_dir))
    events = []
    error_types = {
        "missing_module": ModuleNotFoundError,
        "import_runtime_error": RuntimeError,
        "constructor_value_error": ValueError,
        "constructor_runtime_error": RuntimeError,
        "constructor_type_error": TypeError,
        "constructor_interrupt": KeyboardInterrupt,
    }
    failure_error = error_types.get(failure, ValueError)(
        "Yerel hepsiburada adaptör hata taklidi"
    )

    class HealthyDiscovery(BaseDiscovery):
        platform = "trendyol"

        def __init__(self, target, config, runtime):
            self.target = target
            events.append(("create", self.platform, target.key))

        def discover(self):
            events.append(("discover", self.platform, self.target.key))
            return DiscoveryResult(
                platform=self.platform,
                target_key=self.target.key,
                candidates=[],
                complete=True,
            )

        def close(self):
            events.append(("close", self.platform, self.target.key))

    class HealthyHepsiburada(HealthyDiscovery):
        platform = "hepsiburada"

    class FailingDiscovery(HealthyHepsiburada):
        def __init__(self, target, config, runtime):
            events.append(("create", self.platform, target.key))
            raise failure_error

    real_import = discovery_service.importlib.import_module
    failing = True

    def load(name):
        if name == "app.discovery.trendyol":
            events.append(("load", "trendyol"))
            return types.SimpleNamespace(Discovery=HealthyDiscovery)
        if name == "app.discovery.hepsiburada":
            events.append(("load", "hepsiburada"))
            if failing and failure in ("missing_module", "import_runtime_error"):
                raise failure_error
            implementation = HealthyHepsiburada
            if failing:
                implementation = (
                    object if failure == "invalid_class" else FailingDiscovery
                )
            return types.SimpleNamespace(Discovery=implementation)
        return real_import(name)

    monkeypatch.setattr(discovery_service.importlib, "import_module", load)
    known_error = failure in (
        "missing_module",
        "invalid_class",
        "constructor_value_error",
    )
    argv = ["--scheduled", "--dry-run"] if scheduled else []
    if failure == "constructor_interrupt" or (not scheduled and not known_error):
        with pytest.raises(type(failure_error)) as error:
            discovery_main(argv)
        assert error.value is failure_error
    else:
        assert discovery_main(argv) == 1
    output = capsys.readouterr()
    if known_error:
        assert "Keşif başlatılamadı" in output.err and "Traceback" not in output.err
    elif scheduled and failure != "constructor_interrupt":
        assert "Traceback" in output.err
        assert f"{type(failure_error).__name__}: {failure_error}" in output.err
    else:
        assert "Keşif başlatılamadı" not in output.err
    expected_events = [
        ("load", "trendyol"),
        ("create", "trendyol", "apple_iphone_15"),
        ("discover", "trendyol", "apple_iphone_15"),
        ("close", "trendyol", "apple_iphone_15"),
        ("load", "hepsiburada"),
    ]
    if failure.startswith("constructor_"):
        expected_events.append(("create", "hepsiburada", "apple_iphone_15"))
    assert events == expected_events
    assert run_env.read_bytes() == catalog_before
    assert previous_report.read_bytes() == b"previous report"
    assert not list(report_dir.glob("*.json"))
    if scheduled:
        [log] = log_dir.glob("kesif_*.log")
        text = log.read_text(encoding="utf-8")
        assert text.startswith("Zamanlanmış keşif (önizleme)")
        assert all(line in text for line in output.err.splitlines())
        if failure == "constructor_interrupt":
            assert "Çıkış kodu:" not in text
        else:
            assert text.rstrip().endswith("Çıkış kodu: 1")
    else:
        assert not log_dir.exists()
    with scrape_lock(tmp_path / "scrape.lock"):
        pass

    failing = False
    events.clear()
    assert discovery_main(["--dry-run"]) == 0
    assert [event for event in events if event[0] == "close"] == [
        ("close", "trendyol", "apple_iphone_15"),
        ("close", "hepsiburada", "apple_iphone_15"),
        ("close", "trendyol", "poco_x5_pro"),
        ("close", "hepsiburada", "poco_x5_pro"),
    ]
    report = DiscoveryReport.model_validate_json(previous_report.read_text("utf-8"))
    assert report.complete and len(report.results) == 4
    assert run_env.read_bytes() == catalog_before
    with scrape_lock(tmp_path / "scrape.lock"):
        pass


@pytest.mark.parametrize("complete, code", [(True, 0), (False, 2)])
def test_discovery_cli_exits_0_when_complete_and_2_when_partial(
    run_env, monkeypatch, capsys, complete, code
):
    calls = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return DiscoveryReport(complete=complete, dry_run=kwargs["dry_run"], results=[])

    monkeypatch.setattr("app.discovery.__main__.run", fake_run)
    assert discovery_main(["--dry-run", "--target", "apple_iphone_15"]) == code
    # Elle çalıştırmada rapor yolu verilmez: bugünkü sabit yol kullanılır.
    assert calls == [
        {"dry_run": True, "target_key": "apple_iphone_15", "report_path": None}
    ]
    printed = json.loads(capsys.readouterr().out)
    assert printed["complete"] is complete and printed["dry_run"] is True


class RecordingStream(io.StringIO):
    """reconfigure çağrılarını kaydeden sahte stdout/stderr."""

    def __init__(self):
        super().__init__()
        self.reconfigured = []

    def reconfigure(self, **kwargs):
        self.reconfigured.append(kwargs)


def test_discovery_cli_switches_output_to_utf8(run_env, monkeypatch):
    # Çıktı dosyaya yönlendirildiğinde Windows kod sayfası Türkçe karakterleri
    # bozardı; hata çıktısı da dahil iki akış UTF-8'e ayarlanır.
    monkeypatch.setattr(
        "app.discovery.__main__.run",
        lambda **kwargs: DiscoveryReport(complete=True, dry_run=True, results=[]),
    )
    out, err = RecordingStream(), RecordingStream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    assert discovery_main(["--dry-run"]) == 0
    expected = [{"encoding": "utf-8", "errors": "backslashreplace"}]
    assert out.reconfigured == expected and err.reconfigured == expected
    assert json.loads(out.getvalue())["complete"] is True

    # pythonw.exe altında akışlar hiç yoktur (None); komut yine çalışır.
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert discovery_main(["--dry-run"]) == 0


def test_discovery_cli_exits_1_for_unknown_target(run_env, capsys):
    # Gerçek run(): hedef bulunamayınca hiçbir adaptör kurulmadan hata verir.
    assert discovery_main(["--target", "olmayan_hedef", "--dry-run"]) == 1
    error = capsys.readouterr().err
    assert "Keşif başlatılamadı" in error and "olmayan_hedef" in error


def test_real_config_files_match_contracts():
    # Kullanıcı discovery.json'u elle düzenler: JSON yazım hatası, tekrarlanan hedef
    # anahtarı veya geçersiz network değeri canlı keşiften önce burada yakalanır.
    # Yalnız okunur; gerçek katalog keşifle büyüdüğü için sayılar denetlenmez.
    config = DiscoveryConfig.model_validate_json(
        (CONFIG / "discovery.json").read_text(encoding="utf-8")
    )
    catalog = Catalog.model_validate_json(
        (CONFIG / "catalog.json").read_text(encoding="utf-8")
    )
    assert config.targets and catalog.products and catalog.listings
    # Her etkin platformun keşif modülü vardır (yalnız içe aktarılır, istek yok).
    for platform in catalog.platforms:
        if platform.active:
            assert issubclass(_adapter(platform.key), BaseDiscovery)


# --- Zamanlanmış keşif ------------------------------------------------------------


def clean_adapters():
    """Çakışmasız tek geçerli aday: tarama tam, rapor temiz."""
    _, valid = conflict_candidates()
    return {
        "trendyol": fixed_adapter("trendyol", []),
        "hepsiburada": fixed_adapter("hepsiburada", [valid]),
    }


@pytest.fixture
def scan_env(run_env, monkeypatch):
    """Gerçek komut akışı ağsız: platform adaptörleri sabit adaylarla değiştirilir."""
    adapters = conflict_adapters()
    monkeypatch.setattr(
        "app.discovery.service._adapter", lambda platform: adapters[platform]
    )
    return run_env


def scheduled_files(tmp_path):
    [log] = (tmp_path / "data" / "logs").glob("kesif_*.log")
    [report] = (tmp_path / "data" / "discovery").glob("kesif_*.json")
    return log, report


def test_open_log_uses_prefix_and_utf8(tmp_path):
    with open_log(tmp_path / "logs", "kesif") as log:
        log.write("Tükendi · çıkış\n")
    [path] = (tmp_path / "logs").glob("*.log")
    assert re.fullmatch(r"kesif_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.log", path.name)
    assert path.read_text(encoding="utf-8") == "Tükendi · çıkış\n"


def test_scheduled_discovery_writes_log_and_dated_report(scan_env, tmp_path):
    catalog_before = scan_env.read_bytes()
    assert discovery_main(["--scheduled", "--dry-run"]) == 2  # çakışma: kısmi
    log, report_file = scheduled_files(tmp_path)
    # Log ve rapor aynı zaman damgasını taşır.
    assert log.stem == report_file.stem
    text = log.read_text(encoding="utf-8")
    assert text.startswith("Zamanlanmış keşif (önizleme) · ")
    assert "yeni sayfa 1 (hepsiburada 1)" in text and "çakışma 1" in text
    assert f"Rapor: {Path('data') / 'discovery' / report_file.name}" in text
    assert '"results"' not in text  # tam JSON loga değil rapor dosyasına yazılır
    assert text.rstrip().endswith("Çıkış kodu: 2")
    report = DiscoveryReport.model_validate_json(report_file.read_text("utf-8"))
    assert report.dry_run is True and report.added_listings == [
        "hepsiburada_hbcv0000test01"
    ]
    assert scan_env.read_bytes() == catalog_before  # önizleme kataloğa yazmaz
    # Zamanlanmış çalışma elle çalıştırmanın sabit raporunu ezmez.
    assert not (tmp_path / "data" / "discovery_report.json").exists()


def test_scheduled_discovery_exits_0_when_scan_is_complete(
    run_env, tmp_path, monkeypatch
):
    adapters = clean_adapters()
    monkeypatch.setattr(
        "app.discovery.service._adapter", lambda platform: adapters[platform]
    )
    assert discovery_main(["--scheduled", "--dry-run"]) == 0
    log, _ = scheduled_files(tmp_path)
    assert log.read_text(encoding="utf-8").rstrip().endswith("Çıkış kodu: 0")


def test_scheduled_discovery_requires_dry_run(scan_env, tmp_path, monkeypatch):
    started = []
    monkeypatch.setattr(
        "app.discovery.__main__.run", lambda **kwargs: started.append(kwargs)
    )
    with pytest.raises(SystemExit) as stop:
        discovery_main(["--scheduled"])
    assert stop.value.code == 2
    # Ne log açıldı ne tarama başladı.
    assert started == [] and not (tmp_path / "data").exists()


def test_scheduled_discovery_without_console_still_logs(
    scan_env, tmp_path, monkeypatch
):
    # pythonw.exe (Görev Zamanlayıcı) altında ekran akışları hiç yoktur.
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert discovery_main(["--scheduled", "--dry-run"]) == 2
    log, _ = scheduled_files(tmp_path)
    assert "Özet: " in log.read_text(encoding="utf-8")


def test_busy_scheduled_discovery_is_logged(run_env, tmp_path, monkeypatch):
    def must_not_run(**_):
        raise AssertionError("Kilit meşgulken keşif başlamamalıydı")

    monkeypatch.setattr("app.discovery.__main__.run", must_not_run)
    with scrape_lock(tmp_path / "scrape.lock"):
        assert discovery_main(["--scheduled", "--dry-run"]) == 3
    log = next((tmp_path / "data" / "logs").glob("kesif_*.log"))
    text = log.read_text(encoding="utf-8")
    assert "Keşif başlatılmadı" in text
    assert text.rstrip().endswith("Çıkış kodu: 3")
    assert not list((tmp_path / "data" / "discovery").glob("*.json"))


def test_scheduled_discovery_program_error_is_logged_with_exit_1(
    run_env, tmp_path, monkeypatch
):
    def crash(**_):
        raise TypeError("beklenmeyen program hatası")

    monkeypatch.setattr("app.discovery.__main__.run", crash)
    assert discovery_main(["--scheduled", "--dry-run"]) == 1
    log = next((tmp_path / "data" / "logs").glob("kesif_*.log"))
    text = log.read_text(encoding="utf-8")
    assert "TypeError: beklenmeyen program hatası" in text
    assert text.rstrip().endswith("Çıkış kodu: 1")


def test_scheduled_discovery_does_not_start_when_log_cannot_be_opened(
    run_env, tmp_path, monkeypatch, capsys
):
    # LOG_DIR bir dosyayı gösterir: klasör oluşturulamaz (OSError).
    not_a_dir = tmp_path / "logs"
    not_a_dir.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOG_DIR", str(not_a_dir))
    started = []
    monkeypatch.setattr(
        "app.discovery.__main__.run", lambda **kwargs: started.append(kwargs)
    )
    assert discovery_main(["--scheduled", "--dry-run"]) == 1
    assert "Log dosyası açılamadı" in capsys.readouterr().err
    assert started == []


def test_scheduled_discovery_fails_before_scanning_when_report_folder_is_unusable(
    run_env, tmp_path, monkeypatch
):
    # Yazılamayan rapor klasörü ~35 dakikalık taramadan sonra değil, hemen anlaşılır.
    not_a_dir = tmp_path / "rapor"
    not_a_dir.write_text("", encoding="utf-8")
    monkeypatch.setenv("DISCOVERY_REPORT_DIR", str(not_a_dir))
    started = []
    monkeypatch.setattr(
        "app.discovery.__main__.run", lambda **kwargs: started.append(kwargs)
    )
    assert discovery_main(["--scheduled", "--dry-run"]) == 1
    log = next((tmp_path / "data" / "logs").glob("kesif_*.log"))
    text = log.read_text(encoding="utf-8")
    assert "Keşif başlatılamadı" in text
    assert text.rstrip().endswith("Çıkış kodu: 1")
    assert started == []


def test_report_write_failure_after_scan_is_not_reported_as_start_failure(
    run_env, tmp_path, monkeypatch, capsys
):
    # Tarama bittikten sonra rapor yazılamazsa mesaj "başlatılamadı" demez: tarama
    # yapılmış ve sonucu kaybolmuştur. Çıkış kodu yine 1'dir.
    adapters = clean_adapters()
    monkeypatch.setattr(
        "app.discovery.service._adapter", lambda platform: adapters[platform]
    )
    # Rapor yolu bir klasör olduğu için dosya yazılamaz (OSError).
    (tmp_path / "data" / "discovery_report.json").mkdir(parents=True)
    with pytest.raises(DiscoveryWriteError):
        run(dry_run=True)
    assert discovery_main(["--dry-run"]) == 1
    error = capsys.readouterr().err
    assert "Tarama bitti ama sonuç yazılamadı" in error
    assert "Keşif başlatılamadı" not in error


def test_catalog_write_failure_after_scan_is_reported_and_logged(
    scan_env, tmp_path, monkeypatch
):
    def refuse(*_, **__):
        raise OSError("disk dolu")

    monkeypatch.setattr("app.discovery.service._atomic_catalog", refuse)
    catalog_before = scan_env.read_bytes()
    with pytest.raises(DiscoveryWriteError, match="disk dolu"):
        run()
    assert scan_env.read_bytes() == catalog_before  # yarım katalog kalmaz
    saved = DiscoveryReport.model_validate_json(
        (tmp_path / "data" / "discovery_report.json").read_bytes()
    )
    assert (
        saved.application.state == "prepared"
    )  # yazılmayan katalog için karar izi korunur


def test_scheduled_discovery_logs_unwritten_result_with_exit_1(
    run_env, tmp_path, monkeypatch
):
    def unwritable(**_):
        raise DiscoveryWriteError("disk dolu")

    monkeypatch.setattr("app.discovery.__main__.run", unwritable)
    assert discovery_main(["--scheduled", "--dry-run"]) == 1
    [log] = (tmp_path / "data" / "logs").glob("kesif_*.log")
    text = log.read_text(encoding="utf-8")
    assert "Tarama bitti ama sonuç yazılamadı: disk dolu" in text
    assert "Keşif başlatılamadı" not in text
    assert text.rstrip().endswith("Çıkış kodu: 1")


def test_report_time_round_trips_and_old_reports_still_parse(run_env):
    report = run(dry_run=True, adapters=conflict_adapters())
    # Saat dilimli olmalı: UTC'de utcoffset() sıfır süredir, None değil.
    assert report.generated_at is not None
    assert report.generated_at.utcoffset() is not None
    saved = Path("data/discovery_report.json").read_text(encoding="utf-8")
    assert DiscoveryReport.model_validate_json(saved).generated_at == (
        report.generated_at
    )
    # Alan eklenmeden önce yazılmış rapor (generated_at yok) okunmaya devam eder.
    old = json.loads(saved)
    del old["generated_at"]
    assert DiscoveryReport.model_validate_json(json.dumps(old)).generated_at is None


# --- Raporun siteye gitmeden uygulanması -------------------------------------------


def make_preview(tmp_path, adapters):
    path = tmp_path / "onizleme.json"
    run(dry_run=True, adapters=adapters, report_path=path)
    return path


def test_apply_report_adds_previewed_listings_without_going_to_the_sites(
    run_env, tmp_path, monkeypatch, capsys
):
    preview = make_preview(tmp_path, conflict_adapters())

    def must_not_run(*_, **__):
        raise AssertionError("--apply-report siteye gitmemeli")

    monkeypatch.setattr("app.discovery.service._adapter", must_not_run)
    monkeypatch.setattr("app.discovery.__main__.run", must_not_run)
    # Siteye gitmediği için fiyat turu ya da başka bir keşif sürerken de çalışır.
    with scrape_lock(tmp_path / "scrape.lock"):
        assert discovery_main(["--apply-report", str(preview)]) == 2  # çakışma var
    out = capsys.readouterr().out
    assert "önizleme zamanı: " in out
    assert "+ sayfa hepsiburada_hbcv0000test01" in out
    assert "yazılmadı (çakışma)" in out
    saved = Catalog.model_validate_json(run_env.read_text(encoding="utf-8"))
    assert "hepsiburada_hbcv0000test01" in {item.listing_id for item in saved.listings}
    written = run_env.read_bytes()
    assert b"\r\n" not in written and not written.startswith(codecs.BOM_UTF8)


def test_apply_report_gives_the_same_catalog_as_a_live_run(run_env, tmp_path):
    preview = make_preview(tmp_path, conflict_adapters())
    assert discovery_main(["--apply-report", str(preview)]) == 2
    applied = run_env.read_bytes()
    # Aynı başlangıç katalogundan canlı yazma bayt bayt aynı sonucu vermeli.
    run_env.write_bytes(CATALOG.read_bytes())
    run(adapters=conflict_adapters(), report_path=tmp_path / "canli.json")
    assert run_env.read_bytes() == applied


def test_applying_a_report_twice_adds_and_writes_nothing(
    run_env, tmp_path, monkeypatch, capsys
):
    preview = make_preview(tmp_path, clean_adapters())
    assert discovery_main(["--apply-report", str(preview)]) == 0
    first = run_env.read_bytes()
    assert "+ sayfa hepsiburada_hbcv0000test01" in capsys.readouterr().out

    def must_not_write(*_, **__):
        raise AssertionError("Eklenecek bir şey yokken dosya yazılmamalı")

    monkeypatch.setattr("app.discovery.service._atomic_catalog", must_not_write)
    assert discovery_main(["--apply-report", str(preview)]) == 0
    assert "Katalog değişmedi" in capsys.readouterr().out
    assert run_env.read_bytes() == first


def test_apply_refuses_a_report_that_is_not_a_preview(run_env, tmp_path, capsys):
    live = tmp_path / "canli.json"
    run(adapters=clean_adapters(), report_path=live)  # kataloğa yazan çalışma
    after_live = run_env.read_bytes()
    assert discovery_main(["--apply-report", str(live)]) == 1
    assert "önizleme" in capsys.readouterr().err
    assert run_env.read_bytes() == after_live


def test_apply_refuses_additions_the_preview_did_not_show(run_env, tmp_path, capsys):
    preview = make_preview(tmp_path, clean_adapters())
    data = json.loads(preview.read_text(encoding="utf-8"))
    # Önizleme anında sayfa katalogda varmış, sonradan çıkmış gibi: bugünkü ekleme
    # önizlemede görünmeyen bir şey olur.
    data["added_listings"] = []
    preview.write_text(json.dumps(data), encoding="utf-8")
    before = run_env.read_bytes()
    assert discovery_main(["--apply-report", str(preview)]) == 1
    assert "önizlemeden sonra değişmiş" in capsys.readouterr().err
    assert run_env.read_bytes() == before
    with pytest.raises(ReportMismatch):
        apply_report(
            DiscoveryReport.model_validate_json(preview.read_text("utf-8")), run_env
        )


def test_apply_rejects_foreign_host_and_leaves_catalog_unchanged(
    run_env, tmp_path, capsys
):
    preview = make_preview(tmp_path, clean_adapters())
    data = json.loads(preview.read_text(encoding="utf-8"))
    for result in data["results"]:
        for candidate in result["candidates"]:
            candidate["url"] = "https://www.example.com/telefon-p-HBCV0000TEST01"
    preview.write_text(json.dumps(data), encoding="utf-8")
    before = run_env.read_bytes()
    assert discovery_main(["--apply-report", str(preview)]) == 1
    assert "Rapor uygulanamadı" in capsys.readouterr().err
    assert run_env.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "broken", "trace_wrapper"])
def test_apply_rejects_unreadable_reports(run_env, tmp_path, capsys, kind):
    path = tmp_path / "rapor.json"
    if kind == "broken":
        path.write_text("{ bozuk", encoding="utf-8")
    elif kind == "trace_wrapper":
        # live_discovery_check.py --trace çıktısı: rapor bir sarmalın içindedir.
        report = make_preview(tmp_path, clean_adapters())
        wrapped = {"report": json.loads(report.read_text("utf-8")), "traces": []}
        path.write_text(json.dumps(wrapped), encoding="utf-8")
    before = run_env.read_bytes()
    assert discovery_main(["--apply-report", str(path)]) == 1
    error = capsys.readouterr().err
    assert ("Rapor okunamadı" if kind == "missing" else "geçerli bir keşif raporu") in (
        error
    )
    assert run_env.read_bytes() == before


def test_apply_reads_a_report_saved_with_bom(run_env, tmp_path):
    preview = make_preview(tmp_path, clean_adapters())
    preview.write_bytes(codecs.BOM_UTF8 + preview.read_bytes())
    assert discovery_main(["--apply-report", str(preview)]) == 0


@pytest.mark.parametrize(
    "extra", [["--dry-run"], ["--target", "apple_iphone_15"], ["--scheduled"]]
)
def test_apply_report_cannot_be_combined_with_scan_options(run_env, tmp_path, extra):
    preview = make_preview(tmp_path, clean_adapters())
    before = run_env.read_bytes()
    with pytest.raises(SystemExit) as stop:
        discovery_main(["--apply-report", str(preview), *extra])
    assert stop.value.code == 2
    assert run_env.read_bytes() == before
