"""Referans modeller, LightGBM ve Platt kalibrasyonu (yapay veriyle, ağsız)."""

import inspect
import pickle
import random

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from app.ml.features import FeatureValues, feature_schema
from app.ml.models import (
    CATEGORICAL_FIELDS,
    COLUMNS,
    FROZEN_CHOICES,
    LIGHTGBM_PARAMS,
    LOGISTIC_PARAMS,
    MODEL_RULES,
    PLATT_NAMES,
    PREDICTION_NAMES,
    RAW_NAMES,
    BucketRule,
    LogOdds,
    build_lightgbm,
    build_logistic,
    describe_frozen,
    describe_models,
    design_matrix,
    fit_frozen,
    fit_models,
    predict_frozen,
    predict_models,
)
from app.ml.reporting import json_bytes
from tests.support.ml import feature_values


def dataset(count, seed):
    """Dipten uzaklaştıkça düşüş olasılığı artan, eksik değerli yapay satırlar."""
    rng = random.Random(seed)
    rows, labels = [], []
    for _ in range(count):
        ratio = 1.0 if rng.random() < 0.3 else 1 + rng.random() * 0.3
        labels.append(int(rng.random() < 0.04 + 0.9 * (ratio - 1)))
        brand = rng.choice(["Apple", "Samsung"])
        rows.append(
            feature_values(
                log_return_1d=None if rng.random() < 0.1 else rng.gauss(0, 0.02),
                log_return_7d=rng.gauss(0, 0.04),
                log_return_14d=rng.gauss(0, 0.05),
                log_return_30d=None if rng.random() < 0.1 else rng.gauss(0, 0.08),
                ratio_min_7d=1 + rng.random() * 0.1,
                ratio_min_30d=ratio,
                ratio_mean_30d=0.9 + rng.random() * 0.2,
                volatility_30d=None if rng.random() < 0.2 else rng.random() * 0.05,
                change_count_30d=rng.randint(0, 10),
                days_since_drop_30d=rng.randint(0, 31),
                drop_observed_30d=rng.choice([True, False, None]),
                history_days=rng.randint(1, 300),
                missing_ratio_30d=rng.random() * 0.3,
                weekday=str(rng.randint(0, 6)),
                brand=brand,
                family=f"{brand} {rng.choice(['A', 'B', 'C'])}",
                segment=rng.choice(["standard", "pro"]),
                capacity=rng.choice(["128", "256"]),
            )
        )
    return design_matrix(rows), np.array(labels)


@pytest.fixture(scope="module")
def data():
    return dict(
        train=dataset(1500, 1),
        calibration=dataset(600, 2),
        validation=dataset(400, 3),
    )


@pytest.fixture(scope="module")
def fitted(data):
    return fit_models(*data["train"], *data["calibration"])


def test_model_columns_are_exactly_the_core_feature_contract():
    assert len(COLUMNS) == len(set(COLUMNS))
    assert set(COLUMNS) == set(FeatureValues.model_fields)
    assert set(feature_schema()["categorical_features"]) == set(CATEGORICAL_FIELDS)
    assert list(COLUMNS) == [
        *MODEL_RULES["numeric_features"],
        *MODEL_RULES["categorical_features"],
    ]
    assert set(MODEL_RULES["not_used"]).isdisjoint(COLUMNS)


def test_design_matrix_turns_null_into_nan_and_booleans_into_numbers():
    matrix = design_matrix(
        [
            feature_values(log_return_1d=None, drop_observed_30d=False),
            feature_values(drop_observed_30d=None),
        ]
    )
    assert matrix.shape == (2, len(COLUMNS))
    assert np.isnan(matrix[0, COLUMNS.index("log_return_1d")])
    assert matrix[0, COLUMNS.index("drop_observed_30d")] == 0.0
    assert matrix[1, COLUMNS.index("log_return_1d")] == 0.0
    assert np.isnan(matrix[1, COLUMNS.index("drop_observed_30d")])
    assert matrix[0, COLUMNS.index("brand")] == "Apple"


def test_r0_is_the_training_positive_rate_for_every_row(fitted, data):
    _, train_labels = data["train"]
    validation_x, _ = data["validation"]
    prediction = predict_models(fitted, validation_x)["r0"]
    assert fitted.raw["r0"].rate_ == train_labels.mean()
    assert np.all(prediction == train_labels.mean())


def test_bucket_rule_matches_hand_computation():
    ratios = [1.0] * 4 + [1.01] * 2 + [1.02, 1.03] + [1.20] * 2
    labels = [1, 0, 0, 0, 1, 1, 0, 0, 1, 0]
    rule = BucketRule().fit(
        design_matrix([feature_values(ratio_min_30d=value) for value in ratios]),
        labels,
    )
    # Tam 1,02 ikinci kovaya girer (üst sınır dahil); dördüncü kova boş kalır.
    assert rule.rows_.tolist() == [4, 3, 1, 0, 2]
    assert rule.positives_.tolist() == [1, 2, 0, 0, 1]
    assert rule.prior_rate_ == 0.4
    expected = [9 / 24, 10 / 23, 8 / 21, 8 / 20, 9 / 22]
    assert rule.rates_ == pytest.approx(expected)
    edges = [1.0, 1.02, 1.0200001, 1.10, 1.1000001]
    probe = design_matrix([feature_values(ratio_min_30d=value) for value in edges])
    assert rule.predict_proba(probe)[:, 1] == pytest.approx(expected)


def test_models_accept_null_inputs_and_unseen_categories(fitted):
    odd = design_matrix(
        [
            feature_values(
                log_return_1d=None,
                log_return_30d=None,
                volatility_30d=None,
                change_count_30d=None,
                days_since_drop_30d=None,
                drop_observed_30d=None,
                brand="Nothing",
                family="Nothing Phone 99",
                segment="exotic",
                capacity="1024",
            )
        ]
    )
    result = predict_models(fitted, odd)
    assert list(result) == list(PREDICTION_NAMES)
    for probability in result.values():
        assert np.all(np.isfinite(probability))
        assert np.all((0 < probability) & (probability < 1))


def test_platt_keeps_the_ranking_and_changes_the_probabilities(fitted, data):
    validation_x, validation_y = data["validation"]
    result = predict_models(fitted, validation_x)
    for name in PLATT_NAMES:
        raw, calibrated = result[name], result[f"{name}_platt"]
        assert average_precision_score(validation_y, calibrated) == pytest.approx(
            average_precision_score(validation_y, raw), rel=1e-12
        )
        assert np.array_equal(
            np.argsort(raw, kind="stable"), np.argsort(calibrated, kind="stable")
        )
        assert not np.allclose(raw, calibrated)
    assert "r0_platt" not in result
    platt = describe_models(fitted)["platt"]
    assert all(item["order_preserved"] for item in platt.values())


def test_same_inputs_give_identical_probabilities_and_description(fitted, data):
    again = fit_models(*data["train"], *data["calibration"])
    validation_x, _ = data["validation"]
    first, second = (predict_models(item, validation_x) for item in (fitted, again))
    for name in PREDICTION_NAMES:
        assert np.array_equal(first[name], second[name])
    assert json_bytes(describe_models(fitted)) == json_bytes(describe_models(again))


def test_each_row_is_predicted_independently_of_the_others(fitted, data):
    validation_x, _ = data["validation"]
    whole = predict_models(fitted, validation_x)
    parts = [
        predict_models(fitted, validation_x[:97]),
        predict_models(fitted, validation_x[97:]),
    ]
    for name in PREDICTION_NAMES:
        joined = np.concatenate([part[name] for part in parts])
        assert np.allclose(whole[name], joined, rtol=0, atol=1e-12)


def test_calibration_slice_changes_only_platt_probabilities(fitted, data):
    validation_x, _ = data["validation"]
    base = predict_models(fitted, validation_x)
    train_x, train_y = data["train"]
    calibration_x, calibration_y = data["calibration"]
    other_x, other_y = dataset(600, 99)
    for variant_x, variant_y in (
        (calibration_x, 1 - calibration_y),
        (other_x, other_y),
    ):
        changed = predict_models(
            fit_models(train_x, train_y, variant_x, variant_y), validation_x
        )
        for name in RAW_NAMES:
            assert np.array_equal(changed[name], base[name]), name
        for name in PLATT_NAMES:
            assert not np.allclose(changed[f"{name}_platt"], base[f"{name}_platt"])


def test_training_labels_change_the_raw_probabilities(fitted, data):
    validation_x, _ = data["validation"]
    base = predict_models(fitted, validation_x)
    train_x, train_y = data["train"]
    changed = predict_models(
        fit_models(train_x, 1 - train_y, *data["calibration"]), validation_x
    )
    for name in RAW_NAMES:
        assert not np.allclose(changed[name], base[name]), name


def test_fitting_accepts_only_training_and_calibration_slices():
    assert list(inspect.signature(fit_models).parameters) == [
        "train_x",
        "train_labels",
        "calibration_x",
        "calibration_labels",
    ]


@pytest.mark.parametrize(
    "problem", ["single_train", "single_calibration", "length", "values", "columns"]
)
def test_invalid_slices_are_rejected(data, problem):
    train_x, train_y = data["train"]
    calibration_x, calibration_y = data["calibration"]
    if problem == "single_train":
        train_y = np.zeros_like(train_y)
    elif problem == "single_calibration":
        calibration_y = np.ones_like(calibration_y)
    elif problem == "length":
        calibration_y = calibration_y[:-1]
    elif problem == "values":
        train_y = train_y + 1
    else:
        train_x = train_x[:, :-1]
    with pytest.raises(ValueError):
        fit_models(train_x, train_y, calibration_x, calibration_y)


def test_description_is_complete_and_json_safe(fitted, data):
    _, train_y = data["train"]
    description = describe_models(fitted)
    json_bytes(description)
    json_bytes(MODEL_RULES)
    buckets = description["r1"]["buckets"]
    assert description["r0"]["rate"] == pytest.approx(train_y.mean())
    assert len(buckets) == 5 and buckets[-1]["upper"] is None
    assert sum(item["rows"] for item in buckets) == len(train_y)
    assert description["r2"]["converged"] is True
    assert description["lightgbm"]["trees"] == LIGHTGBM_PARAMS["n_estimators"]
    assert set(description["platt"]) == set(PLATT_NAMES)
    # Katsayı ve önem adları gerçek girdi adlarını taşır.
    assert {"ratio_min_30d", "brand_Apple"} <= set(description["r2"]["coefficients"])
    assert any(
        name.startswith("missingindicator_")
        for name in description["r2"]["coefficients"]
    )
    assert description["lightgbm"]["gain_importance"]["ratio_min_30d"] > 0


def test_recorded_rules_match_the_estimators_that_run():
    logistic = build_logistic().named_steps["model"].get_params()
    for name, value in LOGISTIC_PARAMS.items():
        assert logistic[name] == value == MODEL_RULES["r2"][name]
    boosted = build_lightgbm().named_steps["model"].get_params()
    recorded = {
        name: value
        for name, value in MODEL_RULES["lightgbm"].items()
        if name in boosted
    }
    assert set(LIGHTGBM_PARAMS) <= set(recorded)
    assert recorded["class_weight"] is None
    assert all(boosted[name] == value for name, value in recorded.items())


@pytest.mark.parametrize("choice", sorted(FROZEN_CHOICES))
def test_frozen_model_gives_the_same_probabilities_as_the_validated_method(
    choice, fitted, data
):
    validation_x, _ = data["validation"]
    frozen = fit_frozen(choice, *data["train"], *data["calibration"])
    result = predict_frozen(frozen, validation_x)
    reference = predict_models(fitted, validation_x)
    assert list(result) == ["r0", choice]
    assert np.array_equal(result["r0"], reference["r0"])
    assert np.array_equal(result[choice], reference[choice])
    assert np.all((0 < result[choice]) & (result[choice] < 1))


def test_only_the_two_selectable_models_can_be_frozen(data):
    assert set(FROZEN_CHOICES) == {"r2_platt", "lightgbm_platt"}
    for choice in ("r1_platt", "r2", "r0", "lightgbm", ""):
        with pytest.raises(ValueError, match="Dondurulabilen"):
            fit_frozen(choice, *data["train"], *data["calibration"])


def test_frozen_model_survives_pickle_with_identical_probabilities(data):
    validation_x, _ = data["validation"]
    frozen = fit_frozen("r2_platt", *data["train"], *data["calibration"])
    loaded = pickle.loads(pickle.dumps(frozen))
    first, second = (predict_frozen(item, validation_x) for item in (frozen, loaded))
    for name in first:
        assert np.array_equal(first[name], second[name])
    assert json_bytes(describe_frozen(frozen)) == json_bytes(describe_frozen(loaded))


def test_frozen_calibration_slice_changes_only_the_platt_probability(data):
    validation_x, _ = data["validation"]
    train_x, train_y = data["train"]
    calibration_x, calibration_y = data["calibration"]
    base = predict_frozen(
        fit_frozen("r2_platt", train_x, train_y, calibration_x, calibration_y),
        validation_x,
    )
    changed = predict_frozen(
        fit_frozen("r2_platt", train_x, train_y, calibration_x, 1 - calibration_y),
        validation_x,
    )
    assert np.array_equal(changed["r0"], base["r0"])
    assert not np.allclose(changed["r2_platt"], base["r2_platt"])
    other = predict_frozen(
        fit_frozen("r2_platt", train_x, 1 - train_y, calibration_x, calibration_y),
        validation_x,
    )
    assert not np.allclose(other["r0"], base["r0"])


def test_frozen_fit_accepts_only_the_choice_and_the_two_slices():
    assert list(inspect.signature(fit_frozen).parameters) == [
        "choice",
        "train_x",
        "train_labels",
        "calibration_x",
        "calibration_labels",
    ]


@pytest.mark.parametrize("problem", ["single_train", "single_calibration", "length"])
def test_frozen_fit_rejects_invalid_slices(data, problem):
    train_x, train_y = data["train"]
    calibration_x, calibration_y = data["calibration"]
    if problem == "single_train":
        train_y = np.zeros_like(train_y)
    elif problem == "single_calibration":
        calibration_y = np.ones_like(calibration_y)
    else:
        calibration_y = calibration_y[:-1]
    with pytest.raises(ValueError):
        fit_frozen("r2_platt", train_x, train_y, calibration_x, calibration_y)


@pytest.mark.parametrize("choice", sorted(FROZEN_CHOICES))
def test_frozen_description_matches_the_fold_description_and_is_json_safe(
    choice, fitted, data
):
    frozen = fit_frozen(choice, *data["train"], *data["calibration"])
    description = describe_frozen(frozen)
    json_bytes(description)
    base = FROZEN_CHOICES[choice]
    reference = describe_models(fitted)
    assert description["choice"] == choice
    assert description["r0"] == reference["r0"]
    assert description[base] == reference[base]
    assert description["platt"] == reference["platt"][base]
    assert description["platt"]["order_preserved"] is True


def test_log_odds_stays_finite_at_the_probability_limits():
    class Stub:
        def predict_proba(self, X):
            return np.array([[1.0, 0.0], [0.0, 1.0]])

    scores = LogOdds(Stub()).decision_function(np.zeros((2, 1)))
    assert np.all(np.isfinite(scores)) and scores[0] < 0 < scores[1]
