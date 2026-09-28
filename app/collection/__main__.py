"""Komut satırı: python -m app.collection [--prefix ÖN_EK] [--scheduled]

Çıkış kodları: 0 tur tamamlandı ve hata yok; 2 tur tamamlandı ama bazı
sayfalarda hata var; 1 tur başlayamadı; 3 başka bir tur/keşif/canlı kontrol
sürüyor; 130 Ctrl+C ile durduruldu (tur 'interrupted').
"""

import argparse
import sys

import psycopg
from pydantic import ValidationError

from app.collection.service import CollectionError, RunInProgress, collect
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
        help="Görev Zamanlayıcı tarafından başlatıldı (tur 'scheduled' kaydedilir)",
    )
    args = parser.parse_args(argv)
    utf8_output()
    settings = Settings()
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
            "Tur durduruldu. Açılmış tur 'interrupted' olarak kapatıldı; "
            "kapatılamadıysa bir sonraki tur kapatır.",
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


def utf8_output() -> None:
    # Görev Zamanlayıcı çıktıyı dosyaya yönlendirdiğinde de Türkçe karakterler
    # bozulmasın; hata çıktısı (stderr) da dahil.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


if __name__ == "__main__":
    sys.exit(main())
