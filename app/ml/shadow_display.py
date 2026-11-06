"""Gösterim onayı ve kayıtlı tahmin okuması; sunum yolu model yüklemez."""

import hashlib
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated, Literal

from filelock import FileLock
from pydantic import Field

from app.contracts import Contract, utc_now
from app.ml import shadow_records as records
from app.ml.dataset import SnapshotError, UtcDatetime, read_snapshot
from app.ml.features import feature_rows
from app.ml.reporting import json_bytes
from app.ml.series import ISTANBUL, build_series

FINAL_DATE = date(2027, 1, 5)
APPROVAL_FILE = "gosterim_onayi.json"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class DisplayApproval(Contract):
    format_version: Literal[1]
    enabled: bool
    model_manifest_sha256: Digest
    evaluation_dir: str = Field(min_length=1)
    evaluation_manifest_sha256: Digest
    choice: str = Field(min_length=1)
    training_families: tuple[str, ...]
    approved_at: UtcDatetime
    updated_at: UtcDatetime


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approval_path(config):
    return records.resolve_path(config.records_dir) / APPROVAL_FILE


def _read_approval(path):
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        return None
    return DisplayApproval.model_validate_json(content)


def _write_approval(path, approval):
    temporary = None
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(approval.model_dump_json().encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def source_snapshot(root, digest, preferred=None):
    """Kayıt SHA'sını görüntünün doğrulanan içeriğiyle eşleştirir."""
    candidates = [] if preferred is None else [preferred]
    candidates.extend(sorted((root / "goruntuler").glob("*/snapshot.json")))
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            envelope = json.loads(path.read_bytes())
        except FileNotFoundError:
            continue
        if not isinstance(envelope, dict) or envelope.get("sha256") != digest:
            continue
        snapshot, actual = read_snapshot(path.parent)
        if actual != digest:
            raise ValueError("Kaynak görüntünün SHA-256'sı uyuşmuyor")
        return snapshot
    raise ValueError("Kayıtla eşleşen kaynak görüntü bulunamadı")


def _report_header(report, config):
    info = report["input"]
    captured = records.parse_utc(info["snapshot_captured_at"])
    if (
        captured.astimezone(ISTANBUL).date() != FINAL_DATE
        or report["final_date_matches"] is not True
        or info["last_closed_day"] != (FINAL_DATE - timedelta(days=1)).isoformat()
        or info["start_day"] != config.start_day.isoformat()
        or info["model_manifest_sha256"] != config.model_manifest_sha256
        or report["gate"]["status"] != "met"
        or report["opens_display"] is not False
        or report["model_trained"] is not False
        or report["predictions_generated"] is not False
    ):
        raise ValueError("Kesin rapor gösterim koşullarını sağlamıyor")
    return captured


def _sealed_report(approval, config):
    directory = Path(approval.evaluation_dir)
    if _sha(directory / "manifest.json") != approval.evaluation_manifest_sha256:
        raise ValueError("Onaylı değerlendirme manifesti değişmiş")
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest["format_version"] != 1
        or manifest["kind"] != "shadow_evaluation"
        or manifest["status"] != "complete"
        or not isinstance(manifest["files"], dict)
        or set(manifest["files"]) != {"evaluations.jsonl", "report.json", "report.md"}
    ):
        raise ValueError("Onaylı değerlendirme manifesti geçersiz")
    for name, digest in manifest["files"].items():
        if _sha(directory / name) != digest:
            raise ValueError("Onaylı değerlendirme dosyası değişmiş")
    report = json.loads((directory / "report.json").read_bytes())
    _report_header(report, config)
    if (
        report["input"] != manifest["input"]
        or report["input"]["choice"] != approval.choice
    ):
        raise ValueError("Onaylı raporun model bilgisi uyuşmuyor")


def set_display(config, evaluation_dir=None, disable=False, now=None):
    """Kesin raporu doğrulayıp ayrı onay yazar; resmi kanıtları değiştirmez."""
    now = now or utc_now()
    path = _approval_path(config)
    if disable:
        if not path.parent.exists():
            return False
    else:
        if now.astimezone(ISTANBUL).date() < FINAL_DATE:
            raise ValueError("Gösterim 5 Ocak 2027 öncesinde açılamaz")
        if evaluation_dir is None:
            raise ValueError("Kesin değerlendirme klasörü gerekli")
        # Ağır değerlendirme bağımlılıkları yalnız elle açılışta kullanılır.
        from app.ml import shadow_evaluation

        directory = Path(evaluation_dir).resolve()
        digest = _sha(directory / "manifest.json")
        report, rows = shadow_evaluation.read_outputs(directory)
        captured = _report_header(report, config)
        if captured > now:
            raise ValueError("Değerlendirme zamanı gelecekte")
        model = shadow_evaluation.load_evaluation_model(config)
        if (
            report["input"]["choice"] != model.choice
            or report["input"]["reference_rate"] != model.reference_rate
        ):
            raise ValueError("Değerlendirme modeli ön kayıtla uyuşmuyor")
        main = shadow_evaluation._selections(rows)["main"][0]
        scores = shadow_evaluation._score_rows(main, "primary", model.choice)
        if json.loads(json_bytes(scores)) != report["scores"]["main"]:
            raise ValueError("Kapının puanları kayıtlı olasılıklarla uyuşmuyor")
        snapshot = source_snapshot(path.parent, report["input"]["snapshot_sha256"])
        if snapshot.captured_at != captured:
            raise ValueError("Kesin raporun kaynak zamanı uyuşmuyor")
        if _sha(directory / "manifest.json") != digest:
            raise ValueError("Doğrulama sırasında değerlendirme değişti")
        path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path.parent / "gosterim_onayi.lock"), timeout=0):
        previous = _read_approval(path)
        if disable:
            if previous is None or not previous.enabled:
                return False
            approval = previous.model_copy(update=dict(enabled=False, updated_at=now))
        else:
            if previous is not None and (
                previous.evaluation_manifest_sha256 != digest
                or previous.model_manifest_sha256 != config.model_manifest_sha256
            ):
                raise ValueError("Mevcut onay farklı raporla sessizce değiştirilemez")
            if previous is not None and previous.enabled:
                return True
            approval = DisplayApproval(
                format_version=1,
                enabled=True,
                model_manifest_sha256=config.model_manifest_sha256,
                evaluation_dir=str(directory),
                evaluation_manifest_sha256=digest,
                choice=model.choice,
                training_families=tuple(sorted(model.families)),
                approved_at=previous.approved_at if previous else now,
                updated_at=now,
            )
        _write_approval(path, approval)
    return approval.enabled


def _inventory(config, now, choice):
    root = records.resolve_path(config.records_dir)
    keys, product_keys, inventory = set(), set(), []
    for folder in sorted(root.glob(f"{records.RECORD_PREFIX}*")):
        if not folder.is_dir():
            continue
        try:
            (folder / "manifest.json").stat()
        except FileNotFoundError:
            continue
        manifest, rows = records.read_shadow_outputs(folder)
        captured = records.parse_utc(manifest["snapshot_captured_at"])
        closed = captured.astimezone(ISTANBUL).date() - timedelta(days=1)
        if (
            manifest["model_manifest_sha256"] != config.model_manifest_sha256
            or manifest["choice"] != choice
            or manifest["last_closed_day"] != closed.isoformat()
            or manifest["start_day"] != config.start_day.isoformat()
            or captured > now
            or not re.fullmatch(r"[0-9a-f]{64}", manifest["snapshot_sha256"])
        ):
            raise ValueError("Resmi kaydın model veya zaman bilgisi uyuşmuyor")
        for row in rows:
            day = date.fromisoformat(row["anchor_day"])
            key = row["product_id"], day
            product_key = row["product_key"], day
            if (
                key in keys
                or product_key in product_keys
                or not config.start_day <= day <= closed
            ):
                raise ValueError("Resmi kayıt anahtarı tekrarlı veya tarih dışı")
            if row["recorded_after_days"] != (closed + timedelta(days=1) - day).days:
                raise ValueError("Resmi kaydın gecikme bilgisi uyuşmuyor")
            keys.add(key)
            product_keys.add(product_key)
            inventory.append((folder, manifest, row))
    return inventory


def prediction_for(product, config=None, now=None):
    """Yalnız İstanbul'da dün başlayan kayıt sunulur; eski güne dönülmez."""
    config = config or records.load_config()
    now = now or utc_now()

    def response(state, reasons=(), forecast=None):
        return dict(state=state, reasons=reasons, forecast=forecast, generated_at=now)

    approval = _read_approval(_approval_path(config))
    if approval is None or not approval.enabled:
        return response("closed", ("display_closed",))
    if (
        now.astimezone(ISTANBUL).date() < FINAL_DATE
        or approval.approved_at > now
        or approval.model_manifest_sha256 != config.model_manifest_sha256
    ):
        return response("closed", ("display_not_approved",))
    _sealed_report(approval, config)
    day = now.astimezone(ISTANBUL).date() - timedelta(days=1)
    inventory = _inventory(config, now, approval.choice)
    match = [
        item
        for item in inventory
        if item[2]["product_id"] == product.product_id
        and item[2]["anchor_day"] == day.isoformat()
    ]
    if not match:
        return response("unavailable", ("expected_daily_record_missing",))
    folder, manifest, row = match[0]
    if row["product_key"] != product.product_key:
        raise ValueError("Resmi kayıt ürün kimliği uyuşmuyor")
    root = records.resolve_path(config.records_dir)
    preferred = root / "goruntuler" / folder.name.replace("tahmin_", "veri_", 1)
    snapshot = source_snapshot(
        root, manifest["snapshot_sha256"], preferred / "snapshot.json"
    )
    if snapshot.captured_at != records.parse_utc(manifest["snapshot_captured_at"]):
        raise ValueError("Kaynak görüntü zamanı uyuşmuyor")
    source_product = next(
        (item for item in snapshot.products if item.product_id == product.product_id),
        None,
    )
    if source_product is None or source_product.product_key != product.product_key:
        raise ValueError("Kaynak görüntü ürün kimliği uyuşmuyor")
    _, series = build_series(snapshot)
    own = next(
        item
        for item in series
        if item.source == "own" and item.product_id == product.product_id
    )
    feature = next(
        (
            item
            for item in feature_rows(own, source_product)
            if item.metadata.anchor_day == day
        ),
        None,
    )
    if (
        feature is None
        or row["anchor_at"] != feature.metadata.model_dump(mode="json")["anchor_at"]
        or row["features"] != feature.features.model_dump(mode="json")
    ):
        raise ValueError("Kayıt girdileri kaynak görüntüyle uyuşmuyor")
    missing = sum(
        own.days.get(day - timedelta(days=back), {}).get("reference_price") is None
        for back in range(14)
    )
    reasons = []
    if feature.features.history_days < 30:
        reasons.append(records.HISTORY_REASON)
    if 100 * missing > 30 * 14:
        reasons.append(records.MISSING_REASON)
    if feature.features.family not in approval.training_families:
        reasons.append(records.FAMILY_REASON)
    if row["reasons"] != sorted(reasons) or row["missing_days_14"] != missing:
        raise ValueError("Kayıt yeterliliği kaynak görüntüyle uyuşmuyor")
    if reasons:
        return response("insufficient_data", tuple(sorted(reasons)))
    anchor = own.days[day]
    return response(
        "available",
        forecast=dict(
            probability=row["probabilities"][approval.choice],
            model_name=approval.choice,
            anchor_day=day,
            anchor_at=anchor["anchor_at"],
            reference_price_kurus=anchor["reference_price"],
            target_start=day + timedelta(days=1),
            target_end=day + timedelta(days=7),
            recorded_at=records.parse_utc(manifest["snapshot_captured_at"]),
            listing_count=len(anchor["scope"]),
        ),
    )


READ_ERRORS = (OSError, ValueError, TypeError, KeyError, StopIteration, SnapshotError)
