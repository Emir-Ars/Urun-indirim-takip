"""Gerçek keşif akışını katalog değişmeden inceler.

`--trace`, keşfin rapora yazmadığı kararları da basar: elenen arama kartları ve
nedenleri, seçilen filtreler, varyant kaynaklarının döndürdüğü ürünler.
`--save-responses`, tek hedefin ham HTML/JSON yanıtlarını yeni klasöre kaydeder.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.console import utf8_output
from app.contracts import Catalog
from app.discovery.service import _adapter, run
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.scraper.http import FetchError
from app.settings import Settings


def _capture_responses(pages, directory):
    directory.mkdir(parents=True, exist_ok=False)
    records = []
    request = pages._request

    def captured(method, url, **kwargs):
        record = {
            "method": method,
            "url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        records.append(record)
        try:
            body = request(method, url, **kwargs)
            suffix = ".json" if body.lstrip().startswith((b"{", b"[")) else ".html"
            filename = f"{len(records):04d}{suffix}"
            (directory / filename).write_bytes(body)
            record["file"] = filename
            return body
        except FetchError as exc:
            record.update(error_code=exc.code, error=str(exc))
            raise
        finally:
            record["request_count"] = pages.request_count
            (directory / "index.json").write_text(
                json.dumps(records, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    # JSON ayrıştırması başarısız olsa da kaynağın özgün baytları korunmalı.
    pages._request = captured


def traced_adapters(collected, response_dir=None):
    """Üretim adaptörlerini yalnız izlerini toplayan alt sınıflarla sarar."""
    settings = Settings()
    catalog = Catalog.model_validate_json(
        settings.catalog_path.read_text(encoding="utf-8-sig")
    )
    adapters = {}
    for platform in catalog.platforms:
        base = _adapter(platform.key)

        class Traced(base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if response_dir is not None:
                    try:
                        _capture_responses(
                            self.pages,
                            response_dir / f"{self.platform}_{self.target.key}",
                        )
                    except OSError:
                        self.close()
                        raise

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


def main(argv=None):
    utf8_output()
    parser = argparse.ArgumentParser(description="Canlı keşif denetimi (dry-run)")
    parser.add_argument("target", nargs="?", help="Yalnızca bu hedefi çalıştır")
    parser.add_argument("--trace", action="store_true", help="Karar izini de bas")
    parser.add_argument(
        "--save-responses",
        type=Path,
        metavar="KLASOR",
        help="Tek hedefin ham yanıtlarını yeni klasöre kaydet (karar izi dahil)",
    )
    args = parser.parse_args(argv)
    if args.save_responses and not args.target:
        parser.error("Ham yanıt kaydı için tek bir hedef belirtilmeli")
    trace = args.trace or args.save_responses is not None
    traces = []
    try:
        # Fiyat turu veya başka bir tarama sürerken siteye gidilmesin.
        with scrape_lock():
            if args.save_responses is not None:
                try:
                    args.save_responses.mkdir(parents=True, exist_ok=False)
                except FileExistsError:
                    parser.error("Ham yanıt klasörü zaten var; yeni bir klasör seç")
            adapters = traced_adapters(traces, args.save_responses) if trace else None
            report = run(
                dry_run=True,
                target_key=args.target,
                adapters=adapters,
                report_path=(
                    args.save_responses / "report.json" if args.save_responses else None
                ),
            )
    except ScrapeBusy as exc:
        print(f"Başlatılmadı: {exc}", file=sys.stderr)
        return 3
    output = report.model_dump(mode="json")
    if trace:
        output = {"report": output, "traces": traces}
    if args.save_responses is not None:
        output["responses"] = str(args.save_responses)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if report.complete else 2


if __name__ == "__main__":
    sys.exit(main())
