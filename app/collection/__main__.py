"""Komut satırı: python -m app.collection [--prefix ÖN_EK] [--scheduled]

Çıkış kodları: 0 tur tamamlandı ve hata yok; 2 tur tamamlandı ama bazı
sayfalarda hata var; 1 tur başlayamadı ya da tur ortasında veritabanı hatası
oldu (yazılan sonuçlar kalır, tur 'interrupted' kapatılır; bağlantı koptuysa
'running' kalır ve sonraki tur kapatır); 3 başka bir tur/keşif/canlı kontrol
sürüyor; 130 Ctrl+C ile durduruldu (tur 'interrupted').

--scheduled (Görev Zamanlayıcı) ile bütün çıktı data/logs/tur_<yerel tarih-saat>.log
dosyasına da yazılır. Görev pythonw.exe ile penceresiz çalışır; ekran olmadığı
için turun tek yazılı kaydı bu dosyadır. Tek istisna: log dosyası açılamazsa
(klasör oluşturulamadı, yazma izni yok, disk dolu) tur hiç başlamaz ve kod 1
döner; mesaj hiçbir yere yazılamaz, veritabanında tur kaydı da olmaz. Görev
Zamanlayıcı'da yalnız "son sonuç 0x1" görünür.
"""

import argparse
import sys
import traceback
from datetime import datetime

import psycopg
from pydantic import ValidationError

from app.collection.service import CollectionError, RunInProgress, collect
from app.console import open_log, tee_output, utf8_output
from app.database.catalog_sync import CatalogConflict
from app.database.connection import connect, database_url
from app.database.migrate import MigrationError
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.settings import Settings

OUTCOME_NAMES = {
    "offer": "fiyat",
    "sold_out": "Tükendi",
    "error": "hata",
    "unchecked": "bakılmadı",
}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fiyat toplama turu")
    parser.add_argument(
        "--prefix", default="", help="Yalnızca bu product_key ön ekiyle (ör. poco_)"
    )
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Görev Zamanlayıcı başlattı: tur 'scheduled' kaydedilir, çıktı "
        "data/logs altına da yazılır",
    )
    args = parser.parse_args(argv)
    utf8_output()
    settings = Settings()
    if not args.scheduled:
        return run(args, settings)
    try:
        log = open_log(settings.log_dir, "tur")
    except OSError as exc:
        print(f"Log dosyası açılamadı: {exc}", file=sys.stderr)
        return 1
    with log, tee_output(log):
        print(f"Zamanlanmış tur · {datetime.now():%Y-%m-%d %H:%M:%S} (yerel saat)")
        try:
            code = run(args, settings)
        except Exception:
            # Program hatası: ayrıntısı ekransız çalışmada da kaybolmasın.
            traceback.print_exc()
            code = 1
        print(f"Çıkış kodu: {code}")
        return code


def run(args, settings: Settings) -> int:
    try:
        with scrape_lock(settings.lock_path):
            with connect(database_url()) as conn:
                report = collect(
                    conn,
                    settings.catalog_path,
                    settings.runtime(),
                    trigger="scheduled" if args.scheduled else "manual",
                    prefix=args.prefix,
                )
    except (ScrapeBusy, RunInProgress) as exc:
        print(f"Tur başlatılmadı: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print(
            "Komut durduruldu. Tamamlanmış tur 'completed' kalır; "
            "yarım kalan tur 'interrupted' olarak kapatılır. "
            "Kapatılamadıysa bir sonraki tur kapatır.",
            file=sys.stderr,
        )
        return 130
    except (
        CollectionError,
        CatalogConflict,
        MigrationError,
        RuntimeError,
        OSError,
        ValidationError,
        psycopg.Error,
    ) as exc:
        print(f"Tur başarısız: {exc}", file=sys.stderr)
        return 1
    counts = " · ".join(
        f"{OUTCOME_NAMES.get(name, name)} {count}"
        for name, count in report.summary.outcomes.items()
    )
    print(f"Tur {report.run_id} tamamlandı: {report.planned} sayfa → {counts}")
    if report.summary.error_codes:
        codes = ", ".join(
            f"{code} {count}" for code, count in report.summary.error_codes.items()
        )
        print(f"Hata kodları: {codes}")
    return 2 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
