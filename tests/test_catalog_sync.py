"""catalog.json → veritabanı kopyası eşitlemesi."""

import json
import os
from pathlib import Path

import pytest

from app.contracts import Catalog
from app.database.__main__ import main
from app.database.catalog_sync import (
    CatalogConflict,
    catalog_rows,
    plan_sync,
    read_catalog,
    sync_catalog,
)
from app.database.migrate import migrate

FIXTURE = Path(__file__).parent / "fixtures" / "discovery" / "catalog.json"
PLATFORM = {
    "key": "trendyol",
    "name": "Trendyol",
    "hosts": ["www.trendyol.com"],
    "active": True,
}


def product(product_id, storage_gb, **changes):
    return {
        "product_id": product_id,
        "product_key": f"apple_iphone_15_{storage_gb}gb",
        "brand": "Apple",
        "model": "iPhone 15",
        "storage_gb": storage_gb,
        "active": True,
        **changes,
    }


def listing(number, product_id, **changes):
    return {
        "listing_id": f"trendyol_{number}",
        "product_id": product_id,
        "platform": "trendyol",
        "url": f"https://www.trendyol.com/apple/iphone-15-p-{number}",
        "color": "Siyah",
        "active": True,
        **changes,
    }


def make(products, listings, platforms=(PLATFORM,)):
    return Catalog.model_validate(
        {
            "platforms": list(platforms),
            "products": list(products),
            "listings": list(listings),
        }
    )


BASE = make([product(1, 128), product(2, 256)], [listing(1, 1), listing(2, 2)])


def counts(plan):
    return {
        name: (
            len(c.added),
            len(c.updated),
            len(c.deactivated),
            c.unchanged,
        )
        for name, c in plan.tables.items()
    }


def table_counts(conn):
    return tuple(
        conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        for name in ("platforms", "products", "listings")
    )


# --- plan_sync: veritabanısız kararlar ----------------------------------------


def test_empty_database_adds_everything():
    plan = plan_sync({}, BASE)
    assert counts(plan) == {
        "platforms": (1, 0, 0, 0),
        "products": (2, 0, 0, 0),
        "listings": (2, 0, 0, 0),
    }


def test_same_catalog_changes_nothing():
    plan = plan_sync(catalog_rows(BASE), BASE)
    assert not plan.changed
    assert counts(plan)["listings"] == (0, 0, 0, 2)


def test_mutable_fields_are_updated():
    new = make(
        [product(1, 128), product(2, 256, active=False)],
        [
            listing(1, 1, color="Gece Siyahı", url="https://www.trendyol.com/x-p-1"),
            listing(2, 2, active=False),
        ],
    )
    plan = plan_sync(catalog_rows(BASE), new)
    assert plan.tables["products"].updated == [(2, {"active": (True, False)})]
    assert plan.tables["listings"].updated == [
        (
            "trendyol_1",
            {
                "url": (
                    "https://www.trendyol.com/apple/iphone-15-p-1",
                    "https://www.trendyol.com/x-p-1",
                ),
                "color": ("Siyah", "Gece Siyahı"),
            },
        ),
        ("trendyol_2", {"active": (True, False)}),
    ]


@pytest.mark.parametrize(
    "changed, field",
    [
        (listing(1, 2), "product_id"),
        (
            listing(1, 1, platform="hepsiburada", url="https://www.hepsiburada.com/a"),
            "platform",
        ),
    ],
)
def test_listing_identity_cannot_change(changed, field):
    hepsiburada = {**PLATFORM, "key": "hepsiburada", "name": "Hepsiburada"}
    hepsiburada["hosts"] = ["www.hepsiburada.com"]
    new = make(
        [product(1, 128), product(2, 256)],
        [changed, listing(2, 2)],
        platforms=(PLATFORM, hepsiburada),
    )
    with pytest.raises(CatalogConflict, match=f"trendyol_1: {field} değişemez"):
        plan_sync(catalog_rows(BASE), new)


@pytest.mark.parametrize(
    "changes, field",
    [
        ({"product_key": "apple_iphone_15_128gb_yeni"}, "product_key"),
        ({"brand": "Apple Inc"}, "brand"),
        ({"model": "iPhone 15 Plus"}, "model"),
        ({"storage_gb": 512, "product_key": "apple_iphone_15_512gb"}, "storage_gb"),
    ],
)
def test_product_identity_cannot_change(changes, field):
    new = make(
        [{**product(1, 128), **changes}, product(2, 256)],
        [listing(1, 1), listing(2, 2)],
    )
    with pytest.raises(CatalogConflict, match=f"products 1: {field} değişemez"):
        plan_sync(catalog_rows(BASE), new)


def test_missing_records_are_deactivated_not_deleted():
    new = make([product(1, 128)], [listing(1, 1)])
    plan = plan_sync(catalog_rows(BASE), new)
    assert plan.tables["products"].deactivated == [2]
    assert plan.tables["listings"].deactivated == ["trendyol_2"]
    assert counts(plan)["listings"] == (0, 0, 1, 1)


def test_missing_record_already_inactive_is_unchanged():
    current = catalog_rows(BASE)
    current["listings"]["trendyol_2"]["active"] = False
    plan = plan_sync(current, make([product(1, 128), product(2, 256)], [listing(1, 1)]))
    assert plan.tables["listings"].deactivated == []
    assert not plan.changed


def test_new_listing_reusing_an_existing_url_is_conflict():
    # trendyol_2 katalogdan düşmüş ama veritabanında duruyor;
    # yeni sayfa aynı adresi kullanıyor.
    new = make(
        [product(1, 128), product(2, 256)],
        [listing(1, 1), listing(9, 2, url=listing(2, 2)["url"])],
    )
    with pytest.raises(CatalogConflict, match="platform\\+url"):
        plan_sync(catalog_rows(BASE), new)


def test_new_product_reusing_an_existing_key_is_conflict():
    new = make(
        [product(1, 128), product(3, 512, product_key="apple_iphone_15_256gb")],
        [listing(1, 1)],
    )
    with pytest.raises(CatalogConflict, match="product_key"):
        plan_sync(catalog_rows(BASE), new)


def test_catalog_checksum_ignores_line_endings(tmp_path):
    text = FIXTURE.read_text(encoding="utf-8").replace("\r\n", "\n")
    lf, crlf = tmp_path / "lf.json", tmp_path / "crlf.json"
    lf.write_bytes(text.encode("utf-8"))
    crlf.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert read_catalog(lf)[1] == read_catalog(crlf)[1]


# --- sync_catalog: gerçek veritabanı ---------------------------------------------


@pytest.fixture
def migrated(db):
    migrate(db)
    return db


def test_fixture_catalog_is_synced_once(migrated):
    catalog, _ = read_catalog(FIXTURE)
    plan = sync_catalog(migrated, catalog)
    assert [len(c.added) for c in plan.tables.values()] == [2, 6, 45]
    assert table_counts(migrated) == (2, 6, 45)
    assert not sync_catalog(migrated, catalog).changed


def test_dry_run_writes_nothing(migrated):
    plan = sync_catalog(migrated, BASE, dry_run=True)
    assert plan.changed
    assert table_counts(migrated) == (0, 0, 0)


def test_conflict_writes_nothing(migrated):
    sync_catalog(migrated, BASE)
    # Yeni bir ürün + sayfa geçerli, ama trendyol_1 başka ürüne taşınmış.
    new = make(
        [product(1, 128), product(2, 256), product(3, 512)],
        [listing(1, 2), listing(2, 2), listing(3, 3)],
    )
    with pytest.raises(CatalogConflict):
        sync_catalog(migrated, new)
    assert table_counts(migrated) == (1, 2, 2)


def test_deactivation_keeps_the_row(migrated):
    sync_catalog(migrated, BASE)
    sync_catalog(migrated, make([product(1, 128), product(2, 256)], [listing(1, 1)]))
    rows = migrated.execute(
        "SELECT listing_id, active FROM listings ORDER BY listing_id"
    ).fetchall()
    assert rows == [("trendyol_1", True), ("trendyol_2", False)]


def test_product_deactivation_is_written(migrated):
    sync_catalog(migrated, BASE)
    sync_catalog(migrated, make([product(1, 128)], [listing(1, 1)]))
    rows = migrated.execute(
        "SELECT product_id, active FROM products ORDER BY product_id"
    ).fetchall()
    assert rows == [(1, True), (2, False)]


def test_address_moved_to_a_new_listing_is_applied(migrated):
    sync_catalog(migrated, BASE)
    old_url = listing(1, 1)["url"]
    new = make(
        [product(1, 128), product(2, 256)],
        [
            listing(1, 1, url="https://www.trendyol.com/yeni-p-1"),
            listing(2, 2),
            listing(3, 1, url=old_url),
        ],
    )
    sync_catalog(migrated, new)  # önce güncelleme, sonra ekleme: çakışma yok
    urls = dict(migrated.execute("SELECT listing_id, url FROM listings").fetchall())
    assert urls["trendyol_3"] == old_url


def test_address_swap_is_a_clear_conflict(migrated):
    sync_catalog(migrated, BASE)
    swapped = make(
        [product(1, 128), product(2, 256)],
        [
            listing(1, 1, url=listing(2, 2)["url"]),
            listing(2, 2, url=listing(1, 1)["url"]),
        ],
    )
    with pytest.raises(CatalogConflict, match="iki adımda"):
        sync_catalog(migrated, swapped)
    urls = dict(migrated.execute("SELECT listing_id, url FROM listings").fetchall())
    assert urls["trendyol_1"] == listing(1, 1)["url"]  # hiçbir şey yazılmadı


def test_catalog_with_byte_order_mark_is_read(tmp_path):
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + FIXTURE.read_bytes())
    assert read_catalog(path)[0] == read_catalog(FIXTURE)[0]


def test_synced_listing_accepts_a_result_row(migrated):
    sync_catalog(migrated, BASE)
    run_id = migrated.execute(
        "INSERT INTO collection_runs (trigger, status, catalog_sha256, planned_count)"
        " VALUES ('manual', 'running', %s, 1) RETURNING run_id",
        ("0" * 64,),
    ).fetchone()[0]
    migrated.execute(
        "INSERT INTO listing_checks (run_id, listing_id, product_id)"
        " VALUES (%s, 'trendyol_1', 1)",
        (run_id,),
    )


# --- Komut satırı ---------------------------------------------------------------


def test_cli_refuses_to_sync_before_migrate(db, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("CATALOG_PATH", str(FIXTURE))
    assert main(["sync-catalog"]) == 1
    assert "önce `migrate`" in capsys.readouterr().err


def test_cli_dry_run_then_write_then_nothing(migrated, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("CATALOG_PATH", str(FIXTURE))

    assert main(["sync-catalog", "--dry-run"]) == 0
    assert "hiçbir şey yazılmadı" in capsys.readouterr().out
    assert table_counts(migrated) == (0, 0, 0)

    assert main(["sync-catalog"]) == 0
    assert "Eşitleme yazıldı" in capsys.readouterr().out
    assert table_counts(migrated) == (2, 6, 45)

    assert main(["sync-catalog"]) == 0
    assert "Değişiklik yok" in capsys.readouterr().out


def test_cli_reports_conflict_and_fails(migrated, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    sync_catalog(migrated, BASE)
    moved = BASE.model_dump()
    moved["listings"][0]["product_id"] = 2
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(moved), encoding="utf-8")
    monkeypatch.setenv("CATALOG_PATH", str(path))
    assert main(["sync-catalog"]) == 1
    assert "trendyol_1: product_id değişemez" in capsys.readouterr().err
