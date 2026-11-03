"""Deney katmanı: seçim kuralı, sızıntı korumaları ve sınırlı veri (yapay kanıtla)."""

import dataclasses

import pytest

from app.ml.experiment import (
    BASELINE,
    CANDIDATE,
    EXPERIMENT_RULES,
    evaluate_selection,
    fit_folds,
    load_experiment_inputs,
    run_experiment,
)
from app.ml.metrics import METRIC_RULES
from app.ml.reporting import json_bytes
from tests.support.ml import write_ml_evidence

KEY_FIELDS = ("product_id", "source", "anchor_day")


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    # Yalnız tekrar sayısı düşer; hesap ve kurallar aynıdır. Gerçek sayı ve
    # yöntem tests/test_ml_metrics.py'de sınanır.
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    paths = write_ml_evidence(tmp_path_factory.mktemp("evidence"))
    return load_experiment_inputs(paths["labels"], paths["features"], paths["split"])


@pytest.fixture(scope="module")
def baseline(inputs):
    return run_experiment(inputs.split, inputs.plan)


def fingerprint(result):
    return json_bytes([result.predictions, result.models, result.report])


def altered(inputs, keys=None, predicate=None, flip_labels=True):
    """Seçilen başlangıçların girdisini (ve etiketini) değiştirir; plan aynı kalır."""
    samples, features = [], []
    for sample, values in zip(inputs.split.samples, inputs.split.features):
        if (keys is not None and sample.anchor.key in keys) or (
            predicate is not None and predicate(sample)
        ):
            if flip_labels and sample.anchor.label is not None:
                anchor = sample.anchor.model_copy(
                    update={"label": 1 - sample.anchor.label}
                )
                sample = dataclasses.replace(sample, anchor=anchor)
            values = values.model_copy(
                update=dict(
                    ratio_min_30d=values.ratio_min_30d * 2,
                    volatility_30d=None,
                    brand="Other",
                )
            )
        samples.append(sample)
        features.append(values)
    return dataclasses.replace(
        inputs.split, samples=tuple(samples), features=tuple(features)
    )


def keys_with_role(inputs, role):
    return {
        tuple(row[name] for name in KEY_FIELDS)
        for row in inputs.plan.assignments
        if row["role"] == role
    }


def test_only_ready_folds_are_fitted_on_exactly_their_validation_rows(inputs):
    results = fit_folds(inputs.split, inputs.plan)
    ready = [fold for fold in inputs.plan.folds if fold["status"] == "ready"]
    assert len(results) == len(ready) == 4
    for result, fold in zip(results, ready):
        expected = [
            tuple(member[name] for name in KEY_FIELDS)
            for member in fold["members"]["validation"]
        ]
        assert result.month == fold["month"]
        assert [target.key for target in result.targets] == expected
        assert all(target.source == "cimri" for target in result.targets)
        assert all(
            len(values) == len(expected) for values in result.predictions.values()
        )


def test_report_states_rules_scope_and_closed_gates(inputs, baseline):
    report = baseline.report
    assert report["experiment_rules"] == EXPERIMENT_RULES
    assert report["validation_scores_computed"] is True
    assert (
        report["test_opened"]
        is report["own_source_scored"]
        is report["model_frozen"]
        is False
    )
    assert [item["purpose"] for item in report["bootstrap"]] == [
        "selection",
        "reference_step",
        "reference_step",
    ]
    assert report["selection"]["status"] in {"met", "not_met", "not_evaluable"}
    assert report["selection"]["decides_model"] is False
    assert report["combined"]["rows"] == len(baseline.predictions)
    assert report["combined"]["rows"] == sum(
        fold["scores"]["r0"]["rows"] for fold in report["folds"]
    )
    assert report["combined"]["scores"]["r0"]["brier_skill"] == pytest.approx(0)
    assert [fold["month"] for fold in baseline.models["folds"]] == [
        fold["month"] for fold in inputs.plan.folds
    ]
    # R0 her katta tek bir sabittir; birleşik puanda satır kendi katının R0'ını taşır.
    constants = {}
    for row in baseline.predictions:
        constants.setdefault(row["fold"], set()).add(row["r0"])
    assert len(constants) == 4 and all(
        len(values) == 1 for values in constants.values()
    )


def test_reserved_test_rows_cannot_change_any_experiment_output(inputs, baseline):
    reserved = keys_with_role(inputs, "test_reserved")
    assert reserved
    changed = run_experiment(altered(inputs, keys=reserved), inputs.plan)
    assert fingerprint(changed) == fingerprint(baseline)


def test_own_source_and_unlabelled_rows_cannot_change_any_experiment_output(
    inputs, baseline
):
    own = [row for row in inputs.split.samples if row.anchor.source == "own"]
    unlabelled = [
        row
        for row in inputs.split.samples
        if row.anchor.source == "cimri" and row.anchor.label is None
    ]
    assert own and unlabelled
    changed = run_experiment(
        altered(
            inputs,
            predicate=lambda sample: sample.anchor.source == "own"
            or sample.anchor.label is None,
        ),
        inputs.plan,
    )
    assert fingerprint(changed) == fingerprint(baseline)


def test_changing_training_rows_does_change_the_output(inputs, baseline):
    # Olumlu kontrol: yukarıdaki eşitlikler, değişikliğin işlemediği için değil,
    # modelin o satırları gerçekten kullanmadığı için geçer.
    training = {
        tuple(member[name] for name in KEY_FIELDS)
        for member in inputs.plan.folds[0]["members"]["train"][:60]
    }
    changed = run_experiment(altered(inputs, keys=training), inputs.plan)
    assert fingerprint(changed) != fingerprint(baseline)


def test_limited_evidence_gives_a_complete_but_unevaluable_result(tmp_path):
    root = tmp_path / "limited"
    root.mkdir()
    paths = write_ml_evidence(root, count=10)
    limited = load_experiment_inputs(paths["labels"], paths["features"], paths["split"])
    result = run_experiment(limited.split, limited.plan)
    assert result.predictions == []
    assert result.report["combined"]["rows"] == 0
    assert result.report["selection"]["status"] == "not_evaluable"
    assert all(fold["scores"] is None for fold in result.report["folds"])
    json_bytes(result.report)


def scores(brier=0.20, log_loss=0.60):
    return dict(brier=brier, log_loss=log_loss)


def decide(folds=4, lower=0.01, candidate=None, baseline=None):
    interval = dict(
        lower=lower,
        upper=None if lower is None else lower + 0.05,
        point_difference=0.03,
        reasons=[] if lower is not None else ["insufficient_valid_repeats"],
    )
    combined = {
        CANDIDATE: candidate or scores(),
        BASELINE: baseline or scores(),
    }
    return evaluate_selection(folds, combined, interval)


def passed(result):
    return {item["name"]: item["passed"] for item in result["conditions"]}


def test_selection_is_met_only_when_all_four_conditions_hold():
    result = decide()
    assert result["status"] == "met"
    assert all(passed(result).values()) and len(passed(result)) == 4
    # Eşitlik "kötü değil" sayılır.
    assert decide(candidate=scores(0.20, 0.60), baseline=scores(0.20, 0.60))[
        "status"
    ] == ("met")
    assert result["decides_model"] is False


@pytest.mark.parametrize(
    "kwargs, failed",
    [
        (dict(lower=0.0), "ap_interval_lower_above_zero"),
        (dict(lower=-0.02), "ap_interval_lower_above_zero"),
        (dict(candidate=scores(brier=0.21)), "brier_not_worse_than_baseline"),
        (dict(candidate=scores(log_loss=0.61)), "log_loss_not_worse_than_baseline"),
    ],
)
def test_one_failed_condition_means_not_met(kwargs, failed):
    result = decide(**kwargs)
    assert result["status"] == "not_met"
    assert passed(result)[failed] is False
    assert list(passed(result).values()).count(False) == 1


def test_missing_folds_or_interval_are_not_evaluable_not_failures():
    assert decide(folds=3)["status"] == "not_evaluable"
    assert decide(folds=0)["status"] == "not_evaluable"
    # Kat eksikse diğer koşullar ne kadar iyi görünürse görünsün karar verilmez.
    assert decide(folds=3, candidate=scores(0.01, 0.01))["status"] == "not_evaluable"
    result = decide(lower=None)
    assert result["status"] == "not_evaluable"
    assert passed(result)["ap_interval_lower_above_zero"] is None
    assert result["values"]["interval_reasons"] == ["insufficient_valid_repeats"]
    assert decide(candidate=scores(None, None))["status"] == "not_evaluable"


def test_a_proven_failure_is_not_met_even_without_an_interval():
    assert decide(lower=None, candidate=scores(brier=0.50))["status"] == "not_met"
