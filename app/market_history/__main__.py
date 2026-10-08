"""Cimri geçmişini yerel dosyalara alır veya kaydedilmiş dosyaları aktarır."""

import argparse
import sys
from pathlib import Path

import psycopg

from app.console import utf8_output
from app.contracts import Catalog
from app.database.connection import connect, database_url
from app.database.market_history import HistoryImportBusy, import_history
from app.database.migrate import MigrationError
from app.market_history.capture import capture, read_mapping
from app.market_history.importer import HistoryImportError, read_capture
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
    transfer = commands.add_parser("import", help="Kaydedilmiş geçmişi ağsız aktar")
    transfer.add_argument("directory", type=Path, metavar="ALIM_KLASORU")
    transfer.add_argument(
        "--dry-run", action="store_true", help="Yalnız karşılaştır, veritabanına yazma"
    )
    args = parser.parse_args(argv)
    utf8_output()
    settings = Settings()
    if args.command == "import":
        return run_import(args, settings)
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


def run_import(args, settings) -> int:
    try:
        with scrape_lock(settings.lock_path):
            catalog = Catalog.model_validate_json(
                settings.catalog_path.read_text(encoding="utf-8-sig")
            )
            batch = read_capture(args.directory, catalog)
            print(f"Alım raporu: {args.directory / 'report.json'}")
            print(f"Rapor SHA-256: {batch.report_sha256}")
            with connect(database_url()) as conn:
                result = import_history(conn, batch, dry_run=args.dry_run)
    except (ScrapeBusy, HistoryImportBusy) as exc:
        print(f"Aktarım başlatılmadı: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print(
            "Aktarım durduruldu. Tamamlanmış ürünler korunur; son ürünün "
            "kesin sonucunu aynı klasörü yeniden çalıştırarak doğrulayın. "
            "Tekrar aktarım kayıt çoğaltmaz.",
            file=sys.stderr,
        )
        return 130
    except (
        HistoryImportError,
        MigrationError,
        RuntimeError,
        ValueError,
        OSError,
        psycopg.Error,
    ) as exc:
        print(
            f"Aktarım durdu: {exc}. Önceki tamamlanmış ürünler korunur.",
            file=sys.stderr,
        )
        return 1
    action = "eklenecek" if args.dry_run else "eklendi"
    print(
        f"Toplam: {sum(p.added for p in result.products)} {action}, "
        f"{sum(p.unchanged for p in result.products)} aynı; "
        f"çelişkili ürün: {sum(bool(p.conflicts) for p in result.products)}; "
        f"atlanan ürün: {result.skipped}."
    )
    if args.dry_run:
        print("Önizleme (--dry-run): veritabanına hiçbir şey yazılmadı.")
    return 2 if result.partial else 0


if __name__ == "__main__":
    sys.exit(main())
