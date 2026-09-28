"""Komut satırı: şemayı kurar (migrate), durumunu gösterir (status) ve katalogu
veritabanına eşitler (sync-catalog)."""

import argparse
import sys

import psycopg
from pydantic import ValidationError

from app.database.catalog_sync import CatalogConflict, read_catalog, sync_catalog
from app.database.connection import connect, database_url
from app.database.migrate import MigrationError, applied, migrate, pending
from app.settings import Settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Veritabanını yönet")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate", help="Bekleyen migration'ları uygula")
    commands.add_parser("status", help="Uygulanmış ve bekleyen migration'lar")
    sync = commands.add_parser(
        "sync-catalog", help="catalog.json'u veritabanındaki kopyaya eşitle"
    )
    sync.add_argument(
        "--dry-run", action="store_true", help="Değişiklikleri göster, yazma"
    )
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        with connect(database_url()) as conn:
            if args.command == "migrate":
                run_migrate(conn)
            elif args.command == "status":
                run_status(conn)
            else:
                run_sync(conn, dry_run=args.dry_run)
    except (
        CatalogConflict,
        MigrationError,
        RuntimeError,
        OSError,
        ValidationError,
        psycopg.Error,
    ) as exc:
        print(f"Veritabanı komutu başarısız: {exc}", file=sys.stderr)
        return 1
    return 0


def run_migrate(conn) -> None:
    done = migrate(conn)
    for migration in done:
        print(f"uygulandı: {migration.file_name}")
    if not done:
        print("Şema güncel; uygulanacak migration yok.")


def run_status(conn) -> None:
    for version, name, applied_at in applied(conn):
        print(f"{version:03d}_{name}.sql  uygulandı  {applied_at:%Y-%m-%d %H:%M} UTC")
    waiting = pending(conn)
    for migration in waiting:
        print(f"{migration.file_name}  BEKLİYOR")
    if not waiting:
        print("Şema güncel.")


def run_sync(conn, *, dry_run: bool) -> None:
    if pending(conn):
        raise MigrationError("Şema güncel değil; önce `migrate` çalıştırın")
    path = Settings().catalog_path
    catalog, digest = read_catalog(path)
    plan = sync_catalog(conn, catalog, dry_run=dry_run)
    print(f"Katalog: {path} (sha256 {digest[:12]}…)")
    for name, changes in plan.tables.items():
        print(
            f"  {name:<10} {len(changes.added):>4} eklendi"
            f"  {len(changes.updated):>3} güncellendi"
            f"  {len(changes.deactivated):>3} pasife alındı"
            f"  {changes.unchanged:>4} değişmedi"
        )
    for name, changes in plan.tables.items():
        for key, diff in changes.updated:
            fields = ", ".join(
                f"{c}: {old!r} → {new!r}" for c, (old, new) in diff.items()
            )
            print(f"  güncellendi  {name} {key}: {fields}")
        for key in changes.deactivated:
            print(f"  pasife alındı  {name} {key} (katalogda yok; silinmedi)")
    if not plan.changed:
        print("Değişiklik yok; veritabanı katalogla aynı.")
    elif dry_run:
        print("Deneme (--dry-run): hiçbir şey yazılmadı.")
    else:
        print("Eşitleme yazıldı.")


if __name__ == "__main__":
    sys.exit(main())
