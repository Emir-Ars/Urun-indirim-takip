"""Temel SQL kayıtlarıyla yerel API'yi karşılaştırır; hiçbir DB kaydı yazmaz."""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.ui.api_client import ApiClient, ApiClientError  # noqa: E402

RELATIONS = {
    "schema_migrations": "version",
    "platforms": "key",
    "products": "product_id",
    "listings": "listing_id",
    "collection_runs": "run_id",
    "listing_checks": "run_id, listing_id",
    "market_history": "product_id, source, day",
    "product_run_prices": "product_id, run_id",
}
CHECK_FIELDS = (
    "run_id",
    "listing_id",
    "product_id",
    "checked_at",
    "outcome",
    "current_price",
    "original_price",
    "seller_name",
    "seller_rating",
    "seller_rating_scale",
    "stock_status",
    "error_code",
)
RUN_FIELDS = (
    "run_id",
    "trigger",
    "status",
    "started_at",
    "finished_at",
    "planned_count",
)


class CheckError(Exception):
    pass


def json_value(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def fingerprint(rows):
    raw = json.dumps(
        json_value(rows),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_reader(conn):
    row = conn.execute("""
        SELECT current_database(), current_user, session_user, rolcanlogin,
               rolsuper, rolcreatedb, rolcreaterole, rolinherit, rolreplication,
               rolbypassrls, current_setting('default_transaction_read_only')
        FROM pg_roles WHERE rolname = current_user
    """).fetchone()
    database, user, session, *flags, read_only = row
    expected = (
        "fiyat_takip_api"
        if database == "fiyat_takip"
        else ("fiyat_takip_api_test" if database.endswith("_test") else None)
    )
    if (
        expected is None
        or user != expected
        or session != expected
        or flags != [True, False, False, False, False, False, False]
        or read_only != "on"
    ):
        raise CheckError("Okuma hesabı veya veritabanı uygun değil.")
    privileged = conn.execute("""
        WITH reader AS (SELECT oid FROM pg_roles WHERE rolname = current_user)
        SELECT EXISTS (SELECT 1 FROM pg_auth_members
                       WHERE member = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_database
                       WHERE datdba = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_namespace
                       WHERE nspowner = (SELECT oid FROM reader))
            OR EXISTS (SELECT 1 FROM pg_class
                       WHERE relowner = (SELECT oid FROM reader))
            OR has_database_privilege(current_user, current_database(), 'CREATE')
            OR has_schema_privilege(current_user, 'public', 'CREATE')
            OR EXISTS (
                SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','f')
                  AND (has_table_privilege(current_user,c.oid,
                       'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                       OR has_any_column_privilege(current_user,c.oid,
                           'INSERT,UPDATE,REFERENCES'))
            )
    """).fetchone()[0]
    if privileged:
        raise CheckError("Okuma hesabının fazladan yetkisi var.")
    for relation in RELATIONS:
        name = f"public.{relation}"
        if conn.execute("SELECT to_regclass(%s)", (name,)).fetchone()[0] is None:
            raise CheckError("Gerekli veritabanı nesnesi bulunmuyor.")
        if not conn.execute(
            "SELECT has_table_privilege(current_user,%s,'SELECT')", (name,)
        ).fetchone()[0]:
            raise CheckError("Okuma hesabının SELECT izni eksik.")
    return {"database": database, "user": user, "read_only": True}


def read_dataset(conn):
    with conn.transaction():
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        conn.execute("SET LOCAL TimeZone = 'UTC'")
        identity = validate_reader(conn)
        with conn.cursor(row_factory=dict_row) as cursor:
            data = {}
            for relation, ordering in RELATIONS.items():
                cursor.execute(f"SELECT * FROM public.{relation} ORDER BY {ordering}")
                data[relation] = cursor.fetchall()
    migrations = []
    for path in sorted((ROOT / "app/database/migrations").glob("*.sql")):
        version, name = path.stem.split("_", 1)
        raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        migrations.append(
            (int(version), name, hashlib.sha256(raw.encode()).hexdigest())
        )
    recorded = [
        (r["version"], r["name"], r["checksum"]) for r in data["schema_migrations"]
    ]
    if recorded != migrations:
        raise CheckError("Migration kayıtları ve proje şeması uyuşmuyor.")
    return identity, data


def listing_result(check, listings, platforms):
    result = {key: check[key] for key in CHECK_FIELDS}
    page = listings[check["listing_id"]]
    platform = platforms[page["platform"]]
    result.update(
        platform=page["platform"],
        platform_name=platform["name"],
        platform_active=platform["active"],
        url=page["url"],
        color=page["color"],
        listing_active=page["active"],
    )
    for key in ("seller_rating", "seller_rating_scale"):
        if result[key] is not None:
            result[key] = float(result[key])
    return result


def reference_statistics(history):
    current = history[-1] if history else None
    pages = current["planned_listing_ids"] if current else []
    scope = []
    for row in reversed(history):
        if row["partial"] or row["planned_listing_ids"] != pages:
            break
        scope.insert(0, row)
    reason = "no_history" if current is None else "incomplete_scope"
    if not scope:
        empty = dict(
            value=None,
            reasons=[reason],
            period_started_at=None,
            period_ended_at=None,
            observations=0,
        )
        return dict(
            source_run_id=current["run_id"] if current else None,
            scope_started_at=None,
            scope_ended_at=None,
            scope_runs=0,
            planned_listing_ids=pages,
            low_30d=empty.copy(),
            high_in_scope=empty.copy(),
            volatility_30d=dict(**empty, transitions=0, days=0),
        )
    start, end = scope[0]["run_started_at"], current["run_started_at"]
    cutoff = end - timedelta(days=30)
    window = [r for r in scope if cutoff <= r["run_started_at"] <= end]
    prices = [r["best_price"] for r in scope if r["best_price"] is not None]
    recent_prices = [r["best_price"] for r in window if r["best_price"] is not None]
    low_reasons = []
    if start > cutoff:
        low_reasons.append("insufficient_period")
    if not recent_prices:
        low_reasons.append("no_prices")
    logs, used, days = [], set(), set()
    istanbul = ZoneInfo("Europe/Istanbul")
    for index in range(1, len(window)):
        previous, row = window[index - 1], window[index]
        times = [previous["best_checked_at"], row["best_checked_at"]]
        if (
            previous["best_price"] is None
            or row["best_price"] is None
            or any(t is None for t in times)
        ):
            continue
        seconds = (times[1] - times[0]).total_seconds()
        if 0 < seconds <= 64800:
            logs.append(math.log(row["best_price"] / previous["best_price"]))
            used.update((previous["run_id"], row["run_id"]))
            days.update(t.astimezone(istanbul).date() for t in times)
    volatility_reasons = []
    if not recent_prices:
        volatility_reasons.append("no_prices")
    if len(logs) < 14:
        volatility_reasons.append("insufficient_transitions")
    if len(days) < 7:
        volatility_reasons.append("insufficient_days")
    value = None
    if not volatility_reasons:
        mean = math.fsum(logs) / len(logs)
        value = (
            math.sqrt(math.fsum((x - mean) ** 2 for x in logs) / (len(logs) - 1)) * 100
        )
    period = dict(period_started_at=max(start, cutoff), period_ended_at=end)
    return dict(
        source_run_id=current["run_id"],
        scope_started_at=start,
        scope_ended_at=end,
        scope_runs=len(scope),
        planned_listing_ids=pages,
        low_30d=dict(
            value=None if low_reasons else min(recent_prices),
            reasons=low_reasons,
            observations=len(recent_prices),
            **period,
        ),
        high_in_scope=dict(
            value=max(prices) if prices else None,
            reasons=[] if prices else ["no_prices"],
            observations=len(prices),
            period_started_at=start,
            period_ended_at=end,
        ),
        volatility_30d=dict(
            value=value,
            reasons=volatility_reasons,
            observations=len(used),
            transitions=len(logs),
            days=len(days),
            **period,
        ),
    )


def reference_product(data, product, generated_at, history_days=30, cimri_days=366):
    listings = {r["listing_id"]: r for r in data["listings"]}
    platforms = {r["key"]: r for r in data["platforms"]}
    runs = {
        r["run_id"]: r for r in data["collection_runs"] if r["status"] == "completed"
    }
    checks = defaultdict(list)
    for row in data["listing_checks"]:
        if row["product_id"] == product["product_id"] and row["run_id"] in runs:
            checks[row["run_id"]].append(listing_result(row, listings, platforms))
    history, previous_answered, best_by_run = [], [], {}
    for run_id in sorted(checks):
        pages = sorted(checks[run_id], key=lambda r: r["listing_id"])
        offers = sorted(
            (r for r in pages if r["outcome"] == "offer"),
            key=lambda r: (r["current_price"], r["listing_id"]),
        )
        best = offers[0] if offers else None
        best_by_run[run_id] = best
        answered = [
            r["listing_id"] for r in pages if r["outcome"] in ("offer", "sold_out")
        ]
        times = [r["checked_at"] for r in pages if r["checked_at"] is not None]
        previous = history[-1] if history else None
        hours = None
        if previous:
            gap = runs[run_id]["started_at"] - previous["run_started_at"]
            microseconds = (gap.days * 86400 + gap.seconds) * 1000000 + gap.microseconds
            hours = float(
                (Decimal(microseconds) / Decimal(3600000000)).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
        errors = sum(r["outcome"] == "error" for r in pages)
        history.append(
            dict(
                run_id=run_id,
                product_id=product["product_id"],
                run_started_at=runs[run_id]["started_at"],
                run_finished_at=runs[run_id]["finished_at"],
                planned_pages=len(pages),
                answered_pages=len(answered),
                offer_pages=len(offers),
                sold_out_pages=sum(r["outcome"] == "sold_out" for r in pages),
                error_pages=errors,
                best_price=best["current_price"] if best else None,
                best_listing_id=best["listing_id"] if best else None,
                best_checked_at=best["checked_at"] if best else None,
                last_checked_at=max(times) if times else None,
                previous_run_id=previous["run_id"] if previous else None,
                previous_best_price=previous["best_price"] if previous else None,
                hours_since_previous=hours,
                comparable_with_previous=bool(
                    previous and answered and answered == previous_answered
                ),
                planned_listing_ids=[r["listing_id"] for r in pages],
                partial=len(answered) < len(pages),
                unchecked_pages=len(pages) - len(answered) - errors,
            )
        )
        previous_answered = answered
    current = history[-1] if history else None
    best = best_by_run[current["run_id"]] if current else None
    last = next(
        (
            best_by_run[r["run_id"]]
            for r in reversed(history)
            if r["best_price"] is not None
        ),
        None,
    )
    state = "no_history"
    if current:
        state = (
            "offer"
            if best
            else (
                "sold_out"
                if current["sold_out_pages"] == current["planned_pages"]
                else "unverified"
            )
        )
    visible = []
    if current:
        cutoff = current["run_started_at"] - timedelta(days=history_days)
        visible = [
            r
            for r in history
            if cutoff <= r["run_started_at"] <= current["run_started_at"]
        ]
    market = [
        r
        for r in data["market_history"]
        if r["product_id"] == product["product_id"] and r["source"] == "cimri"
    ]
    if market:
        last_day = max(r["day"] for r in market)
        market = [
            {
                key: r[key]
                for key in (
                    "day",
                    "price_kurus",
                    "source",
                    "source_product_id",
                    "source_url",
                    "captured_at",
                )
            }
            for r in sorted(market, key=lambda r: r["day"])
            if last_day - timedelta(days=cimri_days - 1) <= r["day"] <= last_day
        ]
    age = (
        max(0.0, (generated_at - best["checked_at"]).total_seconds()) if best else None
    )
    return dict(
        product=product,
        state=state,
        current=current,
        checks=(
            sorted(checks[current["run_id"]], key=lambda r: r["listing_id"])
            if current
            else []
        ),
        best_offer=best,
        last_successful_offer=last,
        history=visible,
        cimri_history=market,
        statistics=reference_statistics(history),
        generated_at=generated_at,
        currency="TRY",
        price_age_seconds=age,
        is_stale=age >= 64800 if age is not None else None,
    )


def differences(expected, actual, path=""):
    result = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            field = f"{path}.{key}" if path else key
            if key not in expected or key not in actual:
                result.append(field)
            else:
                result.extend(differences(expected[key], actual[key], field))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            result.append(f"{path}.length")
        for index, (a, b) in enumerate(zip(expected, actual)):
            result.extend(differences(a, b, f"{path}[{index}]"))
    elif (
        path.endswith("volatility_30d.value")
        and isinstance(expected, float)
        and isinstance(actual, float)
    ):
        if not math.isclose(expected, actual, rel_tol=1e-9, abs_tol=1e-12):
            result.append(path)
    elif type(expected) is not type(actual) or expected != actual:
        result.append(path)
    return result


def check_api(conn, client, report):
    identity, before = read_dataset(conn)
    report.update(
        identity=identity, before={k: fingerprint(v) for k, v in before.items()}
    )
    products = [r for r in before["products"] if r["active"]]
    report["expected_products"] = len(products)
    mismatches = differences(
        products,
        json_value([r.model_dump() for r in client.list_products()]),
        "products",
    )
    mismatches += differences(
        {"ready": True}, client.get_health().model_dump(), "health"
    )
    status = {}
    for name, state in (("running", "running"), ("completed", "completed")):
        matching = [r for r in before["collection_runs"] if r["status"] == state]
        last = max(matching, key=lambda r: r["run_id"]) if matching else None
        status[name] = {key: last[key] for key in RUN_FIELDS} if last else None
    mismatches += differences(
        json_value(status), json_value(client.get_status().model_dump()), "status"
    )
    report["endpoint_differences"] = mismatches
    for product in products:
        reply = client.get_product(product["product_key"])
        expected = reference_product(before, product, reply.generated_at)
        errors = differences(json_value(expected), json_value(reply.model_dump()))
        report["products"].append(
            dict(
                product_key=product["product_key"],
                matched=not errors,
                differences=errors,
                state=reply.state,
                run_id=reply.current.run_id if reply.current else None,
                best_price=reply.best_offer.current_price if reply.best_offer else None,
                history_points=len(reply.history),
                cimri_points=len(reply.cimri_history),
                cimri_missing=sum(r.price_kurus is None for r in reply.cimri_history),
            )
        )
    _, after = read_dataset(conn)
    report["after"] = {k: fingerprint(v) for k, v in after.items()}
    changed = [k for k in RELATIONS if report["before"][k] != report["after"][k]]
    report["changed_relations"] = changed
    if changed:
        report["status"] = "inconclusive"
        return 2
    report["status"] = (
        "mismatch"
        if mismatches or any(not r["matched"] for r in report["products"])
        else "verified"
    )
    return 1 if report["status"] == "mismatch" else 0


def configured_url():
    url = os.getenv("API_DATABASE_URL", "").strip()
    if not url:
        raise CheckError("API_DATABASE_URL tanımlı değil.")
    try:
        params = conninfo_to_dict(url)
    except psycopg.Error:
        raise CheckError(
            "API_DATABASE_URL geçerli bir PostgreSQL adresi değil."
        ) from None
    database = params.get("dbname", "")
    expected = (
        "fiyat_takip_api"
        if database == "fiyat_takip"
        else ("fiyat_takip_api_test" if database.endswith("_test") else None)
    )
    if expected is None or params.get("user") != expected:
        raise CheckError("Yalnız API okuma hesabı ve izin verilen DB kullanılabilir.")
    return url


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        args.output_dir.mkdir(parents=True, exist_ok=False)
    except OSError:
        print("Yeni bir çıktı klasörü gerekli; mevcut klasör değiştirilmedi.")
        return 1
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    worktree = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    report = dict(
        started_at=datetime.now(timezone.utc),
        commit=commit.stdout.strip() if commit.returncode == 0 else None,
        worktree_dirty=(
            bool(worktree.stdout.strip()) if worktree.returncode == 0 else None
        ),
        verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        api="http://127.0.0.1:8000",
        history_days=30,
        cimri_days=366,
        status="failed",
        products=[],
    )
    try:
        url = configured_url()
        with psycopg.connect(url, autocommit=True, connect_timeout=3) as conn:
            with ApiClient() as client:
                code = check_api(conn, client, report)
    except KeyboardInterrupt:
        report.update(status="interrupted", error_code="interrupted")
        code = 130
    except (CheckError, ApiClientError) as error:
        report["error_code"] = (
            error.code if isinstance(error, ApiClientError) else "readiness_error"
        )
        print(str(error))
        code = 1
    except psycopg.Error:
        report["error_code"] = "database_error"
        print("Veritabanı okunamadı; bağlantı ve okuma izinlerini kontrol et.")
        code = 1
    except Exception:
        report["error_code"] = "check_error"
        print("Kontrol tamamlanamadı; ham hata ayrıntısı rapora yazılmadı.")
        code = 1
    report.update(finished_at=datetime.now(timezone.utc), exit_code=code)
    path = args.output_dir / "report.json"
    path.write_text(
        json.dumps(json_value(report), ensure_ascii=False, indent=2, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print(f"Rapor: {path}")
    labels = {
        "verified": "doğrulandı",
        "mismatch": "uyuşmazlık",
        "inconclusive": "kaynak değişti; sakin zamanda yeniden kontrol et",
        "failed": "tamamlanamadı",
        "interrupted": "kesildi",
    }
    print(
        f"Durum: {labels[report['status']]} · "
        f"Kontrol edilen ürün: {len(report['products'])}"
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
