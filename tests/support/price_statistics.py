"""İstatistik testlerinin sentetik tur ve Cimri geçmişi."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.contracts import Product
from app.database.read import MarketPoint, ProductRun, ProductSnapshot

START = datetime(2024, 11, 1, 7, tzinfo=timezone.utc)
PRODUCT = Product(
    product_id=1,
    product_key="apple_iphone_15_128gb",
    brand="Apple",
    model="iPhone 15",
    storage_gb=128,
    active=True,
)
CIMRI = (
    MarketPoint(
        date(2024, 11, 1),
        1,
        "cimri",
        "123456",
        "https://www.cimri.com/cep-telefonlari/test,a123456",
        START,
    ),
)


def run(run_id, at, price=10000, pages=("a", "b"), answered=None):
    answered = len(pages) if answered is None else answered
    offers = int(price is not None)
    checked = at + timedelta(minutes=1)
    return ProductRun(
        run_id=run_id,
        product_id=1,
        run_started_at=at,
        run_finished_at=at + timedelta(minutes=30),
        planned_pages=len(pages),
        answered_pages=answered,
        offer_pages=offers,
        sold_out_pages=answered - offers,
        error_pages=len(pages) - answered,
        best_price=price,
        best_listing_id="a" if offers else None,
        best_checked_at=checked if offers else None,
        last_checked_at=checked,
        previous_run_id=run_id - 1 if run_id > 1 else None,
        previous_best_price=None,
        hours_since_previous=Decimal("12") if run_id > 1 else None,
        comparable_with_previous=run_id > 1,
        planned_listing_ids=pages,
    )


def snapshot(*runs, history=None, cimri=()):
    return ProductSnapshot(
        product=PRODUCT,
        current=runs[-1] if runs else None,
        checks=(),
        best_offer=None,
        last_successful_offer=None,
        history=tuple(runs) if history is None else history,
        all_history=tuple(runs),
        cimri_history=cimri,
    )
