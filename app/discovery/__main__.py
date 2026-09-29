"""Komutla keşif önizlemesi veya katalog güncellemesi.

Çıkış kodları: 0 tarama tam; 2 tarama kısmi (Hepsiburada arama API'si engelli
olduğu için bugün her zaman); 1 keşif başlatılamadı (ayar veya katalog
okunamadı, hedef bulunamadı, adaptör sözleşmeye uymuyor); 3 başka bir fiyat
turu, keşif veya canlı kontrol sürüyor (ortak kilit), keşif başlatılmadı.
"""

import argparse
import json
import sys

from app.discovery.service import run
from app.scrape_lock import ScrapeBusy, scrape_lock


def main(argv=None):
    parser = argparse.ArgumentParser(description="Telefon bağlantılarını keşfet")
    parser.add_argument("--dry-run", action="store_true", help="Kataloğu değiştirme")
    parser.add_argument("--target", help="Yalnızca bu hedefi çalıştır")
    args = parser.parse_args(argv)
    utf8_output()
    try:
        # Fiyat turuyla aynı anda siteye gidilmesin (ortak kilit).
        with scrape_lock():
            report = run(dry_run=args.dry_run, target_key=args.target)
    except ScrapeBusy as exc:
        # Tur ve canlı kontrol araçlarıyla aynı kod: hata değil, sıra meselesi.
        print(f"Keşif başlatılmadı: {exc}", file=sys.stderr)
        return 3
    except (OSError, ValueError, ImportError) as exc:
        print(f"Keşif başlatılamadı: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if report.complete else 2


def utf8_output() -> None:
    # Çıktı dosyaya yönlendirildiğinde de Türkçe karakterler bozulmasın; hata
    # çıktısı (stderr) da dahil. pythonw.exe altında akışlar hiç yoktur (None).
    # app.collection ve app.database komutları aynı küçük döngünün kopyasını tutar.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


if __name__ == "__main__":
    sys.exit(main())
