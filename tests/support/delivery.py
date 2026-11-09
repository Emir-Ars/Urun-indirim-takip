"""Gerçek dosyalardan bağımsız, tam kanıt zincirli teslim örneği."""

import json
import shutil
from datetime import datetime, timezone

from app.delivery import bundle
from app.delivery.export import copy_assets
from app.ml import shadow_records
from app.ml.reporting import json_bytes
from tests.support.ml import write_evaluation_evidence


def write_source(root):
    from app.ml.__main__ import main

    evidence = write_evaluation_evidence(root / "training")
    evaluation = evidence["records"] / "degerlendirme_01"
    assert (
        main(
            [
                "shadow-evaluate",
                "--snapshot",
                str(evidence["source"]),
                "--config",
                str(evidence["config"]),
                "--output-dir",
                str(evaluation),
            ]
        )
        == 0
    )
    source = root / "source"
    config = source / "config"
    config.mkdir(parents=True)
    catalog = dict(
        platforms=[
            dict(
                key="hepsiburada",
                name="Hepsiburada",
                hosts=["www.hepsiburada.com"],
                active=True,
            )
        ],
        products=[
            dict(
                product_id=1,
                product_key="apple_iphone_15_128gb",
                brand="Apple",
                model="iPhone 15",
                storage_gb=128,
                active=True,
            )
        ],
        listings=[
            dict(
                listing_id="hepsiburada_a",
                product_id=1,
                platform="hepsiburada",
                url="https://www.hepsiburada.com/test",
                color="Siyah",
                active=True,
            )
        ],
    )
    for name, data in (
        ("catalog.json", catalog),
        ("discovery.json", {"targets": []}),
        ("runtime.json", {}),
        ("market_history.json", {"version": 1, "source": "cimri", "entries": []}),
    ):
        (config / name).write_bytes(json_bytes(data))
    golge = source / bundle.SHADOW
    for kind in ("labels", "features", "split", "model"):
        shutil.copytree(evidence[kind], golge / "kanitlar" / kind)
    shutil.copytree(evidence["record"], golge / "tahmin_01")
    shutil.copytree(evaluation, golge / "degerlendirme_01")
    shutil.copytree(evidence["source"], golge / "goruntuler" / "veri_test")
    data = shadow_records.load_config(evidence["config"]).model_dump(mode="json")
    data["records_dir"] = bundle.SHADOW
    data["evidence"] = {
        key: f"{bundle.SHADOW}/kanitlar/{key}"
        for key in ("labels", "features", "split", "model")
    }
    (config / "shadow.json").write_bytes(json_bytes(data))
    return source


def write_bundle(source, destination, proof):
    reference = source / "config/shadow.json"
    copy_assets(source, destination, reference)
    dump = destination / "database.dump"
    if not dump.exists():
        dump.write_bytes(b"PGDMPsynthetic")
    _, config = bundle.validate_assets(destination, reference)
    manifest = bundle.BundleManifest(
        format_version=1,
        kind="delivery_bundle",
        status="complete",
        created_at=datetime(2026, 11, 9, 12, tzinfo=timezone.utc),
        code_commit="a" * 40,
        source_dirty=True,
        code_sha256=bundle.code_sha256(reference),
        model_manifest_sha256=config.model_manifest_sha256,
        database=proof,
        files={
            name: bundle.sha(destination / name)
            for name in sorted(bundle.inventory(destination))
        },
    )
    # UTC alanı JSON üzerinden katı sözleşmeye çevrilir.
    (destination / "manifest.json").write_bytes(
        json_bytes(json.loads(manifest.model_dump_json())) + b"\n"
    )
    return bundle.verify_bundle(destination, reference)
