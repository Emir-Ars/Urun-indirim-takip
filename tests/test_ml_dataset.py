"""ML veri görüntüsünün sözleşmesi, dosyası ve katman sınırı (veritabanısız)."""

import hashlib
import json
import subprocess
import sys
from datetime import timedelta, timezone
from pathlib import Path

import pytest

from app.ml.dataset import (
    FILE_NAME,
    SnapshotError,
    build_snapshot,
    read_snapshot,
    write_snapshot,
)
from tests.support.ml import CAPTURED_AT, START, market, snapshot_tables

ROOT = Path(__file__).resolve().parents[1]


def build(tables=None):
    return build_snapshot(tables or snapshot_tables(), CAPTURED_AT, 5)


def canonical(value):
    # Biçimin bağımsız tanımı: anahtarlar sıralı, boşluksuz, UTF-8.
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def test_written_snapshot_reads_back_identical(tmp_path):
    snapshot = build()
    digest = write_snapshot(snapshot, tmp_path / "ml_veri")
    loaded, loaded_digest = read_snapshot(tmp_path / "ml_veri")
    assert loaded == snapshot
    assert loaded_digest == digest
    envelope = json.loads((tmp_path / "ml_veri" / FILE_NAME).read_bytes())
    assert envelope["sha256"] == digest
    assert digest == hashlib.sha256(canonical(envelope["payload"])).hexdigest()
    assert envelope["payload"]["format_version"] == 1
    assert envelope["payload"]["schema_version"] == 5
    assert envelope["payload"]["captured_at"] == "2026-10-28T09:30:00Z"
    assert len(loaded.listing_checks) == 5
    # Yarıda kalan turda kontrol edilmemiş sayfa ve fiyatı boş Cimri günü korunur.
    assert loaded.listing_checks[4].outcome is None
    assert loaded.market_history[1].price_kurus is None


def test_same_data_gives_same_bytes_whatever_the_row_order(tmp_path):
    shuffled = {name: rows[::-1] for name, rows in snapshot_tables().items()}
    write_snapshot(build(), tmp_path / "a")
    write_snapshot(build(shuffled), tmp_path / "b")
    first = (tmp_path / "a" / FILE_NAME).read_bytes()
    assert first == (tmp_path / "b" / FILE_NAME).read_bytes()
    assert [row.run_id for row in build(shuffled).collection_runs] == [1, 2]


def test_existing_directory_is_left_untouched(tmp_path):
    target = tmp_path / "ml_veri"
    target.mkdir()
    (target / "eski.txt").write_text("eski", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_snapshot(build(), target)
    assert [path.name for path in target.iterdir()] == ["eski.txt"]


def tamper_price(envelope):
    envelope["payload"]["listing_checks"][0]["current_price"] += 1


def tamper_digest(envelope):
    envelope["sha256"] = "0" * 64


def add_key(envelope):
    envelope["note"] = "elle eklendi"


@pytest.mark.parametrize("tamper", [tamper_price, tamper_digest, add_key])
def test_changed_file_is_rejected(tmp_path, tamper):
    write_snapshot(build(), tmp_path / "ml_veri")
    path = tmp_path / "ml_veri" / FILE_NAME
    envelope = json.loads(path.read_bytes())
    tamper(envelope)
    path.write_bytes(canonical(envelope))
    with pytest.raises(SnapshotError, match="parmak izi|zarf"):
        read_snapshot(tmp_path / "ml_veri")


@pytest.mark.parametrize("raw", [b"", b'{"sha256":', "ü".encode("latin-1"), b"[1]"])
def test_unreadable_file_is_rejected(tmp_path, raw):
    (tmp_path / "ml_veri").mkdir()
    (tmp_path / "ml_veri" / FILE_NAME).write_bytes(raw)
    with pytest.raises(SnapshotError):
        read_snapshot(tmp_path / "ml_veri")


def test_rehashed_file_still_has_its_links_checked(tmp_path):
    write_snapshot(build(), tmp_path / "ml_veri")
    path = tmp_path / "ml_veri" / FILE_NAME
    envelope = json.loads(path.read_bytes())
    envelope["payload"]["listings"][0]["product_id"] = 99
    envelope["sha256"] = hashlib.sha256(canonical(envelope["payload"])).hexdigest()
    path.write_bytes(canonical(envelope))
    with pytest.raises(SnapshotError, match="hepsiburada_a"):
        read_snapshot(tmp_path / "ml_veri")


def duplicate_listing(tables):
    tables["listings"].append(dict(tables["listings"][0]))


def duplicate_product_key(tables):
    tables["products"][1]["product_key"] = tables["products"][0]["product_key"]


def listing_without_product(tables):
    tables["listings"][0]["product_id"] = 9


def listing_without_platform(tables):
    tables["listings"][0]["platform"] = "amazon"


def check_without_run(tables):
    tables["listing_checks"][0]["run_id"] = 9


def check_with_other_product(tables):
    tables["listing_checks"][0]["product_id"] = 2


def planned_count_mismatch(tables):
    tables["collection_runs"][0]["planned_count"] = 4


def offer_without_price(tables):
    tables["listing_checks"][0]["current_price"] = None


def sold_out_with_price(tables):
    tables["listing_checks"][1]["current_price"] = 100


def outcome_without_time(tables):
    tables["listing_checks"][1]["checked_at"] = None


def time_without_outcome(tables):
    tables["listing_checks"][4]["checked_at"] = START + timedelta(hours=12)


def checked_after_run(tables):
    tables["listing_checks"][0]["checked_at"] = START + timedelta(hours=1)


def checked_before_run(tables):
    tables["listing_checks"][0]["checked_at"] = START - timedelta(seconds=1)


def running_tour(tables):
    tables["collection_runs"][1].update(status="running", finished_at=None)


def finished_before_start(tables):
    tables["collection_runs"][0]["finished_at"] = START - timedelta(minutes=1)


def local_time(tables):
    tables["collection_runs"][0]["started_at"] = START.astimezone(
        timezone(timedelta(hours=3))
    )


def market_without_product(tables):
    tables["market_history"].append(market(9, START.date(), 100))


def duplicate_market_day(tables):
    tables["market_history"].append(dict(tables["market_history"][0]))


def market_from_other_source(tables):
    tables["market_history"][0]["source"] = "akakce"


def missing_table(tables):
    del tables["market_history"]


def unexpected_field(tables):
    tables["listing_checks"][0]["seller_name"] = "Satıcı"


@pytest.mark.parametrize(
    "change,message",
    [
        (duplicate_listing, "listings: .*sıralı ve tekil"),
        (duplicate_product_key, "ürün anahtarı"),
        (listing_without_product, "Sayfa hepsiburada_a"),
        (listing_without_platform, "Sayfa hepsiburada_a"),
        (check_without_run, "Tur 9 sayfa hepsiburada_a"),
        (check_with_other_product, "Tur 1 sayfa hepsiburada_a"),
        (planned_count_mismatch, "Tur 1: planlanan 4"),
        (offer_without_price, "sonuç alanları"),
        (sold_out_with_price, "sonuç alanları"),
        (outcome_without_time, "sonuç alanları"),
        (time_without_outcome, "sonuç alanları"),
        (checked_after_run, "tur aralığı dışında"),
        (checked_before_run, "tur aralığı dışında"),
        (running_tour, "status"),
        (finished_before_start, "bitiş başlangıçtan önce"),
        (local_time, "UTC"),
        (market_without_product, "Cimri ürün 9"),
        (duplicate_market_day, "market_history: .*sıralı ve tekil"),
        (market_from_other_source, "source"),
        (missing_table, "tablolar"),
        (unexpected_field, "seller_name"),
    ],
)
def test_inconsistent_rows_are_rejected(change, message):
    tables = snapshot_tables()
    change(tables)
    # Pydantic'in ValidationError'ı da ValueError'dır.
    with pytest.raises(ValueError, match=message):
        build(tables)


def test_ml_modules_do_not_load_database_or_network_layers():
    # Etiket ve deney ağsız, veritabanısız çalışır; veritabanına yalnız komut
    # dosyası (__main__) okuma hesabıyla bağlanır.
    source = """
import importlib
import importlib.abc
import pkgutil
import socket
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        forbidden = ('psycopg', 'psycopg_pool', 'curl_cffi', 'httpx', 'requests',
                     'app.database', 'app.api', 'app.ui', 'app.collection',
                     'app.discovery', 'app.market_history', 'app.scraper.http')
        if any(fullname == item or fullname.startswith(item + '.')
               for item in forbidden):
            raise AssertionError('Yasak katman yuklendi: ' + fullname)
def no_connection(*args, **kwargs):
    raise AssertionError('Ag baglantisi acildi')
sys.meta_path.insert(0, Guard())
socket.create_connection = no_connection
import app.ml
names = [m.name for m in pkgutil.iter_modules(app.ml.__path__)]
assert 'dataset' in names, names
for name in names:
    if name != '__main__':
        importlib.import_module('app.ml.' + name)
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
