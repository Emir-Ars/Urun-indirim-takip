"""product_run_prices görünümü: iki turun fiyatı ne zaman karşılaştırılabilir.

Kural (002 migration): iki tur ancak ürünün cevap veren sayfa kümesi (offer veya
sold_out; hata cevap değildir, Tükendi gerçek cevaptır) aynıysa karşılaştırılır.
Testler gerçek PostgreSQL test veritabanında küçük bir dünyayla çalışır: ürün 1'in
üç sayfası (a, b, c), ürün 2'nin bir sayfası (d) vardır. Fiyatlar kuruştur.
"""

from datetime import datetime, timedelta, timezone

import pytest
from psycopg import sql
from psycopg.rows import dict_row

from app.database.migrate import migrate

START = datetime(2026, 10, 1, 7, 0, tzinfo=timezone.utc)
PAGES = {1: ["trendyol_a", "trendyol_b", "trendyol_c"], 2: ["trendyol_d"]}
OWNER = {page: product for product, pages in PAGES.items() for page in pages}
RESULT_FIELDS = {
    "offer": {
        "outcome": "offer",
        "seller_name": "Satıcı",
        "stock_status": "Stokta Var",
    },
    "sold_out": {"outcome": "sold_out", "stock_status": "Tükendi"},
    "error": {"outcome": "error", "error_code": "network"},
    "planned": {},
}


def insert(conn, table, **values):
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)),
    )
    conn.execute(query, list(values.values()))


@pytest.fixture
def world(db):
    migrate(db)
    insert(db, "platforms", key="trendyol", name="Trendyol", active=True)
    for product_id in PAGES:
        insert(
            db,
            "products",
            product_id=product_id,
            product_key=f"urun_{product_id}",
            brand="Apple",
            model=f"Model {product_id}",
            storage_gb=128,
            active=True,
        )
    for page, product_id in OWNER.items():
        insert(
            db,
            "listings",
            listing_id=page,
            product_id=product_id,
            platform="trendyol",
            url=f"https://www.trendyol.com/x/{page}-p-1",
            color="Siyah",
            active=True,
        )
    return db


def add_run(conn, hours, status="completed"):
    started = START + timedelta(hours=hours)
    finished = None if status == "running" else started + timedelta(minutes=30)
    return conn.execute(
        "INSERT INTO collection_runs (trigger, status, started_at, finished_at,"
        " catalog_sha256, planned_count) VALUES ('scheduled', %s, %s, %s, %s, 1)"
        " RETURNING run_id",
        (status, started, finished, "0" * 64),
    ).fetchone()[0]


def put(conn, run_id, page, result, price=None):
    values = {"run_id": run_id, "listing_id": page, "product_id": OWNER[page]}
    values.update(RESULT_FIELDS[result])
    if result != "planned":
        values["checked_at"] = START
    if price is not None:
        values["current_price"] = price
    insert(conn, "listing_checks", **values)


def run_with(conn, hours, results, status="completed"):
    """results: {sayfa: (sonuç, fiyat)} ya da {sayfa: sonuç}; yeni bir tur açar."""
    run_id = add_run(conn, hours, status)
    for page, result in results.items():
        put(conn, run_id, page, *(result if isinstance(result, tuple) else (result,)))
    return run_id


def row(conn, run_id, product_id=1):
    cursor = conn.cursor(row_factory=dict_row)
    cursor.execute(
        "SELECT * FROM product_run_prices WHERE run_id = %s AND product_id = %s",
        (run_id, product_id),
    )
    return cursor.fetchone()


def all_ok(price_a=10_000):
    return {
        "trendyol_a": ("offer", price_a),
        "trendyol_b": ("offer", 20_000),
        "trendyol_c": "sold_out",
    }


def test_same_answering_pages_are_comparable_and_report_the_changes(world):
    first = run_with(world, 0, all_ok(10_000))
    second = run_with(world, 12, all_ok(9_000))
    result = row(world, second)
    assert result["comparable_with_previous"] is True
    assert result["previous_run_id"] == first
    assert (result["best_price"], result["previous_best_price"]) == (9_000, 10_000)
    assert result["best_listing_id"] == "trendyol_a"
    assert result["hours_since_previous"] == 12
    assert (
        result["planned_pages"],
        result["answered_pages"],
        result["offer_pages"],
        result["sold_out_pages"],
        result["error_pages"],
    ) == (3, 3, 2, 1, 0)


def test_first_run_has_nothing_to_compare_with(world):
    first = run_with(world, 0, all_ok())
    result = row(world, first)
    assert result["comparable_with_previous"] is False
    assert result["previous_run_id"] is None
    assert result["hours_since_previous"] is None


def test_an_error_breaks_the_comparison_going_in_and_coming_out(world):
    run_with(world, 0, all_ok())
    broken = run_with(world, 12, {**all_ok(), "trendyol_a": "error"})
    recovered = run_with(world, 24, all_ok())
    steady = run_with(world, 36, all_ok())
    assert row(world, broken)["comparable_with_previous"] is False
    assert row(world, recovered)["comparable_with_previous"] is False
    assert row(world, steady)["comparable_with_previous"] is True
    # Hata alan tur "en ucuz fiyat"ı yukarı iter: karşılaştırılsaydı sahte düşüş olurdu.
    assert row(world, broken)["best_price"] == 20_000
    assert row(world, recovered)["best_price"] == 10_000


def test_the_same_page_failing_twice_keeps_the_runs_comparable(world):
    # İki turda da aynı sayfa eksikse cevap veren küme aynıdır.
    run_with(world, 0, {**all_ok(), "trendyol_a": "error"})
    second = run_with(world, 12, {**all_ok(), "trendyol_a": "error"})
    assert row(world, second)["comparable_with_previous"] is True


def test_a_new_page_breaks_the_comparison_only_once(world):
    two_pages = {"trendyol_a": ("offer", 10_000), "trendyol_b": ("offer", 20_000)}
    run_with(world, 0, two_pages)
    grown = run_with(world, 12, all_ok())
    steady = run_with(world, 24, all_ok())
    assert row(world, grown)["comparable_with_previous"] is False
    assert row(world, steady)["comparable_with_previous"] is True


def test_a_new_page_that_fails_does_not_change_the_answering_set(world):
    two_pages = {"trendyol_a": ("offer", 10_000), "trendyol_b": ("offer", 20_000)}
    run_with(world, 0, two_pages)
    second = run_with(world, 12, {**two_pages, "trendyol_c": "error"})
    result = row(world, second)
    assert result["comparable_with_previous"] is True
    assert (result["planned_pages"], result["answered_pages"]) == (3, 2)


def test_sold_out_is_an_answer_and_is_not_a_price(world):
    first = run_with(world, 0, {"trendyol_d": ("offer", 30_000)})
    second = run_with(world, 12, {"trendyol_d": "sold_out"})
    result = row(world, second, product_id=2)
    assert result["previous_run_id"] == first
    assert result["comparable_with_previous"] is True
    # Fiyatın yerini Tükendi almıştır: best_price boştur, düşüş değildir.
    assert (result["best_price"], result["previous_best_price"]) == (None, 30_000)


def test_a_product_with_no_answers_is_never_comparable(world):
    run_with(world, 0, {"trendyol_d": "error"})
    second = run_with(world, 12, {"trendyol_d": "error"})
    result = row(world, second, product_id=2)
    assert result["answered_pages"] == 0
    assert result["comparable_with_previous"] is False


def test_products_are_compared_separately(world):
    both = {**all_ok(), "trendyol_d": ("offer", 30_000)}
    run_with(world, 0, both)
    second = run_with(world, 12, {**both, "trendyol_a": "error"})
    assert row(world, second, product_id=1)["comparable_with_previous"] is False
    assert row(world, second, product_id=2)["comparable_with_previous"] is True


def test_only_completed_runs_take_part(world):
    first = run_with(world, 0, all_ok())
    interrupted = run_with(
        world, 12, {"trendyol_a": ("offer", 10_000)}, status="interrupted"
    )
    running = run_with(world, 18, {"trendyol_a": "planned"}, status="running")
    third = run_with(world, 24, all_ok())
    in_view = world.execute(
        "SELECT count(*) FROM product_run_prices WHERE run_id IN (%s, %s)",
        (interrupted, running),
    ).fetchone()[0]
    assert in_view == 0
    result = row(world, third)
    assert result["previous_run_id"] == first
    assert result["comparable_with_previous"] is True
    assert result["hours_since_previous"] == 24


def test_a_run_that_skips_a_product_does_not_hide_its_previous_run(world):
    # `--prefix` turu yalnız bazı ürünlere bakar; diğer ürünlerin önceki turu atlanır.
    first = run_with(world, 0, {**all_ok(), "trendyol_d": ("offer", 30_000)})
    run_with(world, 12, {"trendyol_d": ("offer", 29_000)})
    third = run_with(world, 24, {**all_ok(), "trendyol_d": ("offer", 31_000)})
    assert row(world, third, product_id=1)["previous_run_id"] == first
    assert row(world, third, product_id=1)["comparable_with_previous"] is True


def test_a_long_gap_is_reported_but_does_not_block_the_comparison(world):
    # Bilgisayar uyurken kaçan turlar: 40 saatlik boşluk.
    run_with(world, 0, all_ok())
    second = run_with(world, 40, all_ok())
    result = row(world, second)
    assert result["hours_since_previous"] == 40
    assert result["comparable_with_previous"] is True


def test_best_price_ignores_sold_out_and_error_pages(world):
    run_id = run_with(
        world,
        0,
        {
            "trendyol_a": ("offer", 15_000),
            "trendyol_b": "sold_out",
            "trendyol_c": "error",
        },
    )
    result = row(world, run_id)
    assert (result["best_price"], result["best_listing_id"]) == (15_000, "trendyol_a")


def test_equal_prices_choose_the_smaller_page_id(world):
    run_id = run_with(
        world,
        0,
        {"trendyol_c": ("offer", 10_000), "trendyol_b": ("offer", 10_000)},
    )
    assert row(world, run_id)["best_listing_id"] == "trendyol_b"
