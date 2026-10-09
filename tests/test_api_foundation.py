"""Yerel API'nin bağımlılıkları, ağ koruması ve gerçek okuma hesabı."""

import asyncio
import os
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import errors, sql
from streamlit.testing.v1 import AppTest

from conftest import _no_production_database_url

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts/api_okuma_rolu.sql"
READ_OBJECTS = (
    "schema_migrations",
    "platforms",
    "products",
    "listings",
    "collection_runs",
    "listing_checks",
    "product_run_prices",
    "market_history",
)
WRITE_TABLES = (
    ("schema_migrations", "version"),
    ("platforms", "key"),
    ("products", "product_id"),
    ("listings", "listing_id"),
    ("collection_runs", "status"),
    ("listing_checks", "outcome"),
    ("market_history", "price_kurus"),
)


@pytest.mark.parametrize("url", ["https://www.trendyol.com", "http://127.0.0.1:8000"])
def test_httpx_real_sync_requests_are_blocked(url):
    with httpx.Client(trust_env=False) as client:
        with pytest.raises(pytest.fail.Exception, match="internete çıkmaya çalıştı"):
            client.get(url)


def test_httpx_real_async_requests_are_blocked():
    async def request():
        async with httpx.AsyncClient(trust_env=False) as client:
            with pytest.raises(
                pytest.fail.Exception, match="internete çıkmaya çalıştı"
            ):
                await client.get("http://127.0.0.1:8000")

    asyncio.run(request())


def test_httpx_mock_transport_remains_available():
    calls = []

    def respond(request):
        calls.append(str(request.url))
        return httpx.Response(200, json={"ready": True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert client.get("http://127.0.0.1:8000/health").json() == {"ready": True}
    assert calls == ["http://127.0.0.1:8000/health"]


def test_fastapi_test_client_does_not_need_a_network_connection():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ready": True}

    with TestClient(app) as client:
        assert client.get("/health").json() == {"ready": True}


def test_httpx_asgi_transport_remains_available():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"ready": True}

    async def request():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            assert (await client.get("/health")).json() == {"ready": True}

    asyncio.run(request())


def test_production_database_addresses_are_cleared(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/production")
    monkeypatch.setenv("API_DATABASE_URL", "postgresql://example/production")
    _no_production_database_url.__wrapped__(monkeypatch)
    assert "DATABASE_URL" not in os.environ
    assert "API_DATABASE_URL" not in os.environ


def test_streamlit_app_test_can_run_and_change_a_selection():
    app = AppTest.from_string(
        "import streamlit as st\n"
        "choice = st.selectbox('Telefon', ['Apple', 'Samsung'])\n"
        "st.text(choice)\n"
    ).run()
    assert not app.exception
    assert app.text[0].value == "Apple"
    app.selectbox[0].set_value("Samsung").run()
    assert not app.exception
    assert app.text[0].value == "Samsung"


@pytest.mark.parametrize("relation", READ_OBJECTS)
def test_api_role_can_read_required_objects(api_db, relation):
    api_db.execute(
        sql.SQL("SELECT * FROM public.{} LIMIT 1").format(sql.Identifier(relation))
    )


def test_api_role_is_unprivileged_and_read_only_by_default(api_db):
    row = api_db.execute(
        "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit,"
        " rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user"
    ).fetchone()
    assert row == (True, False, False, False, False, False, False)
    assert api_db.execute("SHOW default_transaction_read_only").fetchone() == ("on",)
    assert api_db.execute(
        "SELECT count(*) FROM pg_auth_members WHERE member=("
        "SELECT oid FROM pg_roles WHERE rolname=current_user)"
    ).fetchone() == (0,)


@pytest.mark.parametrize("table,column", WRITE_TABLES)
@pytest.mark.parametrize("operation", ["insert", "update", "delete", "truncate"])
def test_api_role_cannot_write_even_when_read_only_default_is_disabled(
    api_db, table, column, operation
):
    api_db.execute("SET default_transaction_read_only=off")
    relation = sql.Identifier("public", table)
    queries = {
        "insert": sql.SQL("INSERT INTO {} DEFAULT VALUES").format(relation),
        "update": sql.SQL("UPDATE {} SET {}={} WHERE false").format(
            relation, sql.Identifier(column), sql.Identifier(column)
        ),
        "delete": sql.SQL("DELETE FROM {} WHERE false").format(relation),
        "truncate": sql.SQL("TRUNCATE {}").format(relation),
    }
    with pytest.raises(errors.InsufficientPrivilege):
        api_db.execute(queries[operation])


@pytest.mark.parametrize(
    "query",
    ["CREATE TABLE public.api_probe (id integer)", "CREATE SCHEMA api_probe"],
)
def test_api_role_cannot_create_persistent_objects(api_db, query):
    api_db.execute("SET default_transaction_read_only=off")
    with pytest.raises(errors.InsufficientPrivilege):
        api_db.execute(query)


def test_api_role_can_read_a_consistent_snapshot(api_db):
    with api_db.transaction():
        api_db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        assert api_db.execute("SHOW transaction_isolation").fetchone() == (
            "repeatable read",
        )
        assert api_db.execute("SHOW transaction_read_only").fetchone() == ("on",)
        assert api_db.execute(
            "SELECT count(*) FROM public.schema_migrations"
        ).fetchone() == (4,)


def test_role_setup_can_be_repeated_without_changing_project_rows(api_db, db):
    before = db.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
    db.execute(SETUP.read_text(encoding="utf-8"))
    assert (
        db.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
        == before
    )
    assert api_db.execute("SELECT count(*) FROM schema_migrations").fetchone() == (4,)


def test_role_setup_rejects_write_grants_and_rolls_back_its_grants(api_db, db):
    db.execute("REVOKE SELECT ON products FROM fiyat_takip_api_test")
    db.execute("GRANT INSERT ON listings TO fiyat_takip_api_test")
    with pytest.raises(errors.RaiseException, match="yazma veya nesne oluşturma"):
        db.execute(SETUP.read_text(encoding="utf-8"))
    db.rollback()
    assert db.execute(
        "SELECT has_table_privilege('fiyat_takip_api_test'," " 'products', 'SELECT')"
    ).fetchone() == (False,)


def test_role_setup_rejects_missing_schema_objects(api_db, db):
    db.execute("DROP VIEW product_run_prices")
    with pytest.raises(errors.RaiseException, match="eksik nesne: product_run_prices"):
        db.execute(SETUP.read_text(encoding="utf-8"))
    db.rollback()
    assert db.execute("SELECT count(*) FROM schema_migrations").fetchone() == (4,)
