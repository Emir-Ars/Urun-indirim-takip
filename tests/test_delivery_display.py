"""Teslim bakımında aynı kesin kapı, kopya sınırı ve değişmeyen kanıtlar."""

import json
import pickle
import shutil
from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.contracts import Product
from app.delivery import bundle, display, prepare
from app.delivery.__main__ import main
from app.delivery.state import DeliveryState, load_state
from app.ml import shadow_display, shadow_records
from tests.support.delivery import add_final_evaluation, write_bundle, write_source
from tests.support.shadow_display import NOW


def state_data(**updates):
    data = dict(
        format_version=1,
        status="complete",
        bundle_sha256="a" * 64,
        code_sha256="b" * 64,
        code_commit="c" * 40,
        database="delivery_test",
        captured_at="2026-11-09T13:55:00Z",
        prepared_at="2026-11-09T14:00:00Z",
        display_enabled=False,
    )
    data.update(updates)
    return data


def test_state_preserves_utc_and_rejects_bad_metadata(tmp_path):
    path = tmp_path / "ready.json"
    path.write_text(json.dumps(state_data()), encoding="utf-8")
    assert load_state(path).captured_at.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "field,value",
    [
        ("bundle_sha256", "bad"),
        ("status", "partial"),
        ("display_enabled", True),
        ("database", "other"),
        ("prepared_at", "2026-11-08T12:00:00Z"),
        ("captured_at", "2026-11-09T16:55:00+03:00"),
        ("captured_at", "2026-11-09T13:55:00"),
    ],
)
def test_invalid_state_is_not_a_trusted_banner(field, value):
    data = state_data()
    data[field] = value
    with pytest.raises(ValueError):
        DeliveryState.model_validate_json(json.dumps(data))


@pytest.fixture(scope="module")
def final_source(tmp_path_factory):
    source = write_source(tmp_path_factory.mktemp("delivery_display"))
    add_final_evaluation(source)
    return source


@pytest.fixture
def case(tmp_path, final_source, monkeypatch):
    from app.delivery.database import SCHEMA_SHA256, TABLES
    from app.database.migrate import load

    proof = bundle.DatabaseProof(
        name="delivery_test",
        server_version=170011,
        schema_sha256=SCHEMA_SHA256,
        migrations={m.file_name: m.checksum for m in load()},
        tables={name: dict(rows=0, sha256="0" * 64) for name in TABLES},
        sequence_value=1,
        sequence_called=False,
    )
    package = tmp_path / "package"
    manifest, digest = write_bundle(final_source, package, proof)
    root = tmp_path / "installed"
    shutil.copytree(package / "config", root / "config")
    shutil.copytree(package / bundle.SHADOW, root / bundle.SHADOW)
    calls = []

    def check(package, mode, *, verified=None):
        assert mode == "check" and verified == (manifest, digest)
        calls.append(mode)

    monkeypatch.setattr(prepare, "prepare_target", check)
    monkeypatch.setattr(bundle, "verify_bundle", lambda *a: (manifest, digest))
    monkeypatch.setattr(bundle, "ROOT", root)
    monkeypatch.setattr(shadow_records, "ROOT", root)
    monkeypatch.setattr(display, "utc_now", lambda: NOW)
    monkeypatch.setattr(shadow_display, "utc_now", lambda: NOW)
    return SimpleNamespace(
        root=root, package=package, manifest=manifest, digest=digest, calls=calls
    )


def test_maintenance_opens_reads_current_and_closes_without_mutating_official_files(
    case, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Gösterim bakımı pickle yükleyemez")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    before = {
        name: bundle.sha(case.root / name)
        for name in case.manifest.files
        if name != "database.dump"
    }
    result = display.set_delivery_display(case.package, "degerlendirme_final")
    assert result["enabled"] is True and result["official_files_unchanged"]
    path = case.root / bundle.SHADOW / shadow_display.APPROVAL_FILE
    approval = shadow_display.DisplayApproval.model_validate_json(path.read_bytes())
    assert approval.evaluation_dir == str(
        (case.root / bundle.SHADOW / "degerlendirme_final").resolve()
    )
    config = shadow_records.load_config(case.root / "config/shadow.json")
    data = json.loads((case.root / "config/catalog.json").read_bytes())
    product = Product.model_validate(data["products"][0])
    current = shadow_display.prediction_for(product, config, NOW)
    assert current["state"] == "available" and current["forecast"] is not None
    stale = shadow_display.prediction_for(product, config, NOW + timedelta(days=1))
    assert stale["state"] == "unavailable" and stale["forecast"] is None
    assert display.set_delivery_display(case.package, disable=True)["enabled"] is False
    assert shadow_display.prediction_for(product, config, NOW)["forecast"] is None
    prepare.check_files(case.manifest)
    assert all(
        bundle.sha(case.root / name) == digest for name, digest in before.items()
    )
    assert case.calls == ["check", "check"]


def test_early_open_and_foreign_report_never_create_approval(case, monkeypatch):
    monkeypatch.setattr(shadow_display, "utc_now", lambda: NOW - timedelta(days=1))
    with pytest.raises(bundle.DeliveryError):
        display.set_delivery_display(case.package, "degerlendirme_final")
    for name in ("../degerlendirme_final", "degerlendirme_other", "C:/report"):
        with pytest.raises(bundle.DeliveryError):
            display.set_delivery_display(case.package, name)
    assert not (case.root / bundle.SHADOW / shadow_display.APPROVAL_FILE).exists()


@pytest.mark.parametrize(
    "tamper", ["foreign_path", "future", "model", "families", "malformed"]
)
def test_approval_is_verified_separately_from_official_inventory(case, tamper):
    display.set_delivery_display(case.package, "degerlendirme_final")
    path = case.root / bundle.SHADOW / shadow_display.APPROVAL_FILE
    data = json.loads(path.read_bytes())
    if tamper == "malformed":
        path.write_bytes(b"broken")
    else:
        if tamper == "foreign_path":
            data["evaluation_dir"] = str(
                case.package / bundle.SHADOW / "degerlendirme_final"
            )
        elif tamper == "future":
            data["updated_at"] = (NOW + timedelta(days=1)).isoformat()
        elif tamper == "model":
            data["model_manifest_sha256"] = "0" * 64
        else:
            data["training_families"] = ["unknown"]
        path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises((ValueError, bundle.DeliveryError)):
        prepare.check_files(case.manifest)


def test_failed_copy_preflight_prevents_any_approval_write(case, monkeypatch):
    def fail(*args, **kwargs):
        raise bundle.DeliveryError("Kopya uyuşmuyor")

    monkeypatch.setattr(prepare, "prepare_target", fail)
    monkeypatch.setattr(
        shadow_display, "set_display", lambda *a: pytest.fail("Onay yazılmamalı")
    )
    with pytest.raises(bundle.DeliveryError):
        display.set_delivery_display(case.package, disable=True)


def test_delivery_cli_requires_one_explicit_display_action():
    with pytest.raises(SystemExit) as error:
        main(["shadow-display", "--bundle", "unused"])
    assert error.value.code == 2
