"""Gösterim testleri için gerçek veri kökünden bağımsız yapay dosyalar."""

import hashlib
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.ml import shadow_records as records
from app.ml.dataset import write_snapshot
from app.ml.features import feature_rows
from app.ml.reporting import json_bytes
from app.ml.series import build_series
from app.ml.shadow_display import APPROVAL_FILE, DisplayApproval
from tests.support.ml import label_snapshot, label_tables, write_shadow_config

NOW = datetime(2027, 1, 5, 12, tzinfo=timezone.utc)


def write_json(path, value):
    path.write_bytes(json_bytes(value) + b"\n")


def seal_files(directory, manifest):
    manifest["files"] = {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in manifest["files"]
    }
    write_json(directory / "manifest.json", manifest)
    return hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()


def display_case(root, *, prices=None, short=False, unseen=False):
    tables = label_tables(count=369, prices=prices)
    if short:
        cutoff = NOW.date() - timedelta(days=20)
        tables["collection_runs"] = [
            row
            for row in tables["collection_runs"]
            if row["started_at"].date() >= cutoff
        ]
        runs = {row["run_id"] for row in tables["collection_runs"]}
        tables["listing_checks"] = [
            row for row in tables["listing_checks"] if row["run_id"] in runs
        ]
        tables["market_history"] = [
            row for row in tables["market_history"] if row["day"] >= cutoff
        ]
    snapshot = label_snapshot(tables)
    record_root = root / "records"
    digest = write_snapshot(snapshot, record_root / "goruntuler" / "veri_01")
    config_path = write_shadow_config(
        root / "shadow.json",
        {key: "unused" for key in ("labels", "features", "split", "model")},
        record_root,
        sha="a" * 64,
    )
    # Bu testin modeli yok; ayar yalnız salt okunur sunum sözleşmesini temsil eder.
    import json

    data = json.loads(config_path.read_bytes())
    data["evidence"] = {
        key: "unused" for key in ("labels", "features", "split", "model")
    }
    write_json(config_path, data)
    config = records.load_config(config_path)
    day, series = build_series(snapshot)
    product = snapshot.products[0]
    own = next(item for item in series if item.source == "own")
    feature = next(
        item for item in feature_rows(own, product) if item.metadata.anchor_day == day
    )
    missing = sum(
        own.days.get(day - timedelta(days=back), {}).get("reference_price") is None
        for back in range(14)
    )
    reasons = []
    if feature.features.history_days < 30:
        reasons.append(records.HISTORY_REASON)
    if 100 * missing > 30 * 14:
        reasons.append(records.MISSING_REASON)
    if unseen:
        reasons.append(records.FAMILY_REASON)
    row = dict(
        product_id=product.product_id,
        product_key=product.product_key,
        source="own",
        anchor_day=day.isoformat(),
        anchor_at=feature.metadata.model_dump(mode="json")["anchor_at"],
        recorded_after_days=1,
        features=feature.features.model_dump(mode="json"),
        missing_days_14=missing,
        reasons=sorted(reasons),
        showable=not reasons,
        probabilities=None if short else {"r0": 0.5, "r2_platt": 0.37},
    )
    folder = record_root / "tahmin_01"
    folder.mkdir()
    write_json(folder / "predictions.jsonl", row)
    (folder / "report.md").write_text("Yapay kayıt\n", encoding="utf-8")
    manifest = dict(
        format_version=1,
        status="complete",
        kind="shadow_predictions",
        shadow_rules=records.SHADOW_RULES,
        choice="r2_platt",
        model_manifest_sha256=config.model_manifest_sha256,
        snapshot_sha256=digest,
        snapshot_captured_at=snapshot.captured_at.isoformat(),
        last_closed_day=day.isoformat(),
        start_day=config.start_day.isoformat(),
        summary=dict(records._summarize([row]), skipped_recorded=0),
        files={"predictions.jsonl": "", "report.md": ""},
    )
    seal_files(folder, manifest)
    report = dict(
        input=dict(
            snapshot_sha256=digest,
            snapshot_captured_at=snapshot.captured_at.isoformat(),
            last_closed_day=day.isoformat(),
            start_day=config.start_day.isoformat(),
            model_manifest_sha256=config.model_manifest_sha256,
            choice="r2_platt",
        ),
        final_date_matches=True,
        gate=dict(status="met"),
        opens_display=False,
        model_trained=False,
        predictions_generated=False,
    )
    evaluation = record_root / "degerlendirme_test"
    evaluation.mkdir()
    write_json(evaluation / "report.json", report)
    (evaluation / "report.md").write_text("Yapay onaylı rapor\n", encoding="utf-8")
    (evaluation / "evaluations.jsonl").write_bytes(b"")
    evaluation_sha = seal_files(
        evaluation,
        dict(
            format_version=1,
            kind="shadow_evaluation",
            status="complete",
            input=report["input"],
            files={"report.json": "", "report.md": "", "evaluations.jsonl": ""},
        ),
    )
    approval = DisplayApproval(
        format_version=1,
        enabled=True,
        model_manifest_sha256=config.model_manifest_sha256,
        evaluation_dir=str(evaluation.resolve()),
        evaluation_manifest_sha256=evaluation_sha,
        choice="r2_platt",
        training_families=("unseen",) if unseen else (feature.features.family,),
        approved_at=NOW,
        updated_at=NOW,
    )
    (record_root / APPROVAL_FILE).write_text(
        approval.model_dump_json(), encoding="utf-8"
    )
    return SimpleNamespace(
        config=config,
        path=config_path,
        root=record_root,
        snapshot=snapshot,
        row=row,
        manifest=manifest,
        folder=folder,
        product=product,
        approval=approval,
        evaluation=evaluation,
    )
