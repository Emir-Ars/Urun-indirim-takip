"""Keşif sonuçlarını kimlikleri koruyarak kataloğa aktarır."""

import importlib
import inspect
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

from filelock import FileLock

from app.contracts import (
    Catalog,
    DiscoveryIssue,
    DiscoveryReport,
    Listing,
    Product,
    utc_now,
)
from app.discovery.base import BaseDiscovery
from app.settings import Settings

# Elle çalıştırmada rapor buraya yazılır ve her çalışmada üzerine yazılır;
# zamanlanmış keşif tarihli bir yol verir (run: report_path).
DEFAULT_REPORT_PATH = Path("data/discovery_report.json")


class ReportMismatch(ValueError):
    """Rapor, katalogun bugünkü hâliyle önizlemedeki eklemeleri vermiyor."""


def _adapter(platform: str):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", platform):
        raise ValueError("Geçersiz platform anahtarı")
    module = importlib.import_module(f"app.discovery.{platform}")
    # Discovery adı olmayan modül (ör. base) de sözleşme hatasıdır: ValueError,
    # komut satırında traceback yerine çıkış 1.
    implementation = getattr(module, "Discovery", None)
    if (
        implementation is None
        or not inspect.isclass(implementation)
        or not issubclass(implementation, BaseDiscovery)
        or inspect.isabstract(implementation)
    ):
        raise ValueError("Keşif adaptörü sözleşmeye uymuyor")
    return implementation


def _url_identity(platform, url):
    """Bağlantının adresindeki site kimliği (Trendyol -p-<sayı>, Hepsiburada HBCV…).

    Mevcut bağlantılar listing_id ile değil bu kimlikle eşleştirilir; böylece elle
    adlandırılmış eski kayıtlar da (ör. trendyol_iphone_15_128gb_mavi) "zaten var"
    sayılır. .upper(), adreste küçük harfle yazılmış SKU'yu adayın kimliğiyle eşitler.
    """
    patterns = {
        "trendyol": r"-p-(\d+)(?:[/?]|$)",
        "hepsiburada": r"-p-(HBCV[A-Z0-9]+)(?:[/?]|$)",
    }
    pattern = patterns.get(platform)
    if pattern:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def _conflict(candidate, detail: str) -> DiscoveryIssue:
    return DiscoveryIssue(
        platform=candidate.platform,
        target_key=candidate.target_key,
        reason="catalog_conflict",
        detail=f"{candidate.platform_product_id}: {detail}"[:300],
    )


def merge_catalog(catalog: Catalog, candidates):
    """Salt veri dönüşümü; var olan ürün ve bağlantı kimliklerine dokunmaz.

    Katalogla çelişen aday (ör. kayıtlı SKU'nun başka kapasite olarak görülmesi)
    yazılmaz; çakışma olarak döner, diğer adayların birleştirmesi sürer.
    """
    products = list(catalog.products)
    listings = list(catalog.listings)
    identities = {
        (p.brand.casefold(), p.model.casefold(), p.storage_gb): p for p in products
    }
    existing = {
        (item.platform, _url_identity(item.platform, item.url)): item
        for item in listings
        if _url_identity(item.platform, item.url)
    }
    next_id = max((product.product_id for product in products), default=0) + 1
    product_names = {product.product_id: product.name for product in products}
    listing_ids = {item.listing_id for item in listings}
    added_products = []
    added_listings = []
    existing_listings = []
    conflicts = []
    # Sıralama kimlik atamasını belirleyici yapar: yeni product_id'ler next_id'den
    # sırayla verilir. Adaylar sitenin döndürdüğü sırayla değil sabit anahtarla
    # işlendiği için aynı aday kümesi her zaman aynı kimlikleri ve katalog sırasını
    # üretir (kimlik bir kez verilir, sonra değişmez).
    for candidate in sorted(
        candidates,
        key=lambda item: (
            item.target_key,
            item.storage_gb,
            item.platform,
            item.platform_product_id,
        ),
    ):
        identity = (
            candidate.brand.casefold(),
            candidate.model.casefold(),
            candidate.storage_gb,
        )
        product = identities.get(identity)
        # Çakışma ürün oluşturmadan önce denetlenir; böylece bağlantısız ürün kalmaz.
        listing_key = (candidate.platform, candidate.platform_product_id.upper())
        old = existing.get(listing_key)
        if old is not None:
            if product is None or old.product_id != product.product_id:
                conflicts.append(
                    _conflict(
                        candidate,
                        f"katalogda {old.listing_id} "
                        f"'{product_names.get(old.product_id)}' ürününe bağlı; "
                        f"aday {candidate.model} {candidate.storage_gb} GB",
                    )
                )
                continue
            existing_listings.append(old.listing_id)
            continue
        listing_id = f"{candidate.platform}_{candidate.platform_product_id.lower()}"
        if listing_id in listing_ids:
            conflicts.append(
                _conflict(
                    candidate, f"{listing_id} kimliği başka bir URL'de kullanılıyor"
                )
            )
            continue
        if product is None:
            product_key = f"{candidate.target_key}_{candidate.storage_gb}gb"
            product = Product(
                product_id=next_id,
                product_key=product_key,
                brand=candidate.brand,
                model=candidate.model,
                storage_gb=candidate.storage_gb,
            )
            products.append(product)
            identities[identity] = product
            product_names[product.product_id] = product.name
            added_products.append(product_key)
            next_id += 1
        new = Listing(
            listing_id=listing_id,
            product_id=product.product_id,
            platform=candidate.platform,
            url=candidate.url,
            color=candidate.color,
        )
        listings.append(new)
        existing[listing_key] = new
        listing_ids.add(listing_id)
        added_listings.append(listing_id)
    updated = Catalog(
        platforms=catalog.platforms,
        products=products,
        listings=listings,
    )
    return updated, added_products, added_listings, existing_listings, conflicts


def _atomic_catalog(path: Path, catalog: Catalog):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        # newline="\n": Windows'ta da LF yazılır; her yazımda dosyanın bütün satır
        # sonları değişmez.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                catalog.model_dump(mode="json"), handle, ensure_ascii=False, indent=2
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def observed_colors(candidates):
    """Doğrulanan renkleri kapasite ve platform bazında raporlar."""
    colors = {}
    for candidate in candidates:
        capacity = colors.setdefault(candidate.target_key, {}).setdefault(
            str(candidate.storage_gb), {}
        )
        capacity.setdefault(candidate.platform, set()).add(
            candidate.color or "Bilinmiyor"
        )
    return {
        target: {
            capacity: {
                platform: sorted(values) for platform, values in platforms.items()
            }
            for capacity, platforms in capacities.items()
        }
        for target, capacities in colors.items()
    }


def retained_unobserved_listings(catalog, targets, results):
    """Etkin olduğu hâlde bu taramada görülmeyen sayfalar (katalogdan silinmez).

    Pasif bağlantılar zaten takip edilmediği için listelenmez.
    """
    by_key = {target.key: target for target in targets}
    retained = set()
    for result in results:
        target = by_key[result.target_key]
        product_ids = {
            product.product_id
            for product in catalog.products
            if product.brand.casefold() == target.brand.casefold()
            and product.model.casefold() == target.model.casefold()
        }
        observed = {
            candidate.platform_product_id.upper() for candidate in result.candidates
        }
        for listing in catalog.listings:
            if (
                listing.active
                and listing.product_id in product_ids
                and listing.platform == result.platform
                and _url_identity(listing.platform, listing.url) not in observed
            ):
                retained.add(listing.listing_id)
    return sorted(retained)


def _report_candidates(results):
    # Canlı yazma, önizleme ve rapor uygulama aynı aday listesini birleştirir:
    # --apply-report'un "önizlemedeki eklemeleri verir" varsayımı buna dayanır.
    return [candidate for result in results for candidate in result.candidates]


def _merge_into_catalog_file(catalog_path, candidates, check=None):
    """Kataloğu kilit altında okur, birleştirir ve yalnız değiştiyse yazar.

    Bu kilit yalnız kataloğun oku-birleştir-yaz anını korur; siteye gidişi sıraya
    koyan data/scrape.lock çağıran tarafta (__main__, canlı araç) alınır. Tarama
    dakikalar sürdüğü için katalog kilit altında yeniden okunur: bu arada dosya
    değişmiş olabilir. İçerik değişmediyse dosya hiç yazılmaz; tekrar çalıştırmada
    bayt düzeyinde aynı kalır. `check`, yazmadan önce eklenecek ürün ve bağlantı
    kimlikleriyle çağrılır; istisna atarsa hiçbir şey yazılmaz.
    """
    with FileLock(str(catalog_path) + ".lock", timeout=30):
        latest = Catalog.model_validate_json(
            catalog_path.read_text(encoding="utf-8-sig")
        )
        updated, products, listings, existing, conflicts = merge_catalog(
            latest, candidates
        )
        if check is not None:
            check(products, listings)
        if updated != latest:
            _atomic_catalog(catalog_path, updated)
    return products, listings, existing, conflicts


def apply_report(report: DiscoveryReport, catalog_path: Path):
    """İncelenen önizleme raporunu siteye gitmeden kataloğa uygular.

    Yeniden tarama, Hepsiburada'nın ilk 36 kartı değişebildiği için incelenenden
    farklı sayfalar bulabilir; bu yüzden eklenecekler raporun kendi adaylarından
    hesaplanır. Katalog önizlemeden sonra elle değiştiyse (ör. başka bir ürün
    eklendi) bu hesap önizlemede olmayan bir ekleme üretebilir; o durumda hiçbir
    şey yazılmaz. Önizlemede görünen ama artık katalogda olan kayıtlar sorun
    değildir: aynı rapor ikinci kez uygulanırsa eklenecek bir şey kalmaz.
    """
    if not report.dry_run:
        raise ValueError(
            "Rapor bir önizleme (--dry-run) değil; bu çalışma kataloğu zaten yazdı"
        )
    preview_products = set(report.added_products)
    preview_listings = set(report.added_listings)

    def within_preview(products, listings):
        extra = sorted(
            (set(products) - preview_products) | (set(listings) - preview_listings)
        )
        if extra:
            raise ReportMismatch(
                "Katalog önizlemeden sonra değişmiş; önizlemede olmayan eklemeler "
                f"çıktı ({', '.join(extra)}). Hiçbir şey yazılmadı; yeni bir "
                "önizleme alın (--dry-run)."
            )

    return _merge_into_catalog_file(
        catalog_path, _report_candidates(report.results), within_preview
    )


def summarize_report(report: DiscoveryReport) -> str:
    """Raporun tek satırlık özeti.

    Keşfin çıkış kodu Hepsiburada arama API'si engelli olduğu için bugün her zaman
    2'dir ve tek başına bir şey söylemez; uyarılar nedene göre sayılarak beklenen
    `search_api` ile gerçek sorunlar ayrılır.
    """
    conflicts = sum(issue.reason == "catalog_conflict" for issue in report.rejected)
    platforms = ", ".join(
        f"{platform} {count}"
        for platform, count in sorted(report.coverage_changes.items())
        if count
    )
    parts = [
        f"yeni ürün {len(report.added_products)}",
        f"yeni sayfa {len(report.added_listings)}"
        + (f" ({platforms})" if platforms else ""),
        f"zaten kayıtlı {len(report.existing_listings)}",
        f"görülmeyen {len(report.retained_unobserved_listings)}",
        f"çakışma {conflicts}",
        f"reddedilen {len(report.rejected) - conflicts}",
        f"tam sonuç {sum(r.complete for r in report.results)}/{len(report.results)}",
    ]
    warnings = Counter(issue.reason for issue in report.pending)
    if warnings:
        parts.append(
            "uyarı "
            + ", ".join(
                f"{reason} {count}" for reason, count in sorted(warnings.items())
            )
        )
    return "Özet: " + " · ".join(parts)


def run(*, dry_run=False, target_key=None, adapters=None, report_path=None):
    settings = Settings()
    config = settings.discovery()
    catalog_path = settings.catalog_path
    # utf-8-sig: Windows düzenleyicilerinin koyduğu BOM da okunur; BOM'suz dosya aynı.
    catalog = Catalog.model_validate_json(catalog_path.read_text(encoding="utf-8-sig"))
    runtime = settings.runtime()
    targets = [
        item
        for item in config.targets
        if item.active and (target_key is None or item.key == target_key)
    ]
    if target_key and not targets:
        raise ValueError(f"Keşif hedefi bulunamadı: {target_key}")
    results = []
    for target in targets:
        for platform in catalog.platforms:
            if not platform.active:
                continue
            implementation = (
                adapters[platform.key]
                if adapters is not None
                else _adapter(platform.key)
            )
            discovery = implementation(target, config, runtime)
            try:
                results.append(discovery.discover())
            finally:
                discovery.close()
    candidates = _report_candidates(results)
    if dry_run:
        # Önizleme: birleştirme sonucu yalnız rapora girer; katalog kilidi alınmaz,
        # dosya hiç yazılmaz.
        _, products, listings, existing, conflicts = merge_catalog(catalog, candidates)
    else:
        products, listings, existing, conflicts = _merge_into_catalog_file(
            catalog_path, candidates
        )
    report = DiscoveryReport(
        complete=bool(results)
        and all(result.complete for result in results)
        and not conflicts,
        dry_run=dry_run,
        generated_at=utc_now(),
        results=results,
        added_products=products,
        added_listings=listings,
        existing_listings=existing,
        retained_unobserved_listings=retained_unobserved_listings(
            catalog, targets, results
        ),
        pending=[
            issue
            for result in results
            for issue in result.issues
            if issue.reason != "candidate_rejected"
        ],
        rejected=[
            issue
            for result in results
            for issue in result.issues
            if issue.reason == "candidate_rejected"
        ]
        + conflicts,
        coverage_changes={
            platform.key: sum(
                listing_id.startswith(platform.key + "_") for listing_id in listings
            )
            for platform in catalog.platforms
        },
        observed_colors=observed_colors(candidates),
    )
    report_path = report_path if report_path is not None else DEFAULT_REPORT_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
