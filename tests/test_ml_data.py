"""ML veri görüntüsünün veritabanı okuması ve `python -m app.ml snapshot` komutu."""

import os
from datetime import date, datetime, timedelta, timezone

import pytest
from psycopg.pq import TransactionStatus

from app.database.migrate import load
from app.database.ml_data import MlDataBusy, MlDataError, read_ml_data
from app.ml.__main__ import main
from app.ml.dataset import build_snapshot, read_snapshot
from tests.support.read_world import START, add_market, add_run

UTC = timezone.utc


def fill(world):
    first = add_run(
        world, START, {"a": ("offer", 4_299_900), "b": "sold_out", "c": "error"}
    )
    second = add_run(
        world,
        START + timedelta(hours=12),
        {"a": ("offer", 4_199_900), "d": "planned"},
        status="interrupted",
    )
    add_market(world, date(2024, 10, 30), 4_350_000)
    add_market(world, date(2024, 10, 31), None)
    return first, second


def test_reads_every_table_with_the_read_account(world, api_db):
    first, second = fill(world)
    data = read_ml_data(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    assert data.schema_version == len(load())
    tables = data.tables
    assert [row["product_id"] for row in tables["products"]] == [1, 2, 3]
    assert tables["products"][2] == {
        "product_id": 3,
        "product_key": "poco_x6_pro_512gb",
        "brand": "POCO",
        "model": "X6 Pro",
        "storage_gb": 512,
        "active": False,
    }
    assert tables["platforms"] == [
        {"key": "hepsiburada", "active": True},
        {"key": "trendyol", "active": True},
    ]
    assert tables["listings"][2] == {
        "listing_id": "c",
        "product_id": 1,
        "platform": "hepsiburada",
        "active": True,
    }
    assert tables["collection_runs"] == [
        {
            "run_id": first,
            "trigger": "manual",
            "status": "completed",
            "started_at": START,
            "finished_at": START + timedelta(minutes=30),
            "planned_count": 3,
        },
        {
            "run_id": second,
            "trigger": "manual",
            "status": "interrupted",
            "started_at": START + timedelta(hours=12),
            "finished_at": START + timedelta(hours=12, minutes=30),
            "planned_count": 2,
        },
    ]
    assert tables["listing_checks"][0] == {
        "run_id": first,
        "listing_id": "a",
        "product_id": 1,
        "checked_at": START + timedelta(minutes=1),
        "outcome": "offer",
        "current_price": 4_299_900,
    }
    assert [
        (row["outcome"], row["current_price"]) for row in tables["listing_checks"]
    ] == [
        ("offer", 4_299_900),
        ("sold_out", None),
        ("error", None),
        ("offer", 4_199_900),
        (None, None),
    ]
    assert tables["market_history"] == [
        {
            "product_id": 1,
            "source": "cimri",
            "source_product_id": "123456",
            "day": day,
            "price_kurus": price,
            "captured_at": START,
        }
        for day, price in ((date(2024, 10, 30), 4_350_000), (date(2024, 10, 31), None))
    ]
    snapshot = build_snapshot(tables, datetime(2026, 10, 28, tzinfo=UTC), 5)
    assert len(snapshot.listing_checks) == 5


def test_refuses_while_a_tour_is_running(world, api_db):
    run_id = add_run(world, START, {"a": "planned"}, status="running")
    with pytest.raises(MlDataBusy, match=f"Tur {run_id} sürüyor"):
        read_ml_data(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE


def test_refuses_when_a_migration_is_pending(world, api_db):
    world.execute(
        "DELETE FROM schema_migrations"
        " WHERE version = (SELECT max(version) FROM schema_migrations)"
    )
    with pytest.raises(MlDataError, match="Bekleyen migration"):
        read_ml_data(api_db)


def test_refuses_the_owner_account(migrated):
    with pytest.raises(MlDataError, match="okuma hesabı"):
        read_ml_data(migrated)


@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])


def test_cli_writes_a_verified_snapshot(world, api_env, tmp_path, capsys):
    fill(world)
    target = tmp_path / "ml_veri"
    assert main(["snapshot", "--output-dir", str(target)]) == 0
    snapshot, digest = read_snapshot(target)
    out = capsys.readouterr().out
    assert f"SHA-256: {digest}" in out
    assert f"Şema sürümü: {len(load())}" in out
    assert "Ürün: 3 (etkin 2); sayfa: 5 (etkin 5)" in out
    assert "Tur: 2 (tamamlanan 1, yarıda kalan 1); sayfa sonucu: 5" in out
    assert "Cimri: 2 satır, 1 ürün (eksik fiyat 1)" in out
    assert "Dosya yeniden okunup doğrulandı. Veritabanına yazılmadı." in out
    assert len(snapshot.products) == 3


def test_cli_does_not_create_a_directory_while_a_tour_runs(
    world, api_env, tmp_path, capsys
):
    add_run(world, START, {"a": "planned"}, status="running")
    target = tmp_path / "ml_veri"
    assert main(["snapshot", "--output-dir", str(target)]) == 3
    assert "sürüyor" in capsys.readouterr().err
    assert not target.exists()


def test_cli_refuses_an_existing_directory_before_reading(tmp_path, capsys):
    # Adres tanımlı değil: klasör denetimi veritabanından önce yapılmalı.
    (tmp_path / "eski.txt").write_text("eski", encoding="utf-8")
    assert main(["snapshot", "--output-dir", str(tmp_path)]) == 1
    assert "klasör zaten var" in capsys.readouterr().err
    assert [path.name for path in tmp_path.iterdir()] == ["eski.txt"]


def test_cli_without_api_database_url_fails(tmp_path, capsys):
    target = tmp_path / "ml_veri"
    assert main(["snapshot", "--output-dir", str(target)]) == 1
    assert "API_DATABASE_URL tanımlı değil" in capsys.readouterr().err
    assert not target.exists()
