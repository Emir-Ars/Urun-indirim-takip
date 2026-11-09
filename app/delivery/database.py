"""Kaynağın salt okunur görüntüsü ve yalnız Docker hedefinin SQL hazırlığı."""

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from app.database.migrate import load, pending
from app.delivery.bundle import DatabaseProof, DeliveryError
from app.ml.reporting import json_bytes

TABLES = {
    "schema_migrations": "version",
    "platforms": "key",
    "products": "product_id",
    "listings": "listing_id",
    "collection_runs": "run_id",
    "listing_checks": "run_id, listing_id",
    "market_history": "product_id, source, day",
    "product_run_prices": "run_id, product_id",
}
OWNER = "fiyat_takip_owner"
# 001–005'in PostgreSQL 17 kataloğu; sahiplik ve ACL ayrıca doğrulanır.
SCHEMA_SHA256 = "a6d766d193c0f5ee9e55d3145d646fb276c1d2ade9d3bcc53f4f12cef841e4e3"


def schema_sha256(conn):
    queries = (
        "SELECT c.relname,c.relkind,c.relpersistence,c.relrowsecurity,"
        "c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' ORDER BY c.relname",
        "SELECT c.relname,a.attnum,a.attname,format_type(a.atttypid,a.atttypmod),"
        "a.attnotnull,a.attidentity,a.attgenerated,a.attisdropped,"
        "pg_get_expr(d.adbin,d.adrelid) FROM pg_attribute a "
        "JOIN pg_class c ON c.oid=a.attrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum "
        "WHERE n.nspname='public' AND a.attnum>0 ORDER BY c.relname,a.attnum",
        "SELECT c.relname,k.conname,pg_get_constraintdef(k.oid),k.convalidated "
        "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' "
        "ORDER BY c.relname,k.conname",
        "SELECT c.relname,pg_get_indexdef(i.indexrelid),i.indisvalid FROM pg_index i "
        "JOIN pg_class c ON c.oid=i.indrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' ORDER BY c.relname,pg_get_indexdef(i.indexrelid)",
        "SELECT c.relname,pg_get_viewdef(c.oid) FROM pg_class c JOIN pg_namespace n "
        "ON n.oid=c.relnamespace WHERE n.nspname='public' "
        "AND c.relkind='v' ORDER BY c.relname",
        "SELECT p.proname,pg_get_function_identity_arguments(p.oid),"
        "pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY p.proname,p.oid",
        "SELECT c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) "
        "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname",
        "SELECT c.relname,s.seqtypid::regtype::text,s.seqstart,s.seqincrement,s.seqmax,"
        "s.seqmin,s.seqcache,s.seqcycle FROM pg_sequence s "
        "JOIN pg_class c ON c.oid=s.seqrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' ORDER BY c.relname",
    )
    values = [conn.execute(query).fetchall() for query in queries]
    return hashlib.sha256(json_bytes(values)).hexdigest()


def reader_name(database):
    if database == "fiyat_takip":
        return "fiyat_takip_api"
    if re.fullmatch(r"[a-z][a-z0-9_]*_test", database):
        return "fiyat_takip_api_test"
    raise DeliveryError("Teslim veritabanı adı uygun değil.")


def fingerprint(conn):
    name = conn.execute("SELECT current_database()").fetchone()[0]
    reader_name(name)
    if pending(conn):
        raise DeliveryError("Veritabanında bekleyen migration var.")
    relations = {
        row[0]
        for row in conn.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n "
            "ON n.oid=c.relnamespace WHERE n.nspname='public' "
            "AND c.relkind IN ('r','p','v','m','f')"
        )
    }
    if relations != set(TABLES):
        raise DeliveryError("Veritabanının tablo/görünüm kapsamı uyumsuz.")
    structure = schema_sha256(conn)
    if structure != SCHEMA_SHA256:
        raise DeliveryError(
            "Veritabanının gerçek şeması migration sözleşmesine uymuyor."
        )
    if conn.execute(
        "SELECT EXISTS(SELECT 1 FROM collection_runs WHERE status='running')"
    ).fetchone()[0]:
        raise DeliveryError("Süren toplama turu varken paket hazırlanamaz.")
    tables = {}
    for table, order in TABLES.items():
        digest, count = hashlib.sha256(), 0
        query = sql.SQL(
            "SELECT row_to_json(t)::text FROM (SELECT * FROM public.{} ORDER BY {}) t"
        ).format(sql.Identifier(table), sql.SQL(order))
        for row in conn.execute(query):
            digest.update(row[0].encode("utf-8") + b"\n")
            count += 1
        tables[table] = dict(rows=count, sha256=digest.hexdigest())
    value, called = conn.execute(
        "SELECT last_value, is_called FROM public.collection_runs_run_id_seq"
    ).fetchone()
    return DatabaseProof(
        name=name,
        server_version=conn.info.server_version,
        migrations={m.file_name: m.checksum for m in load()},
        schema_sha256=structure,
        tables=tables,
        sequence_value=value,
        sequence_called=called,
    )


def source_connection(url):
    if any(os.getenv(name) for name in ("PGPASSWORD", "PGSERVICE", "PGPASSFILE")):
        raise DeliveryError(
            "Kaynak parola yalnız standart pgpass dosyasından okunmalı."
        )
    parameters = conninfo_to_dict(url)
    if (
        parameters.get("password")
        or parameters.get("passfile")
        or parameters.get("service")
    ):
        raise DeliveryError("Kaynak parola yalnız yerel pgpass dosyasından okunmalı.")
    if parameters.get("dbname") is None:
        raise DeliveryError("Kaynak veritabanı adı gerekli.")
    reader_name(parameters["dbname"])
    return psycopg.connect(
        url,
        autocommit=True,
        connect_timeout=10,
        options=(
            "-c default_transaction_read_only=on -c TimeZone=UTC "
            "-c DateStyle=ISO,YMD -c lock_timeout=5s "
            "-c search_path=pg_catalog,public"
        ),
    )


def dump_database(conn, executable, destination, snapshot):
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, check=True
    )
    if not re.search(r"\b17\.", version.stdout):
        raise DeliveryError("pg_dump sürümü 17 olmalı.")
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PG")
        and key not in ("DATABASE_URL", "API_DATABASE_URL")
    }
    environment.update(
        PGHOST=conn.info.host,
        PGPORT=str(conn.info.port),
        PGUSER=conn.info.user,
        PGDATABASE=conn.info.dbname,
        PGOPTIONS="-c default_transaction_read_only=on -c TimeZone=UTC",
    )
    result = subprocess.run(
        [
            str(executable),
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--schema=public",
            "--lock-wait-timeout=5s",
            "--snapshot=" + snapshot,
            "--file=" + str(destination),
            "--no-password",
        ],
        env=environment,
        capture_output=True,
    )
    if result.returncode:
        raise DeliveryError(
            "pg_dump tamamlanamadı; parola/bağlantı ayrıntısı çıktıya alınmadı."
        )


def target_connection(database, secret):
    if sys.platform != "linux" or not Path("/.dockerenv").is_file():
        raise DeliveryError(
            "Hedef bağlantısı yalnız Docker hazırlık konteynerinde açılır."
        )
    reader_name(database)
    password = Path(secret).read_text(encoding="utf-8").removesuffix("\n")
    if not password or any(c in password for c in "\n\r\0"):
        raise DeliveryError("Docker gizli dosyası geçersiz.")
    return psycopg.connect(
        host="db",
        port=5432,
        dbname=database,
        user="postgres",
        password=password,
        autocommit=True,
        connect_timeout=5,
        options=(
            "-c TimeZone=UTC -c DateStyle=ISO,YMD -c lock_timeout=5s "
            "-c search_path=pg_catalog,public"
        ),
    )


def bootstrap(conn):
    if conn.info.host != "db" or conn.info.user != "postgres":
        raise DeliveryError(
            "Yazma işlemi yalnız Docker yönetici bağlantısında yapılır."
        )
    reader_name(conn.info.dbname)
    if conn.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n "
        "ON n.oid=c.relnamespace WHERE n.nspname='public')"
    ).fetchone()[0]:
        raise DeliveryError("Hedef veritabanı boş değil; üzerine yazılmadı.")
    with conn.transaction():
        conn.execute(
            sql.SQL(
                "CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS"
            ).format(sql.Identifier(OWNER))
        )
        conn.execute(
            sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                sql.Identifier(conn.info.dbname), sql.Identifier(OWNER)
            )
        )
        # Özel arşiv public şemasını da oluşturur; yalnız boş hedef kaldırılır.
        conn.execute("DROP SCHEMA public")
