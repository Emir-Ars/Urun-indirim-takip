"""Teslim paketinin bozulma, kaynak izolasyonu ve tekrar hazırlama sınırları."""

import json
import os
import pickle
import shutil
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from filelock import FileLock

from app.contracts import Catalog
from app.database.catalog_sync import sync_catalog
from app.delivery import bundle, database, export, prepare
from app.delivery.__main__ import main
from app.ml.reporting import json_bytes
from app.scrape_lock import ScrapeBusy
from tests.support.delivery import write_bundle, write_source
from tests.support.read_world import START, add_run


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    return write_source(tmp_path_factory.mktemp("delivery_source"))


@pytest.fixture
def proof():
    from app.database.migrate import load

    return bundle.DatabaseProof(
        name="delivery_test",
        server_version=170011,
        migrations={m.file_name: m.checksum for m in load()},
        schema_sha256=database.SCHEMA_SHA256,
        tables={name: dict(rows=0, sha256="0" * 64) for name in database.TABLES},
        sequence_value=1,
        sequence_called=False,
    )


@pytest.fixture
def package(source, proof, tmp_path):
    path = tmp_path / "package"
    write_bundle(source, path, proof)
    return path


def test_complete_chain_is_portable_without_unpickling(package, source, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Paket doğrulaması pickle açamaz")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    manifest, identity = bundle.verify_bundle(package, source / "config/shadow.json")
    assert len(identity) == 64
    assert manifest.source_dirty is True
    assert not any("gosterim_onayi" in name for name in manifest.files)
    assert not any("training" in name or "secrets" in name for name in manifest.files)
    assert any("goruntuler/" in name for name in manifest.files)
    assert any("degerlendirme_" in name for name in manifest.files)


def test_evaluation_cannot_lose_its_original_record(package, source):
    name = f"{bundle.SHADOW}/tahmin_01/manifest.json"
    (package / name).unlink()
    path = package / "manifest.json"
    document = json.loads(path.read_bytes())
    document["files"].pop(name)
    path.write_bytes(json_bytes(document))
    with pytest.raises((ValueError, OSError)):
        bundle.verify_bundle(package, source / "config/shadow.json")


@pytest.mark.parametrize(
    "change", ["hash", "extra", "missing", "dump", "code", "migration", "model", "path"]
)
def test_corrupted_package_is_rejected_before_target(package, source, change):
    path = package / "manifest.json"
    document = json.loads(path.read_bytes())
    if change == "hash":
        (package / "config/runtime.json").write_bytes(b"{} ")
    elif change == "extra":
        (package / "password.txt").write_text("yapay")
    elif change == "missing":
        (package / "config/runtime.json").unlink()
    elif change == "dump":
        (package / "database.dump").write_bytes(b"invalid")
        document["files"]["database.dump"] = bundle.sha(package / "database.dump")
    elif change == "code":
        document["code_sha256"] = "0" * 64
    elif change == "migration":
        document["database"]["migrations"] = {}
    elif change == "model":
        document["model_manifest_sha256"] = "0" * 64
    else:
        document["files"]["../outside"] = "0" * 64
    path.write_bytes(json_bytes(document))
    with pytest.raises((bundle.DeliveryError, ValueError)):
        bundle.verify_bundle(package, source / "config/shadow.json")


def test_sources_duplicates_and_partial_records(source, tmp_path):
    copy = tmp_path / "source"
    shutil.copytree(source, copy)
    golge = copy / bundle.SHADOW
    partial = golge / "tahmin_partial"
    partial.mkdir()
    (partial / "predictions.jsonl").write_bytes(b"half")
    (golge / "gosterim_onayi.json").write_bytes(b"private Windows approval")
    output = tmp_path / "out"
    export.copy_assets(copy, output, copy / "config/shadow.json")
    assert not (output / bundle.SHADOW / partial.name).exists()
    assert not (output / bundle.SHADOW / "gosterim_onayi.json").exists()
    source_folder = next((output / bundle.SHADOW / "goruntuler").iterdir())
    (source_folder / "snapshot.json").unlink()
    with pytest.raises((ValueError, OSError)):
        bundle.validate_assets(output, copy / "config/shadow.json")
    shutil.copytree(golge / "tahmin_01", golge / "tahmin_02")
    with pytest.raises(ValueError, match="iki kayıt klasöründe"):
        export.copy_assets(copy, tmp_path / "duplicate", copy / "config/shadow.json")


@pytest.mark.parametrize(
    "path", ["../x", "/x", "C:/x", "a\\b", "a/../b", "./a", "a//b", ""]
)
def test_unsafe_paths(path, tmp_path):
    with pytest.raises(bundle.DeliveryError):
        bundle.safe_path(tmp_path, path)


def test_reparse_point_rejected(tmp_path, monkeypatch):
    folder = tmp_path / "evidence"
    folder.mkdir()
    original = Path.lstat

    def lstat(path, *args, **kwargs):
        if path == folder:
            return SimpleNamespace(st_mode=0, st_file_attributes=0x400)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(bundle.DeliveryError):
        bundle.inventory(tmp_path)


def test_export_busy_and_existing_destination_do_not_touch_db(
    source, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        database, "source_connection", lambda *a: pytest.fail("DB açılmamalı")
    )
    with pytest.raises(bundle.DeliveryError):
        export.export_bundle(source, "pg_dump", "unused", source=source)
    with FileLock(str(source / "data/scrape.lock")):
        with pytest.raises(ScrapeBusy):
            export.export_bundle(tmp_path / "new", "pg_dump", "unused", source=source)
    assert not (tmp_path / "new").exists()


def test_source_connection_forces_read_only_and_hides_password(monkeypatch):
    calls = []
    monkeypatch.setattr(psycopg, "connect", lambda *a, **k: calls.append((a, k)))
    for key in ("PGPASSWORD", "PGPASSFILE", "PGSERVICE"):
        monkeypatch.delenv(key, raising=False)
    database.source_connection("postgresql://tester@localhost/delivery_test")
    assert "default_transaction_read_only=on" in calls[0][1]["options"]
    with pytest.raises(bundle.DeliveryError):
        database.source_connection("postgresql://tester:secret@localhost/delivery_test")
    monkeypatch.setenv("PGPASSFILE", "secret")
    with pytest.raises(bundle.DeliveryError):
        database.source_connection("postgresql://tester@localhost/delivery_test")
    assert len(calls) == 1


def test_dump_uses_same_snapshot_and_never_passes_password(tmp_path, monkeypatch):
    import subprocess

    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(stdout="pg_dump (PostgreSQL) 17.11", returncode=0)

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setenv("DATABASE_URL", "private")
    monkeypatch.setenv("PGPASSWORD", "private")
    conn = SimpleNamespace(
        info=SimpleNamespace(
            host="localhost", port=5432, user="reader", dbname="delivery_test"
        )
    )
    database.dump_database(conn, "pg_dump", tmp_path / "out", "snapshot-id")
    args, options = calls[-1]
    assert "--snapshot=snapshot-id" in args
    assert "--format=custom" in args and "--no-password" in args
    assert "default_transaction_read_only=on" in options["env"]["PGOPTIONS"]
    assert "PGPASSWORD" not in options["env"] and "DATABASE_URL" not in options["env"]
    assert "private" not in str(calls)


def test_container_guard_blocks_native_target(monkeypatch):
    monkeypatch.setattr(database.sys, "platform", "win32")
    monkeypatch.setattr(
        psycopg, "connect", lambda *a, **k: pytest.fail("Bağlantı açılmamalı")
    )
    with pytest.raises(bundle.DeliveryError, match="Docker"):
        database.target_connection("fiyat_takip", "unused")


def test_database_proof_detects_changed_rows_and_running_turn(world):
    first = database.fingerprint(world)
    add_run(world, START, {"a": ("offer", 10000)})
    with pytest.raises(bundle.DeliveryError, match="parmak"):
        prepare.check_database(world, first)
    add_run(world, START + timedelta(days=1), {"a": "planned"}, status="running")
    with pytest.raises(bundle.DeliveryError, match="Süren"):
        database.fingerprint(world)


@pytest.mark.parametrize("change", ["column", "trigger", "constraint"])
def test_migration_rows_do_not_hide_schema_drift(migrated, change):
    if change == "column":
        migrated.execute("ALTER TABLE products ADD COLUMN unexpected text")
    elif change == "trigger":
        migrated.execute(
            "ALTER TABLE market_history DISABLE TRIGGER market_history_no_update"
        )
    else:
        migrated.execute(
            "ALTER TABLE products DROP CONSTRAINT products_product_id_check"
        )
    with pytest.raises(bundle.DeliveryError, match="gerçek şeması"):
        database.fingerprint(migrated)


def test_export_is_consistent_and_manifest_is_last(
    migrated, source, tmp_path, monkeypatch
):
    catalog = Catalog.model_validate_json((source / "config/catalog.json").read_bytes())
    sync_catalog(migrated, catalog)
    before = database.fingerprint(migrated)

    def connect(url):
        assert url == os.environ["TEST_DATABASE_URL"]
        return psycopg.connect(
            url,
            autocommit=True,
            options=(
                "-c default_transaction_read_only=on -c TimeZone=UTC "
                "-c DateStyle=ISO,YMD"
            ),
        )

    def dump(conn, executable, path, snapshot):
        assert conn.execute("SHOW transaction_read_only").fetchone()[0] == "on"
        assert (
            conn.execute("SHOW transaction_isolation").fetchone()[0]
            == "repeatable read"
        )
        assert snapshot and not (path.parent / "manifest.json").exists()
        path.write_bytes(b"PGDMPsynthetic")

    monkeypatch.setattr(database, "source_connection", connect)
    monkeypatch.setattr(database, "dump_database", dump)
    path = tmp_path / "bundle"
    manifest, digest = export.export_bundle(
        path,
        "pg_dump",
        os.environ["TEST_DATABASE_URL"],
        source=source,
        reference=source / "config/shadow.json",
    )
    assert len(digest) == 64 and manifest.database == before
    assert database.fingerprint(migrated) == before


def test_installed_files_detect_corruption_and_extra_files(package, source, tmp_path):
    manifest, _ = bundle.verify_bundle(package, source / "config/shadow.json")
    root = tmp_path / "installed"
    for name in manifest.files:
        if name.startswith(("config/", bundle.SHADOW + "/")):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(package / name, target)
    prepare.check_files(manifest, root)
    (root / "config/extra").write_bytes(b"unknown")
    with pytest.raises(bundle.DeliveryError, match="kapsam"):
        prepare.check_files(manifest, root)
    (root / "config/extra").unlink()
    (root / "config/runtime.json").write_bytes(b"changed")
    with pytest.raises(bundle.DeliveryError, match="SHA"):
        prepare.check_files(manifest, root)


def test_cli_does_not_echo_connection_or_sql_failure(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://person:private@host/fiyat_takip")
    monkeypatch.setattr(
        export,
        "export_bundle",
        lambda *a: (_ for _ in ()).throw(psycopg.Error("private")),
    )
    assert main(["export", "--output", "unused"]) == 1
    assert "private" not in capsys.readouterr().err
