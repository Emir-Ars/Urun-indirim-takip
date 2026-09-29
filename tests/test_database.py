"""Migration koşucusu ve şema kuralları; gerçek PostgreSQL test veritabanında.

Sondaki bölüm conftest.py'deki emniyet kemerlerini (internet kesici,
DATABASE_URL silme, `_test` ad denetimi) veritabanına bağlanmadan dener.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest
from curl_cffi import requests as curl_requests
from psycopg import errors, sql

from app.database.__main__ import main
from app.database.migrate import (
    MigrationError,
    applied,
    checksum,
    load,
    migrate,
    pending,
)
from app.scraper.http import PageClient
from app.settings import Runtime
from conftest import ensure_test_database

NOW = datetime(2026, 9, 28, 7, 0, tzinfo=timezone.utc)
CATALOG_SHA = "0" * 64
OFFER = {
    "outcome": "offer",
    "checked_at": NOW,
    "current_price": 5724900,
    "seller_name": "Örnek Satıcı",
    "stock_status": "Stokta Var",
}
SOLD_OUT = {"outcome": "sold_out", "checked_at": NOW, "stock_status": "Tükendi"}
ERROR = {"outcome": "error", "checked_at": NOW, "error_code": "parse"}
# Geçerli, bitmiş bir tur; CHECK testleri bundan tek alan değiştirir.
RUN = {
    "trigger": "manual",
    "status": "completed",
    "started_at": NOW,
    "finished_at": NOW,
    "catalog_sha256": CATALOG_SHA,
    "planned_count": 1,
}
# schema fixture'ındaki kayıtlarla çakışmayan geçerli katalog satırları.
CATALOG_ROWS = {
    "platforms": {"key": "hepsiburada", "name": "Hepsiburada", "active": True},
    "products": {
        "product_id": 3,
        "product_key": "apple_iphone_15_512gb",
        "brand": "Apple",
        "model": "iPhone 15",
        "storage_gb": 512,
        "active": True,
    },
    "listings": {
        "listing_id": "trendyol_9",
        "product_id": 1,
        "platform": "trendyol",
        "url": "https://www.trendyol.com/apple/iphone-15-p-9",
        "color": "Siyah",
        "active": True,
    },
}


def write(directory, name, text):
    (directory / name).write_text(text, encoding="utf-8")


def tables(conn):
    rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    return {row[0] for row in rows}


def insert(conn, table, **values):
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    conn.execute(query, list(values.values()))


def start_run(conn, status="running"):
    finished_at = None if status == "running" else NOW
    return conn.execute(
        "INSERT INTO collection_runs"
        " (trigger, status, started_at, finished_at, catalog_sha256, planned_count)"
        " VALUES ('manual', %s, %s, %s, %s, 1) RETURNING run_id",
        (status, NOW, finished_at, CATALOG_SHA),
    ).fetchone()[0]


@pytest.fixture
def schema(db):
    """001 uygulanmış veritabanı: 1 platform, 2 ürün, 1 sayfa, 1 süren tur."""
    migrate(db)
    insert(db, "platforms", key="trendyol", name="Trendyol", active=True)
    for product_id, storage in ((1, 128), (2, 256)):
        insert(
            db,
            "products",
            product_id=product_id,
            product_key=f"apple_iphone_15_{storage}gb",
            brand="Apple",
            model="iPhone 15",
            storage_gb=storage,
            active=True,
        )
    insert(
        db,
        "listings",
        listing_id="trendyol_1",
        product_id=1,
        platform="trendyol",
        url="https://www.trendyol.com/apple/iphone-15-p-1",
        color="Siyah",
        active=True,
    )
    return db, start_run(db)


def check(conn, run_id, **fields):
    insert(
        conn,
        "listing_checks",
        run_id=run_id,
        listing_id="trendyol_1",
        product_id=1,
        **fields,
    )


# --- Migration koşucusu -----------------------------------------------------


def test_checksum_ignores_line_endings():
    assert checksum("SELECT 1;\r\nSELECT 2;\r\n") == checksum("SELECT 1;\nSELECT 2;\n")


def test_load_rejects_gaps_and_bad_names(tmp_path):
    write(tmp_path, "001_a.sql", "SELECT 1;")
    write(tmp_path, "003_c.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match=r"boşluksuz.*\(bulunan: \[1, 3\]\)"):
        load(tmp_path)

    bad_name = tmp_path / "bad_name"
    bad_name.mkdir()
    write(bad_name, "1_a.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="dosya adı"):
        load(bad_name)


def test_load_rejects_two_files_with_the_same_number(tmp_path):
    # İki ayrı dalda aynı numara alınmış dosyalar: mesaj tekrarlanan numarayı
    # gösterir, yoksa "boşluksuz artmalı" tek başına anlaşılmaz.
    write(tmp_path, "001_a.sql", "SELECT 1;")
    write(tmp_path, "001_b.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match=r"boşluksuz.*\(bulunan: \[1, 1\]\)"):
        load(tmp_path)


def test_load_rejects_missing_files_and_upper_case_names(tmp_path):
    with pytest.raises(MigrationError, match="bulunamadı"):
        load(tmp_path)
    write(tmp_path, "001_A.SQL", "SELECT 1;")
    with pytest.raises(MigrationError, match="dosya adı"):
        load(tmp_path)


def test_connection_sets_utc_and_lock_timeout(db):
    assert db.execute("SHOW TimeZone").fetchone()[0] == "UTC"
    assert db.execute("SHOW lock_timeout").fetchone()[0] == "30s"


def test_cli_status_and_migrate(db, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    assert main(["status"]) == 0
    assert "001_initial.sql  BEKLİYOR" in capsys.readouterr().out
    assert main(["migrate"]) == 0
    assert "uygulandı: 001_initial.sql" in capsys.readouterr().out
    assert main(["migrate"]) == 0
    assert "Şema güncel" in capsys.readouterr().out
    assert main(["status"]) == 0
    assert "001_initial.sql  uygulandı" in capsys.readouterr().out


def test_cli_without_database_url_fails(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert main(["status"]) == 1
    assert "DATABASE_URL tanımlı değil" in capsys.readouterr().err


def test_migrate_applies_each_file_once(db):
    assert [m.file_name for m in migrate(db)] == ["001_initial.sql"]
    assert migrate(db) == []
    assert pending(db) == []
    assert [row[:2] for row in applied(db)] == [(1, "initial")]
    assert {
        "schema_migrations",
        "platforms",
        "products",
        "listings",
        "collection_runs",
        "listing_checks",
    } <= tables(db)


def test_changed_applied_migration_is_rejected(db, tmp_path):
    write(tmp_path, "001_a.sql", "CREATE TABLE a (id integer);")
    migrate(db, tmp_path)
    write(tmp_path, "001_a.sql", "CREATE TABLE a (id bigint);")
    with pytest.raises(MigrationError, match="değiştirilmiş"):
        pending(db, tmp_path)
    with pytest.raises(MigrationError, match="değiştirilmiş"):
        migrate(db, tmp_path)


def test_renamed_applied_migration_is_rejected(db, tmp_path):
    # İçerik aynı (parmak izi tutar) ama uygulanmış dosyanın adı değişmiş:
    # schema_migrations'taki ad ile dosya adı artık uyuşmaz, sessiz geçilmez.
    write(tmp_path, "001_a.sql", "CREATE TABLE a (id integer);")
    migrate(db, tmp_path)
    (tmp_path / "001_a.sql").rename(tmp_path / "001_b.sql")
    renamed = r"001_a\.sql.*001_b\.sql"
    with pytest.raises(MigrationError, match=renamed):
        pending(db, tmp_path)  # status komutunun yolu
    with pytest.raises(MigrationError, match=renamed):
        migrate(db, tmp_path)
    assert [row[:2] for row in applied(db)] == [(1, "a")]  # kayıt değişmedi


def test_database_newer_than_code_is_rejected(db, tmp_path):
    write(tmp_path, "001_a.sql", "CREATE TABLE a (id integer);")
    write(tmp_path, "002_b.sql", "CREATE TABLE b (id integer);")
    migrate(db, tmp_path)
    (tmp_path / "002_b.sql").unlink()
    with pytest.raises(MigrationError, match="koddan daha yeni"):
        migrate(db, tmp_path)


def test_failed_migration_leaves_no_trace(db, tmp_path):
    write(tmp_path, "001_a.sql", "CREATE TABLE a (id integer);")
    write(
        tmp_path,
        "002_b.sql",
        "CREATE TABLE b (id integer);\nSELECT * FROM olmayan_tablo;",
    )
    with pytest.raises(errors.UndefinedTable):
        migrate(db, tmp_path)
    # 001 kalıcı; 002'nin ilk komutu (b tablosu) da geri alındı ve kaydı yok.
    assert "a" in tables(db)
    assert "b" not in tables(db)
    assert [row[0] for row in applied(db)] == [1]


# --- Şema kuralları ------------------------------------------------------------


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({}, id="planlandi"),
        pytest.param(OFFER, id="fiyat"),
        pytest.param(
            {
                **OFFER,
                "original_price": 5999900,
                "seller_rating": 9.4,
                "seller_rating_scale": 10,
                "stock_status": "Kritik Stok",
            },
            id="fiyat-tum-alanlar",
        ),
        pytest.param(
            {"outcome": "sold_out", "checked_at": NOW, "stock_status": "Tükendi"},
            id="tukendi",
        ),
        pytest.param(
            {
                "outcome": "error",
                "checked_at": NOW,
                "error_code": "blocked",
                "error_message": "HTTP 403",
            },
            id="hata",
        ),
    ],
)
def test_valid_results_are_accepted(schema, fields):
    conn, run_id = schema
    check(conn, run_id, **fields)


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param(
            {
                "outcome": "error",
                "checked_at": NOW,
                "error_code": "network",
                "current_price": 5724900,
            },
            id="hata-fiyat-tasiyamaz",
        ),
        pytest.param(
            {
                "outcome": "error",
                "checked_at": NOW,
                "stock_status": "Tükendi",
                "error_code": "parse",
            },
            id="hata-tukendi-olamaz",
        ),
        pytest.param({"outcome": "error", "checked_at": NOW}, id="hata-kodsuz-olamaz"),
        pytest.param(
            {k: v for k, v in OFFER.items() if k != "seller_name"},
            id="fiyat-saticisiz-olamaz",
        ),
        pytest.param({**OFFER, "stock_status": "Tükendi"}, id="fiyat-tukendi-olamaz"),
        pytest.param({**OFFER, "checked_at": None}, id="fiyat-zamansiz-olamaz"),
        pytest.param({**OFFER, "error_code": "parse"}, id="fiyat-hata-kodu-tasiyamaz"),
        pytest.param(
            {"outcome": "sold_out", "checked_at": NOW, "stock_status": "Stokta Var"},
            id="tukendi-stokta-olamaz",
        ),
        pytest.param({"current_price": 5724900}, id="planlanan-fiyat-tasiyamaz"),
        pytest.param({"checked_at": NOW}, id="planlanan-zaman-tasiyamaz"),
        pytest.param({**OFFER, "outcome": "belki"}, id="bilinmeyen-sonuc"),
        pytest.param({**OFFER, "stock_status": "Az Kaldı"}, id="bilinmeyen-stok"),
        pytest.param({**OFFER, "current_price": 0}, id="sifir-fiyat"),
        pytest.param({**OFFER, "original_price": 0}, id="sifir-cizili-fiyat"),
        pytest.param(
            {**OFFER, "seller_rating": 11, "seller_rating_scale": 10},
            id="puan-olcegi-asamaz",
        ),
        # CASE'li CHECK'in NULL korumaları: koşul NULL verseydi satır kabul
        # edilirdi (001_initial.sql başındaki not). Her IS NULL / IS NOT NULL
        # ve boş yazı koruması ayrı ayrı denenir.
        pytest.param({**OFFER, "current_price": None}, id="fiyat-fiyatsiz-olamaz"),
        pytest.param({**OFFER, "stock_status": None}, id="fiyat-stoksuz-olamaz"),
        pytest.param({**OFFER, "seller_name": ""}, id="fiyat-bos-satici-olamaz"),
        pytest.param(
            {**OFFER, "error_message": "HTTP 403"}, id="fiyat-hata-mesaji-tasiyamaz"
        ),
        pytest.param({**SOLD_OUT, "stock_status": None}, id="tukendi-stoksuz-olamaz"),
        pytest.param({**SOLD_OUT, "checked_at": None}, id="tukendi-zamansiz-olamaz"),
        pytest.param(
            {**SOLD_OUT, "error_code": "parse"}, id="tukendi-hata-kodu-tasiyamaz"
        ),
        pytest.param(
            {**SOLD_OUT, "error_message": "HTTP 403"},
            id="tukendi-hata-mesaji-tasiyamaz",
        ),
        pytest.param({**ERROR, "error_code": ""}, id="hata-bos-kod-olamaz"),
        pytest.param({**ERROR, "checked_at": None}, id="hata-zamansiz-olamaz"),
        pytest.param(
            {**ERROR, "seller_name": "Örnek Satıcı"}, id="hata-satici-tasiyamaz"
        ),
        pytest.param(
            {**ERROR, "original_price": 5999900}, id="hata-cizili-fiyat-tasiyamaz"
        ),
        pytest.param({**ERROR, "seller_rating": 9.4}, id="hata-puan-tasiyamaz"),
        pytest.param({"error_code": "parse"}, id="planlanan-hata-kodu-tasiyamaz"),
        pytest.param(
            {"error_message": "HTTP 403"}, id="planlanan-hata-mesaji-tasiyamaz"
        ),
        pytest.param({"seller_name": "Örnek Satıcı"}, id="planlanan-satici-tasiyamaz"),
        pytest.param({"stock_status": "Tükendi"}, id="planlanan-stok-tasiyamaz"),
    ],
)
def test_invalid_results_are_rejected(schema, fields):
    conn, run_id = schema
    with pytest.raises(errors.CheckViolation):
        check(conn, run_id, **fields)


def test_same_page_cannot_be_recorded_twice_in_a_run(schema):
    conn, run_id = schema
    check(conn, run_id)
    with pytest.raises(errors.UniqueViolation):
        check(conn, run_id, **OFFER)


def test_page_result_cannot_be_written_under_another_product(schema):
    conn, run_id = schema
    with pytest.raises(errors.ForeignKeyViolation):
        insert(
            conn,
            "listing_checks",
            run_id=run_id,
            listing_id="trendyol_1",
            product_id=2,
        )


def test_only_one_run_can_be_running(schema):
    # collection_runs_one_running indeksi sabit ((true)) ifadesi üzerindedir ve
    # yalnızca status = 'running' satırlarını kapsar: bu satırların hepsi aynı
    # anahtarı (true) paylaştığı için ikinci 'running' satır benzersizliği bozar;
    # bitmiş turlar indekse girmez, istenildiği kadar olabilir.
    conn, run_id = schema
    with pytest.raises(errors.UniqueViolation):
        start_run(conn)
    start_run(conn, status="completed")
    conn.execute(
        "UPDATE collection_runs SET status = 'interrupted', finished_at = %s"
        " WHERE run_id = %s",
        (NOW, run_id),
    )
    start_run(conn)


@pytest.mark.parametrize(
    "status, finished_at",
    [("running", NOW), ("completed", None), ("interrupted", None)],
)
def test_run_status_and_finish_time_must_agree(schema, status, finished_at):
    conn, _ = schema
    with pytest.raises(errors.CheckViolation):
        conn.execute(
            "INSERT INTO collection_runs (trigger, status, started_at, finished_at,"
            " catalog_sha256, planned_count) VALUES ('manual', %s, %s, %s, %s, 0)",
            (status, NOW, finished_at, CATALOG_SHA),
        )


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({}, id="bitis-baslangicla-ayni"),
        pytest.param({"trigger": "scheduled", "planned_count": 0}, id="zamanlanmis"),
    ],
)
def test_valid_finished_run_is_accepted(schema, changes):
    conn, _ = schema
    insert(conn, "collection_runs", **{**RUN, **changes})


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param(
            {"finished_at": NOW - timedelta(seconds=1)},
            id="bitis-baslangictan-once-olamaz",
        ),
        pytest.param({"trigger": "cron"}, id="bilinmeyen-tetikleyici"),
        pytest.param({"status": "failed"}, id="bilinmeyen-durum"),
        pytest.param({"catalog_sha256": "abc"}, id="kisa-parmak-izi"),
        pytest.param({"catalog_sha256": "A" * 64}, id="buyuk-harfli-parmak-izi"),
        pytest.param({"planned_count": -1}, id="eksi-planlanan-sayi"),
    ],
)
def test_invalid_runs_are_rejected(schema, changes):
    conn, _ = schema
    with pytest.raises(errors.CheckViolation):
        insert(conn, "collection_runs", **{**RUN, **changes})


def test_valid_catalog_rows_are_accepted(schema):
    conn, _ = schema
    for table in ("platforms", "products", "listings"):
        insert(conn, table, **CATALOG_ROWS[table])


@pytest.mark.parametrize(
    "table, changes",
    [
        pytest.param("platforms", {"key": "Hepsiburada"}, id="buyuk-harfli-anahtar"),
        pytest.param("platforms", {"name": ""}, id="bos-platform-adi"),
        pytest.param("products", {"product_key": ""}, id="bos-urun-anahtari"),
        pytest.param("products", {"brand": ""}, id="bos-marka"),
        pytest.param("products", {"storage_gb": 0}, id="sifir-kapasite"),
        pytest.param("listings", {"listing_id": ""}, id="bos-sayfa-kimligi"),
        pytest.param(
            "listings",
            {"url": "http://www.trendyol.com/apple/iphone-15-p-9"},
            id="https-olmayan-adres",
        ),
    ],
)
def test_invalid_catalog_rows_are_rejected(schema, table, changes):
    conn, _ = schema
    with pytest.raises(errors.CheckViolation):
        insert(conn, table, **{**CATALOG_ROWS[table], **changes})


def test_product_identity_ignores_letter_case(schema):
    conn, _ = schema
    with pytest.raises(errors.UniqueViolation):
        insert(
            conn,
            "products",
            product_id=3,
            product_key="apple_iphone_15_128gb_kopya",
            brand="APPLE",
            model="iphone 15",
            storage_gb=128,
            active=True,
        )


# --- Test emniyet kemerleri (conftest.py); veritabanına bağlanılmaz --------------


class NamedConnection:
    """Yalnızca `SELECT current_database()` sorusunu yanıtlayan sahte bağlantı."""

    def __init__(self, name):
        self.name = name

    def execute(self, query):
        assert query == "SELECT current_database()"
        return self

    def fetchone(self):
        return (self.name,)


@pytest.mark.parametrize(
    "name", ["fiyat_takip", "test_fiyat_takip", "fiyat_takip_test_kopya"]
)
def test_database_not_ending_in_test_stops_pytest(name):
    # db fixture'ı bu denetimden sonra public şemasını siliyor: gerçek veritabanı
    # adı buradan geçerse bütün veri gider.
    with pytest.raises(pytest.exit.Exception, match="_test ile bitmeli") as stop:
        ensure_test_database(NamedConnection(name))
    assert stop.value.returncode == 1


def test_database_ending_in_test_is_accepted():
    assert ensure_test_database(NamedConnection("fiyat_takip_test")) == (
        "fiyat_takip_test"
    )


def test_database_url_is_removed_for_every_test():
    # Kalıcı kullanıcı değişkeni gerçek veritabanını gösteriyor olabilir.
    assert "DATABASE_URL" not in os.environ


def test_real_http_request_is_blocked_in_tests(monkeypatch):
    # Sahte istemci verilmeyen PageClient gerçek curl_cffi oturumu açar; istek
    # gönderilmeden test başarısız sayılır. Kemer bozulsa bile adres bu
    # bilgisayardır, internete çıkılmaz.
    import app.scraper.http as http

    monkeypatch.setattr(http, "_LAST_REQUEST", {})  # süreç geneli kayıt kirlenmesin
    runtime = Runtime(
        request_interval_seconds=0, request_attempts=1, request_timeout_seconds=1
    )
    client = PageClient(["127.0.0.1"], runtime)
    try:
        with pytest.raises(pytest.fail.Exception, match="internete çıkmaya çalıştı"):
            client.get("https://127.0.0.1/")
    finally:
        client.close()


def test_module_level_curl_request_is_blocked_in_tests():
    with pytest.raises(pytest.fail.Exception, match="internete çıkmaya çalıştı"):
        curl_requests.get("https://127.0.0.1/", timeout=1)
