"""Salt okunur ürün sorguları: gerçek test hesabı, bağımsız beklenen sonuçlar."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from psycopg import InterfaceError, errors, sql
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row

from app.database import read, runs

START = datetime(2024, 11, 1, 7, tzinfo=timezone.utc)
KEY = "apple_iphone_15_128gb"
OWNER = {"a": 1, "b": 1, "c": 1, "d": 2, "e": 3}


def insert(conn, table, **values):
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() for _ in values),
    )
    conn.execute(query, tuple(values.values()))


@pytest.fixture
def world(api_db, db):
    for key, name in (("trendyol", "Trendyol"), ("hepsiburada", "Hepsiburada")):
        insert(db, "platforms", key=key, name=name, active=True)
    for product_id, key, brand, model, capacity, active in (
        (1, KEY, "Apple", "iPhone 15", 128, True),
        (2, "samsung_s24_256gb", "Samsung", "Galaxy S24", 256, True),
        (3, "poco_x6_pro_512gb", "POCO", "X6 Pro", 512, False),
    ):
        insert(
            db,
            "products",
            product_id=product_id,
            product_key=key,
            brand=brand,
            model=model,
            storage_gb=capacity,
            active=active,
        )
    for page, product_id in OWNER.items():
        platform = "hepsiburada" if page == "c" else "trendyol"
        insert(
            db,
            "listings",
            listing_id=page,
            product_id=product_id,
            platform=platform,
            url=f"https://www.{platform}.com/urun-{page}",
            color="Siyah",
            active=True,
        )
    return db


def add_run(conn, at, results, status="completed"):
    run_id = conn.execute(
        "INSERT INTO collection_runs"
        " (trigger,status,started_at,catalog_sha256,planned_count,note)"
        " VALUES ('manual','running',%s,%s,%s,'Yerel test') RETURNING run_id",
        (at, "0" * 64, len(results)),
    ).fetchone()[0]
    for index, (page, result) in enumerate(sorted(results.items()), 1):
        outcome, price = result if isinstance(result, tuple) else (result, None)
        values = {"run_id": run_id, "listing_id": page, "product_id": OWNER[page]}
        if outcome != "planned":
            values.update(outcome=outcome, checked_at=at + timedelta(minutes=index))
        if outcome == "offer":
            values.update(
                current_price=price,
                original_price=price + 1000,
                seller_name=f"Satıcı {page}",
                seller_rating=Decimal("9.25"),
                seller_rating_scale=Decimal("10"),
                stock_status="Kritik Stok" if page == "b" else "Stokta Var",
            )
        elif outcome == "sold_out":
            values["stock_status"] = "Tükendi"
        elif outcome == "error":
            values.update(error_code="network", error_message="Yerel test hatası")
        insert(conn, "listing_checks", **values)
    if status != "running":
        close_run(conn, run_id, at, status)
    return run_id


def close_run(conn, run_id, at, status="completed"):
    conn.execute(
        "UPDATE collection_runs SET status=%s,finished_at=%s WHERE run_id=%s",
        (status, at + timedelta(minutes=30), run_id),
    )


def add_market(conn, day, price, product_id=1):
    insert(
        conn,
        "market_history",
        product_id=product_id,
        source="cimri",
        source_product_id="123456",
        source_url="https://www.cimri.com/cep-telefonlari/test,a123456",
        day=day,
        price_kurus=price,
        captured_at=START,
        page_sha256="1" * 64,
        api_sha256="2" * 64,
        report_sha256="3" * 64,
    )


def test_product_list_is_active_sorted_and_independent_of_listings(world, api_db):
    world.execute("UPDATE listings SET active=false")
    world.execute("UPDATE platforms SET active=false")
    products = read.list_products(api_db)
    assert tuple(
        (p.product_id, p.product_key, p.brand, p.model, p.storage_gb, p.active)
        for p in products
    ) == (
        (1, KEY, "Apple", "iPhone 15", 128, True),
        (2, "samsung_s24_256gb", "Samsung", "Galaxy S24", 256, True),
    )


def test_empty_product_list_and_run_status(api_db):
    assert read.list_products(api_db) == ()
    assert read.read_run_status(api_db) == read.RunStatus(None, None)


@pytest.mark.parametrize("key", ["unknown", "", "'; DELETE FROM products; --"])
def test_unknown_product_does_not_change_data(world, api_db, key):
    assert read.read_product(api_db, key) is None
    assert world.execute("SELECT count(*) FROM products").fetchone() == (3,)


def test_product_without_a_completed_run_and_passive_lookup(world, api_db):
    add_run(world, START, {"e": ("offer", 10000)}, status="interrupted")
    result = read.read_product(api_db, "poco_x6_pro_512gb")
    assert result.product.active is False
    assert result.state == "no_history"
    assert result.current is result.best_offer is result.last_successful_offer is None
    assert (
        result.checks
        == result.history
        == result.all_history
        == result.cimri_history
        == ()
    )


def test_passive_product_keeps_its_completed_history(world, api_db):
    run_id = add_run(world, START, {"e": ("offer", 10000)})
    result = read.read_product(api_db, "poco_x6_pro_512gb")
    assert result.product.active is False
    assert result.current.run_id == run_id
    assert result.best_offer.current_price == 10000


def test_global_status_does_not_return_interrupted_runs(world, api_db):
    completed = add_run(world, START, {"a": ("offer", 10000)})
    add_run(world, START + timedelta(hours=12), {"d": "error"}, "interrupted")
    running_at = START + timedelta(hours=24)
    running = add_run(world, running_at, {"d": "planned"}, "running")
    status = read.read_run_status(api_db)
    assert status.completed == read.RunInfo(
        completed,
        "manual",
        "completed",
        START,
        START + timedelta(minutes=30),
        1,
        "Yerel test",
    )
    assert status.running == read.RunInfo(
        running, "manual", "running", running_at, None, 1, "Yerel test"
    )


def test_current_run_is_product_specific_and_completed(world, api_db):
    first = add_run(world, START, {"a": ("offer", 20000), "d": ("offer", 30000)})
    latest_global = add_run(world, START + timedelta(hours=12), {"d": ("offer", 25000)})
    add_run(world, START + timedelta(hours=24), {"a": ("offer", 1000)}, "interrupted")
    add_run(world, START + timedelta(hours=36), {"a": ("offer", 500)}, "running")
    result = read.read_product(api_db, KEY)
    assert result.current.run_id == first
    assert result.best_offer.current_price == 20000
    assert tuple(run.run_id for run in result.all_history) == (first,)
    assert read.read_run_status(api_db).completed.run_id == latest_global


@pytest.mark.parametrize(
    "results,state,counts,price",
    [
        (
            {"a": ("offer", 20000), "b": ("offer", 9000), "c": "sold_out"},
            "offer",
            (3, 3, 2, 1, 0, 0),
            9000,
        ),
        (
            {"a": "sold_out", "b": "sold_out", "c": "sold_out"},
            "sold_out",
            (3, 3, 0, 3, 0, 0),
            None,
        ),
        (
            {"a": "error", "b": "error", "c": "error"},
            "unverified",
            (3, 0, 0, 0, 3, 0),
            None,
        ),
        (
            {"a": "sold_out", "b": "error", "c": "planned"},
            "unverified",
            (3, 1, 0, 1, 1, 1),
            None,
        ),
        (
            {"a": ("offer", 12345), "b": "error", "c": "planned"},
            "offer",
            (3, 1, 1, 0, 1, 1),
            12345,
        ),
        (
            {"a": "planned", "b": "planned", "c": "planned"},
            "unverified",
            (3, 0, 0, 0, 0, 3),
            None,
        ),
        (
            {"a": "sold_out", "b": "error", "c": "sold_out"},
            "unverified",
            (3, 2, 0, 2, 1, 0),
            None,
        ),
    ],
)
def test_current_state_and_coverage(world, api_db, results, state, counts, price):
    add_run(world, START, results)
    result = read.read_product(api_db, KEY)
    current = result.current
    assert result.state == state
    assert (
        current.planned_pages,
        current.answered_pages,
        current.offer_pages,
        current.sold_out_pages,
        current.error_pages,
        current.unchecked_pages,
    ) == counts
    assert current.best_price == price
    assert current.partial is (counts[0] != counts[1])
    assert current.planned_listing_ids == ("a", "b", "c")
    assert tuple(check.outcome for check in result.checks) == tuple(
        (
            None
            if results[page] == "planned"
            else results[page][0] if isinstance(results[page], tuple) else results[page]
        )
        for page in ("a", "b", "c")
    )
    assert (result.best_offer.current_price if result.best_offer else None) == price


def test_offer_fields_tie_break_and_check_times(world, api_db):
    run_id = add_run(
        world, START, {"a": ("offer", 10001), "b": ("offer", 10001), "c": "error"}
    )
    result = read.read_product(api_db, KEY)
    assert result.best_offer == read.ListingResult(
        run_id,
        "a",
        1,
        "trendyol",
        "Trendyol",
        True,
        "https://www.trendyol.com/urun-a",
        "Siyah",
        True,
        START + timedelta(minutes=1),
        "offer",
        10001,
        11001,
        "Satıcı a",
        Decimal("9.25"),
        Decimal("10"),
        "Stokta Var",
        None,
        None,
    )
    assert result.current.best_checked_at == START + timedelta(minutes=1)
    assert result.current.last_checked_at == START + timedelta(minutes=3)
    assert result.checks[1].stock_status == "Kritik Stok"
    assert result.checks[2].error_code == "network"
    assert result.checks[2].current_price is None
    assert result.last_successful_offer == result.best_offer


def test_previous_success_is_separate_and_not_limited_by_graph_window(world, api_db):
    first = add_run(world, START, {"a": ("offer", 10000)})
    failed_at = START + timedelta(days=40)
    latest = add_run(world, failed_at, {"a": "error"})
    result = read.read_product(api_db, KEY)
    assert result.state == "unverified"
    assert result.current.run_id == latest
    assert result.best_offer is None
    assert result.current.best_price is None
    assert result.last_successful_offer.run_id == first
    assert result.last_successful_offer.current_price == 10000
    assert result.last_successful_offer.checked_at == START + timedelta(minutes=1)
    assert tuple(run.run_id for run in result.history) == (latest,)
    assert tuple(run.run_id for run in result.all_history) == (first, latest)


def test_catalog_changes_do_not_remove_or_rewrite_old_results(world, api_db):
    run_id = add_run(world, START, {"a": ("offer", 10000), "c": "sold_out"})
    world.execute(
        "UPDATE listings SET active=false,color='Mavi',"
        " url='https://www.trendyol.com/yeni-adres' WHERE listing_id='a'"
    )
    world.execute(
        "UPDATE platforms SET active=false,name='Yeni ad' WHERE key='trendyol'"
    )
    result = read.read_product(api_db, KEY)
    assert result.current.run_id == run_id
    assert result.current.planned_pages == result.current.answered_pages == 2
    assert result.best_offer.listing_active is False
    assert result.best_offer.platform_active is False
    assert result.best_offer.platform_name == "Yeni ad"
    assert result.best_offer.color == "Mavi"
    assert result.best_offer.url == "https://www.trendyol.com/yeni-adres"
    assert result.best_offer.current_price == 10000
    assert result.best_offer.seller_name == "Satıcı a"
    assert result.best_offer.checked_at == START + timedelta(minutes=1)


@pytest.mark.parametrize("days", [1, 30, 366])
def test_own_history_window_uses_last_run_and_includes_boundaries(world, api_db, days):
    latest_at = START + timedelta(days=400)
    lower = latest_at - timedelta(days=days)
    older = add_run(world, lower - timedelta(seconds=1), {"a": ("offer", 11000)})
    boundary = add_run(world, lower, {"a": ("offer", 10000)})
    latest = add_run(world, latest_at, {"a": "sold_out"})
    result = read.read_product(api_db, KEY, history_days=days)
    assert tuple(run.run_id for run in result.history) == (boundary, latest)
    assert tuple(run.best_price for run in result.history) == (10000, None)
    assert tuple(run.run_id for run in result.all_history) == (older, boundary, latest)
    assert result.history[0].previous_run_id == older
    assert result.history[0].previous_best_price == 11000
    assert result.history[0].comparable_with_previous is True


def test_full_history_keeps_scope_changes_and_existing_comparability(world, api_db):
    first = add_run(world, START, {"a": ("offer", 10000)})
    second = add_run(
        world, START + timedelta(days=1), {"a": ("offer", 9000), "b": "error"}
    )
    third = add_run(
        world, START + timedelta(days=2), {"a": ("offer", 8000), "b": "sold_out"}
    )
    result = read.read_product(api_db, KEY)
    assert tuple(run.planned_listing_ids for run in result.all_history) == (
        ("a",),
        ("a", "b"),
        ("a", "b"),
    )
    assert tuple(run.run_id for run in result.all_history) == (first, second, third)
    assert result.all_history[1].partial is True
    assert result.all_history[1].comparable_with_previous is True
    assert result.all_history[2].comparable_with_previous is False
    assert result.all_history[1].hours_since_previous == Decimal("24")


@pytest.mark.parametrize("days", [1, 366])
def test_cimri_window_uses_its_own_last_day_and_keeps_null(world, api_db, days):
    latest = date(2023, 5, 1)
    lower = latest - timedelta(days=days - 1)
    add_market(world, lower - timedelta(days=1), 10000)
    if lower != latest:
        add_market(world, lower, 2**35)
    add_market(world, latest, None)
    add_market(world, latest + timedelta(days=5), 5000, product_id=2)
    result = read.read_product(api_db, KEY, cimri_days=days)
    expected = (
        (
            read.MarketPoint(
                lower,
                2**35,
                "cimri",
                "123456",
                "https://www.cimri.com/cep-telefonlari/test,a123456",
                START,
            ),
        )
        if lower != latest
        else ()
    ) + (
        read.MarketPoint(
            latest,
            None,
            "cimri",
            "123456",
            "https://www.cimri.com/cep-telefonlari/test,a123456",
            START,
        ),
    )
    assert result.cimri_history == expected
    assert result.state == "no_history"
    assert result.history == result.all_history == ()


def test_default_cimri_window_keeps_missing_days_without_filling_them(world, api_db):
    last_day = date(2023, 5, 1)
    add_market(world, last_day - timedelta(days=366), 9000)
    add_market(world, last_day - timedelta(days=365), 10000)
    add_market(world, last_day, None)
    result = read.read_product(api_db, KEY)
    assert tuple(point.day for point in result.cimri_history) == (
        last_day - timedelta(days=365),
        last_day,
    )
    assert tuple(point.price_kurus for point in result.cimri_history) == (10000, None)


@pytest.mark.parametrize("name", ["history_days", "cimri_days"])
@pytest.mark.parametrize("value", [0, 367, -1, True, "30", 1.5, None])
def test_invalid_days_are_rejected_before_using_connection(name, value):
    with pytest.raises(ValueError, match="1–366"):
        read.read_product(None, KEY, **{name: value})


def test_product_snapshot_is_consistent_while_run_and_catalog_change(
    world, api_db, monkeypatch
):
    old = add_run(world, START, {"a": ("offer", 10000)})
    add_market(world, date(2023, 5, 1), 12000)
    next_at = START + timedelta(hours=12)
    new = add_run(world, next_at, {"a": ("offer", 9000)}, "running")
    original = read._rows
    changed = False

    def after_first_read(conn, query, params=()):
        nonlocal changed
        rows = original(conn, query, params)
        if not changed and "FROM products WHERE product_key" in query:
            changed = True
            with world.transaction():
                close_run(world, new, next_at)
                world.execute("UPDATE products SET active=false WHERE product_id=1")
                world.execute(
                    "UPDATE listings SET color='Mavi',"
                    " url='https://www.trendyol.com/yeni' WHERE listing_id='a'"
                )
                world.execute("UPDATE platforms SET active=false WHERE key='trendyol'")
                add_market(world, date(2023, 5, 2), 11000)
        return rows

    monkeypatch.setattr(read, "_rows", after_first_read)
    before = read.read_product(api_db, KEY)
    assert changed
    assert before.product.active is True
    assert before.current.run_id == old
    assert before.best_offer.current_price == 10000
    assert before.best_offer.color == "Siyah"
    assert before.best_offer.url == "https://www.trendyol.com/urun-a"
    assert before.best_offer.platform_active is True
    assert tuple(run.run_id for run in before.history) == (old,)
    assert tuple(point.price_kurus for point in before.cimri_history) == (12000,)
    monkeypatch.setattr(read, "_rows", original)
    after = read.read_product(api_db, KEY)
    assert after.product.active is False
    assert after.current.run_id == new
    assert after.best_offer.current_price == 9000
    assert after.best_offer.color == "Mavi"
    assert after.best_offer.url == "https://www.trendyol.com/yeni"
    assert after.best_offer.platform_active is False
    assert tuple(run.run_id for run in after.history) == (old, new)
    assert tuple(point.price_kurus for point in after.cimri_history) == (12000, 11000)


def test_global_status_is_consistent_during_run_completion(world, api_db, monkeypatch):
    old = add_run(world, START, {"a": "sold_out"})
    at = START + timedelta(hours=12)
    new = add_run(world, at, {"a": ("offer", 10000)}, "running")
    original = read._rows

    def finish_after_running_read(conn, query, params=()):
        rows = original(conn, query, params)
        if params == ("running",):
            close_run(world, new, at)
        return rows

    monkeypatch.setattr(read, "_rows", finish_after_running_read)
    before = read.read_run_status(api_db)
    assert before.running.run_id == new
    assert before.completed.run_id == old
    monkeypatch.setattr(read, "_rows", original)
    after = read.read_run_status(api_db)
    assert after.running is None
    assert after.completed.run_id == new


GETTERS = (
    read.list_products,
    read.read_run_status,
    lambda conn: read.read_product(conn, KEY),
)


@pytest.mark.parametrize("getter", GETTERS)
def test_open_transaction_is_not_committed_or_rolled_back(api_db, getter):
    api_db.execute("BEGIN")
    try:
        api_db.execute("SET LOCAL application_name='caller_transaction'")
        with pytest.raises(ValueError, match="açık bir işlem"):
            getter(api_db)
        assert api_db.info.transaction_status == TransactionStatus.INTRANS
        assert api_db.execute("SHOW application_name").fetchone() == (
            "caller_transaction",
        )
    finally:
        api_db.rollback()


@pytest.mark.parametrize("getter", GETTERS)
def test_read_settings_are_local_and_connection_stays_open(
    world, api_db, monkeypatch, getter
):
    api_db.execute("SET statement_timeout='9s'")
    api_db.execute("SET TimeZone='Europe/Istanbul'")
    original = read._rows
    observed = []

    def observe(conn, query, params=()):
        observed.append(
            tuple(
                conn.execute("SHOW " + name).fetchone()[0]
                for name in (
                    "transaction_isolation",
                    "transaction_read_only",
                    "statement_timeout",
                    "TimeZone",
                )
            )
        )
        return original(conn, query, params)

    monkeypatch.setattr(read, "_rows", observe)
    result = getter(api_db)
    assert observed and set(observed) == {("repeatable read", "on", "5s", "UTC")}
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    assert not api_db.closed
    assert api_db.execute("SHOW statement_timeout").fetchone() == ("9s",)
    assert api_db.execute("SHOW TimeZone").fetchone() == ("Europe/Istanbul",)
    if isinstance(result, read.ProductSnapshot):
        assert result.current is None


@pytest.mark.parametrize("getter", GETTERS)
def test_sql_error_rolls_back_and_next_read_succeeds(
    world, api_db, monkeypatch, getter
):
    api_db.execute("SET statement_timeout='9s'")
    original = read._rows

    def fail(conn, query, params=()):
        conn.execute("SELECT 1/0")

    monkeypatch.setattr(read, "_rows", fail)
    with pytest.raises(errors.DivisionByZero):
        getter(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    assert api_db.execute("SHOW statement_timeout").fetchone() == ("9s",)
    monkeypatch.setattr(read, "_rows", original)
    getter(api_db)


def test_query_timeout_rolls_back_and_connection_can_be_reused(api_db, monkeypatch):
    original = read._rows

    def slow(conn, query, params=()):
        conn.execute("SELECT pg_sleep(6)")

    monkeypatch.setattr(read, "_rows", slow)
    with pytest.raises(errors.QueryCanceled):
        read.list_products(api_db)
    assert api_db.info.transaction_status == TransactionStatus.IDLE
    monkeypatch.setattr(read, "_rows", original)
    assert read.list_products(api_db) == ()


def test_reads_do_not_take_collection_lock_or_change_rows(world, api_db):
    add_run(world, START, {"a": ("offer", 10000), "c": "sold_out"})
    add_market(world, date(2023, 5, 1), None)
    tables = (
        "schema_migrations",
        "platforms",
        "products",
        "listings",
        "collection_runs",
        "listing_checks",
        "market_history",
    )

    def snapshot():
        return tuple(
            world.execute(
                sql.SQL("SELECT * FROM {} ORDER BY 1,2").format(sql.Identifier(table))
            ).fetchall()
            for table in tables
        )

    before = snapshot()
    assert runs.try_lock_runs(world)
    try:
        read.list_products(api_db)
        read.read_run_status(api_db)
        read.read_product(api_db, KEY)
        assert snapshot() == before
    finally:
        runs.unlock_runs(world)
    assert runs.try_lock_runs(world)
    runs.unlock_runs(world)


def test_returned_records_are_frozen_and_preserve_callers_row_factory(world, api_db):
    add_run(world, START, {"a": ("offer", 10000)})
    api_db.row_factory = dict_row
    result = read.read_product(api_db, KEY)
    assert api_db.row_factory is dict_row
    assert result.current.run_started_at.utcoffset() == timedelta(0)
    with pytest.raises(FrozenInstanceError):
        result.current.best_price = 1
    with pytest.raises(FrozenInstanceError):
        result.best_offer.current_price = 1
    assert isinstance(result.current.planned_listing_ids, tuple)


@pytest.mark.parametrize("getter", GETTERS)
def test_closed_connection_raises_database_error(api_db, getter):
    api_db.close()
    with pytest.raises(InterfaceError):
        getter(api_db)
