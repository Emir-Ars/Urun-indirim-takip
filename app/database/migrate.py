"""Numaralı SQL dosyalarını (migration) sırayla ve yalnızca bir kez uygular.

Kurallar: dosya adı `NNN_ad.sql`; numaralar 001'den boşluksuz artar. Her dosya
tek transaction'da uygulanır ve `schema_migrations` tablosuna parmak iziyle
yazılır; hata olursa o dosyadan hiçbir iz kalmaz. Uygulanmış dosya bir daha
değiştirilmez, şema değişikliği yeni numaralı dosyayla yapılır.
"""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
_FILE_NAME = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")
# Aynı anda iki migrate çalışırsa ikincisi bu kilidi bekler.
_LOCK_ID = 2026_0928
_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version integer PRIMARY KEY CHECK (version > 0),
    name text NOT NULL,
    checksum text NOT NULL CHECK (checksum ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


class MigrationError(Exception):
    """Migration dosyaları ile veritabanındaki kayıt tutarsız."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str

    @property
    def file_name(self) -> str:
        return f"{self.version:03d}_{self.name}.sql"


def checksum(text: str) -> str:
    # Windows'ta Git dosyayı CRLF ile açabilir; parmak izi satır sonundan
    # bağımsız olmalı ki aynı dosya CI'da (LF) "değişmiş" görünmesin.
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def load(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILE_NAME.match(path.name)
        if match is None:
            raise MigrationError(
                f"Geçersiz migration dosya adı: {path.name} (beklenen: 001_ad.sql)"
            )
        text = path.read_text(encoding="utf-8-sig")
        migrations.append(Migration(int(match[1]), match[2], text, checksum(text)))
    if [m.version for m in migrations] != list(range(1, len(migrations) + 1)):
        raise MigrationError("Migration numaraları 001'den başlayıp boşluksuz artmalı")
    return migrations


def applied(conn: psycopg.Connection) -> list[tuple[int, str, datetime]]:
    """Uygulanmış migration'lar: (numara, ad, uygulanma zamanı)."""
    if conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0] is None:
        return []
    return conn.execute(
        "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
    ).fetchall()


def pending(
    conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR
) -> list[Migration]:
    """Bekleyen migration'lar; kayıt dosyalarla çelişirse MigrationError.

    Veritabanını değiştirmez. Toplama turu, şema güncel değilse başlamamak için
    bunu kullanır.
    """
    return _unapplied(conn, load(directory))


def migrate(
    conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR
) -> list[Migration]:
    """Bekleyen migration'ları sırayla uygular ve uygulananları döndürür."""
    migrations = load(directory)
    done = []
    while True:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (_LOCK_ID,))
            conn.execute(_BOOKKEEPING)
            waiting = _unapplied(conn, migrations)
            if not waiting:
                return done
            migration = waiting[0]
            conn.execute(migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum)"
                " VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
        done.append(migration)


def _unapplied(
    conn: psycopg.Connection, migrations: list[Migration]
) -> list[Migration]:
    known = {m.version: m for m in migrations}
    recorded = {}
    if conn.execute("SELECT to_regclass('schema_migrations')").fetchone()[0]:
        recorded = dict(
            conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
        )
    unknown = sorted(set(recorded) - set(known))
    if unknown:
        raise MigrationError(
            f"Veritabanı koddan daha yeni: kodda olmayan sürüm(ler) {unknown}"
        )
    for version, digest in recorded.items():
        if known[version].checksum != digest:
            raise MigrationError(
                f"Uygulanmış {known[version].file_name} değiştirilmiş; şema "
                "değişikliği için yeni numaralı bir migration dosyası yazın"
            )
    return [m for m in migrations if m.version not in recorded]
