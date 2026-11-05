"""Anahtarlı tahminlerin ölçütleri.

Doğrulama ve kendi değerlendirme işlevleri saklı testi reddeder. Saklı testi
yalnız `score_reserved_test` ve `reserved_test_bootstrap` puanlar; onlar da
doğrulama hedeflerini reddeder.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Literal

from pydantic import Field

from app.contracts import Contract

METRIC_RULES = {
    "version": 1,
    "pr_auc": "average_precision_not_trapezoidal",
    "brier": "binary_mean_squared_probability_error",
    "log_loss": "float64_machine_epsilon_clip_labels_0_1",
    "calibration_bins": 10,
    "minimum_bin_support": 20,
    "minimum_breakdown_clusters": 5,
    "clusters": "same_product_overlapping_inclusive_positive_target_intervals",
    "bootstrap_block_days": 14,
    "bootstrap_repeats": 2000,
    "bootstrap_seed": 42,
    "bootstrap_confidence": 0.95,
    "bootstrap_minimum_valid": 1800,
    "bootstrap_minimum_calendar_days": 28,
}


class StartKey(Contract):
    product_id: int = Field(gt=0)
    source: Literal["own", "cimri"]
    anchor_day: date

    @property
    def key(self):
        return self.product_id, self.source, self.anchor_day


class Target(StartKey):
    label: int = Field(ge=0, le=1)
    role: Literal[
        "train", "calibration", "validation", "own_evaluation", "test_reserved"
    ]
    brand: str = Field(min_length=1)
    family: str = Field(min_length=1)


class Probability(StartKey):
    probability: float = Field(ge=0, le=1, allow_inf_nan=False)


def _guard(targets, role=None):
    if role == "test_reserved" or any(row.role == "test_reserved" for row in targets):
        raise ValueError("Saklı test bu adımda puanlanamaz")
    if role is not None and (
        role not in {"validation", "own_evaluation"}
        or any(row.role != role for row in targets)
    ):
        raise ValueError("Değerlendirme rolü uyuşmuyor")
    keys = [row.key for row in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Tekrarlı değerlendirme anahtarı")


def _reserved_guard(targets):
    if not targets or any(row.role != "test_reserved" for row in targets):
        raise ValueError(
            "Saklı test puanlaması yalnız boş olmayan saklı test hedeflerini alır"
        )
    keys = [row.key for row in targets]
    if len(keys) != len(set(keys)):
        raise ValueError("Tekrarlı değerlendirme anahtarı")


def _align(targets, predictions):
    keys = [row.key for row in targets]
    values = []
    for rows in predictions:
        rows = list(rows)
        if [row.key for row in rows] != keys:
            raise ValueError("Tahmin anahtarları veya sırası hedeflerle uyuşmuyor")
        values.append([row.probability for row in rows])
    return values


def _aligned(targets, *predictions, role):
    targets = list(targets)
    _guard(targets, role)
    return targets, _align(targets, predictions)


def _reserved_aligned(targets, *predictions):
    targets = list(targets)
    _reserved_guard(targets)
    return targets, _align(targets, predictions)


def positive_clusters(targets):
    targets = list(targets)
    _guard(targets)
    return _clusters(targets)


def _clusters(targets):
    intervals = defaultdict(list)
    for row in targets:
        if row.label == 1:
            intervals[row.product_id, row.source].append(
                (row.anchor_day + timedelta(days=1), row.anchor_day + timedelta(days=7))
            )
    count = 0
    for periods in intervals.values():
        end = None
        for left, right in sorted(periods):
            if end is None or left > end:
                count += 1
                end = right
            else:
                end = max(end, right)
    return count


def _calibration_bins(labels, probabilities):
    size = METRIC_RULES["calibration_bins"]
    bins = [[] for _ in range(size)]
    for label, probability in zip(labels, probabilities):
        bins[min(int(probability * size), size - 1)].append((label, probability))
    return [
        dict(
            lower=index / size,
            upper=(index + 1) / size,
            count=len(rows),
            mean_probability=sum(p for _, p in rows) / len(rows) if rows else None,
            observed_rate=sum(y for y, _ in rows) / len(rows) if rows else None,
            low_support=len(rows) < METRIC_RULES["minimum_bin_support"],
        )
        for index, rows in enumerate(bins)
    ]


def _scores(labels, probabilities, references):
    import numpy as np
    from sklearn.metrics import average_precision_score, log_loss

    n = len(labels)
    reasons = []
    if not n:
        return dict(
            rows=0,
            positive_rate=None,
            average_precision=None,
            brier=None,
            log_loss=None,
            brier_skill=None,
            reference_brier=None,
            reasons=["empty"],
            calibration=_calibration_bins([], []),
        )
    y, p, reference = (
        np.asarray(values, dtype=np.float64)
        for values in (labels, probabilities, references)
    )
    brier = float(np.mean((p - y) ** 2))
    reference_brier = float(np.mean((reference - y) ** 2))
    both = len(set(labels)) == 2
    if not both:
        reasons.append("single_class")
    if reference_brier == 0:
        reasons.append("reference_zero_loss")
    eps = np.finfo(np.float64).eps
    return dict(
        rows=n,
        positive_rate=float(np.mean(y)),
        average_precision=float(average_precision_score(y, p)) if both else None,
        brier=brier,
        log_loss=float(log_loss(y, np.clip(p, eps, 1 - eps), labels=[0, 1])),
        reference_brier=reference_brier,
        brier_skill=1 - brier / reference_brier if reference_brier else None,
        calibration=_calibration_bins(labels, probabilities),
        reasons=reasons,
    )


def score_predictions(targets, probabilities, references, *, role="validation"):
    targets, (p, r0) = _aligned(targets, probabilities, references, role=role)
    return _score_all(targets, p, r0)


def score_reserved_test(targets, probabilities, references):
    """Saklı testin tek puanlama girişi; doğrulama hedeflerini kabul etmez."""
    targets, (p, r0) = _reserved_aligned(targets, probabilities, references)
    return _score_all(targets, p, r0)


def _score_all(targets, p, r0):
    labels = [row.label for row in targets]
    result = _scores(labels, p, r0)
    result["positive_window_clusters"] = _clusters(targets)
    breakdowns, product_scores = {}, []
    for attribute in ("brand", "family", "product_id"):
        groups = defaultdict(list)
        for index, target in enumerate(targets):
            groups[str(getattr(target, attribute))].append(index)
        cells = {}
        for name, indices in sorted(groups.items()):
            subset = [targets[index] for index in indices]
            clusters = _clusters(subset)
            supported = clusters >= METRIC_RULES["minimum_breakdown_clusters"]
            scores = (
                _scores(
                    [labels[i] for i in indices],
                    [p[i] for i in indices],
                    [r0[i] for i in indices],
                )
                if supported
                else None
            )
            cells[name] = dict(
                rows=len(indices),
                positive_window_clusters=clusters,
                status="supported" if supported else "insufficient_clusters",
                scores=scores,
            )
            if attribute == "product_id" and supported:
                product_scores.append(scores)
        breakdowns[attribute] = cells
    result["breakdowns"] = breakdowns
    macro_scores = {}
    for name in ("average_precision", "brier", "log_loss", "brier_skill"):
        values = [item[name] for item in product_scores if item[name] is not None]
        macro_scores[name] = dict(
            value=sum(values) / len(values) if values else None, products=len(values)
        )
    result["macro"] = dict(
        total_products=len(breakdowns["product_id"]),
        supported_products=len(product_scores),
        scores=macro_scores,
    )
    return result


def calendar_block_indices(targets, rng):
    """Takvim günleri kırpılır; bir günün ürünleri asla bölünmez."""
    import numpy as np

    by_day = defaultdict(list)
    for index, target in enumerate(targets):
        by_day[target.anchor_day].append(index)
    first, last = min(by_day), max(by_day)
    span = (last - first).days + 1
    length = min(METRIC_RULES["bootstrap_block_days"], span)
    starts = rng.integers(0, span - length + 1, size=(span + length - 1) // length)
    sampled_days = (starts[:, None] + np.arange(length)).ravel()[:span]
    return [
        index
        for offset in sampled_days
        for index in by_day[first + timedelta(days=int(offset))]
    ]


def paired_bootstrap(targets, model, reference_model, *, role="validation"):
    targets, (model, reference_model) = _aligned(
        targets, model, reference_model, role=role
    )
    if role != "validation":
        raise ValueError(
            "Model seçimi güven aralığı yalnız doğrulama katlarından hesaplanır"
        )
    return _bootstrap(targets, model, reference_model)


def reserved_test_bootstrap(targets, model, reference_model):
    """Saklı test için aynı tarih bloklu AP farkı aralığı; tek giriş noktası."""
    targets, (model, reference_model) = _reserved_aligned(
        targets, model, reference_model
    )
    return _bootstrap(targets, model, reference_model)


def own_evaluation_bootstrap(targets, model, reference_model):
    """Kendi verisi için bilgi amaçlı AP farkı; seçim ve saklı test girişi değil."""
    targets = list(targets)
    _guard(targets, "own_evaluation")
    if any(row.source != "own" for row in targets):
        raise ValueError("Gölge güven aralığı yalnız kendi kaynağını kabul eder")
    model, reference_model = _align(targets, (model, reference_model))
    return _bootstrap(targets, model, reference_model)


def _bootstrap(targets, model, reference_model):
    import numpy as np
    from sklearn.metrics import average_precision_score

    span = (
        (
            max(row.anchor_day for row in targets)
            - min(row.anchor_day for row in targets)
        ).days
        + 1
        if targets
        else 0
    )
    result = dict(
        confidence=METRIC_RULES["bootstrap_confidence"],
        block_days=METRIC_RULES["bootstrap_block_days"],
        seed=METRIC_RULES["bootstrap_seed"],
        repeats=METRIC_RULES["bootstrap_repeats"],
        valid_repeats=0,
        invalid_repeats=0,
        point_difference=None,
        lower=None,
        upper=None,
        reasons=[],
    )
    labels = [row.label for row in targets]
    if len(set(labels)) < 2:
        result["reasons"].append("empty_or_single_class")
    if span < METRIC_RULES["bootstrap_minimum_calendar_days"]:
        result["reasons"].append("insufficient_calendar_span")
    if result["reasons"]:
        return result
    y = np.asarray(labels)
    a, b = np.asarray(model), np.asarray(reference_model)
    result["point_difference"] = float(
        average_precision_score(y, a) - average_precision_score(y, b)
    )
    rng = np.random.default_rng(result["seed"])
    differences = []
    for _ in range(result["repeats"]):
        indices = calendar_block_indices(targets, rng)
        if len(set(y[indices].tolist())) < 2:
            continue
        differences.append(
            float(
                average_precision_score(y[indices], a[indices])
                - average_precision_score(y[indices], b[indices])
            )
        )
    result["valid_repeats"] = len(differences)
    result["invalid_repeats"] = result["repeats"] - len(differences)
    if len(differences) < METRIC_RULES["bootstrap_minimum_valid"]:
        result["reasons"].append("insufficient_valid_repeats")
    else:
        tail = round((1 - result["confidence"]) / 2, 12)
        result["lower"], result["upper"] = map(
            float, np.quantile(differences, [tail, 1 - tail], method="linear")
        )
    return result


def metrics_schema():
    return dict(
        format_version=1,
        rules=METRIC_RULES,
        target_schema=Target.model_json_schema(),
        probability_schema=Probability.model_json_schema(),
        formulas={
            "average_precision": "sklearn average_precision_score; tek sınıfta NULL",
            "brier": "mean((p-y)^2)",
            "log_loss": "float64, labels=[0,1], eps uç sınırı",
            "brier_skill": "1-model_brier/reference_brier; sıfır referansta NULL",
            "macro": (
                "Yeterli ürünlerin eşit ağırlıklı ortalaması; " "ölçüt başına kapsama"
            ),
        },
        test_scoring_enabled=False,
    )
