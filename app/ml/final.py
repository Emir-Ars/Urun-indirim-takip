"""Seçilen modeli dondurur ve yalnız denetimlerden sonra yeniden yükler.

Dondurma saklı test satırlarına hiç dokunmaz. Model dosyası pickle olduğu için
açılmadan önce manifestin beklenen SHA-256 değeri, dosya parmak izleri, kural ve
kütüphane sürümleri doğrulanır; açıldıktan sonra kalibrasyon diliminde kayıtlı
olasılıkları birebir üretmek zorundadır.
"""

import hashlib
import json
import pickle
import re
from dataclasses import dataclass

from app.ml.experiment import (
    BASELINE,
    CANDIDATE,
    REFERENCE,
    keyed_probabilities,
    slim_score,
)
from app.ml.metrics import reserved_test_bootstrap, score_reserved_test
from app.ml.models import (
    FrozenModel,
    describe_frozen,
    design_matrix,
    fit_frozen,
    library_versions,
    predict_frozen,
)
from app.ml.reporting import verify_experiment_outputs, verify_model_outputs
from app.ml.splitting import (
    FINAL_ROLES,
    SPLIT_RULES,
    final_boundaries,
    final_samples,
    reserved_test_samples,
    reserved_test_targets,
)

PICKLE_PROTOCOL = 5
READ_CONDITIONS = ("brier_skill_above_zero", "ap_interval_lower_above_zero")

FINAL_RULES = {
    "version": 1,
    "training_source": "cimri",
    # Seçim deney raporundaki sonuçtan kurala göre türetilir; elle model verilmez.
    "selection_to_model": dict(met=CANDIDATE, not_met=BASELINE),
    "calibration_days": SPLIT_RULES["calibration_days"],
    "slices": "train_before_calibration_start_calibration_last_days_before_test",
    "reference_model": REFERENCE,
    "serialization": dict(
        format="pickle",
        protocol=PICKLE_PROTOCOL,
        opened_only_after=(
            "expected_manifest_sha256_file_fingerprints_rules_and_library_versions"
        ),
        reload_check="calibration_probabilities_identical",
    ),
    "reserved_test": dict(
        scored_models=[REFERENCE, "frozen_model"],
        bootstrap="frozen_model_minus_reference",
        read_conditions=list(READ_CONDITIONS),
        decides_model=False,
    ),
}

VALIDATION_FIELDS = (
    "rows",
    "positive_rate",
    "average_precision",
    "brier",
    "log_loss",
    "brier_skill",
)


@dataclass(frozen=True)
class FreezeResult:
    choice: str
    frozen: FrozenModel
    experiment_manifest_sha256: str
    document: dict
    calibration_rows: list


@dataclass(frozen=True)
class LoadedModel:
    frozen: FrozenModel
    manifest: dict
    manifest_sha256: str
    document: dict


@dataclass(frozen=True)
class FinalTestResult:
    predictions: list
    report: dict


def choose_model(experiment_report):
    """Deneyin seçim sonucundan dondurulacak modeli türetir."""
    status = experiment_report["selection"]["status"]
    if status not in FINAL_RULES["selection_to_model"]:
        raise ValueError("Deneyin seçim sonucu değerlendirilemedi; model dondurulamaz")
    return FINAL_RULES["selection_to_model"][status]


def _summary(members):
    anchors = [sample.anchor for sample, _ in members]
    return dict(
        rows=len(anchors),
        positive=sum(anchor.label for anchor in anchors),
        first_anchor=min(anchor.anchor_day for anchor in anchors),
        last_anchor=max(anchor.anchor_day for anchor in anchors),
        latest_target_end=max(anchor.target_end for anchor in anchors),
    )


def freeze_model(inputs, experiment_dir):
    """Son dilimlerle seçilen modeli kurar; saklı test satırı hiç okunmaz."""
    verify_experiment_outputs(experiment_dir, inputs)
    report = json.loads((experiment_dir / "report.json").read_bytes())
    choice = choose_model(report)
    members = {
        role: final_samples(inputs.split, inputs.plan, role) for role in FINAL_ROLES
    }
    matrices = {
        role: design_matrix([features for _, features in rows])
        for role, rows in members.items()
    }
    labels = {
        role: [sample.anchor.label for sample, _ in rows]
        for role, rows in members.items()
    }
    frozen = fit_frozen(
        choice,
        matrices["train"],
        labels["train"],
        matrices["calibration"],
        labels["calibration"],
    )
    predicted = predict_frozen(frozen, matrices["calibration"])
    calibration_rows = [
        dict(
            product_id=sample.anchor.product_id,
            source=sample.anchor.source,
            anchor_day=sample.anchor.anchor_day,
            label=sample.anchor.label,
            **{name: float(values[index]) for name, values in predicted.items()},
        )
        for index, (sample, _) in enumerate(members["calibration"])
    ]
    scores = report["combined"]["scores"]
    document = dict(
        choice=choice,
        selection=report["selection"],
        slices=dict(
            **final_boundaries(inputs.plan),
            train=_summary(members["train"]),
            calibration=_summary(members["calibration"]),
        ),
        model=describe_frozen(frozen),
        experiment_validation={
            name: {field: scores[name][field] for field in VALIDATION_FIELDS}
            for name in (REFERENCE, choice)
        },
    )
    manifest = (experiment_dir / "manifest.json").read_bytes()
    return FreezeResult(
        choice, frozen, hashlib.sha256(manifest).hexdigest(), document, calibration_rows
    )


def load_frozen_model(model_dir, inputs, expected_manifest_sha256):
    """Dondurulan modeli yalnız beklenen manifest SHA-256'sını taşıyorsa açar."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_manifest_sha256 or ""):
        raise ValueError("Beklenen model SHA-256 değeri 64 onaltılık hane olmalı")
    raw_manifest = (model_dir / "manifest.json").read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest() != expected_manifest_sha256:
        raise ValueError("Model manifestinin SHA-256 değeri beklenenle uyuşmuyor")
    manifest = verify_model_outputs(model_dir, inputs)
    try:
        frozen = pickle.loads((model_dir / "model.pkl").read_bytes())
    except Exception as exc:
        raise ValueError(f"Model dosyası açılamadı: {exc}") from exc
    if not isinstance(frozen, FrozenModel) or frozen.choice != manifest["choice"]:
        raise ValueError("Model dosyası manifestteki modeli içermiyor")
    members = final_samples(inputs.split, inputs.plan, "calibration")
    predicted = predict_frozen(
        frozen, design_matrix([features for _, features in members])
    )
    recorded = [
        json.loads(line)
        for line in (model_dir / "calibration_predictions.jsonl")
        .read_bytes()
        .splitlines()
    ]
    keys = [(row["product_id"], row["source"], row["anchor_day"]) for row in recorded]
    expected = [
        (
            sample.anchor.product_id,
            sample.anchor.source,
            sample.anchor.anchor_day.isoformat(),
        )
        for sample, _ in members
    ]
    if (
        keys != expected
        or [row["label"] for row in recorded]
        != [sample.anchor.label for sample, _ in members]
        or any(
            [row[name] for row in recorded] != [float(v) for v in values]
            for name, values in predicted.items()
        )
    ):
        raise ValueError(
            "Yüklenen model kayıtlı kalibrasyon tahminlerini yeniden üretmiyor"
        )
    document = json.loads((model_dir / "model.json").read_bytes())
    return LoadedModel(frozen, manifest, expected_manifest_sha256, document)


def evaluate_reading(score, interval):
    """Saklı test okuma koşulları; sonuçtan önce sabit, modeli değiştirmez.

    Kanıtlanmış bir başarısızlık, başka koşul hesaplanamasa da `not_met` verir;
    başarısız koşul yokken hesaplanamayan varsa `not_evaluable` olur.
    """
    skill, lower = score["brier_skill"], interval["lower"]
    results = {
        "brier_skill_above_zero": None if skill is None else skill > 0,
        "ap_interval_lower_above_zero": None if lower is None else lower > 0,
    }
    if False in results.values():
        status = "not_met"
    elif None in results.values():
        status = "not_evaluable"
    else:
        status = "met"
    return dict(
        status=status,
        conditions=[dict(name=name, passed=results[name]) for name in READ_CONDITIONS],
        values=dict(
            brier_skill=skill,
            ap_difference=interval["point_difference"],
            ap_interval_lower=lower,
            ap_interval_upper=interval["upper"],
            interval_reasons=interval["reasons"],
        ),
        decides_model=False,
    )


def run_final_test(inputs, loaded):
    """Saklı testi yalnız yüklenmiş (SHA'sı doğrulanmış) model için puanlar.

    Bu işleve gelinmeden model parmak izi ve kalibrasyon yeniden üretimiyle
    doğrulanmış olmalıdır; saklı test satırları ancak burada alınır.
    """
    choice = loaded.frozen.choice
    members = reserved_test_samples(inputs.split, inputs.plan)
    targets = reserved_test_targets(members)
    predicted = predict_frozen(
        loaded.frozen, design_matrix([features for _, features in members])
    )
    probabilities = {
        name: keyed_probabilities(targets, values) for name, values in predicted.items()
    }
    reference, model = probabilities[REFERENCE], probabilities[choice]
    scores = {
        REFERENCE: score_reserved_test(targets, reference, reference),
        choice: score_reserved_test(targets, model, reference),
    }
    interval = reserved_test_bootstrap(targets, model, reference)
    positives = sum(target.label for target in targets)
    days = [target.anchor_day for target in targets]
    rows = [
        dict(
            product_id=target.product_id,
            source=target.source,
            anchor_day=target.anchor_day,
            label=target.label,
            **{name: float(values[index]) for name, values in predicted.items()},
        )
        for index, target in enumerate(targets)
    ]
    report = dict(
        final_rules=FINAL_RULES,
        libraries=library_versions(),
        model_manifest_sha256=loaded.manifest_sha256,
        choice=choice,
        reserved_test=dict(
            rows=len(targets),
            positives=positives,
            positive_rate=positives / len(targets),
            first_anchor=min(days),
            last_anchor=max(days),
        ),
        scores={name: slim_score(score) for name, score in scores.items()},
        bootstrap=dict(model=choice, reference=REFERENCE, **interval),
        reading=evaluate_reading(scores[choice], interval),
        experiment_validation=loaded.document["experiment_validation"],
        test_opened=True,
        own_source_scored=False,
        model_changed=False,
    )
    return FinalTestResult(rows, report)
