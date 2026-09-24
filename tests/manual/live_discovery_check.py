"""Gerçek keşif akışını katalog değişmeden inceler."""

import json
import sys

from app.discovery.service import run


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    target = sys.argv[1] if len(sys.argv) > 1 else None
    report = run(dry_run=True, target_key=target)
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if report.complete else 2


if __name__ == "__main__":
    sys.exit(main())
