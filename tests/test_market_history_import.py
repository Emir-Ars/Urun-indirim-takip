"""Ağsız kaynak doğrulaması ve yalnız _test veritabanında geçmiş aktarımı."""

import hashlib
import json
import os
import shutil
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
import pytest

import app.collection.service as collection
import app.database.market_history as storage
import app.market_history.__main__ as command
import app.market_history.capture as captures
import app.market_history.importer as reader
from app.database.catalog_sync import sync_catalog
from app.database.connection import connect
from app.database.migrate import MIGRATIONS_DIR, MigrationError, migrate, pending
from app.database.runs import try_lock_runs, unlock_runs
from app.market_history.capture import Mapping, capture
from app.market_history.importer import HistoryImportError, HistoryPoint, read_capture
from app.scrape_lock import scrape_lock
from app.settings import Runtime
from tests.test_collection import FakeScrapers, OFFER, run_snapshot, write_catalog
from tests.test_database import insert
from tests.test_market_history import (
    FRONTEND_SAMPLES,
    MAPPING,
    SAMPLES,
    fake_clients,
    good_pair,
    page_html,
    small_catalog,
    source_pair,
)

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def save_report(directory, report):
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def snapshot_files(directory):
    return {
        str(p.relative_to(directory)): p.read_bytes()
        for p in directory.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def input_files(tmp_path, monkeypatch):
    monkeypatch.setattr(captures, "utc_now", lambda: NOW)
    catalog = small_catalog()
    client, _ = fake_clients(*(good_pair(sample) for sample in SAMPLES[:3]))
    directory = tmp_path / "capture"
    report = capture(catalog, MAPPING, directory, Runtime(), client_class=client)
    assert report["result"] == "completed"
    return directory, catalog, report


def test_reader_recomputes_history_without_writing_or_network(input_files):
    directory, catalog, report = input_files
    before = snapshot_files(directory)
    batch = read_capture(directory, catalog)
    assert len(batch.verified) == 3 and not batch.skipped
    for product, record in zip(batch.verified, report["products"]):
        assert [(p.day.isoformat(), p.price_kurus) for p in product.points] == [
            (p["day"], p["price_kurus"]) for p in record["history"]["points"]
        ]
        assert product.captured_at == NOW
    assert snapshot_files(directory) == before


def test_report_resolving_outside_capture_is_rejected(
    input_files, tmp_path, monkeypatch
):
    directory, catalog, _ = input_files
    report_path = directory / "report.json"
    outside = tmp_path / "outside.json"
    original = Path.resolve
    monkeypatch.setattr(
        Path,
        "resolve",
        lambda path, **kwargs: (
            outside if path == report_path else original(path, **kwargs)
        ),
    )
    with pytest.raises(HistoryImportError, match="klasörü dışında"):
        read_capture(directory, catalog)


def test_reader_parses_the_same_bytes_it_verified(input_files, monkeypatch):
    directory, catalog, report = input_files
    target = directory / report["products"][0]["api"]["file"]
    original = reader.verified_page

    def replace_after_read(*args):
        target.write_text("{}", encoding="utf-8")
        return original(*args)

    monkeypatch.setattr(reader, "verified_page", replace_after_read)
    batch = read_capture(directory, catalog)
    assert len(batch.verified) == 3 and not batch.skipped
    assert batch.verified[0].api_sha256 == report["products"][0]["api"]["sha256"]
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest() != batch.verified[0].api_sha256
    )


@pytest.mark.parametrize("sample", FRONTEND_SAMPLES, ids=lambda s: s["product_key"])
def test_recorded_sources_can_be_captured_and_revalidated(
    tmp_path, monkeypatch, sample
):
    moment = datetime.fromisoformat(sample["captured_at_utc"])
    monkeypatch.setattr(captures, "utc_now", lambda: moment)
    client, _ = fake_clients((page_html(sample["page"]), deepcopy(sample["response"])))
    catalog = small_catalog([sample["product_key"]])
    directory = tmp_path / "capture"
    report = capture(
        catalog,
        Mapping(version=1, source="cimri", entries=[sample["mapping"]]),
        directory,
        Runtime(),
        client_class=client,
    )
    assert report["result"] == "completed"
    batch = read_capture(directory, catalog)
    assert not batch.skipped and len(batch.verified) == 1
    assert batch.verified[0].summary == report["products"][0]["history"]["summary"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 2),
        ("version", True),
        ("source", "other"),
        ("result", "running"),
        ("finished_at_utc", None),
        ("finished_at_utc", "2026-10-07T12:00:00+00:00"),
        ("started_at_utc", "2026-10-08T12:00:00"),
        ("products", []),
        ("catalog_product_count", 1),
    ],
)
def test_reader_rejects_invalid_envelope(input_files, field, value):
    directory, catalog, report = input_files
    report[field] = value
    save_report(directory, report)
    with pytest.raises(HistoryImportError, match="raporu"):
        read_capture(directory, catalog)


@pytest.mark.parametrize(
    "text", ['{"version":1,"version":1}', '{"version":NaN}', "[]", "{"]
)
def test_reader_rejects_invalid_json(input_files, text):
    directory, catalog, _ = input_files
    (directory / "report.json").write_text(text, encoding="utf-8")
    with pytest.raises(HistoryImportError):
        read_capture(directory, catalog)


@pytest.mark.parametrize("field", ["product_id", "product_key"])
def test_reader_rejects_duplicate_product_identity(input_files, field):
    directory, catalog, report = input_files
    report["products"][1]["product"][field] = report["products"][0]["product"][field]
    save_report(directory, report)
    with pytest.raises(HistoryImportError, match="tekrarlanan"):
        read_capture(directory, catalog)


@pytest.mark.parametrize(
    "field,value",
    [
        ("product_id", 999),
        ("product_key", "unknown"),
        ("brand", "Other"),
        ("model", "Other"),
        ("storage_gb", 8192),
    ],
)
def test_reader_rejects_catalog_identity_change(input_files, field, value):
    directory, catalog, report = input_files
    report["products"][2]["product"][field] = value
    save_report(directory, report)
    with pytest.raises(HistoryImportError, match="kimliği uyuşmuyor"):
        read_capture(directory, catalog)


@pytest.mark.parametrize("field", ["cimri_product_id", "url"])
def test_reader_rejects_duplicate_mapping(input_files, field):
    directory, catalog, report = input_files
    report["products"][1]["mapping"][field] = report["products"][0]["mapping"][field]
    save_report(directory, report)
    with pytest.raises(HistoryImportError, match="tekrarlanan Cimri"):
        read_capture(directory, catalog)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_page",
        "changed_api",
        "bad_hash",
        "path_escape",
        "absolute_path",
        "windows_path",
        "old_time",
        "old_summary",
        "late_time",
        "non_utc",
        "changed_identity",
        "changed_point",
        "bool_point",
        "changed_summary",
        "bad_api_json",
        "wrong_source_id",
        "invalid_price",
        "different_model",
    ],
)
def test_reader_rejects_only_the_damaged_product(input_files, damage, tmp_path):
    directory, catalog, report = input_files
    record = report["products"][0]
    api_path = directory / record["api"]["file"]
    if damage == "missing_page":
        (directory / record["page"]["file"]).unlink()
    elif damage == "changed_api":
        api_path.write_bytes(api_path.read_bytes() + b" ")
    elif damage == "bad_hash":
        record["page"]["sha256"] = "wrong"
    elif damage in {"path_escape", "absolute_path", "windows_path"}:
        outside = tmp_path / "outside.html"
        outside.write_bytes((directory / record["page"]["file"]).read_bytes())
        record["page"]["file"] = {
            "path_escape": "../outside.html",
            "absolute_path": str(outside),
            "windows_path": r"C:\outside.html",
        }[damage]
    elif damage == "old_time":
        record.pop("page_started_at_utc")
    elif damage == "old_summary":
        record["history"]["summary"].pop("latest_price")
    elif damage == "late_time":
        record["captured_at_utc"] = (NOW + timedelta(seconds=1)).isoformat()
    elif damage == "non_utc":
        record["page_started_at_utc"] = "2026-10-08T15:00:00+03:00"
    elif damage == "changed_identity":
        record["identity"]["title"] = "Başka başlık"
    elif damage == "changed_point":
        record["history"]["points"][0]["price_kurus"] += 1
    elif damage == "bool_point":
        record["history"]["summary"]["missing_price_count"] = False
    elif damage == "changed_summary":
        record["history"]["summary"]["table_compared_rows"] += 1
    elif damage == "different_model":
        path = directory / record["page"]["file"]
        text = path.read_text(encoding="utf-8").replace(
            record["product"]["model"], "Other 999"
        )
        path.write_text(text, encoding="utf-8")
        record["page"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    else:
        payload = json.loads(api_path.read_text(encoding="utf-8"))
        if damage == "wrong_source_id":
            payload["data"]["priceHistoryV2"]["productId"] = "999999"
        elif damage == "invalid_price":
            payload["data"]["priceHistoryV2"]["prices"][0] = -1
        api_path.write_text(
            "{" if damage == "bad_api_json" else json.dumps(payload), encoding="utf-8"
        )
        record["api"]["sha256"] = hashlib.sha256(api_path.read_bytes()).hexdigest()
    save_report(directory, report)
    before = snapshot_files(directory)
    batch = read_capture(directory, catalog)
    assert len(batch.verified) == 2 and len(batch.skipped) == 1
    assert batch.skipped[0][0] == record["product"]["product_key"]
    assert snapshot_files(directory) == before


@pytest.mark.parametrize("result", ["partial", "interrupted", "failed"])
@pytest.mark.parametrize(
    "status", ["error", "unmapped", "not_attempted", "interrupted"]
)
def test_reader_does_not_promote_failed_records(input_files, result, status):
    directory, catalog, report = input_files
    report["result"] = result
    record = report["products"][0]
    record["status"] = status
    if status == "unmapped":
        record["mapping"] = None
    save_report(directory, report)
    batch = read_capture(directory, catalog)
    assert len(batch.verified) == 2 and len(batch.skipped) == 1


@pytest.fixture
def prepared(db, input_files, monkeypatch, tmp_path):
    directory, catalog, report = input_files
    migrate(db)
    sync_catalog(db, catalog)
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(catalog.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("CATALOG_PATH", str(catalog_path))
    monkeypatch.setenv("SCRAPE_LOCK_PATH", str(tmp_path / "scrape.lock"))
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv("RUNTIME_PATH", str(tmp_path / "must_not_read_runtime.json"))
    return db, directory, catalog, report


def rows(conn):
    return conn.execute(
        "SELECT * FROM market_history ORDER BY product_id, source, day"
    ).fetchall()


def single(batch, item):
    return replace(batch, products=(item.product,), verified=(item,), skipped=())


def test_import_preview_repeat_and_original_provenance(prepared, capsys):
    conn, directory, catalog, _ = prepared
    before = snapshot_files(directory)
    assert command.main(["import", str(directory), "--dry-run"]) == 0
    assert not rows(conn)
    assert "9 eklenecek" in capsys.readouterr().out
    assert command.main(["import", str(directory)]) == 0
    written = rows(conn)
    assert len(written) == 9
    assert "9 eklendi" in capsys.readouterr().out
    assert command.main(["import", str(directory)]) == 0
    assert "0 eklendi, 9 aynı" in capsys.readouterr().out
    assert rows(conn) == written and snapshot_files(directory) == before
    batch = read_capture(directory, catalog)
    changed = replace(
        batch,
        verified=tuple(
            replace(
                item,
                captured_at=NOW + timedelta(hours=1),
                page_sha256="a" * 64,
                api_sha256="b" * 64,
                report_sha256="c" * 64,
                mapping=item.mapping.model_copy(
                    update={"url": item.mapping.url + "?new=1"}
                ),
            )
            for item in batch.verified
        ),
    )
    result = storage.import_history(conn, changed)
    assert not result.partial and sum(p.unchanged for p in result.products) == 9
    assert rows(conn) == written


def test_preview_uses_read_only_transaction_and_never_attempts_insert(
    prepared, monkeypatch
):
    conn, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    original = storage._existing
    seen = []

    def check_read_only(worker, product):
        seen.append(worker.execute("SHOW transaction_read_only").fetchone()[0])
        assert (
            worker.execute("SHOW transaction_isolation").fetchone()[0]
            == "repeatable read"
        )
        return original(worker, product)

    monkeypatch.setattr(storage, "_existing", check_read_only)
    monkeypatch.setattr(
        storage, "_insert", lambda *a: pytest.fail("Önizleme INSERT denedi")
    )
    result = storage.import_history(conn, batch, dry_run=True)
    assert seen == ["on"] * 3 and not result.partial and not rows(conn)


@pytest.mark.parametrize(
    "old,new", [(None, None), (100, 100), (None, 100), (100, None), (100, 101)]
)
def test_null_and_price_conflicts_skip_all_new_days(prepared, old, new):
    conn, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    item = batch.verified[0]
    day = date(2026, 10, 7)
    old_item = replace(item, points=(HistoryPoint(day, old),))
    storage.import_history(conn, single(batch, old_item))
    previous = rows(conn)
    incoming = replace(
        item,
        points=(HistoryPoint(day - timedelta(days=1), 999), HistoryPoint(day, new)),
    )
    candidate = single(batch, incoming)
    preview = storage.import_history(conn, candidate, dry_run=True)
    actual = storage.import_history(conn, candidate)
    assert actual == preview
    if old != new:
        assert actual.partial and rows(conn) == previous
        assert "2026-10-07" in actual.products[0].conflicts[0]
    else:
        assert not actual.partial and actual.products[0].added == 1
        assert len(rows(conn)) == 2


def test_missing_prices_and_uncompared_dates_survive_cli(prepared, capsys):
    conn, directory, catalog, _ = prepared
    page, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"] = [100, None, 100, 0, 100]
    response["data"]["priceHistoryV2"]["lastDay"] = "2026-10-08"
    page["priceHistoryTablePrices"] = [
        {"date": "08/10/2026", "minPrice": 100},
        {"date": "06/10/2026", "minPrice": 100},
    ]
    client, _ = fake_clients((page_html(page), response))
    new_dir = directory.parent / "missing"
    capture(
        catalog,
        MAPPING,
        new_dir,
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    assert command.main(["import", str(new_dir)]) == 0
    output = capsys.readouterr().out
    assert "eksik fiyat: 2" in output
    assert (
        "Tabloyla karşılaştırılamayan 3 gün: 2026-10-04–2026-10-05, 2026-10-07"
        in output
    )
    assert [(r[4], r[5]) for r in rows(conn)] == [
        (date(2026, 10, day), None if day in (5, 7) else 10000) for day in range(4, 9)
    ]


def test_bigint_overflow_is_rejected_before_storage(input_files):
    directory, catalog, _ = input_files
    page, response = source_pair()
    response["data"]["priceHistoryV2"]["prices"][0] = 2**63
    page["priceHistoryTablePrices"][0]["minPrice"] = 2**63
    client, _ = fake_clients((page_html(page), response))
    new_dir = directory.parent / "overflow"
    capture(
        catalog,
        MAPPING,
        new_dir,
        Runtime(),
        [SAMPLES[0]["product_key"]],
        client_class=client,
    )
    batch = read_capture(new_dir, catalog)
    assert not batch.verified and "bigint sınırını" in batch.skipped[0][1]


def normal_collection(conn, catalog, tmp_path, monkeypatch):
    from app.collection.__main__ import main as collect_main

    contents = catalog.model_dump(mode="json")
    contents["platforms"] = [
        {"key": "trendyol", "name": "Trendyol", "hosts": ["www.trendyol.com"]}
    ]
    contents["listings"] = [
        {
            "listing_id": f"trendyol_{product.product_id}",
            "product_id": product.product_id,
            "platform": "trendyol",
            "url": f"https://www.trendyol.com/phone-p-{product.product_id}",
        }
        for product in catalog.products
    ]
    (tmp_path / "catalog.json").write_text(json.dumps(contents), encoding="utf-8")
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("RUNTIME_PATH", str(runtime_path))
    monkeypatch.setattr(
        collection,
        "create_scraper",
        FakeScrapers(
            {listing["listing_id"]: OFFER for listing in contents["listings"]}
        ),
    )
    previous = rows(conn)
    assert collect_main([]) == 0
    assert conn.execute(
        "SELECT status, planned_count FROM collection_runs"
    ).fetchall() == [("completed", 3)]
    assert rows(conn) == previous


def test_collection_after_import_preserves_history(prepared, tmp_path, monkeypatch):
    conn, directory, catalog, _ = prepared
    assert command.main(["import", str(directory)]) == 0
    normal_collection(conn, catalog, tmp_path, monkeypatch)


def test_source_identity_conflict_preserves_whole_product_and_continues(prepared):
    conn, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    item = batch.verified[0]
    storage.import_history(conn, single(batch, replace(item, points=item.points[:1])))
    changed = replace(
        item, mapping=item.mapping.model_copy(update={"cimri_product_id": "99999"})
    )
    result = storage.import_history(
        conn, replace(batch, verified=(changed, *batch.verified[1:]))
    )
    assert result.partial and result.products[0].added == 0
    assert sum(p.added for p in result.products) == 6 and len(rows(conn)) == 7
    assert [r[2] for r in rows(conn) if r[0] == item.product.product_id] == [
        item.mapping.cimri_product_id
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("product_id", 999),
        ("product_key", "different"),
        ("brand", "Other"),
        ("model", "Other"),
        ("storage_gb", 8192),
    ],
)
def test_database_identity_mismatch_aborts_before_first_write(prepared, field, value):
    conn, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    third = batch.products[2].model_copy(update={field: value})
    batch = replace(batch, products=(*batch.products[:2], third))
    with pytest.raises(HistoryImportError, match="hiçbir ürün yazılmadı"):
        storage.import_history(conn, batch)
    assert not rows(conn)


def test_partial_cli_reports_damage_and_keeps_source_files(prepared, capsys):
    conn, directory, _, report = prepared
    (directory / report["products"][0]["api"]["file"]).write_text(
        "{}", encoding="utf-8"
    )
    before = snapshot_files(directory)
    assert command.main(["import", str(directory)]) == 2
    assert len(rows(conn)) == 6 and snapshot_files(directory) == before
    output = capsys.readouterr().out
    assert "parmak izi uyuşmuyor" in output and "atlanan ürün: 1" in output


@pytest.mark.parametrize("lock_kind", ["file", "database"])
def test_cli_busy_and_retry_release_both_locks(prepared, tmp_path, lock_kind):
    conn, directory, _, _ = prepared
    if lock_kind == "file":
        with scrape_lock(tmp_path / "scrape.lock"):
            assert command.main(["import", str(directory)]) == 3
    else:
        assert try_lock_runs(conn)
        try:
            assert command.main(["import", str(directory)]) == 3
        finally:
            unlock_runs(conn)
    assert not rows(conn)
    assert command.main(["import", str(directory)]) == 0
    with scrape_lock(tmp_path / "scrape.lock"):
        pass
    assert try_lock_runs(conn)
    unlock_runs(conn)


@pytest.mark.parametrize(
    "failure,code", [("sql", 1), ("ctrl_c", 130), ("connection", 1)]
)
def test_mid_product_failure_preserves_completed_products_and_can_restart(
    prepared, monkeypatch, tmp_path, capsys, failure, code
):
    observer, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    original = storage._insert

    def fail_second(worker, product):
        if product.product.product_id != batch.verified[1].product.product_id:
            return original(worker, product)
        original(worker, replace(product, points=product.points[:1]))
        assert len(rows(observer)) == 3
        if failure == "sql":
            worker.execute("SELECT maintenance92_missing_column FROM market_history")
        elif failure == "connection":
            worker.close()
            worker.execute("SELECT 1")
        else:
            raise KeyboardInterrupt()

    with monkeypatch.context() as patch:
        patch.setattr(storage, "_insert", fail_second)
        assert command.main(["import", str(directory)]) == code
    previous = rows(observer)
    assert len(previous) == 3
    if failure == "ctrl_c":
        assert "Tamamlanmış ürünler korunur" in capsys.readouterr().err
    with scrape_lock(tmp_path / "scrape.lock"):
        pass
    assert try_lock_runs(observer)
    unlock_runs(observer)
    assert command.main(["import", str(directory)]) == 0
    assert len(rows(observer)) == 9
    assert [
        r for r in rows(observer) if r[0] == batch.verified[0].product.product_id
    ] == previous
    normal_collection(observer, catalog, tmp_path, monkeypatch)


@pytest.mark.parametrize("different", [False, True])
def test_concurrent_insert_is_compared_after_on_conflict(
    prepared, monkeypatch, different
):
    conn, directory, catalog, _ = prepared
    batch = read_capture(directory, catalog)
    item = batch.verified[0]
    original = storage._insert
    with connect(os.environ["TEST_DATABASE_URL"]) as other:

        def insert_after_comparison(worker, product):
            point = product.points[-1]
            competing = replace(
                product,
                points=(
                    replace(point, price_kurus=point.price_kurus + int(different)),
                ),
            )
            original(other, competing)
            return original(worker, product)

        monkeypatch.setattr(storage, "_insert", insert_after_comparison)
        result = storage.import_history(conn, single(batch, item))
    if different:
        assert result.partial and len(rows(conn)) == 1
        assert result.products[0].added == 0
    else:
        assert not result.partial and len(rows(conn)) == 3
        assert result.products[0].added == 2 and result.products[0].unchanged == 1


def test_lost_commit_reply_reports_uncertainty_and_retry_is_idempotent(
    prepared, monkeypatch, capsys
):
    observer, directory, _, _ = prepared
    real_connect = command.connect

    class LostReply:
        def __init__(self, worker):
            self.worker = worker
            self.first = True

        def __getattr__(self, name):
            return getattr(self.worker, name)

        @contextmanager
        def transaction(self):
            with self.worker.transaction():
                yield
            if self.first:
                self.first = False
                self.worker.close()
                raise psycopg.OperationalError("COMMIT yanıtı kayboldu")

    @contextmanager
    def connection(url):
        with real_connect(url) as worker:
            yield LostReply(worker)

    with monkeypatch.context() as patch:
        patch.setattr(command, "connect", connection)
        assert command.main(["import", str(directory)]) == 1
    assert len(rows(observer)) == 3
    assert "son ürünün sonucu belirsiz" in capsys.readouterr().err
    previous = rows(observer)
    assert command.main(["import", str(directory)]) == 0
    assert len(rows(observer)) == 9
    assert all(row in rows(observer) for row in previous)


def valid_row(product):
    return dict(
        product_id=product.product.product_id,
        source="cimri",
        source_product_id=product.mapping.cimri_product_id,
        source_url=product.mapping.url,
        day=product.points[0].day,
        price_kurus=100,
        captured_at=product.captured_at,
        page_sha256=product.page_sha256,
        api_sha256=product.api_sha256,
        report_sha256=product.report_sha256,
    )


@pytest.mark.parametrize(
    "column,value",
    [
        ("product_id", 999),
        ("source", "other"),
        ("source", None),
        ("source_product_id", ""),
        ("source_product_id", "0"),
        ("source_product_id", "12x"),
        ("source_url", "https://evil.test/cep-telefonlari/a"),
        ("source_url", "http://www.cimri.com/cep-telefonlari/a"),
        ("day", "infinity"),
        ("day", None),
        ("captured_at", "infinity"),
        ("captured_at", None),
        ("price_kurus", 0),
        ("price_kurus", -1),
        ("page_sha256", "x" * 64),
        ("api_sha256", "a" * 63),
        ("report_sha256", None),
    ],
)
def test_schema_rejects_invalid_rows(prepared, column, value):
    conn, directory, catalog, _ = prepared
    fields = valid_row(read_capture(directory, catalog).verified[0])
    fields[column] = value
    with pytest.raises(psycopg.IntegrityError):
        insert(conn, "market_history", **fields)
    assert not rows(conn)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE market_history SET price_kurus = price_kurus + 1",
        "UPDATE market_history SET page_sha256 = repeat('a', 64)",
        "DELETE FROM market_history",
        "TRUNCATE market_history",
    ],
)
def test_history_rows_are_immutable(prepared, statement):
    conn, directory, catalog, _ = prepared
    storage.import_history(conn, read_capture(directory, catalog))
    previous = rows(conn)
    with pytest.raises(psycopg.IntegrityError):
        conn.execute(statement)
    assert rows(conn) == previous


def test_schema_accepts_null_bigint_and_rejects_duplicate(prepared):
    conn, directory, catalog, _ = prepared
    fields = valid_row(read_capture(directory, catalog).verified[0])
    fields["price_kurus"] = None
    insert(conn, "market_history", **fields)
    with pytest.raises(psycopg.errors.UniqueViolation):
        insert(conn, "market_history", **fields)
    fields.update(day=fields["day"] + timedelta(days=1), price_kurus=2**63 - 1)
    insert(conn, "market_history", **fields)
    assert len(rows(conn)) == 2


def test_migration_upgrade_keeps_existing_runs_and_comparability(
    db, tmp_path, monkeypatch
):
    old_migrations = tmp_path / "old_migrations"
    old_migrations.mkdir()
    for path in MIGRATIONS_DIR.glob("00[123]_*.sql"):
        shutil.copy2(path, old_migrations / path.name)
    migrate(db, old_migrations)
    catalog_path = write_catalog(tmp_path / "catalog.json")

    def collect():
        return collection.collect(
            db,
            catalog_path,
            Runtime(),
            create=FakeScrapers(
                {
                    key: OFFER
                    for key in (
                        "trendyol_1",
                        "trendyol_2",
                        "trendyol_3",
                        "hepsiburada_4",
                        "hepsiburada_5",
                        "hepsiburada_6",
                        "trendyol_7",
                    )
                }
            ),
            out=lambda line: None,
        )

    with monkeypatch.context() as patch:
        patch.setattr(collection, "pending", lambda conn: pending(conn, old_migrations))
        first = collect()
    before = run_snapshot(db, first.run_id)
    view = db.execute(
        "SELECT * FROM product_run_prices ORDER BY product_id, run_id"
    ).fetchall()
    assert [m.version for m in migrate(db)] == [4]
    assert migrate(db) == []
    assert run_snapshot(db, first.run_id) == before
    assert (
        db.execute(
            "SELECT * FROM product_run_prices ORDER BY product_id, run_id"
        ).fetchall()
        == view
    )
    second = collect()
    assert not second.errors and second.run_id != first.run_id
    assert run_snapshot(db, first.run_id) == before


def test_pending_migration_prevents_import_without_writing(db, input_files, tmp_path):
    directory, catalog, _ = input_files
    old_migrations = tmp_path / "old"
    old_migrations.mkdir()
    for path in MIGRATIONS_DIR.glob("00[123]_*.sql"):
        shutil.copy2(path, old_migrations / path.name)
    migrate(db, old_migrations)
    sync_catalog(db, catalog)
    with pytest.raises(MigrationError, match="Şema güncel değil"):
        storage.import_history(db, read_capture(directory, catalog))
    assert db.execute("SELECT to_regclass('market_history')").fetchone() == (None,)
    with connect(os.environ["TEST_DATABASE_URL"]) as other:
        assert try_lock_runs(other)
        unlock_runs(other)
