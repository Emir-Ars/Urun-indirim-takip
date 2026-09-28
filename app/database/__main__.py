"""Komut satırı: veritabanı şemasını kurar (migrate) veya durumunu gösterir (status)."""

import argparse
import sys

import psycopg

from app.database.connection import connect, database_url
from app.database.migrate import MigrationError, applied, migrate, pending


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Veritabanı şemasını yönet")
    parser.add_argument(
        "command",
        choices=["migrate", "status"],
        help="migrate: bekleyen migration'ları uygula; status: durumu göster",
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        with connect(database_url()) as conn:
            if args.command == "migrate":
                done = migrate(conn)
                for migration in done:
                    print(f"uygulandı: {migration.file_name}")
                if not done:
                    print("Şema güncel; uygulanacak migration yok.")
            else:
                for version, name, applied_at in applied(conn):
                    print(
                        f"{version:03d}_{name}.sql  uygulandı  "
                        f"{applied_at:%Y-%m-%d %H:%M} UTC"
                    )
                waiting = pending(conn)
                for migration in waiting:
                    print(f"{migration.file_name}  BEKLİYOR")
                if not waiting:
                    print("Şema güncel.")
    except (MigrationError, RuntimeError, OSError, psycopg.Error) as exc:
        print(f"Veritabanı komutu başarısız: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
