"""Yalnız hazırlanmış Docker kopyasında mevcut gösterim kapısını yönetir."""

import re
from pathlib import Path

from app.contracts import utc_now
from app.delivery import bundle
from app.ml import shadow_display as display, shadow_records as records
from app.ml.series import ISTANBUL

CONTROL_FILES = {display.APPROVAL_FILE, "gosterim_onayi.lock"}


def evaluation_path(manifest, name, root):
    if not re.fullmatch(r"degerlendirme_[a-zA-Z0-9_]+", name):
        raise bundle.DeliveryError("Paketteki değerlendirme klasörünün adı gerekli.")
    relative = f"{bundle.SHADOW}/{name}"
    if f"{relative}/manifest.json" not in manifest.files:
        raise bundle.DeliveryError("Değerlendirme bu teslim paketinde bulunmuyor.")
    return bundle.safe_path(root, relative).resolve()


def validate_control(manifest, root):
    root = Path(root)
    approval = display._read_approval(root / bundle.SHADOW / display.APPROVAL_FILE)
    if approval is None:
        return
    from app.ml.shadow_evaluation import load_evaluation_model

    config = records.load_config(root / "config/shadow.json")
    directory = Path(approval.evaluation_dir)
    expected = evaluation_path(manifest, directory.name, root)
    now = utc_now()
    if (
        not directory.is_absolute()
        or directory != expected
        or approval.model_manifest_sha256 != manifest.model_manifest_sha256
        or approval.approved_at.astimezone(ISTANBUL).date() < display.FINAL_DATE
        or not approval.approved_at <= approval.updated_at <= now
    ):
        raise bundle.DeliveryError("Gösterim onayı bu kopya veya tarihle uyuşmuyor.")
    display._sealed_report(approval, config)
    model = load_evaluation_model(bundle.relocated_config(root, config))
    if approval.choice != model.choice or approval.training_families != tuple(
        sorted(model.families)
    ):
        raise bundle.DeliveryError("Gösterim onayı ön kayıtlı modelle uyuşmuyor.")


def set_delivery_display(package, evaluation=None, disable=False):
    from app.delivery.prepare import check_files, prepare_target

    manifest, digest = bundle.verify_bundle(package)
    prepare_target(package, "check", verified=(manifest, digest))
    root = bundle.ROOT
    directory = None if disable else evaluation_path(manifest, evaluation, root)
    config = records.load_config(root / "config/shadow.json")
    try:
        enabled = display.set_display(config, directory, disable)
    except ValueError:
        raise bundle.DeliveryError(
            "Gösterim koşulları doğrulanamadı; onay değiştirilmedi."
        ) from None
    check_files(manifest)
    return dict(bundle_sha256=digest, enabled=enabled, official_files_unchanged=True)
