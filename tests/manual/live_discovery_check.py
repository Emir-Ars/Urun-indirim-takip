"""Gerçek keşif akışını katalog değişmeden inceler.

`--trace`, keşfin rapora yazmadığı kararları da basar: elenen arama kartları ve
nedenleri, seçilen filtreler, varyant kaynaklarının döndürdüğü ürünler.
"""

import argparse
import json
import sys

from app.contracts import Catalog
from app.discovery.service import _adapter, run
from app.settings import Settings


def traced_adapters(collected):
    """Üretim adaptörlerini yalnız izlerini toplayan alt sınıflarla sarar."""
    settings = Settings()
    catalog = Catalog.model_validate_json(
        settings.catalog_path.read_text(encoding="utf-8")
    )
    adapters = {}
    for platform in catalog.platforms:
        base = _adapter(platform.key)

        class Traced(base):
            def discover(self):
                try:
                    return super().discover()
                finally:
                    collected.append(
                        {
                            "platform": self.platform,
                            "target_key": self.target.key,
                            "requests": self.pages.request_count,
                            "trace": self.trace,
                        }
                    )

        adapters[platform.key] = Traced
    return adapters


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Canlı keşif denetimi (dry-run)")
    parser.add_argument("target", nargs="?", help="Yalnızca bu hedefi çalıştır")
    parser.add_argument("--trace", action="store_true", help="Karar izini de bas")
    args = parser.parse_args()
    traces = []
    adapters = traced_adapters(traces) if args.trace else None
    report = run(dry_run=True, target_key=args.target, adapters=adapters)
    output = report.model_dump(mode="json")
    if args.trace:
        output = {"report": output, "traces": traces}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if report.complete else 2


if __name__ == "__main__":
    sys.exit(main())
