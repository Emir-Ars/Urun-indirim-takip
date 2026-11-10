"""Yalnız Docker ağı ve yeni teslim alanlarında geri yükleme sonrası hazırlık."""

import os
import shutil
from pathlib import Path

import psycopg
from psycopg import sql

from app.api.database import validate_readiness
from app.contracts import utc_now
from app.delivery import bundle, database
from app.delivery.state import DeliveryState, READY_FILE, load_state
from app.ml.reporting import json_bytes

READY = READY_FILE


def check_database(conn, expected):
    actual = database.fingerprint(conn)
    if actual.model_dump(exclude={"server_version"}) != expected.model_dump(
        exclude={"server_version"}
    ):
        raise bundle.DeliveryError("Kaynak/kopya veritabanı parmak izleri uyuşmuyor.")


def check_files(manifest, root=None):
    from app.delivery.display import CONTROL_FILES, validate_control

    root = Path(root or bundle.ROOT)
    prefixes = ("config/", bundle.SHADOW + "/")
    expected = {
        name: digest
        for name, digest in manifest.files.items()
        if name.startswith(prefixes)
    }
    actual = {
        f"config/{p}" for p in bundle.inventory(Path(root) / "config") if p != READY
    }
    actual |= {
        f"{bundle.SHADOW}/{p}"
        for p in bundle.inventory(root / bundle.SHADOW)
        if p not in CONTROL_FILES
    }
    if actual != set(expected):
        raise bundle.DeliveryError("Hazırlanmış dosya kapsamı değişmiş.")
    for name, digest in expected.items():
        if bundle.sha(bundle.safe_path(root, name)) != digest:
            raise bundle.DeliveryError("Hazırlanmış dosya SHA'sı değişmiş.")
    validate_control(manifest, root)


def api_connection(name):
    password = (
        Path("/run/secrets/api_password").read_text(encoding="utf-8").removesuffix("\n")
    )
    return psycopg.connect(
        host="db",
        port=5432,
        dbname=name,
        user=database.reader_name(name),
        password=password,
        autocommit=True,
        connect_timeout=5,
        options="-c default_transaction_read_only=on -c TimeZone=UTC",
    )


def check_owner(conn):
    owner = conn.execute(
        "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolinherit, "
        "rolreplication, rolbypassrls FROM pg_roles WHERE rolname=%s",
        (database.OWNER,),
    ).fetchone()
    if owner != (False,) * 7:
        raise bundle.DeliveryError("Şema sahibi rolü uygun değil.")
    wrong = conn.execute(
        "SELECT pg_get_userbyid(datdba) <> %s FROM pg_database "
        "WHERE datname=current_database() UNION ALL "
        "SELECT pg_get_userbyid(nspowner) <> %s FROM pg_namespace "
        "WHERE nspname='public' UNION ALL "
        "SELECT pg_get_userbyid(c.relowner) <> %s FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'",
        (database.OWNER,) * 3,
    ).fetchall()
    if not wrong or any(row[0] for row in wrong):
        raise bundle.DeliveryError("Hedef nesnelerin sahipliği uygun değil.")


def prepare_target(package, mode, *, verified=None):
    manifest, digest = verified or bundle.verify_bundle(package)
    root = bundle.ROOT
    ready_path = root / "config" / READY
    with database.target_connection(
        manifest.database.name, "/run/secrets/admin_password"
    ) as conn:
        if mode == "bootstrap":
            database.bootstrap(conn)
            return dict(status="bootstrapped", bundle_sha256=digest)
        check_database(conn, manifest.database)
        check_owner(conn)
        if mode == "check":
            ready = load_state(ready_path).model_dump(mode="json")
            if (
                ready["bundle_sha256"] != digest
                or ready["code_sha256"] != manifest.code_sha256
                or ready["format_version"] != 1
                or ready["status"] != "complete"
                or ready["database"] != manifest.database.name
                or ready["display_enabled"] is not False
            ):
                raise bundle.DeliveryError("Hazır kopya başka pakete ait.")
            check_files(manifest)
            with api_connection(manifest.database.name) as reader:
                validate_readiness(reader)
            return ready
        if mode != "finalize" or ready_path.exists():
            raise bundle.DeliveryError("Hazır kopyanın üzerine yazılmaz.")
        if any((root / "config").iterdir()) or any((root / bundle.SHADOW).iterdir()):
            raise bundle.DeliveryError("Hedef dosya alanları boş değil.")
        conn.execute(
            (root / "scripts/api_okuma_rolu.sql").read_text(encoding="utf-8-sig")
        )
        password = (
            Path("/run/secrets/api_password")
            .read_text(encoding="utf-8")
            .removesuffix("\n")
        )
        if not password or any(c in password for c in "\n\r\0"):
            raise bundle.DeliveryError("Docker API parola dosyası geçersiz.")
        conn.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(database.reader_name(manifest.database.name)),
                sql.Literal(password),
            )
        )
        with api_connection(manifest.database.name) as reader:
            validate_readiness(reader)
        for name in manifest.files:
            if not name.startswith(("config/", bundle.SHADOW + "/")):
                continue
            target = bundle.safe_path(root, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle.safe_path(package, name), target)
        check_files(manifest)
        ready = DeliveryState(
            format_version=1,
            status="complete",
            bundle_sha256=digest,
            code_sha256=manifest.code_sha256,
            code_commit=manifest.code_commit,
            database=manifest.database.name,
            captured_at=manifest.created_at,
            prepared_at=utc_now(),
            display_enabled=False,
        ).model_dump(mode="json")
        temporary = ready_path.with_suffix(".tmp")
        with temporary.open("xb") as stream:
            stream.write(json_bytes(ready) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, ready_path)
        return ready
