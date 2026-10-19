"""İki ayrı fiyat serisinin ML pencerelerini yalnız okuyarak denetler."""

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

import psycopg
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.manual import api_ui_check as reader  # noqa: E402

ISTANBUL = ZoneInfo("Europe/Istanbul")
PositiveInt = Annotated[int, Field(gt=0)]
RULES = {
    "version": 1,
    "timezone": "Europe/Istanbul",
    "past_days_including_anchor": 30,
    "future_days": 7,
    "drop_percent": 5,
    "scheduled_hours": [10, 22],
    "own_reference": "evening_run_minimum",
    "own_future": "daily_observed_minimum",
    "split_percent": [70, 15, 15],
    "purge": "target_end_must_precede_next_partition",
    "imputation": False,
    "cimri_training_permission": "unverified",
}
REASONS = {
    "insufficient_history_period": "30 günlük geçmiş henüz yok",
    "future_not_available": "yedi günlük gelecek kayıt aralığında yok",
    "history_missing_day": "geçmişte kayıtsız gün var",
    "future_missing_day": "gelecekte kayıtsız gün var",
    "history_missing_price": "geçmişte başlangıç fiyatı eksik",
    "future_missing_price": "gelecekte günlük minimum fiyat eksik",
    "history_day_quality": "geçmişte eksik veya kusurlu tur var",
    "future_day_quality": "gelecekte eksik veya kusurlu tur var",
    "scope_change": "pencerede ürünün takip kapsamı değişti",
    "source_identity_change": "pencerede Cimri ürün kimliği değişti",
}


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ProductRecord(Record):
    product_id: PositiveInt
    product_key: str
    brand: str
    model: str
    storage_gb: PositiveInt
    active: bool


class PlatformRecord(Record):
    key: str
    active: bool


class ListingRecord(Record):
    listing_id: str
    product_id: PositiveInt
    platform: str
    active: bool


class RunRecord(Record):
    run_id: PositiveInt
    trigger: Literal["scheduled", "manual"]
    status: Literal["running", "completed", "interrupted"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None
    planned_count: Annotated[int, Field(ge=0)]


class CheckRecord(Record):
    run_id: PositiveInt
    listing_id: str
    product_id: PositiveInt
    checked_at: AwareDatetime | None
    outcome: Literal["offer", "sold_out", "error"] | None
    current_price: PositiveInt | None


class MarketRecord(Record):
    product_id: PositiveInt
    source: Literal["cimri"]
    source_product_id: Annotated[str, Field(pattern=r"^[1-9][0-9]*$")]
    source_url: str
    day: date
    price_kurus: PositiveInt | None
    captured_at: AwareDatetime


class Snapshot(Record):
    version: Literal[1]
    captured_at: AwareDatetime
    commit: str | None
    verifier_sha256: str
    catalog_sha256: str
    mapping_sha256: str
    source_sha256: dict[str, str]
    source_unchanged: bool
    products: list[ProductRecord]
    platforms: list[PlatformRecord]
    listings: list[ListingRecord]
    collection_runs: list[RunRecord]
    listing_checks: list[CheckRecord]
    market_history: list[MarketRecord]


def now():
    return datetime.now(timezone.utc)


def dates(start, end):
    return [start + timedelta(days=n) for n in range(max(0, (end - start).days + 1))]


def scheduled_slot(at):
    local = at.astimezone(ISTANBUL)
    if local.hour >= 22:
        return local.date(), 22
    if local.hour >= 10:
        return local.date(), 10
    return local.date() - timedelta(days=1), 22


def source_hashes(data):
    return {name: reader.fingerprint(data[name]) for name in reader.RELATIONS}


def unique_index(rows, key):
    result = {key(row): row for row in rows}
    if len(result) != len(rows):
        raise reader.CheckError("Veri görüntüsünde tekrarlı kimlik var.")
    return result


def validate_snapshot(snapshot):
    products = unique_index(snapshot.products, lambda row: row.product_id)
    unique_index(snapshot.products, lambda row: row.product_key)
    platforms = unique_index(snapshot.platforms, lambda row: row.key)
    listings = unique_index(snapshot.listings, lambda row: row.listing_id)
    runs = unique_index(snapshot.collection_runs, lambda row: row.run_id)
    unique_index(snapshot.listing_checks, lambda row: (row.run_id, row.listing_id))
    unique_index(snapshot.market_history, lambda row: (row.product_id, row.day))
    hashes = [
        snapshot.verifier_sha256,
        snapshot.catalog_sha256,
        snapshot.mapping_sha256,
        *snapshot.source_sha256.values(),
    ]
    if set(snapshot.source_sha256) != set(reader.RELATIONS) or any(
        len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        for value in hashes
    ):
        raise reader.CheckError("Veri görüntüsünün parmak izleri geçersiz.")
    for listing in listings.values():
        if listing.product_id not in products or listing.platform not in platforms:
            raise reader.CheckError("Veri görüntüsünde bağlantı kimliği uyuşmuyor.")
    for run in runs.values():
        if (run.status == "running") != (run.finished_at is None) or (
            run.finished_at is not None and run.finished_at < run.started_at
        ):
            raise reader.CheckError("Veri görüntüsünde tur zamanları uyuşmuyor.")
    planned_counts = Counter(row.run_id for row in snapshot.listing_checks)
    if any(planned_counts[row.run_id] != row.planned_count for row in runs.values()):
        raise reader.CheckError("Veri görüntüsünde plan ve kontrol sayıları uyuşmuyor.")
    for check in snapshot.listing_checks:
        listing = listings.get(check.listing_id)
        if (
            check.run_id not in runs
            or listing is None
            or listing.product_id != check.product_id
            or (check.outcome == "offer") != (check.current_price is not None)
            or (check.outcome is None) != (check.checked_at is None)
            or (
                check.checked_at is not None
                and (
                    check.checked_at < runs[check.run_id].started_at
                    or (
                        runs[check.run_id].finished_at is not None
                        and check.checked_at > runs[check.run_id].finished_at
                    )
                )
            )
        ):
            raise reader.CheckError("Veri görüntüsünde kontrol kaydı uyuşmuyor.")
    if any(row.product_id not in products for row in snapshot.market_history):
        raise reader.CheckError("Veri görüntüsünde Cimri ürün kimliği uyuşmuyor.")


def make_snapshot(data, captured_at):
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    fields = {
        "products": ProductRecord,
        "platforms": PlatformRecord,
        "listings": ListingRecord,
        "collection_runs": RunRecord,
        "listing_checks": CheckRecord,
        "market_history": MarketRecord,
    }
    payload = {
        "version": 1,
        "captured_at": captured_at,
        "commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "catalog_sha256": hashlib.sha256(
            (ROOT / "config/catalog.json").read_bytes()
        ).hexdigest(),
        "mapping_sha256": hashlib.sha256(
            (ROOT / "config/market_history.json").read_bytes()
        ).hexdigest(),
        "source_sha256": source_hashes(data),
        "source_unchanged": True,
    }
    for name, model in fields.items():
        payload[name] = [
            {field: row[field] for field in model.model_fields} for row in data[name]
        ]
    snapshot = Snapshot.model_validate(payload)
    validate_snapshot(snapshot)
    return snapshot


def load_snapshot(path):
    envelope = json.loads(path.read_text(encoding="utf-8"))
    if (
        set(envelope) != {"sha256", "payload"}
        or reader.fingerprint(envelope["payload"]) != envelope["sha256"]
    ):
        raise reader.CheckError("Veri görüntüsünün parmak izi uyuşmuyor.")
    snapshot = Snapshot.model_validate_json(json.dumps(envelope["payload"]))
    validate_snapshot(snapshot)
    return snapshot


def grouped_checks(snapshot):
    groups = defaultdict(list)
    for row in snapshot.listing_checks:
        groups[row.product_id, row.run_id].append(row)
    return groups


def own_series(snapshot, product, groups, slots, closed_day):
    product_id = product.product_id
    runs = [
        row for row in snapshot.collection_runs if (product_id, row.run_id) in groups
    ]
    scheduled = sorted(
        (row for row in runs if row.trigger == "scheduled"),
        key=lambda row: (row.started_at, row.run_id),
    )
    start = min((scheduled_slot(row.started_at)[0] for row in scheduled), default=None)
    days = []
    for day in dates(start, closed_day) if start else []:
        reasons = set()
        scopes, prices, reference, run_ids = [], [], None, []
        observed = False
        for hour in (10, 22):
            assigned = slots.get((day, hour), [])
            if len(assigned) != 1:
                reasons.add("missing_slot" if not assigned else "duplicate_slot")
            for run in assigned:
                run_ids.append(run.run_id)
                checks = groups.get((product_id, run.run_id), [])
                if not checks:
                    reasons.add("product_not_planned")
                    continue
                scopes.append(tuple(sorted(row.listing_id for row in checks)))
                observed = observed or any(row.checked_at is not None for row in checks)
                if run.status != "completed":
                    reasons.add("unfinished_run")
                if (
                    run.finished_at
                    and run.finished_at.astimezone(ISTANBUL).date() != day
                ):
                    reasons.add("late_completion")
                if any(row.outcome not in ("offer", "sold_out") for row in checks):
                    reasons.add("incomplete_answers")
                offers = [row.current_price for row in checks if row.outcome == "offer"]
                if run.status == "completed":
                    prices.extend(offers)
                    if hour == 22 and len(assigned) == 1:
                        reference = min(offers, default=None)
        scope = scopes[0] if scopes and len(set(scopes)) == 1 else None
        if len(set(scopes)) > 1:
            reasons.add("intraday_scope_change")
        days.append(
            dict(
                day=day,
                observed=observed,
                reference_price=reference,
                minimum_price=min(prices, default=None),
                scope=scope,
                reasons=sorted(reasons),
                run_ids=run_ids,
            )
        )
    completed = [row for row in runs if row.status == "completed"]
    checks = [row for row in snapshot.listing_checks if row.product_id == product_id]
    gaps = [
        (after.started_at - before.started_at).total_seconds() / 3600
        for before, after in zip(scheduled, scheduled[1:])
    ]
    inventory = dict(
        first_run=min((row.started_at for row in runs), default=None),
        last_run=max((row.started_at for row in runs), default=None),
        runs=len(runs),
        runs_by_trigger=dict(Counter(row.trigger for row in runs)),
        runs_by_status=dict(Counter(row.status for row in runs)),
        completed_product_prices=sum(
            any(c.outcome == "offer" for c in groups[product_id, row.run_id])
            for row in completed
        ),
        listing_checks=len(checks),
        outcomes=dict(Counter(row.outcome or "pending" for row in checks)),
        maximum_scheduled_gap_hours=max(gaps, default=None),
        scope_changes=sum(
            {c.listing_id for c in groups[product_id, before.run_id]}
            != {c.listing_id for c in groups[product_id, after.run_id]}
            for before, after in zip(scheduled, scheduled[1:])
        ),
    )
    return days, inventory


def market_series(snapshot, product, closed_day):
    rows = sorted(
        (
            row
            for row in snapshot.market_history
            if row.product_id == product.product_id
        ),
        key=lambda row: row.day,
    )
    days = [
        dict(
            day=row.day,
            observed=True,
            reference_price=row.price_kurus,
            minimum_price=row.price_kurus,
            scope=(row.source_product_id,),
            reasons=[],
            run_ids=[],
        )
        for row in rows
        if row.day <= closed_day
    ]
    inventory = dict(
        recorded_rows=len(rows),
        recorded_prices=sum(row.price_kurus is not None for row in rows),
        recorded_nulls=sum(row.price_kurus is None for row in rows),
        excluded_unclosed_days=sum(row.day > closed_day for row in rows),
        source_product_ids=sorted({row.source_product_id for row in rows}),
        source_urls=sorted({row.source_url for row in rows}),
        last_captured_at=max((row.captured_at for row in rows), default=None),
        stale_calendar_days=(closed_day - days[-1]["day"]).days if days else None,
        seller_scope_history="unknown",
        training_permission="unverified",
    )
    return days, inventory


def windows_for(product_id, source, days):
    by_day = {row["day"]: row for row in days}
    if not days:
        return []
    start, end = days[0]["day"], days[-1]["day"]
    windows = []
    for anchor in dates(start, end):
        past = dates(anchor - timedelta(days=29), anchor)
        future = dates(anchor + timedelta(days=1), anchor + timedelta(days=7))
        reasons = set()
        if past[0] < start:
            reasons.add("insufficient_history_period")
        if future[-1] > end:
            reasons.add("future_not_available")
        for prefix, period, field in (
            ("history", past, "reference_price"),
            ("future", future, "minimum_price"),
        ):
            present = [by_day[day] for day in period if day in by_day]
            if any(
                start <= day <= end
                and (day not in by_day or not by_day[day]["observed"])
                for day in period
            ):
                reasons.add(f"{prefix}_missing_day")
            if any(row[field] is None for row in present):
                reasons.add(f"{prefix}_missing_price")
            if any(row["reasons"] for row in present):
                reasons.add(f"{prefix}_day_quality")
        scopes = {
            tuple(by_day[day]["scope"])
            for day in past + future
            if day in by_day and by_day[day]["scope"] is not None
        }
        if len(scopes) > 1:
            reasons.add("scope_change" if source == "own" else "source_identity_change")
        base = by_day.get(anchor, {}).get("reference_price")
        prices = [
            by_day[day]["minimum_price"]
            for day in future
            if day in by_day and by_day[day]["minimum_price"] is not None
        ]
        minimum = min(prices, default=None)
        label = int(100 * minimum <= 95 * base) if not reasons else None
        windows.append(
            dict(
                product_id=product_id,
                source=source,
                anchor_day=anchor,
                history_start=past[0],
                target_end=future[-1],
                reference_price=base,
                future_minimum_price=minimum,
                label=label,
                reasons=sorted(reasons),
                partition=None,
            )
        )
    return windows


def label_counts(windows):
    usable = [row for row in windows if row["label"] is not None]
    return dict(
        windows=len(usable),
        positive=sum(row["label"] == 1 for row in usable),
        negative=sum(row["label"] == 0 for row in usable),
        distinct_anchor_days=len({row["anchor_day"] for row in usable}),
    )


def split_windows(windows):
    usable = [row for row in windows if row["label"] is not None]
    days = sorted({row["anchor_day"] for row in usable})
    cuts = (len(days) * 70 // 100, len(days) * 85 // 100)
    periods = dict(
        train=days[: cuts[0]], validation=days[cuts[0] : cuts[1]], test=days[cuts[1] :]
    )
    assignments = {day: name for name, period in periods.items() for day in period}
    for row in usable:
        name = assignments[row["anchor_day"]]
        following = [
            period[0]
            for key, period in periods.items()
            if period and period[0] > row["anchor_day"] and key != name
        ]
        row["partition"] = (
            f"purged_{name}"
            if following and row["target_end"] >= min(following)
            else name
        )
    result = {}
    for name, period in periods.items():
        members = [row for row in usable if row["partition"] == name]
        result[name] = dict(
            first_anchor=period[0] if period else None,
            last_anchor=period[-1] if period else None,
            **label_counts(members),
            by_product={
                str(pid): label_counts(
                    [row for row in members if row["product_id"] == pid]
                )
                for pid in sorted({row["product_id"] for row in windows})
            },
        )
    result["purged"] = label_counts(
        [row for row in usable if row["partition"].startswith("purged_")]
    )
    problems = []
    if not usable:
        problems.append("no_usable_windows")
    if usable and len({row["label"] for row in usable}) < 2:
        problems.append("single_class")
    for name in periods:
        if not result[name]["windows"]:
            problems.append(f"empty_{name}")
        elif not result[name]["positive"] or not result[name]["negative"]:
            problems.append(f"single_class_{name}")
    result["limitations"] = problems
    result["assessment"] = "numerical_candidate" if not problems else "limited"
    return result


def intervals(days):
    result = []
    for day in sorted(set(days)):
        if result and day == result[-1]["end"] + timedelta(days=1):
            result[-1]["end"] = day
            result[-1]["days"] += 1
        else:
            result.append(dict(start=day, end=day, days=1))
    return result


def describe_series(source, days, inventory, windows, closed_day, current_scope):
    first, last = (days[0]["day"], days[-1]["day"]) if days else (None, None)
    present = {row["day"] for row in days if row["observed"]}
    missing = [day for day in dates(first, last) if day not in present] if days else []
    counts = label_counts(windows)
    nonoverlapping, previous_end = 0, None
    for row in windows:
        if row["label"] is not None and (
            previous_end is None or row["history_start"] > previous_end
        ):
            nonoverlapping += 1
            previous_end = row["target_end"]
    periods = []
    for row in days:
        if row["reasons"] or row["scope"] is None:
            continue
        if (
            periods
            and periods[-1]["end"] + timedelta(days=1) == row["day"]
            and periods[-1]["scope"] == row["scope"]
        ):
            periods[-1]["end"] = row["day"]
            periods[-1]["days"] += 1
        else:
            periods.append(
                dict(start=row["day"], end=row["day"], days=1, scope=row["scope"])
            )
    earliest_end = None
    if source == "own" and current_scope and not counts["windows"]:
        streak = 0
        for row in reversed(days):
            if (
                row["day"] != closed_day - timedelta(days=streak)
                or row["reasons"]
                or row["reference_price"] is None
                or row["scope"] != current_scope
            ):
                break
            streak += 1
        earliest_end = closed_day + timedelta(days=max(0, 37 - streak))
    return dict(
        **inventory,
        first_day=first,
        last_day=last,
        calendar_days=(last - first).days + 1 if days else 0,
        observed_days=sum(row["observed"] for row in days),
        reference_prices=sum(row["reference_price"] is not None for row in days),
        missing_reference_prices=sum(row["reference_price"] is None for row in days),
        missing_calendar_days=len(missing),
        missing_calendar_intervals=intervals(missing),
        missing_price_intervals=intervals(
            [row["day"] for row in days if row["reference_price"] is None]
        ),
        day_quality_counts=dict(
            Counter(reason for row in days for reason in row["reasons"])
        ),
        consistent_periods=periods,
        candidate_anchor_days=len(windows),
        excluded_windows=sum(row["label"] is None for row in windows),
        exclusion_counts=dict(
            Counter(reason for row in windows for reason in row["reasons"])
        ),
        **counts,
        nonoverlapping_37_day_windows=nonoverlapping,
        earliest_conditional_window_end=earliest_end,
        earliest_conditional_audit_day=(
            earliest_end + timedelta(days=1) if earliest_end else None
        ),
        forecast_assumption=(
            "same_product_scope_and_complete_prices_every_day" if earliest_end else None
        ),
    )


def analyze(snapshot):
    validate_snapshot(snapshot)
    closed_day = snapshot.captured_at.astimezone(ISTANBUL).date() - timedelta(days=1)
    groups = grouped_checks(snapshot)
    slots = defaultdict(list)
    for run in snapshot.collection_runs:
        if run.trigger == "scheduled":
            slots[scheduled_slot(run.started_at)].append(run)
    active_platforms = {row.key for row in snapshot.platforms if row.active}
    summaries, windows, daily = [], [], []
    for product in snapshot.products:
        current_scope = tuple(
            sorted(
                row.listing_id
                for row in snapshot.listings
                if row.product_id == product.product_id
                and row.active
                and row.platform in active_platforms
            )
        )
        active_pages = len(current_scope)
        summary = dict(product=product.model_dump(), active_tracking_pages=active_pages)
        for source in ("own", "cimri"):
            days, inventory = (
                own_series(snapshot, product, groups, slots, closed_day)
                if source == "own"
                else market_series(snapshot, product, closed_day)
            )
            samples = windows_for(product.product_id, source, days)
            summary[source] = describe_series(
                source,
                days,
                inventory,
                samples,
                closed_day,
                current_scope if product.active else (),
            )
            if source == "own":
                summary[source]["no_active_tracking_pages"] = not active_pages
                summary[source]["collection_available"] = (
                    product.active and active_pages > 0
                )
            windows.extend(samples)
            daily.extend(
                dict(product_id=product.product_id, source=source, **row)
                for row in days
            )
        summaries.append(summary)
    splits = {
        source: split_windows([row for row in windows if row["source"] == source])
        for source in ("own", "cimri")
    }
    result = dict(
        snapshot_at=snapshot.captured_at,
        last_closed_day=closed_day,
        rules=RULES,
        reason_labels=REASONS,
        products=summaries,
        sources={
            source: dict(
                **label_counts([row for row in windows if row["source"] == source]),
                products_with_windows=sum(
                    row[source]["windows"] > 0 for row in summaries
                ),
                split=splits[source],
                training_permission=(
                    "unverified" if source == "cimri" else "not_assessed_by_this_tool"
                ),
            )
            for source in ("own", "cimri")
        },
        model_trained=False,
        production_prediction_enabled=False,
    )
    return result, windows, daily


def markdown_report(result):
    lines = [
        "# Bakım 5 — ML veri yeterliliği",
        "",
        f"Son tamamlanmış takvim günü: {result['last_closed_day']}",
        "",
        "Bu rapor model eğitmez ve tahmin yayımlamaz. "
        "Cimri'nin ML kullanım uygunluğu doğrulanmadı.",
        "Örtüşen pencereler bağımsız örnek sayılmaz; eksik fiyatlar doldurulmadı.",
        "",
        "| Ürün | Kendi: örnek (+ / −) | Cimri: örnek (+ / −) | Koşullu ilk denetim |",
        "|---|---:|---:|---|",
    ]
    for row in result["products"]:
        product = row["product"]
        name = (
            f"{product['brand']} {product['model']} {product['storage_gb']} GB".replace(
                "|", " "
            )
        )
        counts = [
            f"{row[s]['windows']} ({row[s]['positive']} / {row[s]['negative']})"
            for s in ("own", "cimri")
        ]
        earliest = row["own"]["earliest_conditional_audit_day"]
        note = (
            str(earliest)
            if earliest
            else (
                "Etkin takip sayfası yok"
                if row["own"]["no_active_tracking_pages"]
                else "—"
            )
        )
        lines.append(f"| {name} | {counts[0]} | {counts[1]} | {note} |")
    lines.extend(
        [
            "",
            "Tarihler, aynı kapsamda her gün iki tam tur ve geçerli fiyatların "
            "sürmesi koşuluna bağlıdır.",
            "",
        ]
    )
    for source, title in (("own", "Kendi geçmişimiz"), ("cimri", "Cimri geçmişi")):
        data = result["sources"][source]
        limitations = (
            ", ".join(data["split"]["limitations"]) or "bu sayımlarda bulunmadı"
        )
        lines.extend(
            [
                f"## {title}",
                "",
                f"{data['products_with_windows']} üründe {data['windows']} pencere; "
                f"{data['positive']} olumlu / {data['negative']} olumsuz.",
                "",
                "| Zaman bölümü | Örnek | Olumlu | Olumsuz | Farklı gün |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for partition in ("train", "validation", "test", "purged"):
            part = data["split"][partition]
            lines.append(
                f"| {partition} | {part['windows']} | {part['positive']} "
                f"| {part['negative']} | {part['distinct_anchor_days']} |"
            )
        lines.extend(
            [
                "",
                f"Sayısal değerlendirme: {data['split']['assessment']}; sınırlar: "
                f"{limitations}.",
                "",
            ]
        )
    lines.extend(
        [
            "Bu sayımlar yeterlilik garantisi değildir. Ayrıntılı elenme nedenleri "
            "report.json ve windows.jsonl içindedir.",
            "Pencere bulunmayan ürünler mevcut ölçütlerle ML örneği sağlamaz; "
            "katalogdan kaldırılmaz.",
            "Cimri satıcı kapsamının tarih boyunca aynı kaldığı doğrulanamaz. "
            "Kullanım belirsizliği ve ölçüm farkı ayrı sınırlardır.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            reader.json_value(value),
            stream,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")


def save_outputs(output, snapshot, result, windows, daily, proof):
    payload = snapshot.model_dump(mode="json")
    write_json(
        output / "snapshot.json",
        dict(sha256=reader.fingerprint(payload), payload=payload),
    )
    write_json(output / "rules.json", RULES)
    write_json(output / "report.json", result)
    write_json(
        output / "source_check.json",
        dict(
            proof,
            analysis_verifier_sha256=hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        ),
    )
    for name, records in (("windows.jsonl", windows), ("daily.jsonl", daily)):
        with (output / name).open("x", encoding="utf-8") as stream:
            for row in records:
                stream.write(
                    json.dumps(
                        reader.json_value(row), ensure_ascii=False, allow_nan=False
                    )
                    + "\n"
                )
    with (output / "report.md").open("x", encoding="utf-8") as stream:
        if result["status"] != "verified":
            stream.write("**Kesin kabul edilmedi: denetimde kaynak değişti.**\n\n")
        stream.write(markdown_report(result))
    write_json(
        output / "manifest.json",
        {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.iterdir())
            if path.is_file()
        },
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path)
    args = parser.parse_args(argv)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Yeni bir çıktı klasörü gerekli; mevcut klasör değiştirilmedi.")
        return 1
    try:
        if args.snapshot:
            snapshot = load_snapshot(args.snapshot)
            result, windows, daily = analyze(snapshot)
            proof = dict(mode="offline", source_unchanged=snapshot.source_unchanged)
        else:
            url = reader.configured_url()
            with psycopg.connect(url, autocommit=True, connect_timeout=3) as conn:
                _, before = reader.read_dataset(conn)
                if any(row["status"] == "running" for row in before["collection_runs"]):
                    raise reader.CheckError(
                        "Toplama turu sürüyor; denetim başlatılmadı."
                    )
                snapshot = make_snapshot(before, now())
                result, windows, daily = analyze(snapshot)
                _, after = reader.read_dataset(conn)
                after_hashes = source_hashes(after)
                changed = [
                    name
                    for name in reader.RELATIONS
                    if after_hashes[name] != snapshot.source_sha256[name]
                ]
                snapshot = snapshot.model_copy(update={"source_unchanged": not changed})
                proof = dict(
                    mode="database",
                    before=snapshot.source_sha256,
                    after=after_hashes,
                    changed_relations=changed,
                    source_unchanged=not changed,
                )
        code = 0 if snapshot.source_unchanged else 2
        result.update(
            status="verified" if code == 0 else "inconclusive", exit_code=code
        )
        save_outputs(args.output_dir, snapshot, result, windows, daily, proof)
    except KeyboardInterrupt:
        code, error = 130, "interrupted"
    except reader.CheckError as failure:
        print(str(failure))
        code, error = 1, "readiness_error"
    except psycopg.Error:
        code, error = 1, "database_error"
    except (ValidationError, ValueError, KeyError, TypeError):
        code, error = 1, "snapshot_error"
    except Exception:
        code, error = 1, "check_error"
    else:
        print(f"Rapor: {args.output_dir / 'report.json'}")
        label = "doğrulandı" if code == 0 else "kaynak değişti; kesin kabul edilmedi"
        print(
            f"Durum: {label} · Ürün: {len(result['products'])} "
            f"· Kendi örnek: {result['sources']['own']['windows']} "
            f"· Cimri örnek: {result['sources']['cimri']['windows']}"
        )
        print(
            "Çıkış 0, denetimin tamamlandığını gösterir; "
            "ML için yeterlilik veya Cimri kullanım izni değildir."
        )
        return code
    failure = dict(status="failed", exit_code=code, error_code=error)
    try:
        target = (
            args.output_dir / "failure.json"
            if (args.output_dir / "report.json").exists()
            else args.output_dir / "report.json"
        )
        write_json(target, failure)
    except OSError:
        pass
    print(f"Denetim tamamlanamadı: {error}. Çıkış: {code}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
