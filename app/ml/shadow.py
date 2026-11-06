"""Gölge mod: dondurulan modelle kendi serimiz için değişmeyen tahmin kaydı.

Ağsız ve veritabanısızdır: veri görüntüsünden girdileri bellekte hesaplar, ön
kayıtlı SHA-256'sı doğrulanmış modelle olasılık üretir ve yeni bir klasöre
yazar. Olasılık ekranda gösterilmez. Bir (ürün, gün) için kayıt bir kez yazılır
ve sonradan değişmez; kayıtlı gün yeniden tahmin edilmez.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from pathlib import Path

from filelock import FileLock

from app.ml.experiment import load_experiment_inputs
from app.ml.features import feature_rows
from app.ml.final import LoadedModel, load_frozen_model
from app.ml.models import design_matrix, library_versions, predict_frozen
from app.ml.reporting import json_bytes
from app.ml.series import ISTANBUL, build_series
from app.ml.splitting import final_samples

from app.ml.shadow_records import (
    CONFIG_PATH as CONFIG_PATH,
    ROOT as ROOT,
    RECORD_PREFIX as RECORD_PREFIX,
    OUTPUT_FILES as OUTPUT_FILES,
    HISTORY_REASON as HISTORY_REASON,
    MISSING_REASON as MISSING_REASON,
    FAMILY_REASON as FAMILY_REASON,
    REASON_TITLES as REASON_TITLES,
    SHADOW_RULES as SHADOW_RULES,
    ROW_FIELDS as ROW_FIELDS,
    ShadowEvidence as ShadowEvidence,
    ShadowConfig as ShadowConfig,
    resolve_path as resolve_path,
    load_config as load_config,
    _summarize as _summarize,
    _check_row as _check_row,
    read_shadow_outputs as read_shadow_outputs,
    recorded_keys as recorded_keys,
)

__all__ = [
    "CONFIG_PATH",
    "ROOT",
    "OUTPUT_FILES",
    "ROW_FIELDS",
    "ShadowEvidence",
    "ShadowConfig",
    "load_config",
    "_check_row",
    "read_shadow_outputs",
    "recorded_keys",
]


@dataclass(frozen=True)
class ShadowModel:
    loaded: LoadedModel
    training_families: frozenset


@dataclass(frozen=True)
class ShadowResult:
    rows: list
    skipped_recorded: int
    snapshot_sha256: str
    captured_at: str
    last_closed_day: date


def load_model(config):
    """Modeli yalnız ön kayıtlı SHA-256 ve kanıt zinciri doğrulanırsa açar."""
    evidence = config.evidence
    inputs = load_experiment_inputs(
        resolve_path(evidence.labels),
        resolve_path(evidence.features),
        resolve_path(evidence.split),
    )
    loaded = load_frozen_model(
        resolve_path(evidence.model), inputs, config.model_manifest_sha256
    )
    families = frozenset(
        features.family
        for _, features in final_samples(inputs.split, inputs.plan, "train")
    )
    return ShadowModel(loaded, families)


def is_official(directory, records_dir):
    """Yalnız kayıt okuyucusunun taradığı doğrudan alt klasörler resmidir."""
    directory = Path(directory).resolve()
    records_dir = Path(records_dir).resolve()
    return directory.parent == records_dir and directory.name.startswith(RECORD_PREFIX)


def record_lock(records_dir):
    """Anahtar okuma ve yazma birlikte kilitlenir; iki süreç aynı günü yazamaz."""
    records_dir = Path(records_dir).resolve()
    records_dir.mkdir(parents=True, exist_ok=True)
    return FileLock(str(records_dir / "tahmin.lock"), timeout=0)


def _utc_text(value):
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _recent_missing_days(series, day):
    count = 0
    for back in range(SHADOW_RULES["recent_window_days"]):
        entry = series.days.get(day - timedelta(days=back))
        if entry is None or entry["reference_price"] is None:
            count += 1
    return count


def build_shadow_predictions(snapshot, snapshot_sha256, model, start_day, recorded):
    """Kayıtsız her kendi başlangıcı için tek satır; kısa geçmişte olasılıksız."""
    closed_day, series_list = build_series(snapshot)
    products = {product.product_id: product for product in snapshot.products}
    captured_day = snapshot.captured_at.astimezone(ISTANBUL).date()
    pending, skipped = [], 0
    for series in series_list:
        if series.source != "own":
            continue
        for feature_row in feature_rows(series, products[series.product_id]):
            meta = feature_row.metadata
            if meta.anchor_day < start_day:
                continue
            if (meta.product_id, meta.anchor_day) in recorded:
                skipped += 1
                continue
            pending.append((series, feature_row))
    pending.sort(
        key=lambda item: (item[1].metadata.product_id, item[1].metadata.anchor_day)
    )
    rows = []
    for series, feature_row in pending:
        meta, features = feature_row.metadata, feature_row.features
        missing = _recent_missing_days(series, meta.anchor_day)
        reasons = []
        if features.history_days < SHADOW_RULES["minimum_history_days"]:
            reasons.append(HISTORY_REASON)
        if 100 * missing > (
            SHADOW_RULES["maximum_recent_missing_percent"]
            * SHADOW_RULES["recent_window_days"]
        ):
            reasons.append(MISSING_REASON)
        if features.family not in model.training_families:
            reasons.append(FAMILY_REASON)
        rows.append(
            dict(
                product_id=meta.product_id,
                product_key=meta.product_key,
                source="own",
                anchor_day=meta.anchor_day.isoformat(),
                anchor_at=_utc_text(meta.anchor_at),
                recorded_after_days=(captured_day - meta.anchor_day).days,
                features=features.model_dump(mode="json"),
                missing_days_14=missing,
                reasons=sorted(reasons),
                showable=not reasons,
                probabilities=None,
            )
        )
    predictable = [
        index for index, row in enumerate(rows) if HISTORY_REASON not in row["reasons"]
    ]
    if predictable:
        matrix = design_matrix([pending[index][1].features for index in predictable])
        predicted = predict_frozen(model.loaded.frozen, matrix)
        for position, index in enumerate(predictable):
            rows[index]["probabilities"] = {
                name: float(values[position]) for name, values in predicted.items()
            }
    return ShadowResult(
        rows,
        skipped,
        snapshot_sha256,
        _utc_text(snapshot.captured_at),
        closed_day,
    )


def shadow_markdown_report(manifest):
    summary = manifest["summary"]
    lines = [
        "# Gölge mod tahmin kaydı",
        "",
        f"Veri görüntüsü: {manifest['snapshot_captured_at']} (UTC) · "
        f"SHA-256 {manifest['snapshot_sha256']}",
        f"Son kapanmış gün: {manifest['last_closed_day']} · "
        f"başlangıç günü: {manifest['start_day']}",
        f"Model: {manifest['choice']} (manifest SHA-256 "
        f"{manifest['model_manifest_sha256']})",
        "",
        "Bu olasılıklar ekranda gösterilmez. Her kayıt, başlangıç gününün "
        "22:00 turuna kadar bilinen girdilerle üretilmiştir ve sonradan "
        "değiştirilmez. Kapı değerlendirmesi ayrı bir adımdır; bu kayıt tek "
        "başına model başarısı kanıtı değildir.",
        "",
        "| Ölçü | Sayı |",
        "|---|---:|",
        f"| Yeni kayıt | {summary['rows']} |",
        f"| Olasılık üretilen | {summary['predicted']} |",
        f"| Gösterilebilir | {summary['showable']} |",
        f"| Daha önce kayıtlı (atlanan) | {summary['skipped_recorded']} |",
        f"| Ertesi gün kaydedilen | {summary['on_time']} |",
        f"| Geç veya geriye dönük kaydedilen | {summary['late']} |",
        "",
        "## Gösterilemeyen satırların gerekçeleri",
        "",
    ]
    if summary["reasons"]:
        lines += ["| Gerekçe | Satır |", "|---|---:|"]
        lines += [
            f"| {REASON_TITLES[reason]} | {count} |"
            for reason, count in summary["reasons"].items()
        ]
    else:
        lines.append("Gösterilemeyen satır yok.")
    lines += ["", "## Günlük dağılım", "", "| Gün | Yeni | Olasılık | Gösterilebilir |"]
    lines.append("|---|---:|---:|---:|")
    lines += [
        f"| {entry['day']} | {entry['rows']} | {entry['predicted']} | "
        f"{entry['showable']} |"
        for entry in summary["per_day"]
    ]
    lines += [
        "",
        "Kayıt yerel dosyadır; parmak izi yalnız bütünlük denetimidir, imza "
        "değildir.",
        "",
    ]
    return "\n".join(lines)


def write_shadow_outputs(directory, result, model, start_day):
    """Klasörü yazar; manifest en son oluşur. Var olan klasöre yazılmaz."""
    directory.mkdir(parents=True, exist_ok=False)
    loaded = model.loaded
    summary = dict(_summarize(result.rows), skipped_recorded=result.skipped_recorded)
    manifest = dict(
        format_version=1,
        status="complete",
        kind="shadow_predictions",
        shadow_rules=SHADOW_RULES,
        choice=loaded.frozen.choice,
        model_manifest_sha256=loaded.manifest_sha256,
        snapshot_sha256=result.snapshot_sha256,
        snapshot_captured_at=result.captured_at,
        last_closed_day=result.last_closed_day,
        start_day=start_day,
        libraries=library_versions(),
        summary=summary,
    )
    files = {
        "predictions.jsonl": b"".join(json_bytes(row) + b"\n" for row in result.rows),
        "report.md": shadow_markdown_report(json.loads(json_bytes(manifest))).encode(
            "utf-8"
        ),
    }
    for name, content in files.items():
        (directory / name).write_bytes(content)
    manifest["files"] = {
        name: hashlib.sha256(content).hexdigest() for name, content in files.items()
    }
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")
