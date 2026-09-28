"""Migration koşucusu ve şema kuralları; gerçek PostgreSQL test veritabanında."""

from datetime import datetime, timezone

import pytest
from psycopg import errors, sql

from app.database.migrate import (
    MigrationError,
    applied,
    checksum,
    load,
    migrate,
    pending,
)

NOW = datetime(2026, 9, 28, 7, 0, tzinfo=timezone.utc)
CATALOG_SHA = "0" * 64
OFFER = {
    "outcome": "offer",
    "checked_at": NOW,
    "current_price": 5724900,
    "seller_name": "Örnek Satıcı",
    "stock_status": "Stokta Var",
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
    with pytest.raises(MigrationError, match="boşluksuz"):
        load(tmp_path)

    bad_name = tmp_path / "bad_name"
    bad_name.mkdir()
    write(bad_name, "1_a.sql", "SELECT 1;")
    with pytest.raises(MigrationError, match="dosya adı"):
        load(bad_name)


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
        pytest.param(
            {**OFFER, "seller_rating": 11, "seller_rating_scale": 10},
            id="puan-olcegi-asamaz",
        ),
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
