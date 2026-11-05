"""Değişmez gölge kayıtlarını yeni görüntüdeki gerçek sonuçlarla değerlendirir."""

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.ml import shadow
from app.ml.experiment import load_experiment_inputs
from app.ml.features import FEATURE_RULES, feature_rows
from app.ml.labels import RULES as LABEL_RULES
from app.ml.labels import relaxed_windows
from app.ml.metrics import (
    METRIC_RULES,
    Probability,
    Target,
    own_evaluation_bootstrap,
    score_predictions,
)
from app.ml.reporting import json_bytes, verify_model_outputs
from app.ml.series import ISTANBUL, build_series, dates
from app.ml.splitting import final_samples

OUTPUT_FILES = ("evaluations.jsonl", "report.json", "report.md")
STATUS_TITLES = {
    "met": "Karşılandı",
    "not_met": "Karşılanmadı",
    "not_evaluable": "Değerlendirilemedi",
}
GROUP_TITLES = {
    "main": "Asıl sonuç (y_sabit, gösterilebilir)",
    "all_eligible": "Tüm uygun kayıtlar (y_sabit)",
    "tracked_showable": "Gösterilebilir kayıtlar (y_izlenen)",
    "tracked_all": "Tüm uygun kayıtlar (y_izlenen)",
    "paired_fixed": "İki etiketi de olanlar (y_sabit)",
    "paired_tracked": "İki etiketi de olanlar (y_izlenen)",
}
SLICE_TITLES = {
    "november": "Kasım",
    "outside_november": "Kasım dışı",
    "missing_at_most_10_percent": "Eksik gün oranı ≤ %10",
    "missing_over_10_percent": "Eksik gün oranı > %10",
    "before_22_november": "22 Kasım öncesi",
    "from_22_november": "22 Kasım ve sonrası",
}
TIMING_TITLES = {
    "on_time": "Ertesi gün kaydedilen",
    "initial_backfill": "İlk toplu doldurmada geriye dönük",
    "late": "Sonraki geç kayıtlar",
}
EVALUATION_RULES = {
    "version": 1,
    "source": "own",
    "primary_label": "y_sabit",
    "primary_population": "labelled_history_at_least_30_and_showable",
    "minimum_calendar_span": 60,
    "november_first": "2026-11-01",
    "november_last": "2026-11-30",
    "november_coverage": "inclusive_anchor_span",
    "minimum_distinct_days_outside_november": 14,
    "minimum_positive_clusters": 30,
    "maximum_mean_gap": 0.05,
    "maximum_supported_bin_gap": 0.15,
    "floating_roundoff_tolerance": 1e-12,
    "insufficient_readiness": "not_evaluable",
    "initial_backfill": "late_rows_in_earliest_snapshot_batch",
    "final_evaluation_date": "2027-01-05",
    "information_cutoff": "2026-11-22",
    "information_missing_ratio_cutoff": 0.10,
}
ROW_FIELDS = shadow.ROW_FIELDS | {
    "role",
    "record_folder",
    "recorded_at",
    "timing",
    "target_end",
    "primary",
    "tracked",
}


@dataclass(frozen=True)
class EvaluationModel:
    choice: str
    reference_rate: float
    families: frozenset
    manifest_sha256: str


@dataclass(frozen=True)
class EvaluationResult:
    report: dict
    rows: list


def _json(value):
    return json.loads(json_bytes(value))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("Kayıt zamanı UTC olmalı")
    return parsed


def _rules():
    return dict(
        evaluation=EVALUATION_RULES,
        metrics=METRIC_RULES,
        labels=LABEL_RULES,
        features=FEATURE_RULES,
        shadow=shadow.SHADOW_RULES,
    )


def load_evaluation_model(config):
    """Kanıtları doğrular; pickle açmadan yalnız model özeti ve R0 okunur."""
    model_dir = shadow.resolve_path(config.evidence.model)
    if _sha(model_dir / "manifest.json") != config.model_manifest_sha256:
        raise ValueError("Ön kayıtlı model manifest SHA-256'sı tutmuyor")
    inputs = load_experiment_inputs(
        shadow.resolve_path(config.evidence.labels),
        shadow.resolve_path(config.evidence.features),
        shadow.resolve_path(config.evidence.split),
    )
    manifest = verify_model_outputs(model_dir, inputs)
    document = json.loads((model_dir / "model.json").read_bytes())
    rate = document["model"]["r0"]["rate"]
    if type(rate) is not float or not math.isfinite(rate) or not 0 <= rate <= 1:
        raise ValueError("Dondurulan modelin R0 oranı geçerli değil")
    families = frozenset(
        features.family
        for _, features in final_samples(inputs.split, inputs.plan, "train")
    )
    return EvaluationModel(
        manifest["choice"], rate, families, config.model_manifest_sha256
    )


def read_inventory(config, captured_at):
    """Kilit yalnız envanter okunurken tutulur; kayıtlar bellekte sabitlenir."""
    root = shadow.resolve_path(config.records_dir)
    origins, rows, incomplete = [], [], []
    with shadow.record_lock(root):
        shadow.recorded_keys(root, config.model_manifest_sha256)
        for folder in sorted(root.glob(f"{shadow.RECORD_PREFIX}*")):
            if not folder.is_dir():
                continue
            if not (folder / "manifest.json").is_file():
                incomplete.append(folder.name)
                continue
            manifest, records = shadow.read_shadow_outputs(folder)
            recorded_at = _utc(manifest["snapshot_captured_at"])
            closed = recorded_at.astimezone(ISTANBUL).date() - timedelta(days=1)
            if (
                not re.fullmatch(r"[0-9a-f]{64}", manifest["snapshot_sha256"])
                or manifest["last_closed_day"] != closed.isoformat()
            ):
                raise ValueError("Kayıt görüntüsünün başlık bilgisi tutarsız")
            if recorded_at > captured_at:
                raise ValueError("Değerlendirme görüntüsü kayıt görüntüsünden eski")
            if manifest["start_day"] != config.start_day.isoformat():
                raise ValueError("Kayıt başlangıç günü gölge ayarıyla uyuşmuyor")
            origins.append(
                dict(
                    folder=folder.name,
                    manifest_sha256=_sha(folder / "manifest.json"),
                    snapshot_sha256=manifest["snapshot_sha256"],
                    captured_at=manifest["snapshot_captured_at"],
                    choice=manifest["choice"],
                )
            )
            rows.extend(
                dict(
                    row,
                    record_folder=folder.name,
                    recorded_at=manifest["snapshot_captured_at"],
                )
                for row in records
            )
    rows.sort(key=lambda row: (row["product_id"], row["anchor_day"]))
    return origins, rows, incomplete


def _eligible(row, target):
    return (
        row["probabilities"] is not None
        and row["features"]["history_days"] >= 30
        and row[target]["label"] in (0, 1)
    )


def _selections(rows):
    primary = [row for row in rows if _eligible(row, "primary")]
    tracked = [row for row in rows if _eligible(row, "tracked")]
    main = [row for row in primary if row["showable"]]
    paired = [row for row in main if _eligible(row, "tracked")]
    return dict(
        main=(main, "primary"),
        all_eligible=(primary, "primary"),
        tracked_showable=([row for row in tracked if row["showable"]], "tracked"),
        tracked_all=(tracked, "tracked"),
        paired_fixed=(paired, "primary"),
        paired_tracked=(paired, "tracked"),
    )


def _vectors(rows, target, choice):
    targets = [
        Target(
            product_id=row["product_id"],
            source="own",
            anchor_day=date.fromisoformat(row["anchor_day"]),
            label=row[target]["label"],
            role="own_evaluation",
            brand=row["features"]["brand"],
            family=row["features"]["family"],
        )
        for row in rows
    ]
    probabilities = [
        Probability(
            **dict(
                target.model_dump(include={"product_id", "source", "anchor_day"}),
                probability=row["probabilities"][choice],
            )
        )
        for target, row in zip(targets, rows)
    ]
    references = [
        Probability(
            **dict(
                target.model_dump(include={"product_id", "source", "anchor_day"}),
                probability=row["probabilities"]["r0"],
            )
        )
        for target, row in zip(targets, rows)
    ]
    return targets, probabilities, references


def _score_rows(rows, target, choice):
    targets, probabilities, references = _vectors(rows, target, choice)
    return {
        "r0": score_predictions(targets, references, references, role="own_evaluation"),
        choice: score_predictions(
            targets, probabilities, references, role="own_evaluation"
        ),
    }


def _within(value, limit):
    return value <= limit or math.isclose(value, limit, rel_tol=0, abs_tol=1e-12)


def evaluate_gate(targets, score):
    """Önce veri desteği, sonra ön kayıtlı performans koşulları değerlendirilir."""
    days = sorted({row.anchor_day for row in targets})
    first, last = (days[0], days[-1]) if days else (None, None)
    span = (last - first).days + 1 if days else 0
    november_first = date.fromisoformat(EVALUATION_RULES["november_first"])
    november_last = date.fromisoformat(EVALUATION_RULES["november_last"])
    outside = sum(not november_first <= day <= november_last for day in days)
    readiness = [
        dict(name="calendar_span", value=span, limit=60, passed=span >= 60),
        dict(
            name="november_covered",
            value=bool(days and first <= november_first and last >= november_last),
            passed=bool(days and first <= november_first and last >= november_last),
        ),
        dict(
            name="outside_november_days", value=outside, limit=14, passed=outside >= 14
        ),
        dict(
            name="positive_clusters",
            value=score["positive_window_clusters"],
            limit=30,
            passed=score["positive_window_clusters"] >= 30,
        ),
    ]
    bins = score["calibration"]
    mean = (
        sum(item["count"] * item["mean_probability"] for item in bins if item["count"])
        / score["rows"]
        if score["rows"]
        else None
    )
    gap = abs(mean - score["positive_rate"]) if mean is not None else None
    supported = [item for item in bins if not item["low_support"]]
    maximum_gap = max(
        (abs(item["mean_probability"] - item["observed_rate"]) for item in supported),
        default=None,
    )
    skill = score["brier_skill"]
    performance = [
        dict(
            name="brier_skill",
            value=skill,
            limit=0,
            passed=None if skill is None else skill > 0,
        ),
        dict(
            name="mean_gap",
            value=gap,
            limit=0.05,
            passed=None if gap is None else _within(gap, 0.05),
        ),
        dict(
            name="supported_bin_gap",
            value=maximum_gap,
            limit=0.15,
            passed=None if maximum_gap is None else _within(maximum_gap, 0.15),
        ),
    ]
    if not all(item["passed"] for item in readiness):
        status = "not_evaluable"
    elif any(item["passed"] is False for item in performance):
        status = "not_met"
    elif any(item["passed"] is None for item in performance):
        status = "not_evaluable"
    else:
        status = "met"
    return dict(
        status=status,
        readiness=readiness,
        performance=performance,
        first_anchor=first,
        last_anchor=last,
        labelled_distinct_days=len(days),
        calendar_days_without_label=span - len(days),
        supported_bins=len(supported),
        opens_display=False,
    )


def _summary(rows):
    selected = _selections(rows)
    return dict(
        rows=len(rows),
        predicted=sum(row["probabilities"] is not None for row in rows),
        showable=sum(row["showable"] for row in rows),
        groups={name: len(group) for name, (group, _) in selected.items()},
        null_primary=sum(row["primary"]["label"] is None for row in rows),
        null_tracked=sum(row["tracked"]["label"] is None for row in rows),
        primary_exclusion_reasons=dict(
            sorted(
                Counter(
                    reason
                    for row in rows
                    if row["primary"]["label"] is None
                    for reason in row["primary"]["reasons"]
                ).items()
            )
        ),
        paired_label_differences=sum(
            row["primary"]["label"] != row["tracked"]["label"]
            for row in selected["paired_fixed"][0]
        ),
    )


def _health(config, closed, series, features, rows, incomplete):
    keys = {(row["product_id"], row["anchor_day"]) for row in rows}
    missing = sorted(set(features) - keys)
    daily = []
    for day in dates(config.start_day, closed):
        text = day.isoformat()
        entries = [row for row in rows if row["anchor_day"] == text]
        daily.append(
            dict(
                day=day,
                expected_starts=sum(key[1] == text for key in features),
                recorded=len(entries),
                missing_records=sum(key[1] == text for key in missing),
                no_start_price=sum(
                    s.first_observation is not None
                    and day >= s.first_observation
                    and (pid, text) not in features
                    for pid, s in series.items()
                ),
                not_yet_observed=sum(
                    s.first_observation is None or day < s.first_observation
                    for s in series.values()
                ),
                timing=dict(sorted(Counter(row["timing"] for row in entries).items())),
                null_primary=sum(row["primary"]["label"] is None for row in entries),
            )
        )
    return dict(
        timing=dict(sorted(Counter(row["timing"] for row in rows).items())),
        incomplete_folders=incomplete,
        missing_records=[
            dict(product_id=pid, source="own", anchor_day=day) for pid, day in missing
        ],
        per_day=daily,
    )


def build_evaluation(snapshot, digest, config, model, origins, records, incomplete):
    if model.manifest_sha256 != config.model_manifest_sha256 or any(
        item["choice"] != model.choice for item in origins
    ):
        raise ValueError("Değerlendirme modeli kayıt başlığıyla uyuşmuyor")
    closed, all_series = build_series(snapshot)
    products = {row.product_id: row for row in snapshot.products}
    series = {s.product_id: s for s in all_series if s.source == "own"}
    features, windows = {}, {}
    for pid, s in series.items():
        for item in feature_rows(s, products[pid]):
            if item.metadata.anchor_day >= config.start_day:
                features[pid, item.metadata.anchor_day.isoformat()] = item
        for item in relaxed_windows(s, closed):
            if item["anchor_day"] >= config.start_day:
                windows[pid, item["anchor_day"].isoformat()] = item
    first_batch = min((_utc(item["captured_at"]) for item in origins), default=None)
    rows, seen = [], set()
    for record in records:
        key = record["product_id"], record["anchor_day"]
        if key in seen:
            raise ValueError("Tekrarlı değerlendirme kaydı")
        seen.add(key)
        feature = features.get(key)
        if feature is None:
            raise ValueError(f"Kayıt girdisi yeni görüntüde bulunamadı: {key}")
        metadata = feature.metadata.model_dump(mode="json")
        if (
            record["features"] != feature.features.model_dump(mode="json")
            or record["product_key"] != metadata["product_key"]
            or record["anchor_at"] != metadata["anchor_at"]
            or record["source"] != "own"
        ):
            raise ValueError(
                f"Kayıt girdileri yeni görüntüyle birebir aynı değil: {key}"
            )
        day = feature.metadata.anchor_day
        recorded_at = _utc(record["recorded_at"])
        if recorded_at > snapshot.captured_at:
            raise ValueError("Değerlendirme görüntüsü kayıt görüntüsünden eski")
        after = (recorded_at.astimezone(ISTANBUL).date() - day).days
        missing = sum(
            series[key[0]]
            .days.get(day - timedelta(days=back), {})
            .get("reference_price")
            is None
            for back in range(14)
        )
        reasons = []
        if feature.features.history_days < 30:
            reasons.append(shadow.HISTORY_REASON)
        if 100 * missing > 30 * 14:
            reasons.append(shadow.MISSING_REASON)
        if feature.features.family not in model.families:
            reasons.append(shadow.FAMILY_REASON)
        if (
            record["recorded_after_days"] != after
            or after < 1
            or record["missing_days_14"] != missing
            or record["reasons"] != sorted(reasons)
            or record["showable"] is not (not reasons)
            or (record["probabilities"] is None) != (shadow.HISTORY_REASON in reasons)
        ):
            raise ValueError(f"Kayıt yeterlilik/zaman bilgisi tutarsız: {key}")
        if (
            record["probabilities"] is not None
            and record["probabilities"]["r0"] != model.reference_rate
        ):
            raise ValueError("Kayıttaki R0 dondurulan eğitim oranıyla aynı değil")
        window = windows[key]
        timing = (
            "on_time"
            if after == 1
            else "initial_backfill" if recorded_at == first_batch else "late"
        )
        rows.append(
            dict(
                record,
                role="own_evaluation",
                timing=timing,
                target_end=window["target_end"],
                primary=window["primary"],
                tracked=window["tracked"],
            )
        )
    rows = _json(sorted(rows, key=lambda row: (row["product_id"], row["anchor_day"])))
    groups = _selections(rows)
    scores = {
        name: _score_rows(group, target, model.choice)
        for name, (group, target) in groups.items()
    }
    main = groups["main"][0]
    targets, probabilities, references = _vectors(main, "primary", model.choice)
    cutoff = date.fromisoformat(EVALUATION_RULES["information_cutoff"])
    november_first = date.fromisoformat(EVALUATION_RULES["november_first"])
    november_last = date.fromisoformat(EVALUATION_RULES["november_last"])
    strata = {
        "november": [
            row
            for row in main
            if november_first <= date.fromisoformat(row["anchor_day"]) <= november_last
        ],
        "outside_november": [
            row
            for row in main
            if not november_first
            <= date.fromisoformat(row["anchor_day"])
            <= november_last
        ],
        "missing_at_most_10_percent": [
            row for row in main if row["features"]["missing_ratio_30d"] <= 0.10
        ],
        "missing_over_10_percent": [
            row for row in main if row["features"]["missing_ratio_30d"] > 0.10
        ],
        "before_22_november": [
            row for row in main if date.fromisoformat(row["anchor_day"]) < cutoff
        ],
        "from_22_november": [
            row for row in main if date.fromisoformat(row["anchor_day"]) >= cutoff
        ],
    }
    report = dict(
        input=dict(
            snapshot_sha256=digest,
            snapshot_captured_at=snapshot.captured_at,
            last_closed_day=closed,
            start_day=config.start_day,
            model_manifest_sha256=model.manifest_sha256,
            choice=model.choice,
            reference_rate=model.reference_rate,
            records=origins,
        ),
        rules=_rules(),
        summary=_summary(rows),
        gate=evaluate_gate(targets, scores["main"][model.choice]),
        scores=scores,
        bootstrap=own_evaluation_bootstrap(targets, probabilities, references),
        information_slices={
            name: _score_rows(group, "primary", model.choice)
            for name, group in strata.items()
        },
        health=_health(config, closed, series, features, rows, incomplete),
        final_date_matches=snapshot.captured_at.astimezone(ISTANBUL).date().isoformat()
        == EVALUATION_RULES["final_evaluation_date"],
        opens_display=False,
        model_trained=False,
        predictions_generated=False,
    )
    return EvaluationResult(_json(report), rows)


def evaluate_snapshot(snapshot, digest, config):
    model = load_evaluation_model(config)
    origins, rows, incomplete = read_inventory(config, snapshot.captured_at)
    return build_evaluation(snapshot, digest, config, model, origins, rows, incomplete)


def _number(value):
    return "—" if value is None else f"{value:.4f}"


def _value(value):
    if value is None:
        return "—"
    if type(value) is bool:
        return "Evet" if value else "Hayır"
    return _number(value) if type(value) is float else str(value)


def markdown_report(report):
    info, summary, gate = report["input"], report["summary"], report["gate"]
    choice = info["choice"]
    lines = [
        "# Gölge mod değerlendirmesi",
        "",
        f"Görüntü: {info['snapshot_captured_at']} "
        f"· son kapanmış gün: {info['last_closed_day']}",
        f"Görüntü SHA-256: {info['snapshot_sha256']}",
        f"Model manifest SHA-256: {info['model_manifest_sha256']}",
        "",
        "Kaydedilmiş olasılıklar değerlendirilmiştir; model eğitilmedi, "
        "yeni tahmin üretilmedi.",
        "Asıl sonuç: geçmişi en az 30 gün, y_sabit etiketi 0/1 "
        "ve gösterilebilir kayıtlar.",
        f"Kapı sonucu: **{STATUS_TITLES[gate['status']]}**. Bu rapor arayüzü açmaz.",
        "Ara raporlar yalnız bilgidir; kesin değerlendirme "
        "5 Ocak 2027 görüntüsüyle bir kez yapılır.",
        "Kesin günle aynı görüntü tarihi: "
        f"{'Evet' if report['final_date_matches'] else 'Hayır'}.",
        "",
        f"Kayıt: {summary['rows']} · olasılıklı: {summary['predicted']} "
        f"· asıl sonuç: {summary['groups']['main']}",
        f"NULL y_sabit: {summary['null_primary']} "
        f"· NULL y_izlenen: {summary['null_tracked']}",
        "",
        "## Kapı koşulları",
        "",
        "| Tür | Koşul | Değer | Sonuç |",
        "|---|---|---|---|",
    ]
    titles = dict(
        calendar_span="Dahil takvim aralığı ≥ 60 gün",
        november_covered="Kasım'ın tamamı aralıkta",
        outside_november_days="Kasım dışında ≥ 14 farklı etiketli gün",
        positive_clusters="Olumlu pencere kümesi ≥ 30",
        brier_skill="Brier skill > 0",
        mean_gap="Ortalama fark ≤ 0,05",
        supported_bin_gap="Destekli kovalarda en büyük fark ≤ 0,15",
    )
    for kind, items in (
        ("Veri", gate["readiness"]),
        ("Performans", gate["performance"]),
    ):
        for item in items:
            verdict = (
                "Belirsiz"
                if item["passed"] is None
                else "Sağlandı" if item["passed"] else "Sağlanmadı"
            )
            lines.append(
                f"| {kind} | {titles[item['name']]} | {_value(item['value'])} "
                f"| {verdict} |"
            )
    lines += [
        "",
        f"Etiketli ayrı gün: {gate['labelled_distinct_days']} "
        f"· aralıkta etiketsiz gün: {gate['calendar_days_without_label']}",
        "",
        "## Puanlar",
        "",
        "| Grup | Model | Satır | AP | Brier | Log loss | Brier skill |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, scores in report["scores"].items():
        for model, title in (("r0", "R0 sabit oran"), (choice, "Dondurulan model")):
            score = scores[model]
            lines.append(
                f"| {GROUP_TITLES[name]} | {title} | {score['rows']} "
                f"| {_number(score['average_precision'])} "
                f"| {_number(score['brier'])} | {_number(score['log_loss'])} "
                f"| {_number(score['brier_skill'])} |"
            )
    interval = report["bootstrap"]
    lines += [
        "",
        f"AP farkı: {_number(interval['point_difference'])} "
        f"· %95 aralık [{_number(interval['lower'])}, {_number(interval['upper'])}] "
        "(yalnız bilgi).",
        f"Aralık gerekçeleri: {', '.join(interval['reasons']) or 'yok'}.",
        "",
        "## Asıl sonucun güvenilirlik kovaları",
        "",
        "| Alt | Üst | Satır | Ortalama | Gerçekleşme | Destek |",
        "|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["scores"]["main"][choice]["calibration"]:
        lines.append(
            f"| {item['lower']} | {item['upper']} | {item['count']} "
            f"| {_number(item['mean_probability'])} "
            f"| {_number(item['observed_rate'])} "
            f"| {'Yetersiz' if item['low_support'] else 'Yeterli'} |"
        )
    lines += [
        "",
        "## Bilgi amaçlı kırılımlar",
        "",
        "| Kırılım | Satır | AP | Brier | Brier skill |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, scores in report["information_slices"].items():
        score = scores[choice]
        lines.append(
            f"| {SLICE_TITLES[name]} | {score['rows']} "
            f"| {_number(score['average_precision'])} "
            f"| {_number(score['brier'])} | {_number(score['brier_skill'])} |"
        )
    lines += [
        "",
        "## Kayıt sağlığı",
        "",
        ", ".join(
            f"{title}: {report['health']['timing'].get(name, 0)}"
            for name, title in TIMING_TITLES.items()
        ),
        f"Eksik kayıt: {len(report['health']['missing_records'])} "
        f"· yarım klasör: {len(report['health']['incomplete_folders'])}",
        "Eşleşmiş y_sabit/y_izlenen etiket farkı: "
        f"{summary['paired_label_differences']}",
        "",
        "| Gün | Beklenen başlangıç | Kayıt | Eksik kayıt "
        "| Başlangıç fiyatı yok | Henüz gözlenmemiş |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["health"]["per_day"]:
        lines.append(
            f"| {item['day']} | {item['expected_starts']} | {item['recorded']} "
            f"| {item['missing_records']} | {item['no_start_price']} "
            f"| {item['not_yet_observed']} |"
        )
    lines += [
        "",
        "Ayrıntılı R0, marka/aile/ürün puanları ve dışlama gerekçeleri "
        "report.json içindedir.",
        "Girdi eşleşmesi nedensel hesap denetimidir; yerel kaydın imzası "
        "veya gelecekteki başarının garantisi değildir.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(directory, result):
    directory.mkdir(parents=True, exist_ok=False)
    files = {
        "evaluations.jsonl": b"".join(json_bytes(row) + b"\n" for row in result.rows),
        "report.json": json_bytes(result.report) + b"\n",
        "report.md": markdown_report(result.report).encode("utf-8"),
    }
    for name, content in files.items():
        (directory / name).write_bytes(content)
    manifest = dict(
        format_version=1,
        kind="shadow_evaluation",
        status="complete",
        input=result.report["input"],
        rules=result.report["rules"],
        files={
            name: hashlib.sha256(content).hexdigest() for name, content in files.items()
        },
    )
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def read_outputs(directory):
    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or set(manifest)
        != {"format_version", "kind", "status", "input", "rules", "files"}
        or manifest["format_version"] != 1
        or manifest["kind"] != "shadow_evaluation"
        or manifest["status"] != "complete"
        or manifest["rules"] != _json(_rules())
        or set(manifest["files"]) != set(OUTPUT_FILES)
    ):
        raise ValueError("Gölge değerlendirme manifesti sözleşmeye uymuyor")
    for name in OUTPUT_FILES:
        if _sha(directory / name) != manifest["files"][name]:
            raise ValueError(f"Değerlendirme dosyasının parmak izi tutmuyor: {name}")
    report = json.loads((directory / "report.json").read_bytes())
    rows = [
        json.loads(line)
        for line in (directory / "evaluations.jsonl").read_bytes().splitlines()
    ]
    choice = manifest["input"]["choice"]
    keys = []
    for row in rows:
        if set(row) != ROW_FIELDS or row["role"] != "own_evaluation":
            raise ValueError("Değerlendirme satırı sözleşmeye uymuyor")
        shadow._check_row({name: row[name] for name in shadow.ROW_FIELDS}, choice)
        for target in ("primary", "tracked"):
            label = row[target]["label"]
            if label is not None and (type(label) is not int or label not in (0, 1)):
                raise ValueError("Değerlendirme etiketi geçerli değil")
        keys.append((row["product_id"], row["anchor_day"]))
    if keys != sorted(set(keys)):
        raise ValueError("Değerlendirme anahtarları sıralı ve tekil olmalı")
    if (
        report["input"] != manifest["input"]
        or report["rules"] != manifest["rules"]
        or report["summary"] != _summary(rows)
    ):
        raise ValueError("Değerlendirme özeti satırlarla uyuşmuyor")
    groups = _selections(rows)
    if set(report["scores"]) != set(groups):
        raise ValueError("Değerlendirme grupları uyuşmuyor")
    for name, (group, _) in groups.items():
        if any(
            report["scores"][name][model]["rows"] != len(group)
            for model in ("r0", choice)
        ):
            raise ValueError("Puan grubunun satır sayısı uyuşmuyor")
    targets, _, _ = _vectors(groups["main"][0], "primary", choice)
    if (
        report["gate"]
        != _json(evaluate_gate(targets, report["scores"]["main"][choice]))
        or report["opens_display"] is not False
    ):
        raise ValueError("Kapı sonucu raporla uyuşmuyor")
    if (directory / "report.md").read_text(encoding="utf-8") != markdown_report(report):
        raise ValueError("Türkçe rapor sayısal raporla uyuşmuyor")
    return report, rows
