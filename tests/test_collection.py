"""Fiyat toplama turu: sahte scraper'larla (internete çıkmaz), gerçek PostgreSQL'de."""

import json
import os

import pytest

import app.collection.service as service
from app.collection.__main__ import main
from app.collection.service import CollectionError, RunInProgress, collect
from app.database import runs
from app.database.catalog_sync import CatalogConflict, read_catalog, sync_catalog
from app.database.connection import connect
from app.database.migrate import migrate
from app.discovery.__main__ import main as discovery_main
from app.scrape_lock import scrape_lock
from app.scraper.base import BaseScraper
from app.scraper.http import FetchError
from app.settings import Runtime

PLATFORMS = [
    {"key": "trendyol", "name": "Trendyol", "hosts": ["www.trendyol.com"]},
    {"key": "hepsiburada", "name": "Hepsiburada", "hosts": ["www.hepsiburada.com"]},
]
PRODUCTS = [
    {
        "product_id": 1,
        "product_key": "apple_iphone_15_128gb",
        "brand": "Apple",
        "model": "iPhone 15",
        "storage_gb": 128,
    },
    {
        "product_id": 2,
        "product_key": "poco_x6_pro_512gb",
        "brand": "POCO",
        "model": "X6 Pro",
        "storage_gb": 512,
    },
]
HOSTS = {"trendyol": "www.trendyol.com", "hepsiburada": "www.hepsiburada.com"}


def listing(listing_id, product_id=1, active=True):
    platform = listing_id.split("_")[0]
    return {
        "listing_id": listing_id,
        "product_id": product_id,
        "platform": platform,
        "url": f"https://{HOSTS[platform]}/urun-p-{listing_id.split('_')[1]}",
        "active": active,
    }


LISTINGS = [
    listing("trendyol_1"),
    listing("trendyol_2"),
    listing("trendyol_3"),
    listing("hepsiburada_4"),
    listing("hepsiburada_5"),
    listing("hepsiburada_6"),
    listing("trendyol_7", product_id=2),
    listing("trendyol_8", active=False),
]

OFFER = {
    "current_price": 5724900,
    "seller_name": "Satıcı A",
    "seller_rating": 9.5,
    "seller_rating_scale": 10.0,
    "stock_status": "Stokta Var",
}
SOLD_OUT = {"current_price": None, "stock_status": "Tükendi"}
BEHAVIOURS = {
    "trendyol_1": OFFER,
    "trendyol_2": {**OFFER, "current_price": 5699900, "stock_status": "Kritik Stok"},
    "trendyol_3": SOLD_OUT,
    "hepsiburada_4": FetchError("blocked", "Kaynak HTTP 403"),
    "hepsiburada_5": ValueError("beklenmeyen biçim"),
    "hepsiburada_6": RuntimeError("scraper içinde hata"),
    "trendyol_7": OFFER,
}


class FakeScrapers:
    """create_scraper yerine geçer; her sayfa için verilen davranışı uygular.

    Davranış: gözlem alanları (dict), fırlatılacak istisna ya da gözlemi kendisi
    üreten bir fonksiyon.
    """

    def __init__(self, behaviours, close_error=None):
        self.behaviours = behaviours
        self.close_error = close_error
        self.created = self.closed = 0

    def __call__(self, platform, hosts, runtime):
        self.created += 1
        return _FakeScraper(self)


class _FakeScraper:
    def __init__(self, owner):
        self.owner = owner

    def fetch(self, item):
        action = self.owner.behaviours[item.listing_id]
        if isinstance(action, BaseException):
            raise action
        if callable(action):
            return action(item)
        return BaseScraper.observation(item, **action)

    def close(self):
        self.owner.closed += 1
        if self.owner.close_error:
            raise self.owner.close_error


def write_catalog(path, listings=LISTINGS):
    path.write_text(
        json.dumps(
            {"platforms": PLATFORMS, "products": PRODUCTS, "listings": listings}
        ),
        encoding="utf-8",
    )
    return path


def run_collect(conn, catalog_path, behaviours=BEHAVIOURS, **kwargs):
    lines = []
    report = collect(
        conn,
        catalog_path,
        Runtime(),
        create=FakeScrapers(behaviours),
        out=lines.append,
        **kwargs,
    )
    return report, lines


def results(conn, run_id):
    return {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT listing_id, outcome, error_code, current_price, stock_status,"
            " checked_at IS NOT NULL FROM listing_checks WHERE run_id = %s",
            (run_id,),
        )
    }


def run_row(conn, run_id):
    return conn.execute(
        "SELECT status, trigger, planned_count, finished_at IS NOT NULL, note"
        " FROM collection_runs WHERE run_id = %s",
        (run_id,),
    ).fetchone()


def run_count(conn):
    return conn.execute("SELECT count(*) FROM collection_runs").fetchone()[0]


@pytest.fixture
def migrated(db):
    migrate(db)
    return db


@pytest.fixture
def catalog_path(tmp_path):
    return write_catalog(tmp_path / "catalog.json")


# --- Tur akışı --------------------------------------------------------------------


def test_each_result_is_recorded_and_run_completes(migrated, catalog_path):
    report, lines = run_collect(migrated, catalog_path)
    assert report.planned == 7  # trendyol_8 pasif, planlanmaz
    assert results(migrated, report.run_id) == {
        "trendyol_1": ("offer", None, 5724900, "Stokta Var", True),
        "trendyol_2": ("offer", None, 5699900, "Kritik Stok", True),
        "trendyol_3": ("sold_out", None, None, "Tükendi", True),
        "hepsiburada_4": ("error", "blocked", None, None, True),
        "hepsiburada_5": ("error", "validation", None, None, True),
        "hepsiburada_6": ("error", "unexpected", None, None, True),
        "trendyol_7": ("offer", None, 5724900, "Stokta Var", True),
    }
    assert run_row(migrated, report.run_id)[:4] == ("completed", "manual", 7, True)
    assert report.summary.outcomes == {"error": 3, "offer": 3, "sold_out": 1}
    assert report.summary.error_codes == {
        "blocked": 1,
        "unexpected": 1,
        "validation": 1,
    }
    assert any("57.249,00 TL" in line for line in lines)


def test_every_scraper_is_closed(migrated, catalog_path):
    scrapers = FakeScrapers(BEHAVIOURS)
    collect(migrated, catalog_path, Runtime(), create=scrapers, out=lambda _: None)
    assert scrapers.created == scrapers.closed == 7


def test_ctrl_c_interrupts_run_and_keeps_written_results(migrated, catalog_path):
    behaviours = {**BEHAVIOURS, "trendyol_2": KeyboardInterrupt()}
    with pytest.raises(KeyboardInterrupt):
        run_collect(migrated, catalog_path, behaviours)
    run_id = migrated.execute("SELECT max(run_id) FROM collection_runs").fetchone()[0]
    status, _, planned, finished, note = run_row(migrated, run_id)
    assert (status, planned, finished) == ("interrupted", 7, True)
    assert note == "Durduruldu: KeyboardInterrupt"
    checked = results(migrated, run_id)
    assert checked["trendyol_1"][0] == "offer"
    # Bakılamayan sayfalar sonuçsuz ("planlandı") kalır; uydurma sonuç yok.
    assert [v[0] for k, v in checked.items() if k != "trendyol_1"] == [None] * 6
    # Sonraki tur normal başlar.
    report, _ = run_collect(migrated, catalog_path)
    assert run_row(migrated, report.run_id)[0] == "completed"


def test_stale_running_run_is_closed_by_next_run(migrated, catalog_path):
    catalog, digest = read_catalog(catalog_path)
    sync_catalog(migrated, catalog)
    stale = runs.start_run(
        migrated,
        trigger="scheduled",
        catalog_sha256=digest,
        listings=[("trendyol_1", 1)],
    )
    report, lines = run_collect(migrated, catalog_path)
    assert report.closed_stale == [stale]
    status, _, _, finished, note = run_row(migrated, stale)
    assert (status, finished) == ("interrupted", True)
    assert "Yarıda kaldı" in note
    assert run_row(migrated, report.run_id)[0] == "completed"
    assert any("Yarıda kalmış" in line for line in lines)


def test_prefix_plans_only_matching_products(migrated, catalog_path):
    report, _ = run_collect(migrated, catalog_path, prefix="poco_")
    assert report.planned == 1
    assert list(results(migrated, report.run_id)) == ["trendyol_7"]


def test_no_matching_listing_opens_no_run(migrated, catalog_path):
    with pytest.raises(CollectionError, match="Planlanacak"):
        run_collect(migrated, catalog_path, prefix="olmayan_")
    assert run_count(migrated) == 0


def test_pending_schema_refuses_to_start(db, catalog_path):
    with pytest.raises(CollectionError, match="migrate"):
        run_collect(db, catalog_path)


def test_catalog_conflict_opens_no_run(migrated, catalog_path, tmp_path):
    run_collect(migrated, catalog_path)
    moved = [{**LISTINGS[0], "product_id": 2}, *LISTINGS[1:]]
    with pytest.raises(CatalogConflict):
        run_collect(migrated, write_catalog(tmp_path / "moved.json", moved))
    assert run_count(migrated) == 1


def open_run(conn, catalog_path, listings=(("trendyol_1", 1),)):
    catalog, digest = read_catalog(catalog_path)
    sync_catalog(conn, catalog)
    return runs.start_run(
        conn, trigger="manual", catalog_sha256=digest, listings=list(listings)
    )


def test_result_cannot_be_recorded_twice(migrated, catalog_path):
    run_id = open_run(migrated, catalog_path)
    result = service.error_result("network", "bağlantı koptu")
    runs.record_result(migrated, run_id, "trendyol_1", result)
    with pytest.raises(RuntimeError, match="zaten yazılmış"):
        runs.record_result(migrated, run_id, "trendyol_1", result)


def test_closed_run_accepts_no_result_and_cannot_be_closed_again(
    migrated, catalog_path
):
    run_id = open_run(migrated, catalog_path)
    runs.finish_run(migrated, run_id, "completed")
    result = service.error_result("network", "bağlantı koptu")
    with pytest.raises(RuntimeError, match="tur kapanmış"):
        runs.record_result(migrated, run_id, "trendyol_1", result)
    with pytest.raises(RuntimeError, match="artık 'running' değil"):
        runs.finish_run(migrated, run_id, "interrupted")


def test_run_held_by_another_connection_is_not_touched(migrated, catalog_path):
    # Başka bir süreç (ör. farklı kilit dosyası kullanan bir kopya) tur yürütüyor.
    other = connect(os.environ["TEST_DATABASE_URL"])
    try:
        assert runs.try_lock_runs(other)
        running = open_run(migrated, catalog_path)
        with pytest.raises(RunInProgress):
            run_collect(migrated, catalog_path)
        # Çalışan tur "yarım kalmış" sayılıp kapatılmadı, yeni tur açılmadı.
        assert run_row(migrated, running)[0] == "running"
        assert run_count(migrated) == 1
    finally:
        other.close()
    # Diğer süreç bittiğinde (bağlantı kapanınca kilit düşer) tur başlayabilir.
    report, _ = run_collect(migrated, catalog_path)
    assert report.closed_stale == [running]


def test_value_rejected_by_database_does_not_stop_the_run(migrated, catalog_path):
    # Sözleşmede üst sınır yok, sütun integer: sığmayan çizili fiyat.
    behaviours = {
        **BEHAVIOURS,
        "trendyol_1": {**OFFER, "original_price": 3_000_000_000},
    }
    report, _ = run_collect(migrated, catalog_path, behaviours)
    checked = results(migrated, report.run_id)
    assert checked["trendyol_1"][:2] == ("error", "storage")
    assert checked["trendyol_2"][0] == "offer"  # tur devam etti
    assert run_row(migrated, report.run_id)[0] == "completed"


def test_nul_character_is_removed_from_text(migrated, catalog_path):
    behaviours = {**BEHAVIOURS, "trendyol_1": {**OFFER, "seller_name": "Satıcı\x00 A"}}
    report, _ = run_collect(migrated, catalog_path, behaviours)
    seller = migrated.execute(
        "SELECT seller_name FROM listing_checks"
        " WHERE run_id = %s AND listing_id = 'trendyol_1'",
        (report.run_id,),
    ).fetchone()[0]
    assert seller == "Satıcı A"


def test_sold_out_never_stores_a_price(migrated, catalog_path):
    # Sözleşme Tükendi + fiyata izin veriyor; satın alınamayan fiyat yazılmamalı.
    behaviours = {**BEHAVIOURS, "trendyol_3": {**OFFER, "stock_status": "Tükendi"}}
    report, _ = run_collect(migrated, catalog_path, behaviours)
    row = migrated.execute(
        "SELECT outcome, current_price, seller_name FROM listing_checks"
        " WHERE run_id = %s AND listing_id = 'trendyol_3'",
        (report.run_id,),
    ).fetchone()
    assert row == ("sold_out", None, None)


def test_observation_of_another_listing_is_an_error(migrated, catalog_path):
    def wrong_page(item):
        other = item.model_copy(update={"listing_id": "trendyol_99"})
        return BaseScraper.observation(other, **OFFER)

    behaviours = {**BEHAVIOURS, "trendyol_1": wrong_page}
    report, _ = run_collect(migrated, catalog_path, behaviours)
    assert results(migrated, report.run_id)["trendyol_1"][:2] == (
        "error",
        "validation",
    )


def test_close_failure_keeps_the_result(migrated, catalog_path):
    scrapers = FakeScrapers(BEHAVIOURS, close_error=RuntimeError("kapanmadı"))
    report = collect(
        migrated, catalog_path, Runtime(), create=scrapers, out=lambda _: None
    )
    assert results(migrated, report.run_id)["trendyol_1"][0] == "offer"
    assert run_row(migrated, report.run_id)[0] == "completed"


def test_prefix_is_written_to_the_run_note(migrated, catalog_path):
    report, _ = run_collect(migrated, catalog_path, prefix="poco_")
    assert run_row(migrated, report.run_id)[4] == "--prefix poco_"


def test_run_without_prefix_has_no_note(migrated, catalog_path):
    # 28 Eylül canlı turunda not NULL yerine '' yazılmıştı (concat_ws).
    report, _ = run_collect(migrated, catalog_path)
    assert run_row(migrated, report.run_id)[4] is None


# --- Komut satırı ve ortak kilit -------------------------------------------------


@pytest.fixture
def cli_env(migrated, catalog_path, tmp_path, monkeypatch):
    lock = tmp_path / "scrape.lock"
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps(Runtime().model_dump()), encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("RUNTIME_PATH", str(runtime))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(lock))
    return migrated, lock


def test_cli_exit_codes_and_trigger(cli_env, monkeypatch, capsys):
    conn, lock = cli_env
    all_offers = {key: OFFER for key in BEHAVIOURS}
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(all_offers))
    assert main(["--prefix", "poco_"]) == 0
    assert "tamamlandı" in capsys.readouterr().out

    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    assert main(["--scheduled"]) == 2  # tamamlandı ama hatalı sayfa var
    assert "Hata kodları" in capsys.readouterr().out
    triggers = conn.execute(
        "SELECT trigger FROM collection_runs ORDER BY run_id"
    ).fetchall()
    assert triggers == [("manual",), ("scheduled",)]
    # Tur bitince kilit bırakılmıştır.
    with scrape_lock(lock):
        pass


def test_cli_refuses_while_lock_is_held(cli_env, monkeypatch, capsys):
    conn, lock = cli_env
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    with scrape_lock(lock):
        assert main([]) == 3
    assert "sürüyor" in capsys.readouterr().err
    assert run_count(conn) == 0


def test_cli_ctrl_c_returns_130_and_closes_the_run(cli_env, monkeypatch, capsys):
    conn, _ = cli_env
    behaviours = {**BEHAVIOURS, "trendyol_2": KeyboardInterrupt()}
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(behaviours))
    assert main([]) == 130
    assert "durduruldu" in capsys.readouterr().err
    assert conn.execute("SELECT status FROM collection_runs").fetchone() == (
        "interrupted",
    )


def test_cli_start_failure_returns_1(cli_env, monkeypatch, capsys):
    conn, _ = cli_env
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    assert main(["--prefix", "olmayan_"]) == 1
    assert "Planlanacak" in capsys.readouterr().err
    assert run_count(conn) == 0


def test_discovery_refuses_while_lock_is_held(cli_env, monkeypatch, capsys):
    _, lock = cli_env

    def must_not_run(**_):
        raise AssertionError("Kilit meşgulken keşif başlamamalıydı")

    # Kilit bozulsa bile test gerçek keşfi (canlı istek) başlatamaz.
    monkeypatch.setattr("app.discovery.__main__.run", must_not_run)
    with scrape_lock(lock):
        assert discovery_main(["--dry-run"]) == 1
    assert "sürüyor" in capsys.readouterr().err
