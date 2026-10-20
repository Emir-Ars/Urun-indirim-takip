"""Gerçek kimlik kusurları, otomatik kabul ve yarım katalog yazımı regresyonları."""

import codecs
import json
from copy import deepcopy
from html import escape
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from app.contracts import (
    Catalog,
    DiscoveryConfig,
    DiscoveryEvidence,
    DiscoveryFact,
    DiscoveryReport,
    DiscoveryResult,
    DiscoveryTarget,
    Listing,
    Platform,
    Product,
    RetiredListingBinding,
    utc_now,
)
from app.discovery import service
from app.discovery.__main__ import main
from app.discovery.acceptance import decide, hepsiburada_evidence, trendyol_evidence
from app.discovery.base import BaseDiscovery

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = json.loads(
    (Path(__file__).parent / "fixtures/discovery/acceptance_examples.json").read_text(
        "utf-8"
    )
)
TARGET = DiscoveryTarget(key="apple_iphone_15", brand="Apple", model="iPhone 15")


def page_html(page, platform):
    scripts = [
        f'<script type="application/ld+json">{json.dumps(p)}</script>'
        for p in page["jsonld"]
    ]
    if platform == "trendyol":
        state = {"product": page["product"]}
        scripts.append(
            f"<script>window['__envoy__SHARED_PROPS'] = {json.dumps(state)};</script>"
        )
    else:
        state = {
            "productState": {"product": page["details"][0] if page["details"] else {}},
            "recommendations": page["details"][1:],
            "allVariantCombinations": page["variants"],
        }
        scripts.append(f'<script type="application/json">{json.dumps(state)}</script>')
        scripts.append(f'<h1>{escape(page["heading"])}</h1>')
    return "\n".join(scripts)


def extract(sample, page=None):
    platform = sample["evidence"]["platform"]
    html = page_html(page or sample["page"], platform)
    soup = BeautifulSoup(html, "html.parser")
    fn = trendyol_evidence if platform == "trendyol" else hepsiburada_evidence
    return fn(
        soup, html, sample["evidence"]["url"], sample["evidence"]["platform_product_id"]
    )


@pytest.mark.parametrize(
    "sample", SAMPLES, ids=lambda s: s["evidence"]["platform_product_id"]
)
def test_recorded_acceptance_decisions(sample):
    target = DiscoveryTarget.model_validate_json(json.dumps(sample["target"]))
    saved = DiscoveryEvidence.model_validate_json(json.dumps(sample["evidence"]))
    assert decide(saved, target).status == sample["expected_status"]
    assert len(sample["source_sha256"]) == 64
    if "page" in sample:
        actual = decide(extract(sample), target)
        assert actual.status == sample["expected_status"]
        assert actual.reasons == decide(saved, target).reasons


def hb_sample():
    return next(
        s for s in SAMPLES if s["evidence"]["platform_product_id"] == "HBCV00007A36P9"
    )


def ty_sample():
    return next(
        s for s in SAMPLES if s["evidence"]["platform_product_id"] == "859623143"
    )


def decision_for(sample, page):
    target = DiscoveryTarget.model_validate_json(json.dumps(sample["target"]))
    return decide(extract(sample, page), target)


def test_network_and_condition_cannot_come_from_another_sku():
    sample = hb_sample()
    page = deepcopy(sample["page"])
    other = deepcopy(page["details"][0])
    other["sku"] = "HBCVOTHER"
    other["properties"] = [{"name": "Mobil Bağlantı Hızı", "property": "4G"}]
    page["details"].append(other)
    assert decision_for(sample, page).status == "verified"
    for product in page["jsonld"]:
        product["sku"] = "HBCVOTHER"
    result = decision_for(sample, page)
    assert result.status == "insufficient" and "new_condition_missing" in result.reasons


def test_recommendation_is_not_the_current_product_context():
    sample = hb_sample()
    page = deepcopy(sample["page"])
    own = page["details"][0]
    html = (
        f'<h1>{escape(page["heading"])}</h1>'
        + '<script type="application/json">'
        + json.dumps(
            {"recommendations": [own], "allVariantCombinations": page["variants"]}
        )
        + "</script>"
        + "".join(
            f'<script type="application/ld+json">{json.dumps(p)}</script>'
            for p in page["jsonld"]
        )
    )
    evidence = hepsiburada_evidence(
        BeautifulSoup(html, "html.parser"),
        html,
        sample["evidence"]["url"],
        sample["evidence"]["platform_product_id"],
    )
    target = DiscoveryTarget.model_validate_json(json.dumps(sample["target"]))
    assert "source_identity_missing" in decide(evidence, target).reasons


def test_recorded_4g_page_requires_positive_own_network_property():
    sample = next(
        s for s in SAMPLES if s["evidence"]["platform_product_id"] == "HBCV00005PZUWE"
    )
    page = deepcopy(sample["page"])
    page["details"][0]["properties"] = [
        {"name": "Mobil Bağlantı Hızı", "property": "4.5G"}
    ]
    assert decision_for(sample, page).status == "verified"
    page["details"][0]["properties"][0]["property"] = "5G"
    assert "network_mismatch" in decision_for(sample, page).reasons


def test_explicit_own_5g_title_is_positive_evidence_when_property_is_missing():
    sample = hb_sample()
    page = deepcopy(sample["page"])
    for detail in page["details"]:
        detail.pop("expends", None)
        detail.pop("properties", None)
    assert decision_for(sample, page).status == "verified"


def test_zero_price_and_out_of_stock_metadata_do_not_decide_identity():
    sample = ty_sample()
    page = deepcopy(sample["page"])
    page["product"]["inStock"] = False
    for product in page["jsonld"]:
        product["offers"][0].update(price=0, availability="https://schema.org/InStock")
    assert decision_for(sample, page).status == "verified"


def test_selected_color_survives_generic_webcolor_in_real_adapter(monkeypatch):
    from app.discovery.trendyol import Discovery
    from app.settings import Runtime

    sample = ty_sample()
    page = deepcopy(sample["page"])
    for attr in page["product"]["attributes"]:
        if attr.get("key", {}).get("name") == "Renk":
            attr["value"]["name"] = "Çok Renkli"
    html = page_html(page, "trendyol")
    target = DiscoveryTarget.model_validate_json(json.dumps(sample["target"]))
    discovery = Discovery(target, DiscoveryConfig(targets=[target]), Runtime())
    monkeypatch.setattr(discovery, "get", lambda _: html)
    try:
        candidate = discovery._candidate(sample["evidence"]["url"], "859623143")
        assert candidate.color == "Mavi" and discovery.decisions[0].status == "verified"
    finally:
        discovery.close()


def test_product_group_cannot_borrow_new_condition_from_has_variant():
    sample = ty_sample()
    page = deepcopy(sample["page"])
    product = page["jsonld"][0]
    product["@type"] = "ProductGroup"
    product["hasVariant"] = [
        {"@type": "Product", "sku": "999", "offers": product.pop("offers")}
    ]
    result = decision_for(sample, page)
    assert result.status == "insufficient" and "new_condition_missing" in result.reasons
    product["offers"] = product["hasVariant"][0]["offers"]
    assert decision_for(sample, page).status == "verified"


def test_offer_url_must_belong_to_its_product():
    sample = ty_sample()
    page = deepcopy(sample["page"])
    for product in page["jsonld"]:
        for offer in product["offers"]:
            offer["url"] = "https://www.trendyol.com/other-p-999"
    assert "new_condition_missing" in decision_for(sample, page).reasons


@pytest.mark.parametrize(
    "condition",
    ["https://schema.org/UsedCondition", "https://schema.org/RefurbishedCondition"],
)
def test_non_new_condition_overrides_normal_category(condition):
    sample = ty_sample()
    page = deepcopy(sample["page"])
    page["jsonld"][0]["offers"][0]["itemCondition"] = condition
    result = decision_for(sample, page)
    assert result.status == "mismatch" and "condition_mismatch" in result.reasons


def test_warranty_and_missing_network_do_not_prove_new_or_4g():
    sample = next(
        s for s in SAMPLES if s["evidence"]["platform_product_id"] == "HBCV00005PZUWE"
    )
    result = decide(
        DiscoveryEvidence.model_validate_json(json.dumps(sample["evidence"])),
        DiscoveryTarget.model_validate_json(json.dumps(sample["target"])),
    )
    assert result.status == "insufficient" and "network_missing" in result.reasons
    sample = ty_sample()
    page = deepcopy(sample["page"])
    page["jsonld"][0].pop("offers")
    assert "new_condition_missing" in decision_for(sample, page).reasons


def test_recorded_storage_conflict_is_not_hidden_to_keep_old_acceptance_count():
    sample = next(
        s for s in SAMPLES if s["evidence"]["platform_product_id"] == "HBCV0000E8DHJL"
    )
    assert sample["previous_status"] == "verified"
    assert decision_for(sample, sample["page"]).reasons == ["storage_mismatch"]


def proof(pid="100", capacity=128, color="Siyah", platform="trendyol", **changes):
    url = f"https://www.{platform}.com/telefon-p-{pid}"
    values = {
        "source_id": pid,
        "name": f"Apple iPhone 15 {capacity} GB",
        "brand": "Apple",
        "category": "Cep Telefonu",
        "color": color,
        "condition": "https://schema.org/NewCondition",
    }
    values.update(changes)
    evidence = DiscoveryEvidence(
        platform=platform,
        platform_product_id=pid,
        url=url,
        captured_at=utc_now(),
        html_sha256="0" * 64,
        facts=[
            DiscoveryFact(field=k, value=v, owner_id=pid, source="synthetic_test")
            for k, v in values.items()
            if v is not None
        ],
    )
    return decide(evidence, TARGET)


@pytest.mark.parametrize(
    ("field", "value", "status", "reason"),
    [
        ("color", None, "insufficient", "color_missing"),
        ("color", "Çok Renkli", "insufficient", "color_missing"),
        ("category", "Yenilenmiş Cep Telefonu", "mismatch", "category_mismatch"),
        ("brand", "Samsung", "mismatch", "brand_mismatch"),
        ("name", "Apple iPhone 15 Pro 128 GB", "mismatch", "model_mismatch"),
        ("name", "Apple iPhone 15 128 GB Yenilio A Kalite", "mismatch", "out_of_scope"),
        ("condition", None, "insufficient", "new_condition_missing"),
        ("source_id", "999", "mismatch", "source_id_mismatch"),
    ],
)
def test_missing_and_conflicting_fields(field, value, status, reason):
    result = proof(**{field: value})
    assert result.status == status and reason in result.reasons


def test_color_alias_and_optional_ram_are_not_false_conflicts():
    original = proof(color="Blue")
    facts = [
        *original.evidence.facts,
        DiscoveryFact(
            field="color", value="Mavi", owner_id="100", source="jsonld.color"
        ),
    ]
    decision = decide(original.evidence.model_copy(update={"facts": facts}), TARGET)
    assert decision.status == "verified" and decision.candidate.ram_gb is None


@pytest.fixture
def environment(tmp_path, monkeypatch):
    catalog = Catalog(
        platforms=[
            Platform(key=p, name=p, hosts=[f"www.{p}.com"])
            for p in ["trendyol", "hepsiburada"]
        ],
        products=[
            Product(
                product_id=1,
                product_key="apple_iphone_15_128gb",
                brand="Apple",
                model="iPhone 15",
                storage_gb=128,
            )
        ],
        listings=[],
    )
    path = tmp_path / "catalog.json"
    path.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    (tmp_path / "discovery.json").write_text(
        DiscoveryConfig(targets=[TARGET]).model_dump_json(), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    for key, value in {
        "CATALOG_PATH": path,
        "DISCOVERY_PATH": tmp_path / "discovery.json",
        "RUNTIME_PATH": ROOT / "config/runtime.json",
        "SCRAPE_LOCK_PATH": tmp_path / "scrape.lock",
    }.items():
        monkeypatch.setenv(key, str(value))
    return path


def adapters(*decisions, callback=None):
    def adapter(platform):
        class Fixed(BaseDiscovery):
            hosts = [f"www.{platform}.com"]

            def discover(self):
                if callback:
                    callback()
                found = [d for d in decisions if d.evidence.platform == platform]
                return DiscoveryResult(
                    platform=platform,
                    target_key=self.target.key,
                    decisions=found,
                    candidates=[d.candidate for d in found if d.candidate],
                    complete=True,
                )

        Fixed.platform = platform
        return Fixed

    return {p: adapter(p) for p in ["trendyol", "hepsiburada"]}


def test_auto_accept_creates_only_proven_products_and_preserves_snapshot(environment):
    before = Catalog.model_validate_json(environment.read_bytes())
    valid, missing = proof("101", 256), proof("102", 512, condition=None)
    report = service.run(adapters=adapters(valid, missing))
    after = Catalog.model_validate_json(environment.read_bytes())
    assert report.added_products == ["apple_iphone_15_256gb"]
    assert report.added_listings == ["trendyol_101"]
    assert after.products[:1] == before.products
    assert len(after.products) == 2 and after.products[-1].product_id == 2
    assert report.application.state == "applied"
    written = environment.read_bytes()
    again = service.run(adapters=adapters(valid, missing))
    assert again.application.state == "unchanged" and not again.added_listings
    assert environment.read_bytes() == written


def test_unproven_legacy_adapter_cannot_bypass_gate(environment):
    candidate = proof().candidate
    fake = adapters()

    class Legacy(fake["trendyol"]):
        def discover(self):
            return DiscoveryResult(
                platform="trendyol",
                target_key=TARGET.key,
                candidates=[candidate],
                complete=True,
            )

    fake["trendyol"] = Legacy
    before = environment.read_bytes()
    report = service.run(adapters=fake)
    assert not report.added_listings and not report.complete
    assert any(i.reason == "evidence_missing" for i in report.pending)
    assert environment.read_bytes() == before


def test_conflicting_group_never_gets_first_sorted_candidate(environment):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    candidates = [proof("100", capacity).candidate for capacity in [128, 256]]
    for order in [candidates, list(reversed(candidates))]:
        updated, products, listings, _, conflicts = service.merge_catalog(
            catalog, order
        )
        assert updated == catalog and products == [] and listings == []
        assert len(conflicts) == 2


def test_optional_ram_is_missing_information_but_explicit_ram_conflict_is_rejected(
    environment,
):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    candidate = proof().candidate
    updated, _, listings, _, conflicts = service.merge_catalog(
        catalog, [candidate, candidate.model_copy(update={"ram_gb": 8})]
    )
    assert listings == ["trendyol_100"] and not conflicts
    updated, _, listings, _, conflicts = service.merge_catalog(
        catalog,
        [
            candidate.model_copy(update={"ram_gb": 12}),
            candidate.model_copy(update={"ram_gb": 8}),
        ],
    )
    assert updated == catalog and not listings and len(conflicts) == 2


def binding():
    return RetiredListingBinding(
        platform="trendyol",
        platform_product_id="100",
        listing_id="trendyol_legacy",
        product_id=1,
        product_key="apple_iphone_15_128gb",
    )


def test_retired_identity_can_return_only_to_its_original_product(environment):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    same, _, listings, _, conflicts = service.merge_catalog(
        catalog, [proof().candidate], [binding()]
    )
    assert listings == ["trendyol_legacy"] and not conflicts
    assert same.listings[-1].product_id == 1
    wrong, products, listings, _, conflicts = service.merge_catalog(
        catalog, [proof(capacity=256).candidate], [binding()]
    )
    assert wrong == catalog and not products and not listings and len(conflicts) == 1


def test_coverage_counts_platform_for_a_reserved_id_without_platform_prefix(
    environment,
):
    reserved = binding().model_copy(update={"listing_id": "retired_apple_phone"})
    config = DiscoveryConfig(targets=[TARGET], retired_listing_bindings=[reserved])
    Path("discovery.json").write_text(config.model_dump_json(), encoding="utf-8")
    report = service.run(adapters=adapters(proof()))
    assert report.added_listings == ["retired_apple_phone"]
    assert report.coverage_changes == {"trendyol": 1, "hepsiburada": 0}


@pytest.mark.parametrize("kind", ["listing", "product", "platform"])
def test_inactive_records_are_preserved(environment, kind):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    if kind == "listing":
        catalog = catalog.model_copy(
            update={
                "listings": [
                    Listing(
                        listing_id="old",
                        product_id=1,
                        platform="trendyol",
                        url=proof().candidate.url,
                        active=False,
                    )
                ]
            }
        )
    elif kind == "product":
        catalog = catalog.model_copy(
            update={
                "products": [catalog.products[0].model_copy(update={"active": False})]
            }
        )
    else:
        catalog = catalog.model_copy(
            update={
                "platforms": [
                    p.model_copy(update={"active": False}) for p in catalog.platforms
                ]
            }
        )
    updated, products, listings, *_ = service.merge_catalog(
        catalog, [proof().candidate]
    )
    assert updated == catalog and not products and not listings


def test_partial_search_does_not_block_own_page_evidence(environment):
    fake = adapters(proof())
    base = fake["trendyol"]

    class Partial(base):
        def discover(self):
            return super().discover().model_copy(update={"complete": False})

    fake["trendyol"] = Partial
    report = service.run(adapters=fake)
    assert not report.complete and report.added_listings == ["trendyol_100"]


def test_preview_config_and_payload_changes_are_rejected(environment):
    report = service.run(dry_run=True, adapters=adapters(proof()))
    before = environment.read_bytes()
    for changed in [
        report.model_copy(update={"added_listings": []}),
        report.model_copy(
            update={
                "application": report.application.model_copy(
                    update={"catalog_after": "f" * 64}
                )
            }
        ),
    ]:
        with pytest.raises(service.ReportMismatch):
            service.apply_report(changed, environment)
    path = Path("discovery.json")
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(service.ReportMismatch, match="ayarları"):
        service.apply_report(report, environment)
    assert environment.read_bytes() == before


def test_forged_decision_is_recomputed_even_with_a_fresh_payload_hash(environment):
    report = service.run(dry_run=True, adapters=adapters(proof()))
    result = next(r for r in report.results if r.decisions)
    changed = result.decisions[0].model_copy(update={"status": "insufficient"})
    bad = report.model_copy(
        update={
            "results": [
                r.model_copy(update={"decisions": [changed]}) if r == result else r
                for r in report.results
            ]
        }
    )
    bad = service._seal_report(bad)
    before = environment.read_bytes()
    with pytest.raises(service.ReportMismatch, match="yeniden üretilemiyor"):
        service.apply_report(bad, environment)
    assert environment.read_bytes() == before


def test_old_report_cannot_make_new_additions_but_can_be_read(environment):
    report = service.run(dry_run=True, adapters=adapters(proof()))
    legacy = report.model_copy(update={"application": None})
    assert (
        DiscoveryReport.model_validate_json(legacy.model_dump_json()).application
        is None
    )
    with pytest.raises(service.ReportMismatch, match="Eski rapor"):
        service.apply_report(legacy, environment)
    service.apply_report(report, environment)
    assert service.apply_report(legacy, environment)[1] == []


@pytest.mark.parametrize("failure", ["prepared_report", "catalog", "final_report"])
def test_write_failure_is_recoverable_without_replaying_old_candidates(
    environment, monkeypatch, failure
):
    before = environment.read_bytes()
    original = service._atomic_report
    calls = 0

    def report_write(path, report):
        nonlocal calls
        calls += 1
        if (failure == "prepared_report" and calls == 1) or (
            failure == "final_report" and calls == 2
        ):
            raise OSError("disk full")
        original(path, report)

    with monkeypatch.context() as patch:
        patch.setattr(service, "_atomic_report", report_write)
        if failure == "catalog":

            def catalog_write(*_):
                raise OSError("catalog full")

            patch.setattr(service, "_atomic_catalog", catalog_write)
        with pytest.raises(service.DiscoveryWriteError):
            service.run(adapters=adapters(proof()))
    journal = service._journal_path(environment)
    assert journal.exists() == (failure != "prepared_report")
    assert (environment.read_bytes() != before) == (failure == "final_report")
    if journal.exists():
        service._recover_pending(environment)
        report = DiscoveryReport.model_validate_json(
            Path("data/discovery_report.json").read_bytes()
        )
        assert report.application.state == (
            "applied" if failure == "final_report" else "not_applied"
        )
        assert not journal.exists()
    assert len(Catalog.model_validate_json(environment.read_bytes()).listings) == (
        1 if failure == "final_report" else 0
    )


def test_uncertain_pending_catalog_stops_before_scanning(environment, monkeypatch):
    original = service._atomic_report

    def fail_final(path, report):
        if report.application.state == "applied":
            raise OSError("disk full")
        original(path, report)

    with monkeypatch.context() as patch:
        patch.setattr(service, "_atomic_report", fail_final)
        with pytest.raises(service.DiscoveryWriteError):
            service.run(adapters=adapters(proof()))
    environment.write_bytes(environment.read_bytes() + b"\n")

    def must_not_scan():
        pytest.fail("belirsiz yazım varken site taranmamalı")

    with pytest.raises(service.DiscoveryWriteError, match="belirsiz"):
        service.run(adapters=adapters(callback=must_not_scan))


def test_interrupt_after_atomic_replace_keeps_a_recoverable_intent(
    environment, monkeypatch
):
    original = service._atomic_catalog

    def interrupt(path, catalog):
        original(path, catalog)
        raise KeyboardInterrupt

    with monkeypatch.context() as patch:
        patch.setattr(service, "_atomic_catalog", interrupt)
        with pytest.raises(KeyboardInterrupt):
            service.run(adapters=adapters(proof()))
    assert service._journal_path(environment).exists()
    service._recover_pending(environment)
    report = DiscoveryReport.model_validate_json(
        Path("data/discovery_report.json").read_bytes()
    )
    assert (
        report.application.state == "applied"
        and not service._journal_path(environment).exists()
    )


def test_bad_reservation_does_not_create_an_orphan_product(environment):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    with pytest.raises(ValueError, match="eski ürün"):
        service.merge_catalog(
            catalog,
            [proof(capacity=256).candidate],
            [binding().model_copy(update={"product_id": 999})],
        )


def test_foreign_reuse_of_a_reserved_listing_id_is_rejected(environment):
    catalog = Catalog.model_validate_json(environment.read_bytes())
    catalog = catalog.model_copy(
        update={
            "listings": [
                Listing(
                    listing_id="trendyol_legacy",
                    product_id=1,
                    platform="trendyol",
                    url="https://www.trendyol.com/another-p-999",
                )
            ]
        }
    )
    with pytest.raises(ValueError, match="kimliği katalogla"):
        service.merge_catalog(catalog, [proof().candidate], [binding()])


def test_catalog_or_config_edit_during_scan_is_not_overwritten(environment):
    before = environment.read_bytes()

    def edit():
        p = Path("discovery.json")
        p.write_bytes(p.read_bytes() + b"\n")

    with pytest.raises(service.DiscoveryWriteError, match="tarama sırasında"):
        service.run(adapters=adapters(proof(), callback=edit))
    assert environment.read_bytes() == before


def test_edit_between_prepared_report_and_catalog_replace_is_not_overwritten(
    environment, monkeypatch
):
    original = service._atomic_json

    def edit_after_prepare(path, value):
        original(path, value)
        if path.name.startswith("pending_"):
            environment.write_bytes(environment.read_bytes() + b"\n")

    monkeypatch.setattr(service, "_atomic_json", edit_after_prepare)
    before = environment.read_bytes()
    with pytest.raises(service.DiscoveryWriteError, match="katalog yazılmadı"):
        service.run(adapters=adapters(proof()))
    assert environment.read_bytes() == before + b"\n"


def test_scheduled_auto_accept_records_real_write_result(environment, monkeypatch):
    fake = adapters(proof())
    monkeypatch.setattr(service, "_adapter", lambda p: fake[p])
    assert main(["--scheduled", "--auto-accept"]) == 0
    report = DiscoveryReport.model_validate_json(
        next(Path("data/discovery").glob("kesif_*.json")).read_bytes()
    )
    assert report.application.state == "applied" and report.added_listings == [
        "trendyol_100"
    ]
    assert len(Catalog.model_validate_json(environment.read_bytes()).listings) == 1


def test_auto_accept_respects_the_existing_shared_scrape_lock(environment):
    from app.scrape_lock import scrape_lock

    before = environment.read_bytes()
    with scrape_lock(Path("scrape.lock")):
        assert main(["--scheduled", "--auto-accept"]) == 3
    assert environment.read_bytes() == before


@pytest.mark.parametrize(
    "args",
    [
        ["--auto-accept", "--dry-run"],
        ["--scheduled"],
        ["--apply-report", "report.json", "--auto-accept"],
    ],
)
def test_cli_rejects_incompatible_modes(environment, args):
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2


def test_scheduled_installer_supports_reversible_opt_in_and_bom():
    raw = (ROOT / "scripts/kesif_zamanlayici_kur.ps1").read_bytes()
    assert raw.startswith(codecs.BOM_UTF8)
    text = raw.decode("utf-8-sig")
    assert "[switch]$OtomatikKabul" in text
    assert "-m app.discovery --scheduled --dry-run" in text
    assert "-m app.discovery --scheduled --auto-accept" in text
    assert "-DaysOfWeek Sunday -At '14:00'" in text


def test_configuration_reservations_reject_duplicates():
    with pytest.raises(ValueError, match="benzersiz"):
        DiscoveryConfig(targets=[], retired_listing_bindings=[binding(), binding()])
