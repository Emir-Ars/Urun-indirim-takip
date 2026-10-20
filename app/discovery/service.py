"""Keşif sonuçlarını kimlikleri koruyarak kataloğa aktarır."""

import importlib
import inspect
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from filelock import FileLock, Timeout

from app.contracts import (
    Catalog,
    DiscoveryApplication,
    DiscoveryConfig,
    DiscoveryIssue,
    DiscoveryReport,
    Listing,
    Product,
    utc_now,
)
from app.discovery.acceptance import color_key, decide
from app.discovery.base import BaseDiscovery
from app.scraper.parsing import hepsiburada_sku, trendyol_product_id
from app.settings import Settings

# Elle çalıştırmada rapor buraya yazılır ve her çalışmada üzerine yazılır;
# zamanlanmış keşif tarihli bir yol verir (run: report_path).
DEFAULT_REPORT_PATH = Path("data/discovery_report.json")


class ReportMismatch(ValueError):
    """Rapor, katalogun bugünkü hâliyle önizlemedeki eklemeleri vermiyor."""


class DiscoveryWriteError(RuntimeError):
    """Tarama tamamlandı ama sonucu kataloğa ya da rapora yazılamadı.

    Nedeni disk, kilit zaman aşımı ya da taramadan sonra bozulmuş bir katalog
    olabilir; çıkış kodu 1'dir ama "keşif başlatılamadı"dan farklıdır: tarama
    yapılmıştır. Kalıcı hazırlık kaydı varsa sonraki başlangıçta uzlaştırılır;
    hata tek başına kataloğun değişmediğini söylemez.
    """


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
    readers = {
        "trendyol": trendyol_product_id,
        "hepsiburada": hepsiburada_sku,
    }
    reader = readers.get(platform)
    return reader(url) if reader else None


def _conflict(candidate, detail: str) -> DiscoveryIssue:
    return DiscoveryIssue(
        platform=candidate.platform,
        target_key=candidate.target_key,
        reason="catalog_conflict",
        detail=f"{candidate.platform_product_id}: {detail}"[:300],
    )


def merge_catalog(catalog: Catalog, candidates, bindings=()):
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
    platforms = {item.key: item for item in catalog.platforms}
    added_products = []
    added_listings = []
    existing_listings = []
    conflicts = []
    reserved = {(b.platform, b.platform_product_id.upper()): b for b in bindings}
    for binding in bindings:
        owner = next((p for p in products if p.product_id == binding.product_id), None)
        if owner is None or owner.product_key != binding.product_key:
            raise ValueError("Kaldırılmış bağlantının eski ürün bağı doğrulanamadı")
        old = next(
            (item for item in listings if item.listing_id == binding.listing_id), None
        )
        if old and (
            old.product_id != binding.product_id
            or old.platform != binding.platform
            or _url_identity(old.platform, old.url)
            != binding.platform_product_id.upper()
        ):
            raise ValueError("Kaldırılmış bağlantı kimliği katalogla çelişiyor")
    grouped = {}
    declared_ram = {}
    for candidate in candidates:
        key = (candidate.platform, candidate.platform_product_id.upper())
        grouped.setdefault(key, set()).add(
            (
                candidate.brand.casefold(),
                candidate.model.casefold(),
                candidate.storage_gb,
                color_key(candidate.color),
            )
        )
        if candidate.ram_gb is not None:
            declared_ram.setdefault(key, set()).add(candidate.ram_gb)
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
        if len(grouped[listing_key]) > 1 or len(declared_ram.get(listing_key, ())) > 1:
            conflicts.append(_conflict(candidate, "aynı taramada çelişkili kimlikler"))
            continue
        binding = reserved.get(listing_key)
        if binding and (product is None or product.product_id != binding.product_id):
            conflicts.append(
                _conflict(candidate, "kaldırılmış bağlantı başka ürüne taşınamaz")
            )
            continue
        if product and not product.active:
            conflicts.append(
                _conflict(candidate, "ürün katalogda pasif; yeni sayfa eklenmedi")
            )
            continue
        if (
            candidate.platform not in platforms
            or not platforms[candidate.platform].active
        ):
            conflicts.append(_conflict(candidate, "platform katalogda pasif"))
            continue
        old = existing.get(listing_key)
        if old is not None:
            if binding and old.listing_id != binding.listing_id:
                conflicts.append(
                    _conflict(
                        candidate, "kaldırılmış bağlantının eski kimliği korunmalı"
                    )
                )
                continue
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
        listing_id = (
            binding.listing_id
            if binding
            else f"{candidate.platform}_{candidate.platform_product_id.lower()}"
        )
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


def _guard_results(results, config):
    targets = {t.key: t for t in config.targets if t.active}
    guarded = []
    for result in results:
        target = targets.get(result.target_key)
        if target is None:
            raise ReportMismatch("Raporun hedefi etkin keşif ayarlarında bulunamadı")
        decisions = {}
        for decision in result.decisions:
            evidence = decision.evidence
            if (
                decision.target_key != result.target_key
                or evidence.platform != result.platform
            ):
                raise ReportMismatch("Kanıtın hedef/platform bağı değişmiş")
            if decide(evidence, target) != decision:
                raise ReportMismatch(
                    "Raporun kimlik kararı kanıttan yeniden üretilemiyor"
                )
            key = evidence.platform_product_id.upper()
            if key in decisions:
                raise ReportMismatch("Bir sayfa için tekrarlanan karar var")
            decisions[key] = decision
        accepted, issues = [], list(result.issues)
        for candidate in result.candidates:
            decision = decisions.get(candidate.platform_product_id.upper())
            if not decision:
                issues.append(
                    DiscoveryIssue(
                        platform=result.platform,
                        target_key=target.key,
                        reason="evidence_missing",
                        detail=candidate.platform_product_id,
                    )
                )
                continue
            if decision.status != "verified":
                continue
            proven = decision.candidate
            if (
                candidate.target_key != target.key
                or candidate.platform != result.platform
                or candidate.brand != proven.brand
                or candidate.model != proven.model
                or candidate.storage_gb != proven.storage_gb
                or _url_identity(candidate.platform, candidate.url)
                != proven.platform_product_id
                or urlsplit(candidate.url).hostname != urlsplit(proven.url).hostname
                or color_key(candidate.color) != color_key(proven.color)
            ):
                raise ReportMismatch("Adayın kimliği kaydedilen kanıtla çelişiyor")
            accepted.append(proven)
        for decision in result.decisions:
            if decision.status != "verified":
                issues.append(
                    DiscoveryIssue(
                        platform=result.platform,
                        target_key=target.key,
                        reason=(
                            "identity_mismatch"
                            if decision.status == "mismatch"
                            else "evidence_missing"
                        ),
                        detail=(
                            f"{decision.evidence.platform_product_id}: "
                            f"{', '.join(decision.reasons)}"
                        ),
                    )
                )
        issues = list(dict.fromkeys(issues))
        guarded.append(
            result.model_copy(
                update={
                    "candidates": accepted,
                    "issues": issues,
                    "complete": result.complete and not issues,
                }
            )
        )
    return guarded


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _payload_digest(report):
    payload = report.model_dump(mode="json")
    if payload.get("application"):
        payload["application"].pop("payload_sha256")
        payload["application"].pop("state")
    return _digest(_json_bytes(payload))


def _seal_report(report):
    return report.model_copy(
        update={
            "application": report.application.model_copy(
                update={"payload_sha256": _payload_digest(report)}
            )
        }
    )


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_json_bytes(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def _atomic_report(path, report):
    _atomic_json(path, report.model_dump(mode="json"))


def _journal_path(catalog_path):
    # Elle ve zamanlayıcıyla başlatılan işler aynı kataloğun yarım yazımını görür.
    key = _digest(str(catalog_path.resolve()).casefold().encode())[:20]
    return Settings().discovery_report_dir / f"pending_{key}.json"


def _recover_pending(catalog_path):
    journal = _journal_path(catalog_path)
    if not journal.exists():
        return
    with FileLock(str(catalog_path) + ".lock", timeout=30):
        if not journal.exists():
            return
        saved = json.loads(journal.read_text(encoding="utf-8"))
        report = DiscoveryReport.model_validate_json(json.dumps(saved["report"]))
        application = report.application
        if (
            application is None
            or application.state != "prepared"
            or application.catalog_path != str(catalog_path.resolve())
            or application.payload_sha256 != _payload_digest(report)
        ):
            raise ReportMismatch(
                "Yarım keşif yazımının kaydı geçersiz; yeni yazma durduruldu"
            )
        current = _digest(catalog_path.read_bytes())
        if current == application.catalog_after:
            state = "unchanged" if application.catalog_before == current else "applied"
        elif current == application.catalog_before:
            state = "not_applied"
        else:
            raise ReportMismatch(
                "Yarım keşif yazımı belirsiz; katalog beklenen iki parmak "
                "izinden farklı"
            )
        recovered = report.model_copy(
            update={"application": application.model_copy(update={"state": state})}
        )
        _atomic_report(Path(saved["report_path"]), recovered)
        journal.unlink()


def _persist(catalog_path, config_path, report_path, report, updated):
    application = report.application
    with FileLock(str(catalog_path) + ".lock", timeout=30):
        if (
            _digest(catalog_path.read_bytes()) != application.catalog_before
            or _digest(config_path.read_bytes()) != application.config_sha256
        ):
            raise ReportMismatch(
                "Katalog veya keşif ayarları önizlemeden sonra değişmiş; "
                "hiçbir şey yazılmadı"
            )
        prepared = report.model_copy(
            update={"application": application.model_copy(update={"state": "prepared"})}
        )
        _atomic_report(report_path, prepared)
        journal = _journal_path(catalog_path)
        _atomic_json(
            journal,
            {
                "report_path": str(report_path.resolve()),
                "report": prepared.model_dump(mode="json"),
            },
        )
        if (
            _digest(catalog_path.read_bytes()) != application.catalog_before
            or _digest(config_path.read_bytes()) != application.config_sha256
        ):
            raise ReportMismatch(
                "Hazırlık sırasında katalog/ayar değişmiş; katalog yazılmadı"
            )
        changed = application.catalog_before != application.catalog_after
        if changed:
            _atomic_catalog(catalog_path, updated)
        if _digest(catalog_path.read_bytes()) != application.catalog_after:
            raise DiscoveryWriteError(
                "Katalog yazma sonucu beklenen parmak iziyle uyuşmuyor; "
                "kayıt korunuyor, yeni yazma durdurulmalı"
            )
        final = report.model_copy(
            update={
                "application": application.model_copy(
                    update={"state": "applied" if changed else "unchanged"}
                )
            }
        )
        try:
            _atomic_report(report_path, final)
            journal.unlink()
        except OSError as exc:
            raise DiscoveryWriteError(
                "Katalog yazma aşaması tamamlandı; sonuç raporu tamamlanamadı. "
                "Katalog değişmiş olabilir; sonraki başlangıç kaydı uzlaştıracak."
            ) from exc
    return final


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
    settings = Settings()
    try:
        _recover_pending(catalog_path)
        raw = catalog_path.read_bytes()
        catalog = Catalog.model_validate_json(raw.decode("utf-8-sig"))
        config_raw = settings.discovery_path.read_bytes()
        config = DiscoveryConfig.model_validate_json(config_raw.decode("utf-8-sig"))
        application = report.application
        if application is None:
            merged = merge_catalog(
                catalog,
                _report_candidates(report.results),
                config.retired_listing_bindings,
            )
            if merged[1] or merged[2]:
                raise ReportMismatch(
                    "Eski raporda yeni eklemeyi destekleyen kimlik kanıtı yok; "
                    "yeni önizleme gerekli"
                )
            return merged[1:]
        if (
            application.state != "preview"
            or application.payload_sha256 != _payload_digest(report)
        ):
            raise ReportMismatch(
                "Rapor önizlemeden sonra değişmiş; kanıt/ekleme parmak izi uyuşmuyor"
            )
        if (
            application.catalog_path != str(catalog_path.resolve())
            or _digest(config_raw) != application.config_sha256
            or _digest(raw)
            not in {application.catalog_before, application.catalog_after}
        ):
            raise ReportMismatch(
                "Katalog veya keşif ayarları önizlemeden sonra değişmiş"
            )
        guarded = _guard_results(report.results, config)
        updated, products, listings, existing, conflicts = merge_catalog(
            catalog, _report_candidates(guarded), config.retired_listing_bindings
        )
        if not set(products).issubset(report.added_products) or not set(
            listings
        ).issubset(report.added_listings):
            raise ReportMismatch(
                "Katalog önizlemeden sonra değişmiş; beklenmeyen ekleme"
            )
        after = (
            _digest(_json_bytes(updated.model_dump(mode="json")))
            if updated != catalog
            else _digest(raw)
        )
        if after != application.catalog_after:
            raise ReportMismatch(
                "Önizlemenin beklenen katalog sonucu yeniden üretilemiyor"
            )
        if listings:
            actual = report.model_copy(
                update={
                    "dry_run": False,
                    "added_products": products,
                    "added_listings": listings,
                    "existing_listings": existing,
                }
            )
            actual = actual.model_copy(
                update={
                    "application": application.model_copy(
                        update={
                            "catalog_before": _digest(raw),
                        }
                    )
                }
            )
            actual = _seal_report(actual)
            path = (
                settings.discovery_report_dir
                / f"kabul_{utc_now():%Y%m%d_%H%M%S_%f}.json"
            )
            _persist(catalog_path, settings.discovery_path, path, actual, updated)
        return products, listings, existing, conflicts
    except Timeout as exc:
        raise DiscoveryWriteError(
            "Katalog kilidi alınamadı; hiçbir şey yazılmadı"
        ) from exc


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
    if report.application is not None:
        counts = Counter(
            d.status for result in report.results for d in result.decisions
        )
        parts.append(
            f"kimlik doğrulandı {counts['verified']}, uyuşmazlık {counts['mismatch']}, "
            f"kanıt yetersiz {counts['insufficient']}"
        )
        parts.append(f"yazma {report.application.state}")
    return "Özet: " + " · ".join(parts)


def run(*, dry_run=False, target_key=None, adapters=None, report_path=None):
    settings = Settings()
    try:
        _recover_pending(settings.catalog_path)
    except (OSError, ValueError, KeyError, Timeout) as exc:
        raise DiscoveryWriteError(str(exc)) from exc
    config_raw = settings.discovery_path.read_bytes()
    config = DiscoveryConfig.model_validate_json(config_raw.decode("utf-8-sig"))
    config_sha = _digest(config_raw)
    catalog_path = settings.catalog_path
    # utf-8-sig: Windows düzenleyicilerinin koyduğu BOM da okunur; BOM'suz dosya aynı.
    catalog_raw = catalog_path.read_bytes()
    catalog = Catalog.model_validate_json(catalog_raw.decode("utf-8-sig"))
    catalog_sha = _digest(catalog_raw)
    merge_catalog(catalog, [], config.retired_listing_bindings)
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
    try:
        return _conclude(
            catalog,
            catalog_path,
            targets,
            results,
            dry_run,
            report_path,
            config,
            settings.discovery_path,
            config_sha,
            catalog_sha,
        )
    except (OSError, ValueError, Timeout) as exc:
        # Tarama bitti; yazılamayan şey sonucudur. Çağıran taraf bunu "keşif
        # başlatılamadı" (ayar/katalog okunamadı) hatasından ayırır.
        raise DiscoveryWriteError(str(exc)) from exc


def _conclude(
    catalog,
    catalog_path,
    targets,
    results,
    dry_run,
    report_path,
    config,
    config_path,
    config_sha,
    catalog_sha,
):
    """Tarama sonuçlarını kataloğa birleştirir (dry-run değilse) ve raporu yazar."""
    results = _guard_results(results, config)
    candidates = _report_candidates(results)
    updated, products, listings, existing, conflicts = merge_catalog(
        catalog, candidates, config.retired_listing_bindings
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
            if issue.reason not in {"candidate_rejected", "identity_mismatch"}
        ],
        rejected=[
            issue
            for result in results
            for issue in result.issues
            if issue.reason in {"candidate_rejected", "identity_mismatch"}
        ]
        + conflicts,
        coverage_changes={
            platform.key: sum(
                item.platform == platform.key and item.listing_id in listings
                for item in updated.listings
            )
            for platform in catalog.platforms
        },
        observed_colors=observed_colors(candidates),
    )
    report_path = report_path if report_path is not None else DEFAULT_REPORT_PATH
    if (
        _digest(catalog_path.read_bytes()) != catalog_sha
        or _digest(config_path.read_bytes()) != config_sha
    ):
        raise ReportMismatch(
            "Katalog veya keşif ayarları tarama sırasında değişmiş; "
            "yeni önizleme gerekli"
        )
    application = DiscoveryApplication(
        state="preview" if dry_run else "prepared",
        catalog_path=str(catalog_path.resolve()),
        catalog_before=catalog_sha,
        catalog_after=(
            _digest(_json_bytes(updated.model_dump(mode="json")))
            if updated != catalog
            else catalog_sha
        ),
        config_sha256=config_sha,
        payload_sha256="0" * 64,
    )
    report = report.model_copy(update={"application": application})
    report = _seal_report(report)
    if dry_run:
        _atomic_report(report_path, report)
        return report
    return _persist(catalog_path, config_path, report_path, report, updated)
