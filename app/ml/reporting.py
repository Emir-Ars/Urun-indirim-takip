"""Etiket kanıtlarını belirlenimci dosyalara yazar; manifest en son oluşur."""

import hashlib
import json
from datetime import date, datetime

OUTPUT_FILES = (
    "daily.jsonl",
    "windows.jsonl",
    "strict_windows.jsonl",
    "report.json",
    "report.md",
)


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"JSON'a çevrilemeyen tür: {type(value).__name__}")


def json_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")


def markdown_report(report):
    lines = [
        "# Adım 4.2 — Etiket raporu",
        "",
        f"Son kapanmış İstanbul günü: {report['last_closed_day']}",
        "",
        "Etiket: sonraki 7 günde en az %5 düşüş; en az 6 fiyatlı gün gerekir.",
        "Kendi serimizde birincil hedef başlangıç sayfalarıyla sabittir.",
        "Cimri yarım günleri kullanılmaz. Eksik fiyatlar doldurulmaz.",
        "Olumlu satırlar bağımsız veya farklı düşüş olayları sayısı değildir.",
        "Gelecek alanları yalnız etiket denetimidir; model girdisi değildir.",
        "Model eğitilmedi; eğitim/test bölmesi ve ekranda tahmin yok.",
        "",
        "| Kaynak | Kullanılabilir | Olumlu | Olumsuz | Belirsiz "
        "| Sıkı kullanılabilir |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for source, title in (("own", "Kendi ölçümlerimiz"), ("cimri", "Cimri")):
        summary = report["sources"][source]
        count = summary["primary"]
        lines.append(
            f"| {title} | {count['usable']} | {count['positive']} "
            f"| {count['negative']} | {count['unknown']} "
            f"| {summary['strict']['usable']} |"
        )
    lines += [
        "",
        "## Ürün ve kaynak kırılımı",
        "",
        "| Ürün | Kaynak | Kullanılabilir / olumlu / belirsiz "
        "| Eksik başlangıç günü | İki hedef karşılaştırılabilir / farklı |",
        "|---|---|---:|---:|---:|",
    ]
    for item in report["products"]:
        count = item["primary"]
        lines.append(
            f"| {item['product_id']} — {item['product_name']} | {item['source']} "
            f"| {count['usable']} / {count['positive']} / {count['unknown']} "
            f"| {item['missing_reference_days']} | {item['paired_labels']} "
            f"/ {item['scope_label_differences']} |"
        )
    lines += ["", "## Uygunluk ve günlük kalite gerekçeleri", ""]
    for item in report["products"]:
        for key, title in (
            ("exclusion_reasons", "Birincil pencere"),
            ("tracked_exclusion_reasons", "İkincil pencere"),
            ("daily_reasons", "Gün"),
        ):
            if item[key] is None:
                continue
            detail = (
                "; ".join(
                    f"{report['reason_labels'].get(reason, reason)}: {count}"
                    for reason, count in item[key].items()
                )
                or "Yok"
            )
            lines.append(
                f"Ürün {item['product_id']} / {item['source']} — {title}: {detail}\n"
            )
    lines += ["", "## Sayfa kapsamından gelen farklar", ""]
    for item in report["products"]:
        if item["source"] != "own":
            continue
        ratio = item["scope_label_difference_ratio"]
        formatted = f"%{100 * ratio:.2f}" if ratio is not None else "Hesaplanamadı"
        lines.append(
            f"Ürün {item['product_id']}: karşılaştırılabilir {item['paired_labels']}; "
            f"farklı {item['scope_label_differences']} ({formatted}); "
            f"yalnız izlenen kapsamda düşüş {item['tracked_only_drops']}.\n"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(directory, digest, result):
    from app.ml.labels import RULES

    report, daily, windows, strict = result
    directory.mkdir(parents=True, exist_ok=False)
    for name, rows in (
        ("daily.jsonl", daily),
        ("windows.jsonl", windows),
        ("strict_windows.jsonl", strict),
    ):
        with (directory / name).open("wb") as stream:
            for row in rows:
                stream.write(json_bytes(row) + b"\n")
    (directory / "report.json").write_bytes(json_bytes(report) + b"\n")
    (directory / "report.md").write_text(
        markdown_report(report), encoding="utf-8", newline="\n"
    )
    manifest = dict(
        format_version=1,
        status="complete",
        snapshot_sha256=digest,
        rules=RULES,
        files={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in OUTPUT_FILES
        },
    )
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def verify_outputs(directory, digest):
    from app.ml.labels import RULES

    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format_version") != 1
        or manifest.get("status") != "complete"
        or manifest.get("snapshot_sha256") != digest
        or manifest.get("rules") != RULES
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != set(OUTPUT_FILES)
    ):
        raise ValueError("Etiket manifesti görüntüyle veya kurallarla uyuşmuyor")
    for name in OUTPUT_FILES:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["files"][name]
        ):
            raise ValueError(f"Etiket dosyasının parmak izi tutmuyor: {name}")
    return manifest


FEATURE_OUTPUT_FILES = (
    "features.jsonl",
    "feature_schema.json",
    "report.json",
    "report.md",
)


def feature_markdown_report(report):
    from app.ml.features import FeatureValues

    lines = [
        "# Adım 4.3 — Model girdileri",
        "",
        f"Son kapanmış İstanbul günü: {report['last_closed_day']}",
        "",
        "Girdiler yalnız başlangıç gününe ve öncesine bakar; etiket dosyası okunmaz.",
        "Geçerli başlangıcın etiketi bilinmese de girdi satırı üretilir.",
        "Eksikler NULL'dır; fiyat taşıma, kategori kodlama veya ölçekleme yapılmadı.",
        "Ay ve ürün anahtarı çekirdek dışında, metadata içinde saklanır.",
        "Cimri'nin gün içi saati ve tarihsel erişilebilirliği bilinmez; "
        "günlük tarih esas alınır.",
        "Model eğitimi, zaman bölmesi ve ekranda tahmin yok.",
        "",
        "| Kaynak | Girdi satırı |",
        "|---|---:|",
    ]
    for source, title in (("own", "Kendi ölçümlerimiz"), ("cimri", "Cimri")):
        lines.append(f"| {title} | {report['sources'][source]['rows']} |")
    lines += ["", "## Girdi formülleri", "", "| Alan | Anlamı |", "|---|---|"]
    lines.extend(
        f"| {name} | {field.description} |"
        for name, field in FeatureValues.model_fields.items()
    )
    lines += [
        "",
        "## Ürün/kaynak kırılımı",
        "",
        "| Ürün | Kaynak | Satır | Bilinmeyen segment |",
        "|---|---|---:|---:|",
    ]
    for item in report["products"]:
        lines.append(
            f"| {item['product_id']} — {item['product_name']} | {item['source']} "
            f"| {item['rows']} | {item['unknown_segment_rows']} |"
        )
    lines += [
        "",
        "## Girdi eksiklikleri",
        "",
        "Sayılar NULL alanları gösterir; satırlar bu yüzden elenmez.",
        "",
    ]
    for item in report["products"]:
        detail = (
            "; ".join(
                f"{name}: {count}" for name, count in item["missing"].items() if count
            )
            or "Yok"
        )
        lines.append(f"Ürün {item['product_id']} / {item['source']}: {detail}\n")
    lines += ["", "## Tanınmayan model aileleri", ""]
    if not report["unknown_models"]:
        lines.append("Yok.")
    for item in report["unknown_models"]:
        lines.append(
            f"- Ürün {item['product_id']}: {item['brand']} {item['model']}; "
            "tam model aile olarak korundu, segment unknown."
        )
    return "\n".join(lines).rstrip() + "\n"


def write_feature_outputs(directory, digest, result):
    from app.ml.features import FEATURE_RULES, feature_schema

    report, rows = result
    directory.mkdir(parents=True, exist_ok=False)
    with (directory / "features.jsonl").open("wb") as stream:
        for row in rows:
            stream.write(json_bytes(row.model_dump(mode="json")) + b"\n")
    (directory / "feature_schema.json").write_bytes(
        json_bytes(feature_schema()) + b"\n"
    )
    (directory / "report.json").write_bytes(json_bytes(report) + b"\n")
    (directory / "report.md").write_text(
        feature_markdown_report(report), encoding="utf-8", newline="\n"
    )
    manifest = dict(
        format_version=1,
        status="complete",
        snapshot_sha256=digest,
        feature_rules=FEATURE_RULES,
        files={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in FEATURE_OUTPUT_FILES
        },
    )
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def verify_feature_outputs(directory, digest):
    from app.ml.features import FEATURE_RULES, FeatureRow, feature_schema

    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format_version") != 1
        or manifest.get("status") != "complete"
        or manifest.get("snapshot_sha256") != digest
        or manifest.get("feature_rules") != FEATURE_RULES
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != set(FEATURE_OUTPUT_FILES)
    ):
        raise ValueError("Girdi manifesti görüntüyle veya kurallarla uyuşmuyor")
    for name in FEATURE_OUTPUT_FILES:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["files"][name]
        ):
            raise ValueError(f"Girdi dosyasının parmak izi tutmuyor: {name}")
    if json.loads((directory / "feature_schema.json").read_bytes()) != feature_schema():
        raise ValueError("Girdi şeması kodla uyuşmuyor")
    previous = None
    with (directory / "features.jsonl").open("rb") as stream:
        for line in stream:
            metadata = FeatureRow.model_validate_json(line).metadata
            key = (metadata.product_id, metadata.source, metadata.anchor_day)
            if previous is not None and key <= previous:
                raise ValueError("Girdi kayıtları anahtara göre sıralı ve tekil olmalı")
            previous = key
    return manifest


SPLIT_OUTPUT_FILES = (
    "assignments.jsonl",
    "folds.json",
    "metrics_schema.json",
    "report.json",
    "report.md",
)


def split_markdown_report(report):
    titles = dict(
        train="Eğitim",
        validation="Doğrulama",
        test_reserved="Saklı test",
        purged_train="Eğitimden temizlenen",
        purged_validation="Doğrulamadan temizlenen",
        unlabelled="Etiketsiz Cimri başlangıcı",
        own_evaluation="Kendi değerlendirmesi",
        own_unlabelled="Etiketsiz kendi başlangıcı",
    )
    lines = [
        "# Adım 4.4 — Zaman bölmesi ve uygunluk",
        "",
        "Bütün ürünlerde ortak tarih sınırları; %70/%15/%15, sonra purge.",
        "Her katta eğitim → ayrı 30 gün kalibrasyon → doğrulama ayı vardır.",
        "Sonraki sınıra eşit veya sonrasına uzanan etiketler kullanılmaz.",
        "Model/kalibratör eğitilmedi; gerçek tahmin puanı hesaplanmadı.",
        "Saklı testte yalnız sınır, başlangıç anahtarı ve sayı açıklanır.",
        "Olumlu pencere kümeleri bağımsız gerçek olay sayısı değildir.",
        "",
        f"Bölme durumu: {'sınırlı' if report['status'] == 'limited' else 'yeterli'}.",
        "",
        "| Bölüm | İlk başlangıç | Son başlangıç | Kalan satır | Olumlu | Olumsuz |",
        "|---|---|---|---:|---:|---:|",
    ]
    for role, summary in report["partitions"].items():
        positive = summary.get("positive", "Saklı")
        negative = summary.get("negative", "Saklı")
        lines.append(
            f"| {titles[role]} | {summary['first_anchor']} "
            f"| {summary['last_anchor']} | {summary['rows']} "
            f"| {positive} | {negative} |"
        )
    lines += ["", "## Başlangıç atamaları", ""]
    lines.extend(
        f"- {titles[role]}: {count}"
        for role, count in report["assignment_counts"].items()
    )
    lines += [
        "",
        "## İleri yürüyen katlar",
        "",
        "| Ay | Kalibrasyon başlangıcı | Eğitim | Kalibrasyon | Doğrulama "
        "| Temizlenen eğitim / kalibrasyon / doğrulama |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for fold in report["folds"]:
        stats, purged = fold["statistics"], fold["purged"]
        lines.append(
            f"| {fold['month']} | {fold['calibration_start']} "
            f"| {stats['train']['rows']} | {stats['calibration']['rows']} "
            f"| {stats['validation']['rows']} | {purged['train']} "
            f"/ {purged['calibration']} / {purged['validation']} |"
        )
    lines += ["", "## Sınırlamalar", ""]
    labels = report["limitation_labels"]
    lines.extend(f"- {labels[reason]}" for reason in report["limitations"])
    for fold in report["folds"]:
        lines.extend(
            f"- {fold['month']}: {labels[reason]}" for reason in fold["limitations"]
        )
    if not report["limitations"]:
        lines.append(
            "Bölme kontrollerinde engel yok; "
            "bu model başarısı veya yayın yeterliliği değildir."
        )
    return "\n".join(lines).rstrip() + "\n"


def split_plan_files(plan):
    """Bölme planından türeyen dosyaların baytları; yazma ve karşılaştırma ortak."""
    from app.ml.splitting import SPLIT_RULES

    return {
        "assignments.jsonl": b"".join(
            json_bytes(row) + b"\n" for row in plan.assignments
        ),
        "folds.json": json_bytes(dict(split_rules=SPLIT_RULES, folds=plan.folds))
        + b"\n",
        "report.json": json_bytes(plan.report) + b"\n",
        "report.md": split_markdown_report(plan.report).encode("utf-8"),
    }


def write_split_outputs(directory, inputs, plan):
    from app.ml.metrics import METRIC_RULES, metrics_schema
    from app.ml.splitting import SPLIT_RULES

    directory.mkdir(parents=True, exist_ok=False)
    files = split_plan_files(plan)
    files["metrics_schema.json"] = json_bytes(metrics_schema()) + b"\n"
    for name, content in files.items():
        (directory / name).write_bytes(content)
    manifest = dict(
        format_version=1,
        status="complete",
        snapshot_sha256=inputs.snapshot_sha256,
        input_manifests=inputs.input_manifests,
        split_rules=SPLIT_RULES,
        metric_rules=METRIC_RULES,
        files={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in SPLIT_OUTPUT_FILES
        },
    )
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def verify_split_outputs(directory, digest, input_manifests):
    from collections import Counter
    from datetime import timedelta
    from app.ml.metrics import METRIC_RULES, StartKey, metrics_schema
    from app.ml.splitting import SPLIT_RULES

    manifest = json.loads((directory / "manifest.json").read_bytes())
    if (
        not isinstance(manifest, dict)
        or manifest.get("format_version") != 1
        or manifest.get("status") != "complete"
        or manifest.get("snapshot_sha256") != digest
        or manifest.get("input_manifests") != input_manifests
        or manifest.get("split_rules") != SPLIT_RULES
        or manifest.get("metric_rules") != METRIC_RULES
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != set(SPLIT_OUTPUT_FILES)
    ):
        raise ValueError("Bölme manifesti girişlerle veya kurallarla uyuşmuyor")
    for name in SPLIT_OUTPUT_FILES:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["files"][name]
        ):
            raise ValueError(f"Bölme dosyasının parmak izi tutmuyor: {name}")
    if json.loads((directory / "metrics_schema.json").read_bytes()) != metrics_schema():
        raise ValueError("Ölçüt şeması kodla uyuşmuyor")
    assignments = [
        json.loads(line)
        for line in (directory / "assignments.jsonl").read_bytes().splitlines()
    ]
    roles, previous = {}, None
    allowed = {
        "train",
        "validation",
        "test_reserved",
        "purged_train",
        "purged_validation",
        "unlabelled",
        "own_evaluation",
        "own_unlabelled",
    }
    for row in assignments:
        if (
            set(row) != {"product_id", "source", "anchor_day", "role"}
            or row["role"] not in allowed
        ):
            raise ValueError("Bölme ataması yalnız anahtar ve izinli rol içermeli")
        key = StartKey.model_validate_json(
            json_bytes(
                {name: row[name] for name in ("product_id", "source", "anchor_day")}
            )
        ).key
        if previous is not None and key <= previous:
            raise ValueError("Bölme anahtarları sıralı ve tekil olmalı")
        previous = key
        roles[key] = row["role"]
    report = json.loads((directory / "report.json").read_bytes())
    reserved = report["partitions"]["test_reserved"]
    if (
        set(reserved) != {"first_anchor", "last_anchor", "rows"}
        or reserved["rows"] != sum(role == "test_reserved" for role in roles.values())
        or any(
            report.get(name) is not False
            for name in (
                "model_trained",
                "test_opened",
                "real_prediction_scores_computed",
            )
        )
        or report["assignment_counts"] != dict(Counter(roles.values()))
    ):
        raise ValueError("Saklı test veya bölme raporu sözleşmeye uymuyor")
    folds = json.loads((directory / "folds.json").read_bytes())
    if folds["split_rules"] != SPLIT_RULES or len(folds["folds"]) > 4:
        raise ValueError("Kat kuralları uyuşmuyor")
    for fold in folds["folds"]:
        boundaries = dict(
            train=date.fromisoformat(fold["calibration_start"]),
            calibration=date.fromisoformat(fold["validation_start"]),
            validation=date.fromisoformat(fold["validation_end"]) + timedelta(days=1),
        )
        seen = set()
        for role, rows in fold["members"].items():
            if role not in boundaries:
                raise ValueError("Tanınmayan kat rolü")
            for row in rows:
                key = StartKey.model_validate_json(json_bytes(row)).key
                if (
                    key in seen
                    or key not in roles
                    or key[1] != "cimri"
                    or roles[key]
                    in {"test_reserved", "purged_validation", "unlabelled"}
                    or key[2] + timedelta(days=7) >= boundaries[role]
                ):
                    raise ValueError("Kat üyeliği, purge veya saklı test sınırı bozuk")
                lower = (
                    boundaries["train"]
                    if role == "calibration"
                    else boundaries["calibration"] if role == "validation" else None
                )
                if lower is not None and key[2] < lower:
                    raise ValueError("Kat üyeliği kendi döneminden önce başlıyor")
                seen.add(key)
    return manifest


EXPERIMENT_OUTPUT_FILES = (
    "predictions.jsonl",
    "models.json",
    "report.json",
    "report.md",
)

MODEL_TITLES = dict(
    r0="R0 sabit oran",
    r1="R1 dip kuralı",
    r2="R2 lojistik regresyon",
    lightgbm="LightGBM",
    r1_platt="R1 + Platt",
    r2_platt="R2 + Platt",
    lightgbm_platt="LightGBM + Platt",
)
SELECTION_TITLES = dict(
    met="Karşılandı", not_met="Karşılanmadı", not_evaluable="Değerlendirilemedi"
)
CONDITION_TITLES = {
    "four_ready_folds": "Dört kat hazır",
    "ap_interval_lower_above_zero": "AP farkının %95 aralığında alt sınır 0'ın üstünde",
    "brier_not_worse_than_baseline": "Birleşik Brier, R2 + Platt'tan kötü değil",
    "log_loss_not_worse_than_baseline": "Birleşik log loss, R2 + Platt'tan kötü değil",
}


def _number(value, digits=4):
    return "—" if value is None else f"{value:.{digits}f}"


def _verdict(passed):
    return "hesaplanamadı" if passed is None else "evet" if passed else "hayır"


def experiment_markdown_report(report):
    combined, selection = report["combined"], report["selection"]
    ready = sum(fold["scores"] is not None for fold in report["folds"])
    lines = [
        "# Adım 4.5 — Referans modeller, LightGBM ve kalibrasyon",
        "",
        "Puanlar yalnız doğrulama aylarındadır; saklı test açılmadı, kendi serimiz",
        "puanlanmadı. Modeller yalnız eğitim diliminden, Platt kalibrasyonu modelin",
        "görmediği ayrı 30 günlük dilimden öğrenir. R1, R2 ve LightGBM aynı Platt",
        "kalibrasyonundan geçti; ham hâlleri de tabloda. Seçim sonucu bir öneridir,",
        "model dondurulmadı. Olumlu satırlar bağımsız düşüş olayı sayısı değildir.",
        "",
        f"Değerlendirilen kat: {ready} / {len(report['folds'])}.",
        "",
    ]
    if combined["rows"]:
        lines += [
            "## Birleşik doğrulama (her satır kendi katının modeliyle)",
            "",
            f"Satır: {combined['rows']} · olumlu: {combined['positives']} "
            f"· olumlu oranı (taban AP): %{100 * combined['positive_rate']:.2f}",
            "",
            "| Model | AP | Brier | Log loss | Brier skill |",
            "|---|---:|---:|---:|---:|",
        ]
        for name in MODEL_TITLES:
            score = combined["scores"][name]
            lines.append(
                f"| {MODEL_TITLES[name]} | {_number(score['average_precision'])} "
                f"| {_number(score['brier'])} | {_number(score['log_loss'])} "
                f"| {_number(score['brier_skill'])} |"
            )
        lines += [
            "",
            "## Kat bazında AP",
            "",
            "| Ay | Durum | Satır | Olumlu oranı | "
            + " | ".join(MODEL_TITLES.values())
            + " |",
            "|---|---|---:|---:|" + "---:|" * len(MODEL_TITLES),
        ]
        for fold in report["folds"]:
            scores = fold["scores"]
            if scores is None:
                lines.append(
                    f"| {fold['month']} | atlandı | — | — |"
                    + " — |" * len(MODEL_TITLES)
                )
                continue
            lines.append(
                f"| {fold['month']} | değerlendirildi | {scores['r0']['rows']} "
                f"| %{100 * scores['r0']['positive_rate']:.2f} | "
                + " | ".join(
                    _number(scores[name]["average_precision"]) for name in MODEL_TITLES
                )
                + " |"
            )
    else:
        lines += ["Puanlanacak doğrulama satırı yok.", ""]
    lines += [
        "",
        "## Eşleştirilmiş farklar (14 günlük tarih blokları, %95)",
        "",
        "| Karşılaştırma | Amaç | AP farkı | Alt | Üst | Geçerli tekrar | Not |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["bootstrap"]:
        purpose = "seçim" if item["purpose"] == "selection" else "bilgi"
        lines.append(
            f"| {MODEL_TITLES[item['model']]} − {MODEL_TITLES[item['reference']]} "
            f"| {purpose} | {_number(item['point_difference'])} "
            f"| {_number(item['lower'])} | {_number(item['upper'])} "
            f"| {item['valid_repeats']} / {item['repeats']} "
            f"| {', '.join(item['reasons'])} |"
        )
    lines += [
        "",
        "## LightGBM seçim ölçütü",
        "",
        f"Sonuç: **{SELECTION_TITLES[selection['status']]}**. Bu bir öneridir; "
        "model ayrı bir planda dondurulur.",
        "",
        "| Koşul | Sağlandı mı |",
        "|---|---|",
    ]
    lines.extend(
        f"| {CONDITION_TITLES[item['name']]} | {_verdict(item['passed'])} |"
        for item in selection["conditions"]
    )
    if combined["rows"]:
        lines += [
            "",
            "## Güvenilirlik (birleşik doğrulama)",
            "",
            "Her kovada tahmin ortalaması ile gerçekleşen oran yakınsa model "
            "kalibredir. `*`: 20'den az kayıt.",
        ]
        for name in ("lightgbm", "lightgbm_platt", "r2_platt"):
            lines += [
                "",
                f"### {MODEL_TITLES[name]}",
                "",
                "| Aralık | Satır | Ortalama tahmin | Gerçekleşen oran |",
                "|---|---:|---:|---:|",
            ]
            for bin_ in combined["scores"][name]["calibration"]:
                mark = "*" if bin_["low_support"] else ""
                lines.append(
                    f"| {bin_['lower']:.1f}–{bin_['upper']:.1f} "
                    f"| {bin_['count']}{mark} "
                    f"| {_number(bin_['mean_probability'])} "
                    f"| {_number(bin_['observed_rate'])} |"
                )
        lines += [
            "",
            "## Ürün makro ortalaması ve marka kırılımı",
            "",
            "Beşten az olumlu pencere kümesi olan hücre `yetersiz` yazılır.",
            "",
            "| Model | Yeterli ürün / toplam | Makro AP | Makro Brier |",
            "|---|---:|---:|---:|",
        ]
        for name in MODEL_TITLES:
            macro = combined["scores"][name]["macro"]
            lines.append(
                f"| {MODEL_TITLES[name]} "
                f"| {macro['supported_products']} / {macro['total_products']} "
                f"| {_number(macro['scores']['average_precision']['value'])} "
                f"| {_number(macro['scores']['brier']['value'])} |"
            )
        lines += [
            "",
            "| Marka | Satır | Olumlu pencere kümesi | "
            f"AP {MODEL_TITLES['lightgbm_platt']} | AP {MODEL_TITLES['r2_platt']} |",
            "|---|---:|---:|---:|---:|",
        ]
        brands = {
            name: combined["scores"][name]["breakdowns"]["brand"]
            for name in ("lightgbm_platt", "r2_platt")
        }
        for brand, cell in brands["lightgbm_platt"].items():
            other = brands["r2_platt"][brand]

            def average_precision(item):
                if item["scores"] is None:
                    return "yetersiz"
                return _number(item["scores"]["average_precision"])

            lines.append(
                f"| {brand} | {cell['rows']} | {cell['positive_window_clusters']} "
                f"| {average_precision(cell)} | {average_precision(other)} |"
            )
    lines += [
        "",
        "## Sınırlar",
        "",
        "- Sonuçlar Cimri'nin günlük en düşük fiyatı üzerindedir; kendi ölçümümüzle",
        "  aynı kapsam değildir ve kendi verimizde doğrulanmadı.",
        "- Dört ay, kampanya ve sakin dönemleri sınırlı örnekler; sonuç şansa",
        "  bağlı olabilir. Aralıklar bu belirsizliğin yalnız bir kısmını gösterir.",
        "- Ayarlar sabittir, aranmadı; ablasyon ve TL kaybı sonraki adımdadır.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_experiment_outputs(directory, inputs, result):
    from app.ml.experiment import EXPERIMENT_RULES
    from app.ml.metrics import METRIC_RULES
    from app.ml.models import library_versions
    from app.ml.splitting import SPLIT_RULES

    directory.mkdir(parents=True, exist_ok=False)
    files = {
        "predictions.jsonl": b"".join(
            json_bytes(row) + b"\n" for row in result.predictions
        ),
        "models.json": json_bytes(result.models) + b"\n",
        "report.json": json_bytes(result.report) + b"\n",
        "report.md": experiment_markdown_report(result.report).encode("utf-8"),
    }
    for name, content in files.items():
        (directory / name).write_bytes(content)
    manifest = dict(
        format_version=1,
        status="complete",
        snapshot_sha256=inputs.snapshot_sha256,
        input_manifests=inputs.input_manifests,
        split_rules=SPLIT_RULES,
        metric_rules=METRIC_RULES,
        experiment_rules=EXPERIMENT_RULES,
        libraries=library_versions(),
        files={
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in EXPERIMENT_OUTPUT_FILES
        },
    )
    (directory / "manifest.json").write_bytes(json_bytes(manifest) + b"\n")


def verify_experiment_outputs(directory, inputs):
    from app.ml.experiment import EXPERIMENT_RULES
    from app.ml.metrics import METRIC_RULES
    from app.ml.models import PREDICTION_NAMES
    from app.ml.splitting import SPLIT_RULES

    manifest = json.loads((directory / "manifest.json").read_bytes())
    expected = dict(
        format_version=1,
        status="complete",
        snapshot_sha256=inputs.snapshot_sha256,
        input_manifests=inputs.input_manifests,
        split_rules=SPLIT_RULES,
        metric_rules=METRIC_RULES,
        experiment_rules=EXPERIMENT_RULES,
    )
    if (
        not isinstance(manifest, dict)
        or any(manifest.get(name) != value for name, value in expected.items())
        or set(manifest.get("libraries", ()))
        != {"python", "numpy", "scikit_learn", "lightgbm"}
        or not isinstance(manifest.get("files"), dict)
        or set(manifest["files"]) != set(EXPERIMENT_OUTPUT_FILES)
    ):
        raise ValueError("Deney manifesti girişlerle veya kurallarla uyuşmuyor")
    for name in EXPERIMENT_OUTPUT_FILES:
        if (
            hashlib.sha256((directory / name).read_bytes()).hexdigest()
            != manifest["files"][name]
        ):
            raise ValueError(f"Deney dosyasının parmak izi tutmuyor: {name}")
    labels = {row.anchor.key: row.anchor.label for row in inputs.split.samples}
    reserved = {
        (row["product_id"], row["source"], row["anchor_day"])
        for row in inputs.plan.assignments
        if row["role"] == "test_reserved"
    }
    allowed = {
        (record["product_id"], record["source"], record["anchor_day"]): fold["month"]
        for fold in inputs.plan.folds
        if fold["status"] == "ready"
        for record in fold["members"]["validation"]
    }
    seen = set()
    for line in (directory / "predictions.jsonl").read_bytes().splitlines():
        row = json.loads(line)
        if set(row) != {
            "fold",
            "product_id",
            "source",
            "anchor_day",
            "label",
            *PREDICTION_NAMES,
        }:
            raise ValueError("Tahmin satırının alanları sözleşmeye uymuyor")
        key = (row["product_id"], row["source"], date.fromisoformat(row["anchor_day"]))
        if key in reserved or key in seen:
            raise ValueError("Tahmin dosyasında saklı test veya tekrarlı anahtar var")
        if (
            allowed.get(key) != row["fold"]
            or labels.get(key) != row["label"]
            or not all(0 <= row[name] <= 1 for name in PREDICTION_NAMES)
        ):
            raise ValueError("Tahmin satırı kat doğrulama üyeliğiyle uyuşmuyor")
        seen.add(key)
    if seen != set(allowed):
        raise ValueError("Doğrulama başlangıçlarının tahmini eksik veya fazla")
    report = json.loads((directory / "report.json").read_bytes())
    if (
        report.get("test_opened") is not False
        or report.get("own_source_scored") is not False
        or report.get("model_frozen") is not False
        or report.get("experiment_rules") != EXPERIMENT_RULES
    ):
        raise ValueError("Deney raporu saklı test veya kendi kaynağı kuralına uymuyor")
    json.loads((directory / "models.json").read_bytes())
    return manifest
