"""API cevabı, havuz ve gerçek test okuma hesabının hata akışları."""

import importlib
import os
from contextlib import ExitStack, contextmanager
from datetime import timedelta

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg_pool import PoolClosed, PoolTimeout, TooManyRequests

from app.api import database, main
from app.database import read, runs
from test_database_read import (
    KEY,
    START,
    add_market,
    add_run,
    close_run,
    world as _world,
)

world = _world
PATHS = ("/health", "/api/v1/status", "/api/v1/products", f"/api/v1/products/{KEY}")


class FakePool:
    def __init__(self):
        self.opened = self.closed = self.borrowed = self.returned = 0
        self.failure = None
        self.conn = object()

    def open(self, *, wait):
        assert wait is False
        self.opened += 1

    def close(self):
        self.closed += 1

    @contextmanager
    def connection(self):
        if self.failure:
            raise self.failure
        self.borrowed += 1
        try:
            yield self.conn
        finally:
            self.returned += 1


@pytest.fixture
def stub(monkeypatch):
    pool = FakePool()
    monkeypatch.setattr(database, "create_pool", lambda: pool)
    monkeypatch.setattr(database, "validate_readiness", lambda conn: None)
    monkeypatch.setattr(read, "list_products", lambda conn: ())
    monkeypatch.setattr(
        read, "read_run_status", lambda conn: read.RunStatus(None, None)
    )
    monkeypatch.setattr(read, "read_product", lambda *args: None)
    with TestClient(main.create_app(), raise_server_exceptions=False) as client:
        yield pool, client
    assert pool.opened == pool.closed == 1
    assert pool.borrowed == pool.returned


@pytest.fixture
def client(world, monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    app = main.create_app()
    with TestClient(app, raise_server_exceptions=False) as result:
        yield result
    assert app.state.pool.closed


def assert_error(response, status, code):
    assert response.status_code == status
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["detail"]["code"] == code
    assert isinstance(response.json()["detail"]["message"], str)
    assert "private" not in response.text
    assert "SELECT" not in response.text


def test_import_and_factory_do_not_open_a_pool(monkeypatch):
    def forbidden():
        pytest.fail("İçe aktarma veya uygulama oluşturma bağlantı açtı")

    monkeypatch.setattr(database, "create_pool", forbidden)
    importlib.reload(main)
    app = main.create_app()
    assert not hasattr(app.state, "pool")


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url-private",
        "postgresql://user:private@localhost/db?unknown_option=private",
        "postgresql:///db",
        "postgresql://user@localhost",
        "user=reader",
    ],
)
def test_missing_or_invalid_configuration_does_not_reveal_address(monkeypatch, url):
    monkeypatch.setenv("DATABASE_URL", "postgresql://writer:private@localhost/writer")
    monkeypatch.setenv("API_DATABASE_URL", url)
    with pytest.raises(RuntimeError) as error:
        database.create_pool()
    assert "API_DATABASE_URL" in str(error.value)
    assert "private" not in str(error.value)
    assert "postgresql://" not in str(error.value)


def test_pool_has_separate_read_only_configuration_and_starts_closed(monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://reader@localhost/example_test")
    pool = database.create_pool()
    try:
        assert pool.closed
        assert (pool.min_size, pool.max_size, pool.timeout) == (1, 4, 3)
        assert pool.kwargs["autocommit"] is True
        assert pool.kwargs["connect_timeout"] == 3
        assert "default_transaction_read_only=on" in pool.kwargs["options"]
        assert "statement_timeout=5s" in pool.kwargs["options"]
        assert pool.check_connection == pool._check
    finally:
        pool.close()


def test_lifespan_borrows_only_during_requests_and_returns_connections(stub):
    pool, client = stub
    assert (pool.opened, pool.borrowed) == (1, 0)
    assert client.get(PATHS[0]).json() == {"ready": True}
    assert client.get(PATHS[1]).json() == {"running": None, "completed": None}
    assert client.get(PATHS[2]).json() == []
    assert_error(client.get(PATHS[3]), 404, "product_not_found")
    assert pool.borrowed == pool.returned == 4


@pytest.mark.parametrize("name", ["history_days", "cimri_days"])
@pytest.mark.parametrize("value", ["0", "367", "-1", "1.5", "true", "private"])
def test_invalid_query_is_rejected_without_borrowing_a_connection(stub, name, value):
    pool, client = stub
    assert_error(client.get(PATHS[3], params={name: value}), 422, "invalid_request")
    assert pool.borrowed == 0


@pytest.mark.parametrize("days", [1, 366])
def test_valid_bounds_and_defaults_reach_the_reader_once(stub, monkeypatch, days):
    _, client = stub
    calls = []

    def lookup(conn, key, history_days, cimri_days):
        calls.append((key, history_days, cimri_days))

    monkeypatch.setattr(read, "read_product", lookup)
    client.get(PATHS[3])
    client.get(PATHS[3], params={"history_days": days, "cimri_days": days})
    assert calls == [(KEY, 30, 366), (KEY, days, days)]


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("failure", [PoolTimeout, PoolClosed, TooManyRequests])
def test_unavailable_pool_returns_safe_503_and_can_recover(stub, path, failure):
    pool, client = stub
    pool.failure = failure("private SELECT secret")
    assert_error(client.get(path), 503, "pool_unavailable")
    pool.failure = None
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    "failure, status, code",
    [
        (
            psycopg.OperationalError("private SELECT secret"),
            503,
            "database_unavailable",
        ),
        (
            psycopg.errors.QueryCanceled("private SELECT secret"),
            503,
            "database_unavailable",
        ),
        (ValueError("private SELECT secret"), 500, "internal_error"),
    ],
)
def test_reader_errors_return_connection_and_do_not_become_empty_data(
    stub, monkeypatch, failure, status, code
):
    pool, client = stub

    def fail(conn):
        raise failure

    monkeypatch.setattr(read, "list_products", fail)
    assert_error(client.get(PATHS[2]), status, code)
    assert pool.borrowed == pool.returned == 1
    assert client.get("/health").status_code == 200


def test_response_validation_error_is_a_safe_500(stub, monkeypatch):
    _, client = stub
    monkeypatch.setattr(read, "list_products", lambda conn: [{"product_id": "private"}])
    assert_error(client.get(PATHS[2]), 500, "internal_error")


def test_unknown_route_and_wrong_method_use_safe_errors(stub):
    _, client = stub
    assert_error(client.get("/missing"), 404, "not_found")
    assert_error(client.post("/api/v1/products"), 405, "method_not_allowed")


def test_openapi_describes_routes_models_and_parameter_bounds(stub):
    _, client = stub
    spec = client.get("/openapi.json").json()
    assert set(spec["paths"]) == set(PATHS[:3]) | {"/api/v1/products/{product_key}"}
    product = spec["paths"]["/api/v1/products/{product_key}"]["get"]
    parameters = {entry["name"]: entry["schema"] for entry in product["parameters"]}
    assert parameters["history_days"]["default"] == 30
    assert parameters["cimri_days"]["default"] == 366
    assert parameters["history_days"]["minimum"] == 1
    assert parameters["history_days"]["maximum"] == 366
    properties = spec["components"]["schemas"]["ProductResponse"]["properties"]
    assert "all_history" not in properties
    assert properties["currency"]["const"] == "TRY"
    assert (
        "error_message"
        not in spec["components"]["schemas"]["ListingResponse"]["properties"]
    )
    assert "note" not in spec["components"]["schemas"]["RunResponse"]["properties"]


def test_api_lists_only_active_products_and_reads_passive_keys(client, world):
    assert client.get("/health").json() == {"ready": True}
    assert [p["product_id"] for p in client.get(PATHS[2]).json()] == [1, 2]
    passive = client.get("/api/v1/products/poco_x6_pro_512gb")
    assert passive.status_code == 200
    body = passive.json()
    assert body["product"]["active"] is False
    assert body["state"] == "no_history"
    assert (
        body["current"] is body["best_offer"] is body["last_successful_offer"] is None
    )
    assert body["checks"] == body["history"] == body["cimri_history"] == []
    assert body["statistics"]["low_30d"]["reasons"] == ["no_history"]
    assert body["price_age_seconds"] is body["is_stale"] is None
    assert_error(client.get("/api/v1/products/unknown"), 404, "product_not_found")


def test_product_uses_its_own_completed_run_and_filters_internal_text(client, world):
    completed = add_run(
        world, START, {"a": ("offer", 10001), "b": ("offer", 10001), "c": "error"}
    )
    world.execute(
        "UPDATE collection_runs SET note='private SELECT' WHERE run_id=%s", (completed,)
    )
    world.execute("UPDATE listings SET active=false,color='Mavi' WHERE listing_id='a'")
    world.execute("UPDATE platforms SET active=false WHERE key='trendyol'")
    interrupted = add_run(
        world, START + timedelta(hours=12), {"a": ("offer", 5000)}, status="interrupted"
    )
    other = add_run(world, START + timedelta(hours=24), {"d": ("offer", 4000)})
    running = add_run(
        world, START + timedelta(hours=36), {"a": ("offer", 3000)}, status="running"
    )
    body = client.get(PATHS[3]).json()
    assert body["current"]["run_id"] == completed
    assert body["current"]["run_id"] not in (interrupted, other, running)
    assert body["state"] == "offer"
    assert body["best_offer"]["listing_id"] == "a"
    assert body["best_offer"]["current_price"] == 10001
    assert body["best_offer"]["seller_rating"] == 9.25
    assert body["best_offer"]["seller_rating_scale"] == 10.0
    assert body["best_offer"]["checked_at"] == "2024-11-01T07:01:00Z"
    assert body["best_offer"]["listing_active"] is False
    assert body["best_offer"]["platform_active"] is False
    assert body["best_offer"]["color"] == "Mavi"
    assert body["current"]["partial"] is True
    assert body["current"]["answered_pages"] == 2
    assert body["current"]["error_pages"] == 1
    assert body["current"]["unchecked_pages"] == 0
    assert body["checks"][2]["error_code"] == "network"
    assert "error_message" not in body["checks"][2]
    assert "all_history" not in body
    assert body["statistics"]["source_run_id"] == completed
    assert body["statistics"]["high_in_scope"]["reasons"] == ["incomplete_scope"]
    status = client.get(PATHS[1]).json()
    assert status["running"]["run_id"] == running
    assert status["completed"]["run_id"] == other
    assert "note" not in status["running"]
    assert body["currency"] == "TRY"
    assert client.get(PATHS[3]).headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize(
    "results,state,answered,unchecked",
    [
        ({"a": "sold_out", "b": "sold_out", "c": "sold_out"}, "sold_out", 3, 0),
        ({"a": "error", "b": "sold_out", "c": "planned"}, "unverified", 1, 1),
    ],
)
def test_missing_current_offer_keeps_previous_price_and_null_graphs_separate(
    client, world, results, state, answered, unchecked
):
    older = add_run(
        world, START, {"a": ("offer", 10000), "b": "sold_out", "c": "sold_out"}
    )
    current = add_run(world, START + timedelta(hours=12), results)
    add_market(world, START.date(), 9900)
    add_market(world, (START + timedelta(days=1)).date(), None)
    body = client.get(PATHS[3]).json()
    assert body["state"] == state
    assert body["current"]["run_id"] == current
    assert body["current"]["answered_pages"] == answered
    assert body["current"]["unchecked_pages"] == unchecked
    assert body["best_offer"] is None
    assert body["last_successful_offer"]["run_id"] == older
    assert body["price_age_seconds"] is body["is_stale"] is None
    assert [point["best_price"] for point in body["history"]] == [10000, None]
    assert [point["price_kurus"] for point in body["cimri_history"]] == [9900, None]
    assert body["cimri_history"][1]["day"] == "2024-11-02"


@pytest.mark.parametrize(
    "age,stale",
    [
        (timedelta(hours=18, microseconds=-1), False),
        (timedelta(hours=18), True),
        (timedelta(hours=18, microseconds=1), True),
        (timedelta(seconds=-1), False),
    ],
)
def test_offer_age_uses_actual_check_time_at_eighteen_hour_boundary(
    client, world, monkeypatch, age, stale
):
    add_run(world, START, {"a": ("offer", 10001), "b": "sold_out", "c": "sold_out"})
    monkeypatch.setattr(main, "utc_now", lambda: START + timedelta(minutes=1) + age)
    body = client.get(PATHS[3]).json()
    assert body["price_age_seconds"] == max(0.0, age.total_seconds())
    assert body["is_stale"] is stale


def test_statistics_use_full_snapshot_when_graph_window_is_short(client, world):
    for index in range(61):
        add_run(
            world,
            START + timedelta(hours=12 * index),
            {"a": ("offer", 10001), "b": "sold_out", "c": "sold_out"},
        )
    body = client.get(PATHS[3], params={"history_days": 1}).json()
    assert len(body["history"]) == 3
    stats = body["statistics"]
    assert stats["scope_runs"] == 61
    assert stats["low_30d"]["value"] == stats["high_in_scope"]["value"] == 10001
    assert stats["low_30d"]["observations"] == 61
    assert stats["volatility_30d"]["value"] == 0.0
    assert stats["volatility_30d"]["transitions"] == 60
    assert stats["volatility_30d"]["days"] == 31
    assert "all_history" not in body
    assert (
        client.get(PATHS[3], params={"history_days": 366}).json()["statistics"] == stats
    )


def test_cimri_only_product_does_not_get_current_price_or_own_statistics(client, world):
    add_market(world, START.date(), 10000)
    body = client.get(PATHS[3]).json()
    assert body["state"] == "no_history"
    assert body["history"] == []
    assert len(body["cimri_history"]) == 1
    assert body["statistics"]["volatility_30d"]["reasons"] == ["no_history"]


@pytest.mark.parametrize("relation", database.READ_OBJECTS)
def test_missing_select_permission_gives_503_and_recovers(client, world, relation):
    target = sql.Identifier("public", relation)
    world.execute(
        sql.SQL("REVOKE SELECT ON {} FROM fiyat_takip_api_test").format(target)
    )
    assert_error(client.get("/health"), 503, "read_access_denied")
    assert_error(client.get(PATHS[2]), 503, "read_access_denied")
    world.execute(sql.SQL("GRANT SELECT ON {} TO fiyat_takip_api_test").format(target))
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("relation", database.READ_OBJECTS)
def test_missing_schema_object_is_not_ready(client, world, relation):
    kind = "VIEW" if relation == "product_run_prices" else "TABLE"
    world.execute(
        sql.SQL("DROP {} {} CASCADE").format(
            sql.SQL(kind), sql.Identifier("public", relation)
        )
    )
    assert_error(client.get("/health"), 503, "schema_not_ready")


@pytest.mark.parametrize("change", ["pending", "unknown", "checksum"])
def test_migration_state_is_checked_without_repairing_it(client, world, change):
    if change == "pending":
        world.execute("DELETE FROM schema_migrations WHERE version=4")
    elif change == "unknown":
        world.execute(
            "INSERT INTO schema_migrations (version,name,checksum)"
            " VALUES (5,'unknown',%s)",
            ("0" * 64,),
        )
    else:
        world.execute(
            "UPDATE schema_migrations SET checksum=%s WHERE version=4", ("0" * 64,)
        )
    before = world.execute(
        "SELECT * FROM schema_migrations ORDER BY version"
    ).fetchall()
    assert_error(client.get("/health"), 503, "schema_not_ready")
    assert (
        world.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
        == before
    )


@pytest.mark.parametrize(
    "privilege", ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "UPDATE(brand)"]
)
def test_write_privilege_is_rejected_even_for_read_only_connections(
    client, world, privilege
):
    world.execute(
        sql.SQL("GRANT {} ON products TO fiyat_takip_api_test").format(
            sql.SQL(privilege)
        )
    )
    assert_error(client.get(PATHS[2]), 503, "read_access_denied")
    world.execute(
        sql.SQL("REVOKE {} ON products FROM fiyat_takip_api_test").format(
            sql.SQL(privilege)
        )
    )
    assert client.get("/health").status_code == 200


def test_writer_account_is_not_accepted(world, monkeypatch):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    with TestClient(main.create_app(), raise_server_exceptions=False) as client:
        assert_error(client.get("/health"), 503, "read_access_denied")


def test_readiness_leaves_idle_connection_and_restores_local_settings(api_db):
    api_db.execute("SET statement_timeout='9s'")
    api_db.execute("SET TimeZone='Europe/Istanbul'")
    database.validate_readiness(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    assert api_db.execute("SHOW statement_timeout").fetchone() == ("9s",)
    assert api_db.execute("SHOW TimeZone").fetchone() == ("Europe/Istanbul",)


def test_readiness_failure_rolls_back_and_connection_remains_usable(api_db, db):
    db.execute("REVOKE SELECT ON products FROM fiyat_takip_api_test")
    with pytest.raises(database.UnavailableError):
        database.validate_readiness(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    db.execute("GRANT SELECT ON products TO fiyat_takip_api_test")
    database.validate_readiness(api_db)


def test_product_response_does_not_mix_concurrent_completion_or_catalog_changes(
    client, world, monkeypatch
):
    previous = add_run(
        world, START, {"a": ("offer", 10000), "b": "sold_out", "c": "sold_out"}
    )
    newer = add_run(
        world,
        START + timedelta(hours=12),
        {"a": ("offer", 9000), "b": "sold_out", "c": "sold_out"},
        status="running",
    )
    original = read._rows
    changed = False

    def rows(conn, query, params=()):
        nonlocal changed
        result = original(conn, query, params)
        if not changed and query.startswith(read._PRODUCT_QUERY):
            changed = True
            with world.transaction():
                close_run(world, newer, START + timedelta(hours=12))
                world.execute("UPDATE products SET active=false WHERE product_id=1")
                world.execute("UPDATE listings SET color='Mavi' WHERE listing_id='a'")
        return result

    monkeypatch.setattr(read, "_rows", rows)
    first = client.get(PATHS[3]).json()
    assert first["product"]["active"] is True
    assert first["current"]["run_id"] == previous
    assert first["best_offer"]["current_price"] == 10000
    assert first["best_offer"]["color"] == "Siyah"
    assert first["statistics"]["source_run_id"] == previous
    second = client.get(PATHS[3]).json()
    assert second["product"]["active"] is False
    assert second["current"]["run_id"] == newer
    assert second["best_offer"]["current_price"] == 9000
    assert second["best_offer"]["color"] == "Mavi"
    assert second["statistics"]["source_run_id"] == newer


def test_api_reads_under_collection_lock_without_changing_any_rows(client, world):
    add_run(world, START, {"a": ("offer", 10000), "b": "sold_out", "c": "sold_out"})
    add_market(world, START.date(), None)

    def contents():
        return {
            name: sorted(
                world.execute(
                    sql.SQL("SELECT * FROM {}").format(sql.Identifier("public", name))
                ).fetchall(),
                key=repr,
            )
            for name in database.READ_OBJECTS
        }

    before = contents()
    world.execute("SELECT pg_advisory_lock(%s)", (runs._RUN_LOCK_ID,))
    try:
        for path in PATHS:
            assert client.get(path).status_code == 200
        assert contents() == before
    finally:
        world.execute("SELECT pg_advisory_unlock(%s)", (runs._RUN_LOCK_ID,))


def test_four_connections_are_the_limit_and_busy_pool_recovers(client):
    pool = client.app.state.pool
    assert client.get("/health").status_code == 200
    with ExitStack() as stack:
        held = [stack.enter_context(pool.connection()) for _ in range(4)]
        assert len({conn.info.backend_pid for conn in held}) == 4
        assert all(
            conn.info.transaction_status == TransactionStatus.IDLE for conn in held
        )
        for conn in held:
            assert conn.autocommit is True
            assert conn.execute("SHOW default_transaction_read_only").fetchone() == (
                "on",
            )
            assert conn.execute("SHOW statement_timeout").fetchone() == ("5s",)
            assert conn.execute("SHOW TimeZone").fetchone() == ("UTC",)
        assert_error(client.get("/health"), 503, "pool_unavailable")
    assert client.get("/health").status_code == 200


def test_broken_idle_connection_is_discarded_and_replaced(client, api_db):
    pool = client.app.state.pool
    with pool.connection() as conn:
        old_pid = conn.info.backend_pid
    assert api_db.execute("SELECT pg_terminate_backend(%s)", (old_pid,)).fetchone()[0]
    assert client.get("/health").status_code == 200
    with pool.connection() as conn:
        assert conn.info.backend_pid != old_pid


def test_connection_loss_during_read_returns_503_and_next_read_recovers(
    client, world, api_db, monkeypatch
):
    add_run(world, START, {"a": ("offer", 10000), "b": "sold_out", "c": "sold_out"})
    original = read._rows
    disconnected = False

    def rows(conn, query, params=()):
        nonlocal disconnected
        result = original(conn, query, params)
        if not disconnected and query.startswith(read._PRODUCT_QUERY):
            disconnected = True
            assert api_db.execute(
                "SELECT pg_terminate_backend(%s)", (conn.info.backend_pid,)
            ).fetchone()[0]
        return result

    monkeypatch.setattr(read, "_rows", rows)
    assert_error(client.get(PATHS[3]), 503, "database_unavailable")
    response = client.get(PATHS[3])
    assert response.status_code == 200
    assert response.json()["best_offer"]["current_price"] == 10000


def test_startup_outage_and_exhausted_retries_recover_without_restarting(
    world, monkeypatch
):
    monkeypatch.setenv("API_DATABASE_URL", os.environ["TEST_API_DATABASE_URL"])
    original_connect = psycopg.Connection.connect
    original_pool = database.create_pool
    available = False

    def connect(*args, **kwargs):
        if not available:
            raise psycopg.OperationalError("Yerel test: bağlantı geçici olarak kapalı")
        return original_connect(*args, **kwargs)

    def create_pool():
        pool = original_pool()
        pool.reconnect_timeout = 0.01
        return pool

    monkeypatch.setattr(psycopg.Connection, "connect", connect)
    monkeypatch.setattr(database, "create_pool", create_pool)
    app = main.create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        assert not app.state.pool.closed
        assert_error(client.get("/health"), 503, "pool_unavailable")
        available = True
        assert client.get("/health").status_code == 200
    assert app.state.pool.closed


def test_real_query_timeout_returns_503_and_reuses_clean_connection(
    client, world, monkeypatch
):
    add_run(world, START, {"a": ("offer", 10000), "b": "sold_out", "c": "sold_out"})
    pool = client.app.state.pool
    with pool.connection() as conn:
        before_pid = conn.info.backend_pid
    original = read._rows
    delayed = False

    def rows(conn, query, params=()):
        nonlocal delayed
        if not delayed and query.startswith(read._PRODUCT_QUERY):
            delayed = True
            conn.execute("SELECT pg_sleep(6)")
        return original(conn, query, params)

    monkeypatch.setattr(read, "_rows", rows)
    assert_error(client.get(PATHS[3]), 503, "database_unavailable")
    assert client.get(PATHS[3]).status_code == 200
    with pool.connection() as conn:
        assert conn.info.backend_pid == before_pid
        assert conn.info.transaction_status == TransactionStatus.IDLE
