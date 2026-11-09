"""Teslim paketi üretme, doğrulama ve yalnız Docker içi hazırlık komutları."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg
from filelock import Timeout

from app.console import utf8_output
from app.database.migrate import MigrationError
from app.delivery import bundle
from app.ml.dataset import SnapshotError
from app.scrape_lock import ScrapeBusy
from app.api.database import UnavailableError


def main(argv=None):
    utf8_output()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser(
        "export", help="Salt okunur kaynak veriden yeni paket üretir"
    )
    export.add_argument("--output", type=Path, required=True)
    export.add_argument(
        "--pg-dump",
        type=Path,
        default=Path("C:/Program Files/PostgreSQL/17/bin/pg_dump.exe"),
    )
    for name in ("verify", "bootstrap", "finalize", "check"):
        command = sub.add_parser(name)
        command.add_argument("--bundle", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            from app.delivery.export import export_bundle

            if Path.cwd().resolve() != bundle.ROOT:
                raise bundle.DeliveryError(
                    "Dışa aktarma proje kökünden çalıştırılmalı."
                )
            url = os.getenv("DATABASE_URL", "").strip()
            if not url:
                raise bundle.DeliveryError("Kaynak için şifresiz DATABASE_URL gerekli.")
            manifest, digest = export_bundle(args.output, args.pg_dump, url)
            print(f"Paket: {args.output.resolve()}")
            print(f"Paket SHA-256: {digest}")
            print(f"Model manifest SHA-256: {manifest.model_manifest_sha256}")
            print(
                "Dosyalar doğrulandı. Kaynak DB'ye yazılmadı; eğitim/tahmin çalışmadı."
            )
        elif args.command == "verify":
            manifest, digest = bundle.verify_bundle(args.bundle)
            print(
                json.dumps(
                    dict(
                        bundle_sha256=digest,
                        database=manifest.database.name,
                        code_sha256=manifest.code_sha256,
                        dump_sha256=manifest.files["database.dump"],
                        files=len(manifest.files),
                    ),
                    ensure_ascii=False,
                )
            )
        else:
            from app.delivery.prepare import prepare_target

            print(
                json.dumps(
                    prepare_target(args.bundle, args.command), ensure_ascii=False
                )
            )
        return 0
    except (ScrapeBusy, Timeout):
        print("Teslim işlemi başlamadı: ortak kilit dolu.", file=sys.stderr)
        return 3
    except bundle.DeliveryError as exc:
        print(f"Teslim işlemi tamamlanmadı: {exc}", file=sys.stderr)
        return 1
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        psycopg.Error,
        RuntimeError,
        MigrationError,
        SnapshotError,
        subprocess.SubprocessError,
        UnavailableError,
    ):
        print(
            "Teslim işlemi tamamlanmadı: dosya, kanıt veya bağlantı doğrulanamadı; "
            "gizli ayrıntılar gösterilmedi.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
