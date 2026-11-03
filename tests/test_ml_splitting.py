"""Ortak tarih kesimleri, purge, ayrı kalibrasyon ve saklı test kapısı."""

from copy import deepcopy
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.ml.splitting import (
    FOLD_ROLES,
    Anchor,
    Sample,
    SplitInputs,
    build_split,
    evaluation_targets,
    final_samples,
    fold_samples,
    reserved_test_samples,
    reserved_test_targets,
)
from tests.support.ml import feature_values

FIRST = date(2025, 11, 1)


def samples(count=360, products=(1, 2), source="cimri"):
    return [
        Sample(
            Anchor(
                product_id=pid,
                source=source,
                anchor_day=FIRST + timedelta(days=day),
                target_end=FIRST + timedelta(days=day + 7),
                label=day % 2,
            ),
            f"Brand{pid}",
            f"Family{pid}",
        )
        for pid in products
        for day in range(count)
    ]


def ordered(rows):
    return sorted(rows, key=lambda row: row.anchor.key)


def roles(plan):
    return {
        (row["product_id"], row["source"], row["anchor_day"]): row["role"]
        for row in plan.assignments
    }


def test_unique_date_percentages_and_purge_counts():
    plan = build_split(samples())
    parts = plan.report["partitions"]
    assert parts["validation"]["first_anchor"] == FIRST + timedelta(days=252)
    assert parts["test_reserved"]["first_anchor"] == FIRST + timedelta(days=306)
    assert parts["train"]["rows"] == 245 * 2
    assert parts["validation"]["rows"] == 47 * 2
    assert parts["test_reserved"]["rows"] == 54 * 2
    assert plan.report["assignment_counts"]["purged_train"] == 14
    assert plan.report["assignment_counts"]["purged_validation"] == 14
    assert set(parts["test_reserved"]) == {"first_anchor", "last_anchor", "rows"}


def test_same_day_products_share_role_despite_product_density():
    rows = samples()
    baseline = build_split(rows)
    extra = samples(products=(3,))[:40]
    changed = build_split(ordered(rows + extra))
    for role in baseline.report["partitions"]:
        assert (
            changed.report["partitions"][role]["first_anchor"]
            == baseline.report["partitions"][role]["first_anchor"]
        )
    assignments = roles(changed)
    for row in extra:
        assert (
            assignments[row.anchor.key]
            == assignments[1, "cimri", row.anchor.anchor_day]
        )


def test_target_end_equal_to_boundary_is_removed_for_both_classes():
    plan = build_split(samples())
    assignments = roles(plan)
    assert assignments[1, "cimri", FIRST + timedelta(days=245)] == "purged_train"
    assert assignments[1, "cimri", FIRST + timedelta(days=244)] == "train"
    assert assignments[1, "cimri", FIRST + timedelta(days=299)] == "purged_validation"
    assert assignments[1, "cimri", FIRST + timedelta(days=298)] == "validation"


def test_four_complete_months_and_separate_purged_calibration():
    rows = samples()
    plan = build_split(rows)
    assert plan.report["status"] == "ready"
    assert [fold["month"] for fold in plan.folds] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
    ]
    by_key = {row.anchor.key: row.anchor for row in rows}
    train_counts = []
    for fold in plan.folds:
        assert (fold["validation_start"] - fold["calibration_start"]).days == 30
        sets = {
            role: {
                (item["product_id"], item["source"], item["anchor_day"])
                for item in members
            }
            for role, members in fold["members"].items()
        }
        assert not sets["train"] & sets["calibration"]
        assert not sets["calibration"] & sets["validation"]
        for key in sets["train"]:
            assert by_key[key].target_end < fold["calibration_start"]
        for key in sets["calibration"]:
            assert fold["calibration_start"] <= by_key[key].anchor_day
            assert by_key[key].target_end < fold["validation_start"]
        for key in sets["validation"]:
            assert fold["validation_start"] <= by_key[key].anchor_day
            assert by_key[key].target_end <= fold["validation_end"]
        assert fold["purged"]["calibration"] == 14
        assert fold["purged"]["validation"] == 14
        train_counts.append(len(sets["train"]))
    assert train_counts == sorted(set(train_counts))


def test_empty_selected_month_is_not_replaced_with_a_better_month():
    rows = [row for row in samples() if row.anchor.anchor_day.month != 5]
    plan = build_split(rows)
    may = next(fold for fold in plan.folds if fold["month"] == "2026-05")
    assert may["statistics"]["validation"]["rows"] == 0
    assert "empty_validation" in may["limitations"]
    assert plan.report["status"] == "limited"


def test_own_source_is_evaluation_only_and_does_not_change_cut_dates():
    base = build_split(samples())
    plan = build_split(ordered(samples() + samples(count=30, source="own")))
    assert plan.report["partitions"] == base.report["partitions"]
    assert plan.report["own_evaluation"] == {"rows": 60, "labelled_rows": 60}
    assert all(
        row["role"] == "own_evaluation"
        for row in plan.assignments
        if row["source"] == "own"
    )


def test_unlabelled_starts_do_not_enter_training():
    rows = samples()
    rows[0] = Sample(
        rows[0].anchor.model_copy(update={"label": None}), "Brand1", "Family1"
    )
    plan = build_split(rows)
    assert roles(plan)[rows[0].anchor.key] == "unlabelled"
    assert plan.report["unique_cimri_anchor_days"] == 360


def test_insufficient_history_single_class_and_empty_are_limited():
    assert (
        "fewer_than_four_full_months" in build_split(samples(60)).report["limitations"]
    )
    rows = [
        Sample(row.anchor.model_copy(update={"label": 0}), row.brand, row.family)
        for row in samples()
    ]
    result = build_split(rows)
    assert result.report["status"] == "limited"
    assert "single_class_train" in result.report["limitations"]
    assert build_split([]).report["status"] == "limited"


def test_held_out_labels_do_not_change_any_development_output():
    rows = samples()
    before = build_split(rows)
    assignments = roles(before)
    changed = [
        (
            Sample(
                row.anchor.model_copy(update={"label": 1 - row.anchor.label}),
                row.brand,
                row.family,
            )
            if assignments[row.anchor.key] == "test_reserved"
            else row
        )
        for row in rows
    ]
    after = build_split(changed)
    assert after.report == before.report
    assert after.folds == before.folds
    assert after.assignments == before.assignments


def test_reserved_partition_and_tampered_fold_cannot_yield_targets():
    rows = samples()
    plan = build_split(rows)
    with pytest.raises(ValueError, match="Saklı test"):
        evaluation_targets(rows, plan, partition="test_reserved")
    targets = evaluation_targets(rows, plan, fold_index=0)
    assert targets and all(row.role == "validation" for row in targets)
    tampered = deepcopy(plan)
    key = next(row for row in plan.assignments if row["role"] == "test_reserved")
    tampered.folds[0]["members"]["validation"].append(
        {name: key[name] for name in ("product_id", "source", "anchor_day")}
    )
    with pytest.raises(ValueError, match="Saklı test"):
        evaluation_targets(rows, tampered, fold_index=0)


def test_duplicate_keys_and_wrong_horizon_rejected():
    row = samples(1, products=(1,))[0]
    with pytest.raises(ValueError, match="sıralı ve tekil"):
        build_split([row, row])
    payload = row.anchor.model_dump()
    payload["target_end"] += timedelta(days=1)
    with pytest.raises(ValidationError, match="7 gün"):
        Anchor(**payload)


@pytest.mark.parametrize("kind", ["purged_validation", "old_train"])
def test_fold_selector_rejects_horizon_overlap_and_old_keys(kind):
    rows = samples()
    plan = deepcopy(build_split(rows))
    role = "purged_validation" if kind == "purged_validation" else "train"
    member = next(row for row in plan.assignments if row["role"] == role)
    plan.folds[0]["members"]["validation"] = [
        {name: member[name] for name in ("product_id", "source", "anchor_day")}
    ]
    with pytest.raises(ValueError):
        evaluation_targets(rows, plan, fold_index=0)


def inputs_for(rows):
    # Her satırın girdisi `history_days` ile kendi sırasını taşır; eşleşme görünür.
    return SplitInputs(
        samples=tuple(rows),
        features=tuple(
            feature_values(history_days=index + 1) for index in range(len(rows))
        ),
        snapshot_sha256="0" * 64,
        input_manifests={},
    )


def test_fold_samples_return_each_slice_with_its_own_feature_rows():
    rows = samples()
    plan = build_split(rows)
    inputs = inputs_for(rows)
    position = {row.anchor.key: index for index, row in enumerate(rows)}
    assert len(plan.folds) == 4
    for index, fold in enumerate(plan.folds):
        seen = set()
        for role in FOLD_ROLES:
            members = fold_samples(inputs, plan, index, role)
            keys = [sample.anchor.key for sample, _ in members]
            assert keys == [
                (item["product_id"], item["source"], item["anchor_day"])
                for item in fold["members"][role]
            ]
            assert keys and seen.isdisjoint(keys)
            seen.update(keys)
            for sample, features in members:
                assert sample.anchor.source == "cimri"
                assert sample.anchor.label is not None
                assert features.history_days == position[sample.anchor.key] + 1
        validation = fold_samples(inputs, plan, index, "validation")
        assert [sample.anchor.key for sample, _ in validation] == [
            target.key for target in evaluation_targets(rows, plan, fold_index=index)
        ]


@pytest.mark.parametrize("kind", ["reserved", "own", "unlabelled", "other_slice"])
def test_fold_samples_reject_reserved_own_unlabelled_and_out_of_slice_members(kind):
    rows = ordered(samples() + samples(products=(1,), source="own")[:60])
    plan = deepcopy(build_split(rows))
    changed = list(rows)
    members = plan.folds[0]["members"]
    names = ("product_id", "source", "anchor_day")
    if kind == "reserved":
        row = next(item for item in plan.assignments if item["role"] == "test_reserved")
        members["train"].append({name: row[name] for name in names})
    elif kind == "own":
        row = next(
            item for item in plan.assignments if item["role"] == "own_evaluation"
        )
        members["train"].append({name: row[name] for name in names})
    elif kind == "unlabelled":
        first = members["train"][0]
        index = next(
            position
            for position, row in enumerate(rows)
            if row.anchor.key == tuple(first[name] for name in names)
        )
        anchor = rows[index].anchor.model_copy(update={"label": None})
        changed[index] = Sample(anchor, rows[index].brand, rows[index].family)
    else:
        # Doğrulama ayının bir başlangıcının hedefi kalibrasyon sınırını aşar.
        members["train"].append(members["validation"][0])
    with pytest.raises(ValueError, match="Kat üyesi"):
        fold_samples(inputs_for(changed), plan, 0, "train")


def test_fold_samples_reject_unknown_role_and_fold_number():
    rows = samples()
    plan = build_split(rows)
    inputs = inputs_for(rows)
    with pytest.raises(ValueError, match="Kat rolü"):
        fold_samples(inputs, plan, 0, "test_reserved")
    with pytest.raises(ValueError, match="Kat numarası"):
        fold_samples(inputs, plan, 99, "train")


def final_keys(inputs, plan):
    return {
        role: [s.anchor.key for s, _ in final_samples(inputs, plan, role)]
        for role in ("train", "calibration")
    }


def test_final_samples_use_the_fold_slice_rule_with_the_test_as_scored_period():
    rows = samples()
    plan = build_split(rows)
    inputs = inputs_for(rows)
    test_start = FIRST + timedelta(days=306)
    calibration_start = test_start - timedelta(days=30)
    position = {row.anchor.key: index for index, row in enumerate(rows)}
    train = final_samples(inputs, plan, "train")
    calibration = final_samples(inputs, plan, "calibration")
    # Eğitim 0..268 (hedefi kalibrasyon sınırını aşan 269..275 temizlenir);
    # kalibrasyon 276..298 (hedefi saklı teste uzanan 299..305 temizlenir).
    assert len(train) == 269 * 2 and len(calibration) == 23 * 2
    for sample, features in train:
        assert sample.anchor.target_end < calibration_start
        assert features.history_days == position[sample.anchor.key] + 1
    for sample, features in calibration:
        assert calibration_start <= sample.anchor.anchor_day
        assert sample.anchor.target_end < test_start
        assert features.history_days == position[sample.anchor.key] + 1
    keys = final_keys(inputs, plan)
    assert keys["train"] == sorted(keys["train"])
    assert keys["calibration"] == sorted(keys["calibration"])
    assert not set(keys["train"]) & set(keys["calibration"])
    # Ana bölmenin eğitim, temizlenmiş eğitim ve doğrulama satırları kullanılır.
    used = {roles(plan)[key] for role in keys.values() for key in role}
    assert used == {"train", "purged_train", "validation"}
    reserved = {key for key, role in roles(plan).items() if role == "test_reserved"}
    assert reserved and reserved.isdisjoint(keys["train"] + keys["calibration"])


def test_final_samples_ignore_own_unlabelled_and_reserved_rows():
    rows = samples()
    plan = build_split(rows)
    base = final_keys(inputs_for(rows), plan)
    unlabelled = {(1, "cimri", FIRST + timedelta(days=day)) for day in (10, 280)}
    changed = ordered(
        [
            (
                Sample(
                    row.anchor.model_copy(update={"label": None}),
                    row.brand,
                    row.family,
                )
                if row.anchor.key in unlabelled
                else row
            )
            for row in rows
        ]
        + samples(products=(1,), source="own")[:60]
    )
    changed_plan = build_split(changed)
    result = final_keys(inputs_for(changed), changed_plan)
    assert result["train"] == [key for key in base["train"] if key not in unlabelled]
    assert result["calibration"] == [
        key for key in base["calibration"] if key not in unlabelled
    ]


def test_final_samples_do_not_depend_on_reserved_test_labels_or_features():
    rows = samples()
    plan = build_split(rows)
    reserved = {key for key, role in roles(plan).items() if role == "test_reserved"}
    flipped = [
        (
            Sample(
                row.anchor.model_copy(update={"label": 1 - row.anchor.label}),
                row.brand,
                row.family,
            )
            if row.anchor.key in reserved
            else row
        )
        for row in rows
    ]
    base_inputs = inputs_for(rows)
    features = tuple(
        feature_values(history_days=999) if row.anchor.key in reserved else value
        for row, value in zip(rows, base_inputs.features)
    )
    changed = SplitInputs(tuple(flipped), features, "0" * 64, {})
    changed_plan = build_split(flipped)
    assert changed_plan.assignments == plan.assignments
    for role in ("train", "calibration"):
        assert final_samples(changed, changed_plan, role) == final_samples(
            base_inputs, plan, role
        )


@pytest.mark.parametrize(
    "new_role", ["test_reserved", "purged_validation", "unlabelled"]
)
def test_final_samples_reject_a_development_row_with_a_foreign_role(new_role):
    rows = samples()
    plan = deepcopy(build_split(rows))
    victim = (1, "cimri", FIRST + timedelta(days=10))
    for row in plan.assignments:
        if (row["product_id"], row["source"], row["anchor_day"]) == victim:
            row["role"] = new_role
    with pytest.raises(ValueError, match="Son model satırı"):
        final_samples(inputs_for(rows), plan, "train")


def test_final_samples_reject_unknown_role_and_missing_reserved_test():
    rows = samples()
    plan = deepcopy(build_split(rows))
    inputs = inputs_for(rows)
    with pytest.raises(ValueError, match="Son model rolü"):
        final_samples(inputs, plan, "validation")
    with pytest.raises(ValueError, match="Son model rolü"):
        final_samples(inputs, plan, "test_reserved")
    plan.report["partitions"]["test_reserved"]["first_anchor"] = None
    with pytest.raises(ValueError, match="Saklı test bölümü boş"):
        final_samples(inputs, plan, "train")


def test_reserved_test_samples_are_the_reserved_rows_only():
    rows = ordered(samples() + samples(products=(1,), source="own")[:60])
    plan = build_split(rows)
    members = reserved_test_samples(inputs_for(rows), plan)
    assert len(members) == 54 * 2
    assert len(members) == plan.report["partitions"]["test_reserved"]["rows"]
    assert all(
        roles(plan)[sample.anchor.key] == "test_reserved" for sample, _ in members
    )
    targets = reserved_test_targets(members)
    assert {target.role for target in targets} == {"test_reserved"}
    assert [target.key for target in targets] == [
        sample.anchor.key for sample, _ in members
    ]
    # Eski puanlama yolu saklı testi yine reddeder; yalnız ayrı giriş noktası açar.
    with pytest.raises(ValueError, match="Saklı test"):
        evaluation_targets(rows, plan, partition="test_reserved")


@pytest.mark.parametrize("kind", ["count", "own", "empty"])
def test_reserved_test_samples_reject_a_plan_that_disagrees_with_the_rows(kind):
    rows = ordered(samples() + samples(products=(1,), source="own")[:60])
    plan = deepcopy(build_split(rows))
    if kind == "count":
        plan.report["partitions"]["test_reserved"]["rows"] += 1
    elif kind == "own":
        own = next(row for row in plan.assignments if row["role"] == "own_evaluation")
        own["role"] = "test_reserved"
        plan.report["partitions"]["test_reserved"]["rows"] += 1
    else:
        for row in plan.assignments:
            if row["role"] == "test_reserved":
                row["role"] = "unlabelled"
        plan.report["partitions"]["test_reserved"]["rows"] = 0
    with pytest.raises(ValueError, match="Saklı test"):
        reserved_test_samples(inputs_for(rows), plan)


def test_every_start_needs_exactly_one_feature_row():
    rows = samples(30, products=(1,))
    inputs = inputs_for(rows)
    with pytest.raises(ValueError, match="girdi satırı"):
        SplitInputs(inputs.samples, inputs.features[:-1], "0" * 64, {})
