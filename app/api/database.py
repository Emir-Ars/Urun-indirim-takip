"""API'ye özel bağlantı havuzu ve salt okunur hazırlık denetimi."""

import os

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg_pool import ConnectionPool

from app.database.migrate import MigrationError, pending

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


class UnavailableError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def create_pool() -> ConnectionPool:
    url = os.getenv("API_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("API_DATABASE_URL tanımlı değil.")
    try:
        params = conninfo_to_dict(url)
    except psycopg.Error:
        raise RuntimeError(
            "API_DATABASE_URL geçerli bir PostgreSQL adresi değil."
        ) from None
    if not params.get("user") or not params.get("dbname"):
        raise RuntimeError("API_DATABASE_URL kullanıcı ve veritabanı içermeli.")
    return ConnectionPool(
        url,
        min_size=1,
        max_size=4,
        timeout=3,
        open=False,
        name="fiyat_takip_api",
        check=ConnectionPool.check_connection,
        kwargs={
            "autocommit": True,
            "connect_timeout": 3,
            "application_name": "fiyat_takip_api",
            "options": (
                "-c default_transaction_read_only=on -c statement_timeout=5s"
                " -c TimeZone=UTC -c search_path=pg_catalog,public"
            ),
        },
    )


def validate_readiness(conn: psycopg.Connection) -> None:
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        _validate_role(conn)
        for relation in READ_OBJECTS:
            name = f"public.{relation}"
            if conn.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] is None:
                raise UnavailableError(
                    "schema_not_ready", "Veritabanı şeması hazır değil."
                )
            if not conn.execute(
                "SELECT has_table_privilege(current_user, %s, 'SELECT')", (name,)
            ).fetchone()[0]:
                raise UnavailableError(
                    "read_access_denied", "API okuma hesabının izinleri uygun değil."
                )
        try:
            waiting = pending(conn)
        except MigrationError:
            raise UnavailableError(
                "schema_not_ready", "Veritabanı şeması hazır değil."
            ) from None
        if waiting:
            raise UnavailableError("schema_not_ready", "Veritabanı şeması hazır değil.")


def _validate_role(conn: psycopg.Connection) -> None:
    row = conn.execute(
        "SELECT current_database(), current_user, session_user, rolcanlogin,"
        " rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication,"
        " rolbypassrls FROM pg_roles WHERE rolname = current_user"
    ).fetchone()
    database, user, session_user, *permissions = row
    expected = (
        "fiyat_takip_api"
        if database == "fiyat_takip"
        else "fiyat_takip_api_test" if database.endswith("_test") else None
    )
    unsuitable = (
        expected is None
        or user != expected
        or session_user != expected
        or permissions != [True, False, False, False, False, False, False]
        or conn.execute("SHOW default_transaction_read_only").fetchone()[0] != "on"
    )
    if unsuitable:
        raise UnavailableError(
            "read_access_denied", "API okuma hesabının izinleri uygun değil."
        )
    privileged = conn.execute("""
        WITH reader AS (SELECT oid FROM pg_roles WHERE rolname = current_user)
        SELECT
            EXISTS (SELECT 1 FROM pg_auth_members
                    WHERE member = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_database
                       WHERE datdba = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_namespace
                       WHERE nspowner = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_class
                       WHERE relowner = (SELECT oid FROM reader))
            OR has_database_privilege(current_user, current_database(), 'CREATE')
            OR has_schema_privilege(current_user, 'public', 'CREATE')
            OR EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                AND (
                    has_table_privilege(current_user, c.oid,
                        'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                    OR has_any_column_privilege(current_user, c.oid,
                        'INSERT,UPDATE,REFERENCES')
                )
            )
        """).fetchone()[0]
    if privileged:
        raise UnavailableError(
            "read_access_denied", "API okuma hesabının izinleri uygun değil."
        )
