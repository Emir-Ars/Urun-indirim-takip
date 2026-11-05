"""Gölge mod: dondurulan modelle kendi serimiz için değişmeyen tahmin kaydı.

Ağsız ve veritabanısızdır: veri görüntüsünden girdileri bellekte hesaplar, ön
kayıtlı SHA-256'sı doğrulanmış modelle olasılık üretir ve yeni bir klasöre
yazar. Olasılık ekranda gösterilmez. Bir (ürün, gün) için kayıt bir kez yazılır
ve sonradan değişmez; kayıtlı gün yeniden tahmin edilmez.
"""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from pathlib import Path

from filelock import FileLock
from pydantic import Field

from app.contracts import Contract
from app.ml.experiment import load_experiment_inputs
from app.ml.features import FeatureValues, feature_rows
from app.ml.final import LoadedModel, load_frozen_model
from app.ml.models import design_matrix, library_versions, predict_frozen
from app.ml.reporting import json_bytes
from app.ml.series import ISTANBUL, build_series
from app.ml.splitting import final_samples

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "shadow.json"
RECORD_PREFIX = "tahmin_"
OUTPUT_FILES = ("predictions.jsonl", "report.md")

HISTORY_REASON = "history_below_30"
MISSING_REASON = "recent_missing_over_30_percent"
FAMILY_REASON = "family_not_in_training"
REASON_TITLES = {
    HISTORY_REASON: "Geçmişi 30 günden az (olasılık verilmez)",
    MISSING_REASON: "Son 14 günde eksik gün %30'dan fazla",
    FAMILY_REASON: "Ailesi eğitim diliminde yok",
}

SHADOW_RULES = {
    "version": 1,
    "source": "own",
    "minimum_history_days": 30,
    "recent_window_days": 14,
    "maximum_recent_missing_percent": 30,
    "recorded_after_days": "snapshot_istanbul_date_minus_anchor_day",
    "reasons": sorted(REASON_TITLES),
    "showable": "no_reason",
}
ROW_FIELDS = {
    "product_id",
    "product_key",
    "source",
    "anchor_day",
    "anchor_at",
    "recorded_after_days",
    "features",
    "missing_days_14",
    "reasons",
    "showable",
    "probabilities",
}


class ShadowEvidence(Contract):
    labels: str = Field(min_length=1)
    features: str = Field(min_length=1)
    split: str = Field(min_length=1)
    model: str = Field(min_length=1)


class ShadowConfig(Contract):
    start_day: date
    model_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence: ShadowEvidence
    records_dir: str = Field(min_length=1)


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


def resolve_path(text):
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def load_config(path=None):
    return ShadowConfig.model_validate_json(Path(path or CONFIG_PATH).read_bytes())


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


def _summarize(rows):
    days = {}
    for row in rows:
        entry = days.setdefault(
            row["anchor_day"],
            dict(day=row["anchor_day"], rows=0, predicted=0, showable=0),
        )
        entry["rows"] += 1
        entry["predicted"] += row["probabilities"] is not None
        entry["showable"] += row["showable"]
    return dict(
        rows=len(rows),
        predicted=sum(row["probabilities"] is not None for row in rows),
        showable=sum(row["showable"] for row in rows),
        on_time=sum(row["recorded_after_days"] == 1 for row in rows),
        late=sum(row["recorded_after_days"] > 1 for row in rows),
        reasons=dict(
            sorted(Counter(reason for row in rows for reason in row["reasons"]).items())
        ),
        first_anchor_day=min((row["anchor_day"] for row in rows), default=None),
        last_anchor_day=max((row["anchor_day"] for row in rows), default=None),
        per_day=[days[day] for day in sorted(days)],
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


def _check_row(row, choice):
    if not isinstance(row, dict) or set(row) != ROW_FIELDS or row["source"] != "own":
        raise ValueError("Gölge tahmin satırının alanları sözleşmeye uymuyor")
    reasons = row["reasons"]
    if (
        not isinstance(reasons, list)
        or reasons != sorted(set(reasons))
        or any(reason not in REASON_TITLES for reason in reasons)
        or row["showable"] is not (not reasons)
    ):
        raise ValueError("Gölge tahmin satırının gerekçeleri tutarsız")
    after = row["recorded_after_days"]
    missing = row["missing_days_14"]
    if (
        type(after) is not int
        or after < 1
        or type(missing) is not int
        or not 0 <= missing <= SHADOW_RULES["recent_window_days"]
    ):
        raise ValueError("Gölge tahmin satırının gün sayıları tutarsız")
    FeatureValues.model_validate_json(json_bytes(row["features"]))
    probabilities = row["probabilities"]
    if HISTORY_REASON in reasons:
        valid = probabilities is None
    else:
        valid = (
            isinstance(probabilities, dict)
            and set(probabilities) == {"r0", choice}
            and all(
                type(value) is float and 0 <= value <= 1
                for value in probabilities.values()
            )
        )
    if not valid:
        raise ValueError("Gölge tahmin olasılıkları geçerli değil")
    date.fromisoformat(row["anchor_day"])


def read_shadow_outputs(directory):
    """Kayıt klasörünü doğrular; manifest ve satırları döndürür."""
    manifest = json.loads((directory / "manifest.json").read_bytes())
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if (
        not isinstance(manifest, dict)
        or manifest.get("format_version") != 1
        or manifest.get("status") != "complete"
        or manifest.get("kind") != "shadow_predictions"
        or manifest.get("shadow_rules") != SHADOW_RULES
        or not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("model_manifest_sha256")))
        or not isinstance(manifest.get("choice"), str)
        or not isinstance(files, dict)
        or set(files) != set(OUTPUT_FILES)
    ):
        raise ValueError("Gölge tahmin manifesti sözleşmeye uymuyor")
    for name in OUTPUT_FILES:
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if digest != files[name]:
            raise ValueError(f"Gölge tahmin dosyasının parmak izi tutmuyor: {name}")
    rows = [
        json.loads(line)
        for line in (directory / "predictions.jsonl").read_bytes().splitlines()
    ]
    previous = None
    for row in rows:
        _check_row(row, manifest["choice"])
        key = (row["product_id"], row["anchor_day"])
        if previous is not None and key <= previous:
            raise ValueError("Gölge tahmin satırları sıralı ve tekil olmalı")
        previous = key
    summary = manifest.get("summary")
    skipped = summary.get("skipped_recorded") if isinstance(summary, dict) else None
    if (
        type(skipped) is not int
        or skipped < 0
        or summary != dict(_summarize(rows), skipped_recorded=skipped)
    ):
        raise ValueError("Gölge tahmin özeti satırlarla uyuşmuyor")
    return manifest, rows


def recorded_keys(records_dir, model_manifest_sha256):
    """Resmi kayıt klasörlerindeki (ürün, gün) anahtarları.

    Manifestsiz yarım klasör kayıt sayılmaz. Bozuk, başka modelden üretilmiş
    veya aynı anahtarı iki klasörde taşıyan kayıt sessizce geçilmez; hata verir.
    """
    records_dir = Path(records_dir)
    keys = {}
    if not records_dir.is_dir():
        return set()
    for folder in sorted(records_dir.glob(f"{RECORD_PREFIX}*")):
        if not (folder / "manifest.json").is_file():
            continue
        manifest, rows = read_shadow_outputs(folder)
        if manifest["model_manifest_sha256"] != model_manifest_sha256:
            raise ValueError(f"Kayıt başka bir modelle üretilmiş: {folder.name}")
        for row in rows:
            key = (row["product_id"], date.fromisoformat(row["anchor_day"]))
            if key in keys:
                raise ValueError(
                    f"Aynı gün iki kayıt klasöründe: {keys[key]}, {folder.name}"
                )
            keys[key] = folder.name
    return set(keys)
