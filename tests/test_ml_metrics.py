"""Anahtarlı ölçütler, olumlu pencere kümeleri ve tarih bloklu güven aralığı."""

from collections import Counter
from datetime import date, timedelta
from math import isfinite, log

import numpy as np
import pytest
from pydantic import ValidationError

from app.ml.metrics import (
    Probability,
    Target,
    calendar_block_indices,
    paired_bootstrap,
    positive_clusters,
    reserved_test_bootstrap,
    score_predictions,
    score_reserved_test,
)

DAY = date(2026, 1, 1)


def target(offset, label, product_id=1, role="validation"):
    return Target(
        product_id=product_id,
        source="cimri",
        anchor_day=DAY + timedelta(days=offset),
        label=label,
        role=role,
        brand=f"Brand{product_id}",
        family=f"Family{product_id}",
    )


def probabilities(targets, values):
    return [
        Probability(
            product_id=row.product_id,
            source=row.source,
            anchor_day=row.anchor_day,
            probability=float(value),
        )
        for row, value in zip(targets, values)
    ]


def score(labels, p, reference=None):
    targets = [target(index, label) for index, label in enumerate(labels)]
    return score_predictions(
        targets,
        probabilities(targets, p),
        probabilities(
            targets, reference if reference is not None else [0.5] * len(labels)
        ),
    )


def test_hand_calculated_probability_metrics():
    result = score([0, 1, 1], [0.1, 0.8, 0.6])
    assert result["average_precision"] == 1
    assert result["positive_rate"] == 2 / 3
    assert result["brier"] == pytest.approx(0.07)
    assert result["reference_brier"] == 0.25
    assert result["brier_skill"] == pytest.approx(0.72)
    assert result["log_loss"] == pytest.approx(-(log(0.9) + log(0.8) + log(0.6)) / 3)


def test_average_precision_is_not_trapezoidal_area():
    assert score([1, 0, 1], [0.8, 0.7, 0.6])["average_precision"] == pytest.approx(
        5 / 6
    )


def test_fold_specific_reference_vector_not_validation_prevalence():
    result = score([0, 1], [0.1, 0.9], [0.2, 0.8])
    assert result["reference_brier"] == pytest.approx(0.04)
    assert result["brier_skill"] == pytest.approx(0.75)


def test_empty_and_single_class_metrics_are_explicit():
    empty = score([], [])
    assert empty["rows"] == 0
    assert empty["brier"] is empty["average_precision"] is None
    assert len(empty["calibration"]) == 10
    result = score([0, 0], [0.2, 0.4], [0, 0])
    assert result["average_precision"] is None
    assert result["brier"] == pytest.approx(0.1)
    assert isfinite(result["log_loss"])
    assert result["brier_skill"] is None
    assert result["reasons"] == ["single_class", "reference_zero_loss"]


def test_endpoint_probabilities_only_clipped_for_log_loss():
    result = score([0, 1], [0, 1])
    assert result["brier"] == 0
    assert result["average_precision"] == 1
    assert 0 < result["log_loss"] < 1e-12
    assert isfinite(score([1, 0], [0, 1])["log_loss"])


def test_bin_edges_empty_bins_and_minimum_support():
    result = score([0, 1, 1, 0], [0, 0.1, 0.9, 1])
    bins = result["calibration"]
    assert bins[0]["count"] == 1
    assert bins[1]["count"] == 1
    assert bins[9]["count"] == 2
    assert bins[9]["mean_probability"] == 0.95
    assert bins[3]["observed_rate"] is None
    supported = score([0, 1] * 10, [0.25] * 20)["calibration"][2]
    assert supported["count"] == 20 and not supported["low_support"]
    assert supported["observed_rate"] == 0.5
    assert score([0] * 19, [0.25] * 19)["calibration"][2]["low_support"]


@pytest.mark.parametrize("value", [-0.01, 1.01, float("nan"), float("inf"), "0.5"])
def test_invalid_probabilities_rejected(value):
    with pytest.raises(ValidationError):
        Probability(product_id=1, source="cimri", anchor_day=DAY, probability=value)


@pytest.mark.parametrize("value", [-1, 2, None, True, 1.0])
def test_invalid_labels_rejected(value):
    with pytest.raises(ValidationError):
        target(0, value)


def test_key_order_length_and_duplicate_targets_rejected():
    rows = [target(0, 0), target(1, 1)]
    p = probabilities(rows, [0.1, 0.9])
    for changed in (p[::-1], p[:1]):
        with pytest.raises(ValueError, match="anahtarları"):
            score_predictions(rows, changed, p)
    with pytest.raises(ValueError, match="Tekrarlı"):
        score_predictions([rows[0], rows[0]], [p[0], p[0]], [p[0], p[0]])


def test_reserved_test_rejected_before_predictions_are_read():
    rows = [target(0, 0, role="test_reserved")]

    def forbidden():
        pytest.fail("Saklı tahminler okundu")
        yield

    with pytest.raises(ValueError, match="Saklı test"):
        score_predictions(rows, forbidden(), forbidden())
    with pytest.raises(ValueError, match="Saklı test"):
        paired_bootstrap(rows, forbidden(), forbidden())
    with pytest.raises(ValueError, match="Saklı test"):
        score_predictions([], [], [], role="test_reserved")


def reserved_pair():
    """Aynı anahtarlar ve olasılıklar, biri doğrulama biri saklı test rolünde."""
    values = [(day, day % 2, pid) for day in range(60) for pid in (1, 2)]
    validation = [target(*item) for item in values]
    reserved = [target(*item, role="test_reserved") for item in values]
    good = probabilities(validation, [0.9 if row.label else 0.1 for row in validation])
    bad = probabilities(validation, [0.1 if row.label else 0.9 for row in validation])
    return validation, reserved, good, bad


def test_reserved_scoring_gives_the_same_numbers_as_validation_scoring():
    validation, reserved, good, bad = reserved_pair()
    assert score_reserved_test(reserved, good, bad) == score_predictions(
        validation, good, bad
    )
    assert reserved_test_bootstrap(reserved, good, bad) == paired_bootstrap(
        validation, good, bad
    )
    interval = reserved_test_bootstrap(reserved, good, bad)
    assert interval["valid_repeats"] == interval["repeats"] == 2000
    assert 0 < interval["lower"] <= interval["upper"]


def test_reserved_entry_points_accept_only_non_empty_reserved_targets():
    validation, reserved, good, bad = reserved_pair()

    def forbidden():
        pytest.fail("Tahminler okundu")
        yield

    own = [target(0, 1, role="own_evaluation")]
    mixed = [reserved[0], validation[1]]
    for rows in (validation, own, mixed, []):
        with pytest.raises(ValueError, match="Saklı test puanlaması"):
            score_reserved_test(rows, forbidden(), forbidden())
        with pytest.raises(ValueError, match="Saklı test puanlaması"):
            reserved_test_bootstrap(rows, forbidden(), forbidden())
    with pytest.raises(ValueError, match="Tekrarlı"):
        score_reserved_test([reserved[0], reserved[0]], [good[0]] * 2, [bad[0]] * 2)
    with pytest.raises(ValueError, match="anahtarları"):
        score_reserved_test(reserved, good[::-1], bad)
    with pytest.raises(ValueError, match="anahtarları"):
        reserved_test_bootstrap(reserved, good, bad[:-1])


def test_old_entry_points_still_reject_reserved_targets_including_clusters():
    _, reserved, good, bad = reserved_pair()
    with pytest.raises(ValueError, match="Saklı test"):
        positive_clusters(reserved)
    with pytest.raises(ValueError, match="Saklı test"):
        score_predictions(reserved, good, bad)
    with pytest.raises(ValueError, match="Saklı test"):
        paired_bootstrap(reserved, good, bad)


def test_reserved_bootstrap_reports_a_short_span_like_the_validation_one():
    rows = [target(day, day % 2, role="test_reserved") for day in range(27)]
    p = probabilities(rows, [0.5] * len(rows))
    result = reserved_test_bootstrap(rows, p, p)
    assert result["reasons"] == ["insufficient_calendar_span"]
    assert result["lower"] is result["upper"] is None


def test_overlapping_chained_clusters_and_product_separation():
    rows = [target(offset, 1) for offset in (0, 6, 12, 19)] + [target(0, 1, 2)]
    assert positive_clusters(rows) == 3
    assert positive_clusters([target(0, 1), target(6, 0), target(12, 1)]) == 2


def test_breakdown_support_and_unweighted_product_macro():
    rows, p = [], []
    for pid, days in ((1, [0, 2]), (2, [0, 1, 2, 3])):
        for block in range(5):
            for day in days:
                label = int(day == 0)
                rows.append(target(block * 20 + day, label, pid))
                p.append(
                    (0.9 if label else 0.1) if pid == 1 else (0.4 if label else 0.6)
                )
    rows.extend([target(0, 1, 3), target(2, 0, 3)])
    p.extend([0.5, 0.5])
    result = score_predictions(
        rows, probabilities(rows, p), probabilities(rows, [0.5] * len(rows))
    )
    assert result["breakdowns"]["product_id"]["1"]["positive_window_clusters"] == 5
    assert result["breakdowns"]["product_id"]["3"]["scores"] is None
    assert result["macro"]["supported_products"] == 2
    assert result["macro"]["total_products"] == 3
    assert result["macro"]["scores"]["brier"]["value"] == pytest.approx(0.185)
    assert result["brier"] != pytest.approx(0.185)


def test_block_sampling_keeps_calendar_gaps_and_whole_product_days():
    rows = [target(day, day % 2, pid) for day in (0, 5, 30) for pid in (1, 2)]

    class FixedRng:
        def integers(self, low, high, size):
            assert (low, high, size) == (0, 18, 3)
            return np.array([0, 17, 5])

    indices = calendar_block_indices(rows, FixedRng())
    observed = Counter(rows[index].key for index in indices)
    for row in rows:
        assert observed[row.key] == (
            2 if row.anchor_day == DAY + timedelta(days=5) else 1
        )


def test_bootstrap_is_paired_reproducible_and_uses_declared_defaults():
    rows = [target(day, day % 2, pid) for day in range(60) for pid in (1, 2)]
    good = probabilities(rows, [0.9 if row.label else 0.1 for row in rows])
    bad = probabilities(rows, [0.1 if row.label else 0.9 for row in rows])
    result = paired_bootstrap(rows, good, bad)
    assert result == paired_bootstrap(rows, good, bad)
    assert result["valid_repeats"] == result["repeats"] == 2000
    assert result["confidence"] == 0.95
    assert result["block_days"] == 14 and result["seed"] == 42
    assert 0 < result["lower"] <= result["upper"]


def test_bootstrap_insufficient_span_or_valid_resamples_has_no_interval():
    rows = [target(day, day % 2) for day in range(27)]
    p = probabilities(rows, [0.5] * len(rows))
    assert paired_bootstrap(rows, p, p)["reasons"] == ["insufficient_calendar_span"]
    rows = [target(day, int(day == 0)) for day in range(60)]
    p = probabilities(rows, [0.5] * len(rows))
    result = paired_bootstrap(rows, p, p)
    assert result["valid_repeats"] < 1800
    assert result["lower"] is result["upper"] is None
    assert result["reasons"] == ["insufficient_valid_repeats"]
