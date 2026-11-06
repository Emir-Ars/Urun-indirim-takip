"""Kayıt → API → istemci: güncellik, gizlilik ve güvenli hata sözleşmesi."""

import json
import shutil
import subprocess
import sys
from datetime import timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.api.schemas import PredictionResponse
from app.database import read
from app.ml import shadow_display as display
from app.ui.api_client import ApiClient, ApiClientError, _validate_target
from tests.support.shadow_display import NOW, display_case, seal_files, write_json


@pytest.fixture
def case(tmp_path):
    return display_case(tmp_path)


def test_available_uses_original_evening_price_time_scope_and_period(case):
    result = PredictionResponse.model_validate(
        display.prediction_for(case.product, case.config, NOW)
    )
    assert result.state == "available"
    assert result.forecast.probability == 0.37
    assert result.forecast.reference_price_kurus == 10000
    assert result.forecast.anchor_at.hour == 19
    assert result.forecast.anchor_at.minute == 30
    assert result.forecast.anchor_day.isoformat() == "2027-01-04"
    assert result.forecast.target_start.isoformat() == "2027-01-05"
    assert result.forecast.target_end.isoformat() == "2027-01-11"
    assert result.forecast.listing_count == 1


@pytest.mark.parametrize("mode", ["absent", "disabled", "before_final", "other_model"])
def test_closed_never_returns_probability_or_reads_records(case, mode, monkeypatch):
    path = case.root / display.APPROVAL_FILE
    now = NOW
    if mode == "absent":
        path.unlink()
    elif mode == "before_final":
        now -= timedelta(days=1)
    else:
        updates = (
            dict(enabled=False)
            if mode == "disabled"
            else dict(model_manifest_sha256="b" * 64)
        )
        path.write_text(
            case.approval.model_copy(update=updates).model_dump_json(), encoding="utf-8"
        )
    monkeypatch.setattr(
        display,
        "_inventory",
        lambda *args: pytest.fail("Kapalı gösterimde kayıt okundu"),
    )
    result = display.prediction_for(case.product, case.config, now)
    assert result["state"] == "closed" and result["forecast"] is None
    assert "probability" not in json.dumps(result, default=str)


@pytest.mark.parametrize("delta", [timedelta(days=1), timedelta(hours=9)])
def test_istanbul_midnight_discards_old_probability_without_fallback(case, delta):
    # 12 UTC + 9 saat = İstanbul'da ertesi gün 00.00.
    result = display.prediction_for(case.product, case.config, NOW + delta)
    assert result["state"] == "unavailable"
    assert result["forecast"] is None
    assert result["reasons"] == ("expected_daily_record_missing",)


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("short", "history_below_30"),
        ("missing", "recent_missing_over_30_percent"),
        ("unseen", "family_not_in_training"),
    ],
)
def test_existing_eligibility_rules_hide_probabilities(tmp_path, kind, reason):
    options = (
        {kind: True}
        if kind != "missing"
        else {"prices": [10000] * 363 + [None] * 5 + [10000]}
    )
    case = display_case(tmp_path, **options)
    result = PredictionResponse.model_validate(
        display.prediction_for(case.product, case.config, NOW)
    )
    assert result.state == "insufficient_data"
    assert reason in result.reasons and result.forecast is None


def test_new_daily_record_becomes_available_after_old_probability_disappears(case):
    from app.ml.dataset import write_snapshot
    from app.ml.features import feature_rows
    from app.ml.series import build_series
    from app.ml.shadow_records import _summarize
    from tests.support.ml import label_snapshot

    now = NOW + timedelta(days=1)
    assert (
        display.prediction_for(case.product, case.config, now)["state"] == "unavailable"
    )
    snapshot = label_snapshot(count=370, prices=[10000] * 369 + [15000])
    digest = write_snapshot(snapshot, case.root / "goruntuler" / "veri_02")
    day, series = build_series(snapshot)
    own = next(item for item in series if item.source == "own")
    feature = next(
        item
        for item in feature_rows(own, snapshot.products[0])
        if item.metadata.anchor_day == day
    )
    row = dict(
        case.row,
        anchor_day=day.isoformat(),
        anchor_at=feature.metadata.model_dump(mode="json")["anchor_at"],
        features=feature.features.model_dump(mode="json"),
        probabilities={"r0": 0.5, "r2_platt": 0.42},
    )
    folder = case.root / "tahmin_02"
    folder.mkdir()
    write_json(folder / "predictions.jsonl", row)
    (folder / "report.md").write_text("Yapay yeni günlük kayıt", encoding="utf-8")
    manifest = dict(
        case.manifest,
        snapshot_sha256=digest,
        snapshot_captured_at=snapshot.captured_at.isoformat(),
        last_closed_day=day.isoformat(),
        summary=dict(_summarize([row]), skipped_recorded=0),
    )
    seal_files(folder, manifest)
    before = {
        path: path.read_bytes() for path in case.root.rglob("*") if path.is_file()
    }
    result = PredictionResponse.model_validate(
        display.prediction_for(case.product, case.config, now)
    )
    assert result.state == "available"
    assert result.forecast.probability == 0.42
    assert result.forecast.reference_price_kurus == 15000
    assert result.forecast.anchor_day == day
    after = {path: path.read_bytes() for path in case.root.rglob("*") if path.is_file()}
    assert before == after


def test_incomplete_official_folder_is_ignored(case):
    (case.root / "tahmin_half").mkdir()
    assert (
        display.prediction_for(case.product, case.config, NOW)["state"] == "available"
    )


@pytest.mark.parametrize(
    "failure",
    [
        "hash",
        "model",
        "duplicate",
        "source_missing",
        "source_corrupt",
        "source_hash",
        "anchor",
        "features",
        "reasons",
        "key",
        "header",
        "approval",
        "evaluation",
        "io",
    ],
)
def test_broken_evidence_returns_safe_503_without_breaking_prices(
    case, stub, monkeypatch, failure
):
    _, client = stub
    if failure == "hash":
        (case.folder / "predictions.jsonl").write_bytes(b"private")
    elif failure == "model":
        case.manifest["model_manifest_sha256"] = "b" * 64
        seal_files(case.folder, case.manifest)
    elif failure == "duplicate":
        shutil.copytree(case.folder, case.root / "tahmin_duplicate")
    elif failure.startswith("source"):
        path = case.root / "goruntuler" / "veri_01" / "snapshot.json"
        if failure == "source_missing":
            path.unlink()
        else:
            content = json.loads(path.read_bytes())
            if failure == "source_hash":
                content["sha256"] = "c" * 64
            else:
                content["payload"]["products"][0]["model"] = "private"
            write_json(path, content)
    elif failure in ("anchor", "features", "reasons", "key"):
        if failure == "anchor":
            case.row["anchor_at"] = "2027-01-04T18:30:00Z"
        elif failure == "features":
            case.row["features"]["history_days"] += 1
        elif failure == "reasons":
            case.row.update(reasons=["family_not_in_training"], showable=False)
        else:
            case.row["product_key"] = "unknown"
        write_json(case.folder / "predictions.jsonl", case.row)
        from app.ml.shadow_records import _summarize

        case.manifest["summary"] = dict(_summarize([case.row]), skipped_recorded=0)
        seal_files(case.folder, case.manifest)
    elif failure == "header":
        case.manifest["last_closed_day"] = "2027-01-03"
        seal_files(case.folder, case.manifest)
    elif failure == "approval":
        (case.root / display.APPROVAL_FILE).write_bytes(b"private")
    elif failure == "evaluation":
        (case.evaluation / "report.md").write_bytes(b"private")
    else:
        monkeypatch.setattr(
            display,
            "_read_approval",
            lambda path: (_ for _ in ()).throw(PermissionError("private")),
        )
    monkeypatch.setattr(read, "read_product_identity", lambda *args: case.product)
    monkeypatch.setattr(display.records, "load_config", lambda: case.config)
    monkeypatch.setattr(display, "utc_now", lambda: NOW)
    response = client.get(f"/api/v1/products/{case.product.product_key}/prediction")
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["detail"]["code"] == "prediction_unavailable"
    assert "private" not in response.text
    assert client.get("/api/v1/products").status_code == 200
    assert client.get("/api/v1/status").status_code == 200


def test_unknown_product_returns_404_before_reading_forecast(stub, monkeypatch):
    monkeypatch.setattr(
        display,
        "prediction_for",
        lambda *args: pytest.fail("Bilinmeyen ürün için dosya okundu"),
    )
    response = stub[1].get("/api/v1/products/unknown/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "product_not_found"


def test_api_client_roundtrip_and_closed_payload(case, stub, monkeypatch):
    _, server = stub
    monkeypatch.setattr(read, "read_product_identity", lambda *args: case.product)
    monkeypatch.setattr(display.records, "load_config", lambda: case.config)
    monkeypatch.setattr(display, "utc_now", lambda: NOW)

    def transport(request):
        response = server.get(request.url.path)
        return httpx.Response(response.status_code, json=response.json())

    with ApiClient(transport=httpx.MockTransport(transport)) as reader:
        assert (
            reader.get_prediction(case.product.product_key).forecast.probability == 0.37
        )
        (case.root / display.APPROVAL_FILE).unlink()
        result = reader.get_prediction(case.product.product_key)
        assert result.state == "closed" and result.forecast is None


@pytest.mark.parametrize("suffix", ["?history_days=30", "?x=1", "/other", "#fragment"])
def test_prediction_target_does_not_allow_parameters_or_other_paths(suffix):
    with pytest.raises(ApiClientError):
        _validate_target(
            httpx.Request(
                "GET", "http://127.0.0.1:8000/api/v1/products/phone/prediction" + suffix
            )
        )


@pytest.mark.parametrize(
    "payload",
    [
        dict(
            state="closed",
            reasons=["display_closed"],
            forecast={"probability": 0.4},
            generated_at=NOW.isoformat(),
        ),
        dict(
            state="available", reasons=[], forecast=None, generated_at=NOW.isoformat()
        ),
        dict(state="closed", reasons=[], forecast=None, generated_at=NOW.isoformat()),
        dict(
            state="closed",
            reasons=["family_not_in_training"],
            forecast=None,
            generated_at=NOW.isoformat(),
        ),
    ],
)
def test_client_rejects_incoherent_prediction_payload(payload):
    with pytest.raises(ValidationError):
        PredictionResponse.model_validate_json(json.dumps(payload))
    with ApiClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    ) as reader:
        with pytest.raises(ApiClientError) as error:
            reader.get_prediction("phone")
        assert error.value.code == "invalid_response"


def test_serving_import_and_available_read_do_not_load_model_libraries(case):
    code = """
import json, pickle, socket, sys
from datetime import datetime
def forbidden(*args, **kwargs):
    raise AssertionError("Model, tahmin veya ağ kullanıldı")
pickle.load = pickle.loads = socket.create_connection = forbidden
from app.ml.shadow_display import prediction_for
from app.ml.shadow_records import load_config
from app.ml.dataset import read_snapshot
from app.api.main import create_app
config = load_config(sys.argv[1])
snapshot, _ = read_snapshot(__import__('pathlib').Path(sys.argv[2]))
now = datetime.fromisoformat(sys.argv[3])
result = prediction_for(snapshot.products[0], config, now)
assert result['state'] == 'available'
heavy = {'numpy', 'sklearn', 'lightgbm'}
assert not any(name.split('.')[0] in heavy for name in sys.modules)
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(case.path),
            str(case.root / "goruntuler" / "veri_01"),
            NOW.isoformat(),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_prediction_identity_query_uses_readonly_test_database(world):
    from tests.support.read_world import KEY

    identity = read.read_product_identity(world, KEY)
    assert identity is not None and identity.product_key == KEY
    assert read.read_product_identity(world, "unknown") is None
