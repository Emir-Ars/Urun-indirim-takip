"""Bir defalık Cimri geçmişini yerel dosyalara alır; veritabanına bağlanmaz."""

import argparse
import sys
from pathlib import Path

from app.console import utf8_output
from app.contracts import Catalog
from app.market_history.capture import capture, read_mapping
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.settings import Settings

STATUS_LABELS = {
    "captured": "kaydedildi",
    "error": "hata",
    "unmapped": "eşleştirme henüz yok",
    "not_attempted": "denenmedi",
    "interrupted": "durduruldu",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("capture", help="Yalnız yerel yanıt ve rapor üret")
    collect.add_argument("--mapping", type=Path, required=True, metavar="DOSYA")
    collect.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    collect.add_argument(
        "--product-key",
        action="append",
        help="Yalnız bu katalog ürünü; birkaç ürün için seçenek tekrarlanabilir",
    )
    args = parser.parse_args(argv)
    utf8_output()
    settings = Settings()
    try:
        catalog = Catalog.model_validate_json(
            settings.catalog_path.read_text(encoding="utf-8-sig")
        )
        mapping = read_mapping(args.mapping, catalog)
        runtime = settings.runtime()
        with scrape_lock(settings.lock_path):
            report = capture(
                catalog, mapping, args.output_dir, runtime, args.product_key
            )
    except ScrapeBusy as exc:
        print(f"Alım başlatılmadı: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print(
            f"Alım durduruldu; kaydedilmiş yanıtlar korunur. Klasör: {args.output_dir}",
            file=sys.stderr,
        )
        return 130
    except FileExistsError:
        print(
            "Alım başlatılmadı: klasör zaten var; yeni bir klasör seç.", file=sys.stderr
        )
        return 1
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Alım tamamlanamadı: {exc}", file=sys.stderr)
        return 1
    print(f"Rapor: {args.output_dir / 'report.json'}")
    for record in report["products"]:
        key = record["product"]["product_key"]
        print(
            f"{key}: {STATUS_LABELS[record['status']]}; HTTP: {record['request_count']}"
        )
        if "history" in record:
            summary = record["history"]["summary"]
            comparison = (
                "eşleşti"
                if summary["table_comparison"] == "matched"
                else "karşılaştırılamadı"
            )
            print(
                f"  {summary['point_count']} nokta, {summary['oldest_day']}–"
                f"{summary['newest_day']}; "
                f"eksik fiyat: {summary['missing_price_count']}; "
                f"tablo: {comparison} "
                f"({summary['table_compared_rows']})"
            )
            latest = summary["latest_price"]
            if latest["rule"] == "page_first_offer":
                print("  Alım günü fiyatı: sayfanın ilk teklifinden doğrulandı.")
            if latest["table_comparison"] == "unavailable":
                print(
                    "  Son gün için tablo satırı yok; "
                    "o gün tabloyla karşılaştırılamadı."
                )
        if "error" in record:
            print(f"  {record['error']['code']}: {record['error']['detail']}")
        if "reason" in record:
            print(f"  İstek yapılmadı: {record['reason']}")
    print(
        f"Katalog: {report['catalog_product_count']} ürün; "
        f"eşleştirmesi henüz olmayan: {len(report['unmapped_catalog_product_keys'])}. "
        "Veritabanına yazılmadı."
    )
    return 0 if report["result"] == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
