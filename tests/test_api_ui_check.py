"""Bağımsız SQL–API denetiminin sonuçlarını ve güvenlik sınırlarını sınar."""

import json
import os
from datetime import timedelta

import httpx
import psycopg
import pytest

from app.ui.api_client import ApiClient
from tests.manual import api_ui_check as manual
from test_api import client as _client, world as _world
from test_database_read import KEY, START, add_market, add_run

client = _client
world = _world


def bridge(server):
    def send(request):
        response = server.get(str(request.url))
        return httpx.Response(response.status_code, content=response.content)

    return ApiClient(transport=httpx.MockTransport(send))


@pytest.mark.parametrize("current", ["offer", "sold_out", "error", "planned"])
def test_reference_compares_complete_api_against_base_tables(
    client, world, api_db, current
):
    add_run(world, START, {"a": ("offer", 10001), "b": "sold_out", "d": "error"})
    result = ("offer", 9901) if current == "offer" else current
    add_run(world, START + timedelta(hours=12), {"a": result, "b": "sold_out"})
    add_run(world, START + timedelta(days=1), {"d": ("offer", 9001)})
    add_run(world, START + timedelta(days=2), {"a": ("offer", 1)}, status="interrupted")
    add_market(world, START.date(), 9900)
    add_market(world, START.date() + timedelta(days=1), None)
    report = {"products": []}
    with bridge(client) as reader:
        assert manual.check_api(api_db, reader, report) == 0
    assert report["status"] == "verified"
    assert report["expected_products"] == 2
    assert report["before"] == report["after"]
    assert all(row["matched"] for row in report["products"])
    assert report["products"][0]["cimri_missing"] == 1


def test_empty_database_is_valid(client, api_db, world):
    world.execute("UPDATE products SET active=false")
    report = {"products": []}
    with bridge(client) as reader:
        assert manual.check_api(api_db, reader, report) == 0
    assert report["products"] == [] and report["expected_products"] == 0


@pytest.mark.parametrize("days", [1, 7, 30, 90, 366])
def test_reference_window_boundaries_match_api(client, world, api_db, days):
    add_run(world, START, {"a": ("offer", 10001)})
    add_run(world, START + timedelta(days=days), {"a": ("offer", 9901)})
    if days > 1:
        add_market(world, START.date(), None)
    add_market(world, START.date() + timedelta(days=days - 1), 10101)
    _, data = manual.read_dataset(api_db)
    with bridge(client) as reader:
        reply = reader.get_product(KEY, days, days)
    reference = manual.reference_product(
        data, data["products"][0], reply.generated_at, days, days
    )
    assert (
        manual.differences(
            manual.json_value(reference), manual.json_value(reply.model_dump())
        )
        == []
    )
    assert len(reference["history"]) == 2
    assert len(reference["cimri_history"]) == (1 if days == 1 else 2)


def test_cli_success_records_proof_and_preserves_database(
    client, world, monkeypatch, tmp_path
):
    add_run(world, START, {"a": ("offer", 10001)})
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    monkeypatch.setattr(manual, "ApiClient", lambda: bridge(client))
    path = tmp_path / "proof"
    assert manual.main(["--output-dir", str(path)]) == 0
    report = json.loads((path / "report.json").read_text(encoding="utf-8"))
    assert report["before"] == report["after"]
    assert report["status"] == "verified" and report["expected_products"] == 2
    assert len(report["verifier_sha256"]) == 64
    assert report["started_at"] <= report["finished_at"]


def test_price_mismatch_is_reported_without_raw_values(client, world, api_db):
    add_run(world, START, {"a": ("offer", 10001)})

    def send(request):
        response = client.get(str(request.url))
        body = response.json()
        if request.url.path.endswith(KEY):
            body["best_offer"]["current_price"] += 1
        return httpx.Response(response.status_code, json=body)

    report = {"products": []}
    with ApiClient(transport=httpx.MockTransport(send)) as reader:
        assert manual.check_api(api_db, reader, report) == 1
    assert report["status"] == "mismatch"
    assert report["products"][0]["differences"] == ["best_offer.current_price"]


def test_source_change_is_inconclusive_instead_of_a_bug(client, world, api_db):
    add_run(world, START, {"a": ("offer", 10001)})
    changed = False

    def send(request):
        nonlocal changed
        if not changed:
            world.execute("UPDATE listings SET color='Mavi' WHERE listing_id='a'")
            changed = True
        response = client.get(str(request.url))
        return httpx.Response(response.status_code, content=response.content)

    report = {"products": []}
    with ApiClient(transport=httpx.MockTransport(send)) as reader:
        assert manual.check_api(api_db, reader, report) == 2
    assert report["status"] == "inconclusive"
    assert "listings" in report["changed_relations"]
    assert report["products"][0]["differences"]


def test_reader_rejects_writer_account_without_writing(world):
    with pytest.raises(manual.CheckError, match="Okuma hesabı"):
        manual.read_dataset(world)
    assert world.execute("SELECT count(*) FROM products").fetchone()[0] == 3


def test_reader_rejects_extra_column_write_permission(world, api_db):
    world.execute("GRANT UPDATE (color) ON listings TO fiyat_takip_api_test")
    try:
        with pytest.raises(manual.CheckError, match="fazladan yetkisi"):
            manual.read_dataset(api_db)
    finally:
        world.execute("REVOKE UPDATE (color) ON listings FROM fiyat_takip_api_test")


def test_reader_rejects_inconsistent_migration(world, api_db):
    world.execute(
        "UPDATE schema_migrations SET checksum=%s WHERE version=4", ("a" * 64,)
    )
    with pytest.raises(manual.CheckError, match="Migration"):
        manual.read_dataset(api_db)


def reference_run(index, price, *, hours=12):
    at = START + timedelta(hours=index * hours)
    return dict(
        run_id=index + 1,
        planned_listing_ids=["a"],
        partial=False,
        run_started_at=at,
        best_price=price,
        best_checked_at=at,
    )


def test_independent_statistics_have_known_variance_and_period():
    history = [reference_run(i, 10000 if i % 2 == 0 else 20000) for i in range(61)]
    result = manual.reference_statistics(history)
    assert result["low_30d"]["value"] == 10000
    assert result["high_in_scope"]["value"] == 20000
    assert result["volatility_30d"]["transitions"] == 60
    # 30 adet +log(2), 30 adet -log(2); ortalama sıfır, örnek varyansı 60/59.
    assert result["volatility_30d"]["value"] == pytest.approx(
        69.31471805599453 * (60 / 59) ** 0.5
    )
    assert result["volatility_30d"]["reasons"] == []


def test_reference_never_bridges_missing_prices_or_scope_changes():
    history = [reference_run(i, 10000) for i in range(20)]
    history[10]["best_price"] = None
    result = manual.reference_statistics(history)
    assert result["volatility_30d"]["transitions"] == 17
    history[10]["partial"] = True
    result = manual.reference_statistics(history)
    assert result["scope_runs"] == 9
    assert result["volatility_30d"]["transitions"] == 8
    history[-1]["partial"] = True
    assert manual.reference_statistics(history)["low_30d"]["reasons"] == [
        "incomplete_scope"
    ]
    assert manual.reference_statistics([])["low_30d"]["reasons"] == ["no_history"]


def test_fingerprint_is_stable_but_sensitive_to_all_fields():
    assert manual.fingerprint([{"a": 1, "b": START}]) == manual.fingerprint(
        [{"b": START, "a": 1}]
    )
    assert manual.fingerprint([{"price": None}]) != manual.fingerprint([{"price": 1}])


@pytest.mark.parametrize(
    "url",
    [
        None,
        "not a url",
        "postgresql://writer@localhost/fiyat_takip",
        "postgresql://fiyat_takip_api@localhost/another",
    ],
)
def test_url_never_falls_back_to_writer(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", "private-writer-address")
    if url is not None:
        monkeypatch.setenv("API_DATABASE_URL", url)
    with pytest.raises(manual.CheckError) as error:
        manual.configured_url()
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "failure,code,error_code",
    [
        (KeyboardInterrupt(), 130, "interrupted"),
        (psycopg.OperationalError("private password SELECT"), 1, "database_error"),
        (ValueError("private password SELECT"), 1, "check_error"),
    ],
)
def test_cli_failure_closes_resources_and_writes_safe_report(
    tmp_path, monkeypatch, capsys, failure, code, error_code
):
    events = []

    class Resource:
        def __init__(self, name):
            self.name = name

        def __enter__(self):
            events.append(self.name)
            return self

        def __exit__(self, *args):
            events.append(f"{self.name} closed")

    monkeypatch.setattr(manual, "configured_url", lambda: "unused")
    monkeypatch.setattr(manual.psycopg, "connect", lambda *a, **kw: Resource("sql"))
    monkeypatch.setattr(manual, "ApiClient", lambda: Resource("api"))

    def fail(*args):
        raise failure

    monkeypatch.setattr(manual, "check_api", fail)
    output = tmp_path / "new"
    assert manual.main(["--output-dir", str(output)]) == code
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["error_code"] == error_code
    assert events == ["sql", "api", "api closed", "sql closed"]
    assert "private" not in json.dumps(report) + capsys.readouterr().out


def test_cli_preserves_existing_directory(tmp_path):
    report = tmp_path / "report.json"
    report.write_text("unchanged", encoding="utf-8")
    assert manual.main(["--output-dir", str(tmp_path)]) == 1
    assert report.read_text(encoding="utf-8") == "unchanged"


def test_difference_tolerance_is_only_for_volatility():
    assert manual.differences(1.0, 1.0 + 1e-10, "statistics.volatility_30d.value") == []
    assert manual.differences(1.0, 1.0 + 1e-10, "price_age_seconds") == [
        "price_age_seconds"
    ]
    assert manual.differences(1, True, "price") == ["price"]
