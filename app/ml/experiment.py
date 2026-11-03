"""Modelleri her katta kurar, doğrulama aylarını puanlar ve seçim kuralını uygular.

Saklı test ve kendi kaynağımız bu modülde hiç puanlanmaz. Seçim sonucu yalnız bir
öneridir; modelin dondurulması ve son testin açılması ayrı bir plandır.
"""

import hashlib
from dataclasses import dataclass

from app.ml.metrics import Probability, paired_bootstrap, score_predictions
from app.ml.models import (
    MODEL_RULES,
    PREDICTION_NAMES,
    describe_models,
    design_matrix,
    fit_models,
    library_versions,
    predict_models,
)
from app.ml.reporting import split_plan_files, verify_split_outputs
from app.ml.splitting import (
    SplitInputs,
    SplitPlan,
    build_split,
    evaluation_targets,
    fold_samples,
    load_split_inputs,
)

REFERENCE = "r0"
CANDIDATE = "lightgbm_platt"
BASELINE = "r2_platt"
REQUIRED_READY_FOLDS = 4
CONDITIONS = (
    "four_ready_folds",
    "ap_interval_lower_above_zero",
    "brier_not_worse_than_baseline",
    "log_loss_not_worse_than_baseline",
)
BOOTSTRAP_PAIRS = (
    ("selection", CANDIDATE, BASELINE),
    ("reference_step", "r1_platt", REFERENCE),
    ("reference_step", "r2_platt", "r1_platt"),
)

EXPERIMENT_RULES = {
    "version": 1,
    "training_source": "cimri",
    "scored_role": "validation",
    "models": MODEL_RULES,
    "scored_predictions": list(PREDICTION_NAMES),
    "reference_model": REFERENCE,
    "bootstrap_pairs": [
        dict(purpose=purpose, model=model, reference=reference)
        for purpose, model, reference in BOOTSTRAP_PAIRS
    ],
    "selection": dict(
        candidate=CANDIDATE,
        baseline=BASELINE,
        required_ready_folds=REQUIRED_READY_FOLDS,
        conditions=list(CONDITIONS),
        decides_model=False,
    ),
    "test_scoring_enabled": False,
    "own_source_scoring_enabled": False,
}


@dataclass(frozen=True)
class ExperimentInputs:
    split: SplitInputs
    plan: SplitPlan
    split_manifest_sha256: str

    @property
    def snapshot_sha256(self):
        return self.split.snapshot_sha256

    @property
    def input_manifests(self):
        return {**self.split.input_manifests, "split": self.split_manifest_sha256}


@dataclass(frozen=True)
class FoldResult:
    index: int
    month: str
    targets: list
    predictions: dict
    description: dict


@dataclass(frozen=True)
class ExperimentResult:
    predictions: list
    models: dict
    report: dict


def load_experiment_inputs(labels_dir, features_dir, split_dir):
    """Bölme klasörünün bu etiket/girdi ve bu koddan üretildiğini kanıtlar."""
    split = load_split_inputs(labels_dir, features_dir)
    verify_split_outputs(split_dir, split.snapshot_sha256, split.input_manifests)
    plan = build_split(split.samples)
    for name, content in split_plan_files(plan).items():
        if (split_dir / name).read_bytes() != content:
            raise ValueError(
                "Bölme dosyası, etiket ve girdiden yeniden üretilen bölmeyle "
                f"uyuşmuyor: {name}"
            )
    manifest = (split_dir / "manifest.json").read_bytes()
    return ExperimentInputs(split, plan, hashlib.sha256(manifest).hexdigest())


def fit_folds(split, plan):
    """Hazır her katta modelleri kurar ve yalnız doğrulama ayını tahmin eder."""
    results = []
    for index, fold in enumerate(plan.folds):
        if fold["status"] != "ready":
            continue
        members = {
            role: fold_samples(split, plan, index, role)
            for role in ("train", "calibration", "validation")
        }
        targets = evaluation_targets(split.samples, plan, fold_index=index)
        if [row.key for row in targets] != [
            sample.anchor.key for sample, _ in members["validation"]
        ]:
            raise ValueError("Doğrulama hedefleri kat üyeleriyle uyuşmuyor")
        matrices = {
            role: design_matrix([features for _, features in rows])
            for role, rows in members.items()
        }
        labels = {
            role: [sample.anchor.label for sample, _ in rows]
            for role, rows in members.items()
        }
        models = fit_models(
            matrices["train"],
            labels["train"],
            matrices["calibration"],
            labels["calibration"],
        )
        results.append(
            FoldResult(
                index=index,
                month=fold["month"],
                targets=targets,
                predictions=predict_models(models, matrices["validation"]),
                description=describe_models(models),
            )
        )
    return results


def _probabilities(targets, values):
    return [
        Probability(
            product_id=target.product_id,
            source=target.source,
            anchor_day=target.anchor_day,
            probability=float(value),
        )
        for target, value in zip(targets, values)
    ]


def _core(score):
    return {
        key: value for key, value in score.items() if key not in ("breakdowns", "macro")
    }


def _without_bins(scores):
    if scores is None:
        return None
    return {key: value for key, value in scores.items() if key != "calibration"}


def _slim(score):
    slim = dict(score)
    slim["breakdowns"] = {
        attribute: {
            name: dict(cell, scores=_without_bins(cell["scores"]))
            for name, cell in cells.items()
        }
        for attribute, cells in score["breakdowns"].items()
    }
    return slim


def evaluate_selection(ready_folds, combined, interval):
    """LightGBM'in R2'yi geçip geçmediği; dört koşulun hepsi sonuçtan önce sabittir.

    Kat eksikse değerlendirilemez. Katlar tamamsa kanıtlanmış bir başarısızlık
    (kötü Brier gibi) aralık hesaplanamasa da `not_met` verir; hesaplanamayan ve
    başarısız olmayan koşul varsa sonuç `not_evaluable` olur.
    """
    candidate, baseline = combined[CANDIDATE], combined[BASELINE]

    def not_worse(name):
        values = (candidate[name], baseline[name])
        return None if None in values else values[0] <= values[1]

    lower = interval["lower"]
    results = {
        "four_ready_folds": ready_folds == REQUIRED_READY_FOLDS,
        "ap_interval_lower_above_zero": None if lower is None else lower > 0,
        "brier_not_worse_than_baseline": not_worse("brier"),
        "log_loss_not_worse_than_baseline": not_worse("log_loss"),
    }
    if not results["four_ready_folds"]:
        status = "not_evaluable"
    elif False in results.values():
        status = "not_met"
    elif None in results.values():
        status = "not_evaluable"
    else:
        status = "met"
    return dict(
        status=status,
        candidate=CANDIDATE,
        baseline=BASELINE,
        conditions=[dict(name=name, passed=results[name]) for name in CONDITIONS],
        values=dict(
            ready_folds=ready_folds,
            ap_difference=interval["point_difference"],
            ap_interval_lower=lower,
            ap_interval_upper=interval["upper"],
            interval_reasons=interval["reasons"],
            brier=dict(candidate=candidate["brier"], baseline=baseline["brier"]),
            log_loss=dict(
                candidate=candidate["log_loss"], baseline=baseline["log_loss"]
            ),
        ),
        decides_model=False,
    )


def build_result(plan, results):
    probabilities = {name: [] for name in PREDICTION_NAMES}
    combined_targets, fold_scores, rows = [], {}, []
    for result in results:
        by_model = {
            name: _probabilities(result.targets, result.predictions[name])
            for name in PREDICTION_NAMES
        }
        fold_scores[result.index] = {
            name: _core(
                score_predictions(result.targets, by_model[name], by_model[REFERENCE])
            )
            for name in PREDICTION_NAMES
        }
        combined_targets += result.targets
        for name in PREDICTION_NAMES:
            probabilities[name] += by_model[name]
        for position, target in enumerate(result.targets):
            rows.append(
                dict(
                    fold=result.month,
                    product_id=target.product_id,
                    source=target.source,
                    anchor_day=target.anchor_day,
                    label=target.label,
                    **{
                        name: float(result.predictions[name][position])
                        for name in PREDICTION_NAMES
                    },
                )
            )
    combined = {
        name: score_predictions(
            combined_targets, probabilities[name], probabilities[REFERENCE]
        )
        for name in PREDICTION_NAMES
    }
    intervals = [
        dict(
            purpose=purpose,
            model=model,
            reference=reference,
            **paired_bootstrap(
                combined_targets, probabilities[model], probabilities[reference]
            ),
        )
        for purpose, model, reference in BOOTSTRAP_PAIRS
    ]
    selection = evaluate_selection(
        len(results),
        {name: combined[name] for name in (CANDIDATE, BASELINE)},
        next(item for item in intervals if item["purpose"] == "selection"),
    )
    positives = sum(target.label for target in combined_targets)
    report = dict(
        experiment_rules=EXPERIMENT_RULES,
        libraries=library_versions(),
        split_status=plan.report["status"],
        folds=[
            dict(
                month=fold["month"],
                status=fold["status"],
                limitations=fold["limitations"],
                statistics=fold["statistics"],
                purged=fold["purged"],
                scores=fold_scores.get(index),
            )
            for index, fold in enumerate(plan.folds)
        ],
        combined=dict(
            rows=len(combined_targets),
            positives=positives,
            positive_rate=(
                positives / len(combined_targets) if combined_targets else None
            ),
            scores={name: _slim(score) for name, score in combined.items()},
        ),
        bootstrap=intervals,
        selection=selection,
        validation_scores_computed=True,
        test_opened=False,
        own_source_scored=False,
        model_frozen=False,
    )
    models = dict(
        folds=[dict(month=result.month, **result.description) for result in results]
    )
    return ExperimentResult(rows, models, report)


def run_experiment(split, plan):
    return build_result(plan, fit_folds(split, plan))
