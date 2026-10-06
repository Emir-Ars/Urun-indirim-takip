"""Komutla keşif önizlemesi, katalog güncellemesi ve incelenmiş raporun uygulanması.

python -m app.discovery [--dry-run] [--target KEY]    tarar (siteye gider)
python -m app.discovery --scheduled --dry-run         Görev Zamanlayıcı'nın komutu
python -m app.discovery --apply-report RAPOR          siteye gitmeden raporu uygular

Tarama çıkış kodları: 0 tarama tam; 2 tarama kısmi (Hepsiburada arama API'si
engelli olduğu için bugün her zaman); 1 keşif başlatılamadı (ayar veya katalog
okunamadı, hedef bulunamadı, adaptör sözleşmeye uymuyor) ya da tarama bitti ama
sonuç kataloğa/rapora yazılamadı (mesaj hangisi olduğunu söyler); 3 başka bir
fiyat turu, keşif veya canlı kontrol sürüyor (ortak kilit), keşif başlatılmadı.

--scheduled yalnız --dry-run ile kullanılır: katalog yazılmaz, bütün çıktı
data/logs/kesif_<yerel tarih-saat>.log dosyasına da yazılır ve rapor aynı damgayla
data/discovery/ altına kaydedilir. Görev pythonw.exe ile penceresiz çalışır; ekran
olmadığı için çalışmanın tek yazılı kaydı log dosyasıdır. Log dosyası açılamazsa
keşif hiç başlamaz ve kod 1 döner.

--apply-report çıkış kodları: 0 katalog güncellendi ya da eklenecek bir şey
kalmadı; 2 güncellendi ama katalogla çelişen aday (catalog_conflict) atlandı; 1
hiçbir şey yazılmadı (rapor okunamadı, önizleme değil, katalog önizlemeden sonra
değişmiş...).
"""

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.console import open_log, tee_output, utf8_output
from app.contracts import DiscoveryReport
from app.discovery.service import (
    DEFAULT_REPORT_PATH,
    DiscoveryWriteError,
    apply_report,
    run,
    summarize_report,
)
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.settings import Settings


def main(argv=None):
    parser = argparse.ArgumentParser(description="Telefon bağlantılarını keşfet")
    parser.add_argument("--dry-run", action="store_true", help="Kataloğu değiştirme")
    parser.add_argument("--target", help="Yalnızca bu hedefi çalıştır")
    parser.add_argument(
        "--scheduled",
        action="store_true",
        help="Görev Zamanlayıcı başlattı (yalnız --dry-run ile): çıktı data/logs "
        "altına, rapor tarihli adla data/discovery altına da yazılır",
    )
    parser.add_argument(
        "--apply-report",
        type=Path,
        metavar="RAPOR",
        help="İncelenen önizleme raporunu siteye gitmeden kataloğa ekle",
    )
    args = parser.parse_args(argv)
    if args.apply_report is not None and (
        args.dry_run or args.target or args.scheduled
    ):
        parser.error("--apply-report başka seçeneklerle birlikte kullanılmaz")
    if args.scheduled and not args.dry_run:
        parser.error("--scheduled yalnız --dry-run ile kullanılır")
    utf8_output()
    if args.apply_report is not None:
        return apply(args.apply_report)
    if not args.scheduled:
        return scan(args.dry_run, args.target)
    settings = Settings()
    try:
        log = open_log(settings.log_dir, "kesif")
    except OSError as exc:
        print(f"Log dosyası açılamadı: {exc}", file=sys.stderr)
        return 1
    with log, tee_output(log):
        print(
            f"Zamanlanmış keşif (önizleme) · {datetime.now():%Y-%m-%d %H:%M:%S} "
            "(yerel saat)"
        )
        # Rapor, logla aynı zaman damgasını taşır: ikisi birlikte aranır.
        report_path = settings.discovery_report_dir / f"{Path(log.name).stem}.json"
        try:
            code = scan(True, args.target, report_path, print_json=False)
        except Exception:
            # Program hatası: ayrıntısı ekransız çalışmada da kaybolmasın.
            traceback.print_exc()
            code = 1
        print(f"Çıkış kodu: {code}")
        return code


def scan(dry_run, target_key, report_path=None, print_json=True):
    try:
        if report_path is not None:
            # Yazılamayan bir klasör ~35 dakikalık taramadan sonra değil, hemen
            # anlaşılsın.
            report_path.parent.mkdir(parents=True, exist_ok=True)
        # Fiyat turuyla aynı anda siteye gidilmesin (ortak kilit).
        with scrape_lock():
            report = run(
                dry_run=dry_run, target_key=target_key, report_path=report_path
            )
    except ScrapeBusy as exc:
        # Tur ve canlı kontrol araçlarıyla aynı kod: hata değil, sıra meselesi.
        print(f"Keşif başlatılmadı: {exc}", file=sys.stderr)
        return 3
    except DiscoveryWriteError as exc:
        print(f"Tarama bitti ama sonuç yazılamadı: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, ImportError) as exc:
        print(f"Keşif başlatılamadı: {exc}", file=sys.stderr)
        return 1
    if print_json:
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    # stderr: elle çalıştırmada stdout yalnız rapor JSON'u kalır.
    print(summarize_report(report), file=sys.stderr)
    print(f"Rapor: {report_path or DEFAULT_REPORT_PATH}", file=sys.stderr)
    return 0 if report.complete else 2


def apply(path):
    try:
        report = DiscoveryReport.model_validate_json(
            path.read_text(encoding="utf-8-sig")
        )
    except ValidationError as exc:
        # --trace çıktısı ({"report": ..., "traces": ...}) da buraya düşer.
        first = exc.errors()[0]
        where = ".".join(map(str, first["loc"])) or "dosya"
        print(
            f"{path} geçerli bir keşif raporu değil ({exc.error_count()} hata; "
            f"ilki: {where}: {first['msg']})",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Rapor okunamadı: {exc}", file=sys.stderr)
        return 1
    try:
        products, listings, existing, conflicts = apply_report(
            report, Settings().catalog_path
        )
    except (OSError, ValueError) as exc:
        print(f"Rapor uygulanamadı: {exc}", file=sys.stderr)
        return 1
    made = (
        report.generated_at.astimezone().strftime("%Y-%m-%d %H:%M")
        if report.generated_at
        else "bilinmiyor (eski rapor)"
    )
    print(f"Rapor: {path} (önizleme zamanı: {made}, yerel saat)")
    print(f"Eklendi: {len(products)} ürün, {len(listings)} sayfa")
    for product_key in products:
        print(f"  + ürün {product_key}")
    for listing_id in listings:
        print(f"  + sayfa {listing_id}")
    print(f"Zaten katalogda: {len(existing)} sayfa")
    for issue in conflicts:
        print(f"  ! yazılmadı (çakışma): {issue.detail}")
    if listings:
        print(
            "Katalog güncellendi; sonraki fiyat turu yeni sayfaları veritabanına "
            "ekler. config/catalog.json değişikliğini commit edin."
        )
    else:
        print("Katalog değişmedi.")
    return 2 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
