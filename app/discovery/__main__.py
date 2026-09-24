"""Komutla keşif önizlemesi veya katalog güncellemesi."""

import argparse
import json
import sys

from app.discovery.service import run


def main(argv=None):
    parser = argparse.ArgumentParser(description="Telefon bağlantılarını keşfet")
    parser.add_argument("--dry-run", action="store_true", help="Kataloğu değiştirme")
    parser.add_argument("--target", help="Yalnızca bu hedefi çalıştır")
    args = parser.parse_args(argv)
    try:
        report = run(dry_run=args.dry_run, target_key=args.target)
    except (OSError, ValueError, ImportError) as exc:
        print(f"Keşif başlatılamadı: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if report.complete else 2


if __name__ == "__main__":
    sys.exit(main())
