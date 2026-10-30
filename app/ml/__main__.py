"""ML veri hazırlığı komutları; veritabanına yazmaz."""

import argparse
import sys
from collections import Counter
from pathlib import Path

import psycopg

from app.console import utf8_output
from app.contracts import utc_now
from app.database.connection import API_DATABASE_URL_ENV, connect, database_url
from app.database.ml_data import MlDataBusy, MlDataError, read_ml_data
from app.ml.dataset import (
    FILE_NAME,
    MlSnapshot,
    SnapshotError,
    build_snapshot,
    read_snapshot,
    write_snapshot,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "snapshot", help="Veritabanını okuma hesabıyla okuyup veri görüntüsü yaz"
    )
    snapshot.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    args = parser.parse_args(argv)
    utf8_output()
    return run_snapshot(args.output_dir)


def run_snapshot(directory: Path) -> int:
    # Veritabanı okunmadan önce: yanlış klasör adı boşuna okuma yaptırmasın.
    if directory.exists():
        print(
            "Görüntü alınmadı: klasör zaten var; yeni bir klasör seç.", file=sys.stderr
        )
        return 1
    try:
        with connect(database_url(API_DATABASE_URL_ENV)) as conn:
            data = read_ml_data(conn)
        snapshot = build_snapshot(data.tables, utc_now(), data.schema_version)
        digest = write_snapshot(snapshot, directory)
        # Diske yazılan dosya, sonraki adımların okuyacağı yolla denetlenir.
        read_snapshot(directory)
    except MlDataBusy as exc:
        print(f"Görüntü alınmadı: {exc}", file=sys.stderr)
        return 3
    except FileExistsError:
        print(
            "Görüntü alınmadı: klasör zaten var; yeni bir klasör seç.", file=sys.stderr
        )
        return 1
    except (
        MlDataError,
        SnapshotError,
        RuntimeError,
        ValueError,
        OSError,
        psycopg.Error,
    ) as exc:
        print(f"Görüntü alınmadı: {exc}", file=sys.stderr)
        return 1
    print(f"Görüntü: {directory / FILE_NAME}")
    print(f"SHA-256: {digest}")
    _print_summary(snapshot)
    print("Dosya yeniden okunup doğrulandı. Veritabanına yazılmadı.")
    return 0


def _print_summary(snapshot: MlSnapshot) -> None:
    captured = snapshot.captured_at.isoformat().replace("+00:00", "Z")
    print(f"Şema sürümü: {snapshot.schema_version}; okuma anı (UTC): {captured}")
    print(
        f"Ürün: {len(snapshot.products)} "
        f"(etkin {sum(row.active for row in snapshot.products)}); "
        f"sayfa: {len(snapshot.listings)} "
        f"(etkin {sum(row.active for row in snapshot.listings)})"
    )
    statuses = Counter(run.status for run in snapshot.collection_runs)
    print(
        f"Tur: {len(snapshot.collection_runs)} "
        f"(tamamlanan {statuses['completed']}, "
        f"yarıda kalan {statuses['interrupted']}); "
        f"sayfa sonucu: {len(snapshot.listing_checks)}"
    )
    market = snapshot.market_history
    print(
        f"Cimri: {len(market)} satır, "
        f"{len({row.product_id for row in market})} ürün "
        f"(eksik fiyat {sum(row.price_kurus is None for row in market)})"
    )


if __name__ == "__main__":
    sys.exit(main())
