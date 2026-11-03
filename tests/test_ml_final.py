"""Model dondurma: seçimin türetilmesi, son dilimler ve güvenli yükleme."""

import hashlib
import json
import pickle
from dataclasses import replace

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from app.ml import final
from app.ml.experiment import ExperimentInputs, load_experiment_inputs
from app.ml.final import (
    FINAL_RULES,
    choose_model,
    evaluate_reading,
    freeze_model,
    load_frozen_model,
    run_final_test,
)
from app.ml.metrics import METRIC_RULES
from app.ml.models import (
    FROZEN_CHOICES,
    design_matrix,
    fit_models,
    library_versions,
    predict_frozen,
    predict_models,
)
from app.ml.reporting import (
    FINAL_TEST_OUTPUT_FILES,
    MODEL_OUTPUT_FILES,
    json_bytes,
    verify_final_test_outputs,
    write_final_test_outputs,
    write_model_outputs,
)
from app.ml.splitting import FINAL_ROLES, SplitInputs, final_samples
from tests.support.ml import feature_values, write_experiment_evidence


@pytest.fixture(scope="module", autouse=True)
def fast_bootstrap():
    # Yalnız tekrar sayısı düşer; gerçek sayı ve yöntem tests/test_ml_metrics.py'de.
    patch = pytest.MonkeyPatch()
    patch.setitem(METRIC_RULES, "bootstrap_repeats", 100)
    patch.setitem(METRIC_RULES, "bootstrap_minimum_valid", 90)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def evidence(tmp_path_factory):
    return write_experiment_evidence(tmp_path_factory.mktemp("evidence"))


@pytest.fixture(scope="module")
def limited(tmp_path_factory):
    return write_experiment_evidence(tmp_path_factory.mktemp("limited"), count=10)


@pytest.fixture(scope="module")
def inputs(evidence):
    return load_experiment_inputs(
        evidence["labels"], evidence["features"], evidence["split"]
    )


@pytest.fixture(scope="module")
def frozen_result(inputs, evidence):
    return freeze_model(inputs, evidence["experiment"])


@pytest.fixture
def model_dir(inputs, frozen_result, tmp_path):
    directory = tmp_path / "model"
    write_model_outputs(directory, inputs, frozen_result)
    return directory


def manifest_sha(directory):
    return hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()


def retamper(directory, name=None, content=None, **manifest_changes):
    """Dosyayı ve manifest alanlarını değiştirir; manifestin parmak izlerini yeniler."""
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if name is not None:
        (directory / name).write_bytes(content)
        manifest["files"][name] = hashlib.sha256(content).hexdigest()
    manifest.update(manifest_changes)
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")
    return manifest_sha(directory)


@pytest.fixture
def no_unpickle(monkeypatch):
    def forbidden(data):
        pytest.fail("Denetimlerden önce pickle açıldı")

    monkeypatch.setattr(final.pickle, "loads", forbidden)


def test_model_is_derived_from_the_recorded_selection_status():
    expected = {"met": "lightgbm_platt", "not_met": "r2_platt"}
    assert FINAL_RULES["selection_to_model"] == expected
    for status, model in expected.items():
        assert choose_model({"selection": {"status": status}}) == model
        assert model in FROZEN_CHOICES
    for status in ("not_evaluable", "other", None):
        with pytest.raises(ValueError, match="değerlendirilemedi"):
            choose_model({"selection": {"status": status}})


def test_freeze_follows_the_experiment_report_and_uses_the_final_slices(
    inputs, evidence, frozen_result
):
    report = json.loads((evidence["experiment"] / "report.json").read_bytes())
    assert frozen_result.choice == choose_model(report)
    members = {
        role: final_samples(inputs.split, inputs.plan, role) for role in FINAL_ROLES
    }
    slices = frozen_result.document["slices"]
    for role in FINAL_ROLES:
        assert slices[role]["rows"] == len(members[role])
        assert slices[role]["positive"] == sum(
            sample.anchor.label for sample, _ in members[role]
        )
    assert slices["calibration"]["latest_target_end"] < slices["test_start"]
    assert slices["train"]["latest_target_end"] < slices["calibration_start"]
    keys = [
        (row["product_id"], row["source"], row["anchor_day"])
        for row in frozen_result.calibration_rows
    ]
    assert keys == [sample.anchor.key for sample, _ in members["calibration"]]
    scores = frozen_result.document["experiment_validation"]
    assert set(scores) == {"r0", frozen_result.choice}


def test_frozen_probabilities_equal_the_validated_fold_method(inputs, frozen_result):
    # Aynı dilimlerde `fit_models` (katların yöntemi) aynı olasılıkları vermeli.
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
    reference = predict_models(
        fit_models(
            matrices["train"],
            labels["train"],
            matrices["calibration"],
            labels["calibration"],
        ),
        matrices["calibration"],
    )
    rows = frozen_result.calibration_rows
    choice = frozen_result.choice
    assert [row["r0"] for row in rows] == [float(v) for v in reference["r0"]]
    assert [row[choice] for row in rows] == [float(v) for v in reference[choice]]


def test_freeze_does_not_depend_on_reserved_test_labels_or_features(
    inputs, evidence, frozen_result
):
    reserved = {
        (row["product_id"], row["source"], row["anchor_day"])
        for row in inputs.plan.assignments
        if row["role"] == "test_reserved"
    }
    assert reserved
    samples = tuple(
        (
            replace(
                sample,
                anchor=sample.anchor.model_copy(
                    update={"label": 1 - sample.anchor.label}
                ),
            )
            if sample.anchor.key in reserved
            else sample
        )
        for sample in inputs.split.samples
    )
    features = tuple(
        (
            feature_values(history_days=9999, ratio_min_30d=5.0)
            if sample.anchor.key in reserved
            else value
        )
        for sample, value in zip(inputs.split.samples, inputs.split.features)
    )
    changed = ExperimentInputs(
        SplitInputs(
            samples,
            features,
            inputs.split.snapshot_sha256,
            inputs.split.input_manifests,
        ),
        inputs.plan,
        inputs.split_manifest_sha256,
    )
    again = freeze_model(changed, evidence["experiment"])
    assert json_bytes(again.document) == json_bytes(frozen_result.document)
    assert again.calibration_rows == frozen_result.calibration_rows
    assert pickle.dumps(again.frozen, protocol=5) == pickle.dumps(
        frozen_result.frozen, protocol=5
    )


def test_freeze_does_change_when_a_calibration_label_changes(
    inputs, evidence, frozen_result, monkeypatch
):
    # Pozitif kontrol: yukarıdaki sızıntı testi gerçekten duyarlı mı?
    calibration = {
        sample.anchor.key
        for sample, _ in final_samples(inputs.split, inputs.plan, "calibration")
    }
    samples = tuple(
        (
            replace(
                sample,
                anchor=sample.anchor.model_copy(
                    update={"label": 1 - sample.anchor.label}
                ),
            )
            if sample.anchor.key in calibration
            else sample
        )
        for sample in inputs.split.samples
    )
    changed = ExperimentInputs(
        SplitInputs(
            samples,
            inputs.split.features,
            inputs.split.snapshot_sha256,
            inputs.split.input_manifests,
        ),
        inputs.plan,
        inputs.split_manifest_sha256,
    )
    # Etiketi değişen satırlar deney tahmin dosyasının doğrulama üyesi olabilir.
    monkeypatch.setattr(final, "verify_experiment_outputs", lambda *args: None)
    again = freeze_model(changed, evidence["experiment"])
    assert again.calibration_rows != frozen_result.calibration_rows


def test_freeze_rejects_a_not_evaluable_experiment(limited):
    inputs = load_experiment_inputs(
        limited["labels"], limited["features"], limited["split"]
    )
    report = json.loads((limited["experiment"] / "report.json").read_bytes())
    assert report["selection"]["status"] == "not_evaluable"
    with pytest.raises(ValueError, match="değerlendirilemedi"):
        freeze_model(inputs, limited["experiment"])


def test_freeze_rejects_an_experiment_made_from_other_inputs(inputs, limited):
    with pytest.raises(ValueError):
        freeze_model(inputs, limited["experiment"])


def test_written_model_loads_and_reproduces_the_recorded_calibration(
    inputs, frozen_result, model_dir
):
    assert {path.name for path in model_dir.iterdir()} == {
        *MODEL_OUTPUT_FILES,
        "manifest.json",
    }
    loaded = load_frozen_model(model_dir, inputs, manifest_sha(model_dir))
    assert loaded.manifest["choice"] == frozen_result.choice
    assert loaded.manifest["test_opened"] is False
    assert loaded.manifest["libraries"] == library_versions()
    assert loaded.manifest_sha256 == manifest_sha(model_dir)
    matrix = design_matrix(
        [
            features
            for _, features in final_samples(inputs.split, inputs.plan, "calibration")
        ]
    )
    again = predict_frozen(loaded.frozen, matrix)
    assert [float(v) for v in again[frozen_result.choice]] == [
        row[frozen_result.choice] for row in frozen_result.calibration_rows
    ]
    assert json.loads((model_dir / "model.json").read_bytes())["choice"] == (
        frozen_result.choice
    )


@pytest.mark.parametrize("wrong", ["0" * 64, "abc", "", None, "G" * 64])
def test_a_manifest_that_is_not_the_expected_one_never_opens_the_pickle(
    inputs, model_dir, no_unpickle, wrong
):
    with pytest.raises(ValueError, match="SHA-256"):
        load_frozen_model(model_dir, inputs, wrong)


def test_changed_pickle_fails_its_fingerprint_before_it_is_opened(
    inputs, model_dir, no_unpickle
):
    expected = manifest_sha(model_dir)
    (model_dir / "model.pkl").write_bytes(b"not the frozen model")
    with pytest.raises(ValueError, match="parmak izi"):
        load_frozen_model(model_dir, inputs, expected)


def test_other_library_versions_are_rejected_before_the_pickle_is_opened(
    inputs, model_dir, no_unpickle
):
    libraries = dict(library_versions(), scikit_learn="0.0.0")
    expected = retamper(model_dir, libraries=libraries)
    with pytest.raises(ValueError, match="kütüphane sürümleri"):
        load_frozen_model(model_dir, inputs, expected)


@pytest.mark.parametrize(
    "change",
    [
        dict(test_opened=True),
        dict(choice="r1_platt"),
        dict(format_version=2),
        dict(final_rules={**FINAL_RULES, "version": 2}),
        dict(experiment_manifest_sha256="short"),
    ],
)
def test_manifest_contradicting_the_code_or_the_rules_is_rejected(
    inputs, model_dir, no_unpickle, change
):
    expected = retamper(model_dir, **change)
    with pytest.raises(ValueError, match="Model manifesti"):
        load_frozen_model(model_dir, inputs, expected)


def test_model_made_from_other_input_manifests_is_rejected(
    inputs, model_dir, no_unpickle
):
    other = replace(inputs, split_manifest_sha256="1" * 64)
    with pytest.raises(ValueError, match="Model manifesti"):
        load_frozen_model(model_dir, other, manifest_sha(model_dir))


def test_choice_that_the_recorded_selection_does_not_give_is_rejected(
    inputs, model_dir, no_unpickle
):
    document = json.loads((model_dir / "model.json").read_bytes())
    document["selection"]["status"] = (
        "met" if document["selection"]["status"] == "not_met" else "not_met"
    )
    expected = retamper(model_dir, "model.json", json_bytes(document) + b"\n")
    with pytest.raises(ValueError, match="seçim sonucundan"):
        load_frozen_model(model_dir, inputs, expected)


def test_a_pickle_that_cannot_be_opened_is_a_clear_error(inputs, model_dir):
    expected = retamper(model_dir, "model.pkl", b"garbage that is not a pickle")
    with pytest.raises(ValueError, match="açılamadı"):
        load_frozen_model(model_dir, inputs, expected)


def test_a_pickle_of_the_wrong_object_is_rejected(inputs, model_dir):
    expected = retamper(model_dir, "model.pkl", pickle.dumps({"choice": "r2_platt"}))
    with pytest.raises(ValueError, match="manifestteki modeli"):
        load_frozen_model(model_dir, inputs, expected)


def test_model_that_does_not_reproduce_the_recorded_probabilities_is_rejected(
    inputs, frozen_result, model_dir
):
    rows = [
        json.loads(line)
        for line in (model_dir / "calibration_predictions.jsonl")
        .read_bytes()
        .splitlines()
    ]
    rows[0][frozen_result.choice] = min(0.99, rows[0][frozen_result.choice] + 0.01)
    content = b"".join(json_bytes(row) + b"\n" for row in rows)
    expected = retamper(model_dir, "calibration_predictions.jsonl", content)
    with pytest.raises(ValueError, match="yeniden üretmiyor"):
        load_frozen_model(model_dir, inputs, expected)


def test_calibration_file_with_a_reserved_test_key_is_rejected(
    inputs, model_dir, no_unpickle
):
    reserved = next(
        row for row in inputs.plan.assignments if row["role"] == "test_reserved"
    )
    row = dict(
        product_id=reserved["product_id"],
        source=reserved["source"],
        anchor_day=reserved["anchor_day"].isoformat(),
        label=0,
        r0=0.1,
    )
    choice = json.loads((model_dir / "manifest.json").read_bytes())["choice"]
    row[choice] = 0.1
    expected = retamper(
        model_dir, "calibration_predictions.jsonl", json_bytes(row) + b"\n"
    )
    with pytest.raises(ValueError, match="saklı testsiz"):
        load_frozen_model(model_dir, inputs, expected)


def test_loaded_model_ranks_like_the_original_on_fresh_rows(
    inputs, frozen_result, model_dir
):
    loaded = load_frozen_model(model_dir, inputs, manifest_sha(model_dir))
    rng = np.random.default_rng(3)
    rows = [
        feature_values(
            ratio_min_30d=float(1 + rng.random() * 0.3),
            log_return_7d=float(rng.normal(0, 0.05)),
            days_since_drop_30d=int(rng.integers(0, 31)),
        )
        for _ in range(40)
    ]
    matrix = design_matrix(rows)
    first = predict_frozen(frozen_result.frozen, matrix)
    second = predict_frozen(loaded.frozen, matrix)
    for name in first:
        assert np.array_equal(first[name], second[name])


# --- Saklı testin tek açılışı ---------------------------------------------------


def reserved_keys(inputs):
    return {
        (row["product_id"], row["source"], row["anchor_day"])
        for row in inputs.plan.assignments
        if row["role"] == "test_reserved"
    }


@pytest.fixture(scope="module")
def shared_model(inputs, frozen_result, tmp_path_factory):
    directory = tmp_path_factory.mktemp("shared") / "model"
    write_model_outputs(directory, inputs, frozen_result)
    return directory


@pytest.fixture(scope="module")
def loaded(inputs, shared_model):
    return load_frozen_model(shared_model, inputs, manifest_sha(shared_model))


@pytest.fixture(scope="module")
def final_result(inputs, loaded):
    return run_final_test(inputs, loaded)


@pytest.fixture
def final_dir(inputs, final_result, tmp_path):
    directory = tmp_path / "final"
    write_final_test_outputs(directory, inputs, final_result)
    return directory


def test_final_test_scores_exactly_the_reserved_rows_with_the_frozen_model(
    inputs, loaded, final_result
):
    report, rows = final_result.report, final_result.predictions
    choice = loaded.frozen.choice
    keys = [(row["product_id"], row["source"], row["anchor_day"]) for row in rows]
    assert len(keys) == len(set(keys)) and set(keys) == reserved_keys(inputs)
    assert report["reserved_test"]["rows"] == len(rows)
    assert report["choice"] == choice
    assert report["model_manifest_sha256"] == loaded.manifest_sha256
    assert (report["test_opened"], report["model_changed"]) == (True, False)
    assert report["own_source_scored"] is False
    labels = [row["label"] for row in rows]
    assert report["reserved_test"]["positives"] == sum(labels)
    # Bağımsız yeniden hesap: kayıtlı olasılıklardan AP ve Brier.
    model_p = [row[choice] for row in rows]
    reference_p = [row["r0"] for row in rows]
    score = report["scores"][choice]
    assert score["average_precision"] == pytest.approx(
        average_precision_score(labels, model_p)
    )
    assert score["brier"] == pytest.approx(
        np.mean((np.array(model_p) - np.array(labels)) ** 2)
    )
    assert report["scores"]["r0"]["brier_skill"] == pytest.approx(0.0)
    assert score["brier_skill"] == pytest.approx(
        1
        - np.mean((np.array(model_p) - labels) ** 2)
        / np.mean((np.array(reference_p) - labels) ** 2)
    )
    assert report["experiment_validation"] == loaded.document["experiment_validation"]


def test_reserved_labels_change_the_scores_but_never_the_probabilities(
    inputs, loaded, final_result
):
    reserved = reserved_keys(inputs)
    samples = tuple(
        (
            replace(
                sample,
                anchor=sample.anchor.model_copy(
                    update={"label": 1 - sample.anchor.label}
                ),
            )
            if sample.anchor.key in reserved
            else sample
        )
        for sample in inputs.split.samples
    )
    changed = ExperimentInputs(
        SplitInputs(
            samples,
            inputs.split.features,
            inputs.split.snapshot_sha256,
            inputs.split.input_manifests,
        ),
        inputs.plan,
        inputs.split_manifest_sha256,
    )
    again = run_final_test(changed, loaded)
    name = loaded.frozen.choice
    assert [row[name] for row in again.predictions] == [
        row[name] for row in final_result.predictions
    ]
    assert [row["label"] for row in again.predictions] != [
        row["label"] for row in final_result.predictions
    ]
    assert again.report["scores"][name] != final_result.report["scores"][name]


@pytest.mark.parametrize(
    "skill, lower, status",
    [
        (0.1, 0.02, "met"),
        (0.0, 0.02, "not_met"),
        (0.1, 0.0, "not_met"),
        (-0.1, None, "not_met"),
        (None, -0.01, "not_met"),
        (0.1, None, "not_evaluable"),
        (None, 0.01, "not_evaluable"),
        (None, None, "not_evaluable"),
    ],
)
def test_reading_conditions_have_three_states_and_never_decide_the_model(
    skill, lower, status
):
    interval = dict(point_difference=0.1, lower=lower, upper=0.3, reasons=[])
    result = evaluate_reading(dict(brier_skill=skill), interval)
    assert result["status"] == status
    assert result["decides_model"] is False
    assert [item["name"] for item in result["conditions"]] == list(
        FINAL_RULES["reserved_test"]["read_conditions"]
    )


def test_written_final_test_verifies_and_is_bound_to_the_model(
    inputs, loaded, final_dir
):
    manifest = verify_final_test_outputs(final_dir, inputs, loaded.manifest_sha256)
    assert {path.name for path in final_dir.iterdir()} == {
        *FINAL_TEST_OUTPUT_FILES,
        "manifest.json",
    }
    assert manifest["test_opened"] is True
    assert manifest["model_manifest_sha256"] == loaded.manifest_sha256
    with pytest.raises(ValueError, match="manifesti"):
        verify_final_test_outputs(final_dir, inputs, "1" * 64)


def test_final_test_with_a_changed_fingerprint_is_rejected(inputs, loaded, final_dir):
    (final_dir / "report.md").write_bytes(b"changed")
    with pytest.raises(ValueError, match="parmak izi"):
        verify_final_test_outputs(final_dir, inputs, loaded.manifest_sha256)


@pytest.mark.parametrize("problem", ["missing_row", "wrong_label", "foreign_key"])
def test_final_test_predictions_must_match_the_reserved_rows(
    inputs, loaded, final_dir, problem
):
    rows = [
        json.loads(line)
        for line in (final_dir / "predictions.jsonl").read_bytes().splitlines()
    ]
    if problem == "missing_row":
        rows = rows[:-1]
    elif problem == "wrong_label":
        rows[0]["label"] = 1 - rows[0]["label"]
    else:
        validation = next(
            row for row in inputs.plan.assignments if row["role"] == "validation"
        )
        rows[0].update(
            product_id=validation["product_id"],
            anchor_day=validation["anchor_day"].isoformat(),
        )
    content = b"".join(json_bytes(row) + b"\n" for row in rows)
    retamper(final_dir, "predictions.jsonl", content)
    with pytest.raises(ValueError, match="Saklı test"):
        verify_final_test_outputs(final_dir, inputs, loaded.manifest_sha256)


@pytest.mark.parametrize(
    "flag, value",
    [
        ("test_opened", False),
        ("own_source_scored", True),
        ("model_changed", True),
    ],
)
def test_final_test_report_flags_must_state_what_really_happened(
    inputs, loaded, final_dir, flag, value
):
    report = json.loads((final_dir / "report.json").read_bytes())
    report[flag] = value
    retamper(final_dir, "report.json", json_bytes(report) + b"\n")
    with pytest.raises(ValueError, match="sözleşmeye"):
        verify_final_test_outputs(final_dir, inputs, loaded.manifest_sha256)
