"""Doğrulanmış etiket/girdileri tarih bazında böler; saklı test kapalıdır."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from pydantic import Field, model_validator

from app.ml.features import FeatureRow
from app.ml.metrics import StartKey, Target, positive_clusters
from app.ml.reporting import json_bytes, verify_feature_outputs, verify_outputs

SPLIT_RULES = {
    "version": 1,
    "training_source": "cimri",
    "percent": [70, 15, 15],
    "cut_unit": "unique_labelled_anchor_dates",
    "purge": "target_end_strictly_before_next_start",
    "horizon_days": 7,
    "folds": 4,
    "validation": "last_four_complete_calendar_months_in_purged_development_span",
    "calibration_days": 30,
    "validation_tail_purge": True,
    "test_scoring_enabled": False,
}

LIMIT_LABELS = {
    "fewer_than_four_full_months": "Dört tam doğrulama ayı bulunamadı",
    "limited_fold": "En az bir kat boş veya tek sınıflı",
    "empty_reserved_test": "Saklı test bölümü boş",
    **{
        f"empty_{role}": f"{title} bölümü boş"
        for role, title in (
            ("train", "Eğitim"),
            ("calibration", "Kalibrasyon"),
            ("validation", "Doğrulama"),
        )
    },
    **{
        f"single_class_{role}": f"{title} bölümünde yalnız tek sınıf var"
        for role, title in (
            ("train", "Eğitim"),
            ("calibration", "Kalibrasyon"),
            ("validation", "Doğrulama"),
        )
    },
}


class Anchor(StartKey):
    target_end: date
    label: int | None = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _horizon(self):
        if self.target_end != self.anchor_day + timedelta(days=7):
            raise ValueError("Etiket hedef sonu başlangıç + 7 gün olmalı")
        return self


@dataclass(frozen=True)
class Sample:
    anchor: Anchor
    brand: str
    family: str


@dataclass(frozen=True)
class SplitInputs:
    samples: tuple[Sample, ...]
    snapshot_sha256: str
    input_manifests: dict[str, str]


@dataclass(frozen=True)
class SplitPlan:
    assignments: list[dict]
    folds: list[dict]
    report: dict


def _ordered_keys(keys):
    if any(left >= right for left, right in zip(keys, keys[1:])):
        raise ValueError("Başlangıç anahtarları sıralı ve tekil olmalı")


def load_split_inputs(labels_dir, features_dir):
    raw_labels = (labels_dir / "manifest.json").read_bytes()
    raw_features = (features_dir / "manifest.json").read_bytes()
    manifests = [json.loads(value) for value in (raw_labels, raw_features)]
    if any(not isinstance(value, dict) for value in manifests):
        raise ValueError("Girdi manifesti nesne olmalı")
    digest = manifests[0].get("snapshot_sha256")
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or manifests[1].get("snapshot_sha256") != digest
    ):
        raise ValueError("Etiket ve girdinin görüntü SHA-256 değerleri uyuşmuyor")
    if (
        verify_outputs(labels_dir, digest) != manifests[0]
        or verify_feature_outputs(features_dir, digest) != manifests[1]
    ):
        raise ValueError("Okuma sırasında girdi manifesti değişti")
    windows = (labels_dir / "windows.jsonl").read_bytes()
    features = (features_dir / "features.jsonl").read_bytes()
    for content, manifest, name in (
        (windows, manifests[0], "windows.jsonl"),
        (features, manifests[1], "features.jsonl"),
    ):
        if hashlib.sha256(content).hexdigest() != manifest["files"][name]:
            raise ValueError("Okuma sırasında girdi dosyası değişti")
    anchors = []
    for line in windows.splitlines():
        row = json.loads(line)
        anchors.append(
            Anchor.model_validate_json(
                json_bytes(
                    dict(
                        product_id=row["product_id"],
                        source=row["source"],
                        anchor_day=row["anchor_day"],
                        target_end=row["target_end"],
                        label=row["primary"]["label"],
                    )
                )
            )
        )
    rows = [FeatureRow.model_validate_json(line) for line in features.splitlines()]
    anchor_keys = [row.key for row in anchors]
    feature_keys = [
        (row.metadata.product_id, row.metadata.source, row.metadata.anchor_day)
        for row in rows
    ]
    _ordered_keys(anchor_keys)
    _ordered_keys(feature_keys)
    if anchor_keys != feature_keys:
        raise ValueError("Etiket ve girdi başlangıç anahtarları birebir eşleşmiyor")
    return SplitInputs(
        tuple(
            Sample(anchor, row.features.brand, row.features.family)
            for anchor, row in zip(anchors, rows)
        ),
        digest,
        dict(
            labels=hashlib.sha256(raw_labels).hexdigest(),
            features=hashlib.sha256(raw_features).hexdigest(),
        ),
    )


def _key_record(sample):
    row = sample.anchor
    return dict(product_id=row.product_id, source=row.source, anchor_day=row.anchor_day)


def _target(sample, role):
    return Target(
        **_key_record(sample),
        label=sample.anchor.label,
        role=role,
        brand=sample.brand,
        family=sample.family,
    )


def _stats(samples):
    positive = sum(row.anchor.label == 1 for row in samples)
    return dict(
        rows=len(samples),
        positive=positive,
        negative=len(samples) - positive,
        positive_rate=positive / len(samples) if samples else None,
        positive_window_clusters=positive_clusters(
            [_target(row, "validation") for row in samples]
        ),
    )


def _next_month(day):
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)


def _folds(development):
    if not development:
        return []
    first = min(row.anchor.anchor_day for row in development)
    last = max(row.anchor.anchor_day for row in development)
    month, months = first.replace(day=1), []
    while month <= last:
        following = _next_month(month)
        if month >= first and following - timedelta(days=1) <= last:
            months.append(month)
        month = following
    folds = []
    for start in months[-4:]:
        end, calibration_start = _next_month(start), start - timedelta(days=30)
        raw = dict(
            train=[
                row for row in development if row.anchor.anchor_day < calibration_start
            ],
            calibration=[
                row
                for row in development
                if calibration_start <= row.anchor.anchor_day < start
            ],
            validation=[
                row for row in development if start <= row.anchor.anchor_day < end
            ],
        )
        boundaries = dict(train=calibration_start, calibration=start, validation=end)
        members = {
            role: [row for row in rows if row.anchor.target_end < boundaries[role]]
            for role, rows in raw.items()
        }
        statistics = {role: _stats(rows) for role, rows in members.items()}
        limits = [
            f"{kind}_{role}"
            for role, stat in statistics.items()
            for kind in (
                ["empty"]
                if not stat["rows"]
                else (
                    ["single_class"]
                    if not stat["positive"] or not stat["negative"]
                    else []
                )
            )
        ]
        folds.append(
            dict(
                month=start.strftime("%Y-%m"),
                validation_start=start,
                validation_end=end - timedelta(days=1),
                calibration_start=calibration_start,
                members={
                    role: [_key_record(row) for row in rows]
                    for role, rows in members.items()
                },
                statistics=statistics,
                purged={role: len(raw[role]) - len(members[role]) for role in members},
                limitations=limits,
                status="limited" if limits else "ready",
            )
        )
    return folds


def build_split(samples):
    samples = list(samples)
    _ordered_keys([row.anchor.key for row in samples])
    eligible = [
        row
        for row in samples
        if row.anchor.source == "cimri" and row.anchor.label is not None
    ]
    days = sorted({row.anchor.anchor_day for row in eligible})
    cut_train, cut_validation = len(days) * 70 // 100, len(days) * 85 // 100
    periods = dict(
        train=days[:cut_train],
        validation=days[cut_train:cut_validation],
        test_reserved=days[cut_validation:],
    )
    day_roles = {day: role for role, period in periods.items() for day in period}
    assignments, members = [], {role: [] for role in periods}
    for sample in samples:
        row = sample.anchor
        if row.source == "own":
            role = "own_evaluation" if row.label is not None else "own_unlabelled"
        elif row.label is None:
            role = "unlabelled"
        else:
            role = day_roles[row.anchor_day]
            following = [
                period[0]
                for period in periods.values()
                if period and period[0] > row.anchor_day
            ]
            if following and row.target_end >= min(following):
                role = f"purged_{role}"
            else:
                members[role].append(sample)
        assignments.append(dict(**_key_record(sample), role=role))
    test_start = periods["test_reserved"][0] if periods["test_reserved"] else None
    development = [
        row
        for row in eligible
        if test_start is not None and row.anchor.target_end < test_start
    ]
    folds = _folds(development)
    limitations = []
    if len(folds) < 4:
        limitations.append("fewer_than_four_full_months")
    for role in ("train", "validation"):
        stat = _stats(members[role])
        if not stat["rows"]:
            limitations.append(f"empty_{role}")
        elif not stat["positive"] or not stat["negative"]:
            limitations.append(f"single_class_{role}")
    if not members["test_reserved"]:
        limitations.append("empty_reserved_test")
    if any(fold["limitations"] for fold in folds):
        limitations.append("limited_fold")
    partition_report = {}
    for role, period in periods.items():
        partition_report[role] = dict(
            first_anchor=period[0] if period else None,
            last_anchor=period[-1] if period else None,
            **(
                dict(rows=len(members[role]))
                if role == "test_reserved"
                else _stats(members[role])
            ),
        )
    own = [row for row in samples if row.anchor.source == "own"]
    report = dict(
        split_rules=SPLIT_RULES,
        unique_cimri_anchor_days=len(days),
        status="limited" if limitations else "ready",
        limitations=limitations,
        limitation_labels=LIMIT_LABELS,
        partitions=partition_report,
        assignment_counts=dict(
            sorted(Counter(row["role"] for row in assignments).items())
        ),
        own_evaluation=dict(
            rows=len(own),
            labelled_rows=sum(row.anchor.label is not None for row in own),
        ),
        folds=[
            {key: value for key, value in fold.items() if key != "members"}
            for fold in folds
        ],
        model_trained=False,
        test_opened=False,
        real_prediction_scores_computed=False,
    )
    return SplitPlan(assignments, folds, report)


def evaluation_targets(samples, plan, *, partition="validation", fold_index=None):
    if partition == "test_reserved":
        raise ValueError("Saklı test bu adımda puanlanamaz")
    if partition not in {"validation", "own_evaluation"}:
        raise ValueError(
            "Yalnız doğrulama veya kendi değerlendirme hedefleri alınabilir"
        )
    by_key = {row.anchor.key: row for row in samples}
    roles = {
        (row["product_id"], row["source"], row["anchor_day"]): row["role"]
        for row in plan.assignments
    }
    if fold_index is None:
        keys = [key for key, role in roles.items() if role == partition]
    else:
        if partition != "validation":
            raise ValueError("Kat yalnız doğrulama hedefleri için seçilebilir")
        if not 0 <= fold_index < len(plan.folds):
            raise ValueError("Kat numarası aralık dışında")
        keys = [
            (row["product_id"], row["source"], row["anchor_day"])
            for row in plan.folds[fold_index]["members"]["validation"]
        ]
    if any(roles.get(key) in {"test_reserved", "purged_validation"} for key in keys):
        raise ValueError("Saklı test bu adımda puanlanamaz")
    if any(key not in by_key or by_key[key].anchor.label is None for key in keys):
        raise ValueError("Değerlendirme başlangıcı yok veya etiketsiz")
    if fold_index is not None:
        fold = plan.folds[fold_index]
        if any(
            key[1] != "cimri"
            or not fold["validation_start"] <= key[2] <= fold["validation_end"]
            or by_key[key].anchor.target_end > fold["validation_end"]
            for key in keys
        ):
            raise ValueError("Doğrulama başlangıcı kat sınırlarına uymuyor")
    return [_target(by_key[key], partition) for key in keys]
