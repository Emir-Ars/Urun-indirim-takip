"""Resmi gölge kayıtlarının ortak, model bağımlılığı olmayan okuyucusu."""

import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from pydantic import Field, TypeAdapter

from app.contracts import Contract, Key
from app.ml.features import FeatureValues
from app.ml.reporting import json_bytes

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


def resolve_path(text):
    path = Path(text)
    return path if path.is_absolute() else ROOT / path


def load_config(path=None):
    return ShadowConfig.model_validate_json(Path(path or CONFIG_PATH).read_bytes())


def parse_utc(value):
    if not isinstance(value, str):
        raise ValueError("Kayıt zamanı metin olmalı")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Kayıt zamanı UTC olmalı")
    return parsed


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


def _check_row(row, choice):
    if not isinstance(row, dict) or set(row) != ROW_FIELDS or row["source"] != "own":
        raise ValueError("Gölge tahmin satırının alanları sözleşmeye uymuyor")
    if type(row["product_id"]) is not int or row["product_id"] < 1:
        raise ValueError("Gölge tahmin ürün kimliği geçersiz")
    TypeAdapter(Key).validate_python(row["product_key"], strict=True)
    parse_utc(row["anchor_at"])
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
