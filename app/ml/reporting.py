"""Etiket kanıtlarını belirlenimci dosyalara yazar; manifest en son oluşur."""

import hashlib
import json
from datetime import date, datetime

from app.ml.labels import RULES

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
