"""Fiyat toplama turu: sahte scraper'larla (internete çıkmaz), gerçek PostgreSQL'de."""

import contextlib
import json
import os
import sys

import psycopg
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
from tests.manual import live_scraper_check

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


def write_catalog(path, listings=LISTINGS, products=PRODUCTS, platforms=PLATFORMS):
    path.write_text(
        json.dumps(
            {"platforms": platforms, "products": products, "listings": listings}
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


def last_run_id(conn):
    return conn.execute("SELECT max(run_id) FROM collection_runs").fetchone()[0]


def run_lock_is_free():
    """Tur kilidini başka bir bağlantıdan dener.

    Advisory kilit aynı bağlantıda yeniden alınabildiği için bırakılmadığı
    ancak başka bir bağlantıdan görülür.
    """
    other = connect(os.environ["TEST_DATABASE_URL"])
    try:
        free = runs.try_lock_runs(other)
        if free:
            runs.unlock_runs(other)
        return free
    finally:
        other.close()


def break_second_write(monkeypatch):
    """İkinci sayfanın sonucu yazılırken bağlantı kopmuş gibi davranır."""
    real = runs.record_result
    writes = []

    def flaky(conn, run_id, listing_id, result):
        writes.append(listing_id)
        if len(writes) == 2:
            raise psycopg.OperationalError("bağlantı koptu")
        real(conn, run_id, listing_id, result)

    monkeypatch.setattr(runs, "record_result", flaky)


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
    run_id = last_run_id(migrated)
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


def test_database_error_mid_run_interrupts_it_and_keeps_written_results(
    migrated, catalog_path, monkeypatch
):
    break_second_write(monkeypatch)
    with pytest.raises(psycopg.OperationalError):
        run_collect(migrated, catalog_path)
    run_id = last_run_id(migrated)
    status, _, _, finished, note = run_row(migrated, run_id)
    assert (status, finished) == ("interrupted", True)
    assert note == "Durduruldu: OperationalError"
    checked = results(migrated, run_id)
    assert checked["trendyol_1"][0] == "offer"
    # Bağlantı hatası 'storage' sonucu gibi yazılıp geçilmez; tur durur.
    assert [v[0] for k, v in checked.items() if k != "trendyol_1"] == [None] * 6
    assert run_lock_is_free()


def test_run_that_cannot_be_closed_stays_running_until_the_next_run(
    migrated, catalog_path, monkeypatch
):
    def dead_connection(*_, **__):
        raise psycopg.OperationalError("kapatılamadı")

    with monkeypatch.context() as patch:
        break_second_write(patch)
        patch.setattr(runs, "finish_run", dead_connection)
        # Kapatma hatası asıl hatayı gölgelemez.
        with pytest.raises(psycopg.OperationalError, match="bağlantı koptu"):
            run_collect(migrated, catalog_path)
    run_id = last_run_id(migrated)
    assert run_row(migrated, run_id)[0] == "running"
    report, _ = run_collect(migrated, catalog_path)
    assert report.closed_stale == [run_id]
    assert run_row(migrated, run_id)[0] == "interrupted"


@pytest.mark.parametrize(
    "prefix, behaviours, raised",
    [
        ("", BEHAVIOURS, None),
        ("olmayan_", BEHAVIOURS, CollectionError),
        ("", {**BEHAVIOURS, "trendyol_2": KeyboardInterrupt()}, KeyboardInterrupt),
    ],
    ids=["completed", "not_started", "ctrl_c"],
)
def test_run_lock_is_released_for_other_connections(
    migrated, catalog_path, prefix, behaviours, raised
):
    # Bugün her tur bağlantısını kapatır; tek bağlantıyı uzun süre kullanan bir
    # süreçte sızan kilit sonraki bütün turları "başka tur sürüyor" diye durdururdu.
    expected = pytest.raises(raised) if raised else contextlib.nullcontext()
    with expected:
        run_collect(migrated, catalog_path, behaviours, prefix=prefix)
    assert run_lock_is_free()


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


def test_inactive_product_and_platform_are_not_planned(tmp_path):
    # Katalog, pasif ürüne veya platforma bağlı etkin sayfaya izin verir.
    products = [PRODUCTS[0], {**PRODUCTS[1], "active": False}]
    platforms = [PLATFORMS[0], {**PLATFORMS[1], "active": False}]
    path = write_catalog(
        tmp_path / "catalog.json", products=products, platforms=platforms
    )
    catalog, _ = read_catalog(path)
    planned = service.plan_listings(catalog)
    # trendyol_7 pasif ürünün, hepsiburada_4-6 pasif platformun; trendyol_8 pasif.
    assert [item.listing_id for item in planned] == [
        "trendyol_1",
        "trendyol_2",
        "trendyol_3",
    ]


def test_planned_listing_carries_product_identity_for_the_scraper(catalog_path):
    # Scraper sayfanın doğru telefon olduğunu bu model ve kapasiteyle denetler.
    catalog, _ = read_catalog(catalog_path)
    [item] = service.plan_listings(catalog, prefix="poco_")
    assert (item.listing_id, item.product_name, item.model, item.storage_gb) == (
        "trendyol_7",
        "POCO X6 Pro 512 GB",
        "X6 Pro",
        512,
    )


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


def test_result_for_unplanned_listing_is_refused(migrated, catalog_path):
    run_id = open_run(migrated, catalog_path)  # yalnız trendyol_1 planlı
    result = service.error_result("network", "bağlantı koptu")
    with pytest.raises(RuntimeError, match="planlı değil"):
        runs.record_result(migrated, run_id, "trendyol_2", result)
    # Yeni satır eklenmedi, planlı satıra da dokunulmadı.
    assert results(migrated, run_id) == {"trendyol_1": (None, None, None, None, False)}


def test_summary_counts_listings_without_result_as_unchecked(migrated, catalog_path):
    # Üretimde özet yalnız tamamlanan turdan alınır; 'unchecked' komut satırının
    # "bakılmadı" adını verdiği anahtardır.
    run_id = open_run(migrated, catalog_path, [("trendyol_1", 1), ("trendyol_2", 1)])
    result = service.error_result("network", "bağlantı koptu")
    runs.record_result(migrated, run_id, "trendyol_1", result)
    summary = runs.run_summary(migrated, run_id)
    assert summary.outcomes == {"error": 1, "unchecked": 1}
    assert summary.error_codes == {"network": 1}


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


def test_long_error_message_is_cut_and_empty_one_is_stored_as_null(
    migrated, catalog_path
):
    behaviours = {
        **BEHAVIOURS,
        "trendyol_1": FetchError("network", "x" * 1000),
        "hepsiburada_4": FetchError("parse", ""),
    }
    report, _ = run_collect(migrated, catalog_path, behaviours)
    messages = dict(
        migrated.execute(
            "SELECT listing_id, error_message FROM listing_checks"
            " WHERE run_id = %s AND outcome = 'error'",
            (report.run_id,),
        ).fetchall()
    )
    assert len(messages["trendyol_1"]) == service.MAX_ERROR_MESSAGE
    assert messages["hepsiburada_4"] is None


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
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
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


def test_cli_ctrl_c_returns_130_closes_the_run_and_releases_the_lock(
    cli_env, monkeypatch, capsys
):
    conn, lock = cli_env
    behaviours = {**BEHAVIOURS, "trendyol_2": KeyboardInterrupt()}
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(behaviours))
    assert main([]) == 130
    assert "durduruldu" in capsys.readouterr().err
    assert conn.execute("SELECT status FROM collection_runs").fetchone() == (
        "interrupted",
    )
    with scrape_lock(lock):
        pass


def test_cli_start_failure_returns_1_and_releases_the_lock(
    cli_env, monkeypatch, capsys
):
    conn, lock = cli_env
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    assert main(["--prefix", "olmayan_"]) == 1
    assert "Planlanacak" in capsys.readouterr().err
    assert run_count(conn) == 0
    with scrape_lock(lock):
        pass


def test_cli_database_error_mid_run_returns_1_and_interrupts_the_run(
    cli_env, monkeypatch, capsys
):
    conn, lock = cli_env
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    break_second_write(monkeypatch)
    assert main([]) == 1
    assert "Tur başarısız: bağlantı koptu" in capsys.readouterr().err
    assert conn.execute("SELECT status FROM collection_runs").fetchone() == (
        "interrupted",
    )
    with scrape_lock(lock):
        pass


def test_discovery_refuses_while_lock_is_held(tmp_path, monkeypatch, capsys):
    # Veritabanı gerekmez: TEST_DATABASE_URL yokken de keşfin kilit kuralı sınanır.
    lock = tmp_path / "scrape.lock"
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(lock))

    def must_not_run(**_):
        raise AssertionError("Kilit meşgulken keşif başlamamalıydı")

    # Kilit bozulsa bile test gerçek keşfi (canlı istek) başlatamaz.
    monkeypatch.setattr("app.discovery.__main__.run", must_not_run)
    with scrape_lock(lock):
        # Tur ve canlı araçlarla aynı: başka tarama sürüyorsa 3.
        assert discovery_main(["--dry-run"]) == 3
    error = capsys.readouterr().err
    assert "Keşif başlatılmadı" in error and "sürüyor" in error


def test_live_scraper_check_refuses_while_lock_is_held(tmp_path, monkeypatch, capsys):
    # Kilit bu araçta da "sıra meselesi"dir ve tur, keşif ve diğer canlı araçlarla
    # aynı kodu (3) verir; eskiden 1 dönüyordu (hata gibi görünüyordu).
    lock = tmp_path / "scrape.lock"
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(lock))

    def must_not_run(*_, **__):
        raise AssertionError("Kilit meşgulken canlı okuma başlamamalıydı")

    monkeypatch.setattr(live_scraper_check, "check", must_not_run)
    with scrape_lock(lock):
        assert live_scraper_check.main([]) == 3
    error = capsys.readouterr().err
    assert "Başlatılmadı" in error and "sürüyor" in error


# --- Zamanlanmış turun log dosyası -----------------------------------------------


def log_text(tmp_path):
    [path] = (tmp_path / "logs").glob("tur_*.log")
    return path.read_text(encoding="utf-8")


def test_scheduled_run_writes_everything_to_a_log(cli_env, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    assert main(["--scheduled"]) == 2
    text = log_text(tmp_path)
    assert "[7/7]" in text  # her sayfanın ilerleme satırı
    assert "Tükendi" in text  # Türkçe karakterler bozulmadan
    assert "RuntimeError: scraper içinde hata" in text  # beklenmeyen hata ayrıntısı
    assert "Hata kodları" in text
    assert text.rstrip().endswith("Çıkış kodu: 2")


def test_scheduled_run_without_console_still_logs(cli_env, tmp_path, monkeypatch):
    # pythonw.exe (Görev Zamanlayıcı) altında ekran akışları hiç yoktur.
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    assert main(["--scheduled"]) == 2
    assert "Hata kodları" in log_text(tmp_path)


def test_busy_scheduled_run_is_logged(cli_env, tmp_path, monkeypatch):
    _, lock = cli_env
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    with scrape_lock(lock):
        assert main(["--scheduled"]) == 3
    text = log_text(tmp_path)
    assert "Tur başlatılmadı" in text
    assert text.rstrip().endswith("Çıkış kodu: 3")


def test_program_error_is_logged_with_exit_1(cli_env, tmp_path, monkeypatch):
    def crash(*_, **__):
        raise TypeError("beklenmeyen program hatası")

    monkeypatch.setattr("app.collection.__main__.collect", crash)
    assert main(["--scheduled"]) == 1
    text = log_text(tmp_path)
    assert "TypeError: beklenmeyen program hatası" in text
    assert text.rstrip().endswith("Çıkış kodu: 1")


def test_scheduled_run_does_not_start_when_log_cannot_be_opened(
    tmp_path, monkeypatch, capsys
):
    # LOG_DIR bir dosyayı gösterir: klasör oluşturulamaz (OSError).
    not_a_dir = tmp_path / "logs"
    not_a_dir.write_text("", encoding="utf-8")
    monkeypatch.setenv("LOG_DIR", str(not_a_dir))
    started = []
    monkeypatch.setattr("app.collection.__main__.run", lambda *a: started.append(a))
    assert main(["--scheduled"]) == 1
    assert "Log dosyası açılamadı" in capsys.readouterr().err
    assert started == []  # ne kilit ne veritabanı: tur hiç başlatılmadı


def test_manual_run_writes_no_log(cli_env, tmp_path, monkeypatch):
    monkeypatch.setattr(service, "create_scraper", FakeScrapers(BEHAVIOURS))
    assert main(["--prefix", "poco_"]) == 0
    assert not (tmp_path / "logs").exists()
