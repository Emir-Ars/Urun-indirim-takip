"""AppTest ve tarayıcı önizlemesi için ortak, açıkça yapay ekran verisi."""

from datetime import date, datetime, timedelta, timezone

import httpx

from app.api.schemas import (
    HistoryResponse,
    IndicatorResponse,
    ListingResponse,
    MarketResponse,
    ProductResponse,
    RunResponse,
    StatisticsResponse,
    StatusResponse,
    VolatilityResponse,
)
from app.contracts import Product
from app.ui.api_client import ApiClient

AT = datetime(2026, 10, 9, 9, tzinfo=timezone.utc)
PRODUCTS = (
    Product(
        product_id=1,
        product_key="apple_iphone_15_128gb",
        brand="Apple",
        model="iPhone 15",
        storage_gb=128,
    ),
    Product(
        product_id=2,
        product_key="samsung_galaxy_s24_256gb",
        brand="Samsung",
        model="Galaxy S24",
        storage_gb=256,
    ),
)
SCENARIOS = (
    "Teklif ve grafik boşlukları",
    "Eski teklif",
    "Kısmi kapsam",
    "Bütün sayfalar stoksuz",
    "Fiyat doğrulanamadı",
    "Yalnız Cimri geçmişi",
    "Cimri geçmişi yok",
    "Fiyatların hepsi eksik",
    "API bağlantı hatası",
    "Bozuk API cevabı",
    "Etkin telefon yok",
)


def sample_history(run_id=1, **updates) -> HistoryResponse:
    started = AT - timedelta(hours=12 * (7 - run_id))
    fields = dict(
        run_id=run_id,
        product_id=1,
        run_started_at=started,
        run_finished_at=started + timedelta(minutes=30),
        planned_pages=2,
        answered_pages=2,
        offer_pages=2,
        sold_out_pages=0,
        error_pages=0,
        best_price=3000001 - run_id * 10000,
        best_listing_id="a",
        best_checked_at=started + timedelta(minutes=5),
        last_checked_at=started + timedelta(minutes=20),
        previous_run_id=run_id - 1 if run_id > 1 else None,
        previous_best_price=3000001 - (run_id - 1) * 10000 if run_id > 1 else None,
        hours_since_previous=12.0 if run_id > 1 else None,
        comparable_with_previous=run_id > 1,
        planned_listing_ids=("a", "b"),
        partial=False,
        unchecked_pages=0,
    )
    fields.update(updates)
    return HistoryResponse(**fields)


def sample_offer(run_id=7, **updates) -> ListingResponse:
    fields = dict(
        run_id=run_id,
        listing_id="a",
        product_id=1,
        platform="trendyol",
        platform_name="Trendyol",
        platform_active=True,
        url="https://example.com/ornek-telefon",
        color="Siyah",
        listing_active=True,
        checked_at=AT + timedelta(minutes=5),
        outcome="offer",
        current_price=2930001,
        original_price=3150000,
        seller_name="Örnek Satıcı",
        seller_rating=9.25,
        seller_rating_scale=10.0,
        stock_status="Stokta Var",
        error_code=None,
    )
    fields.update(updates)
    return ListingResponse(**fields)


def sample_market(day=date(2026, 10, 8), price=2950000) -> MarketResponse:
    return MarketResponse(
        day=day,
        price_kurus=price,
        source="cimri",
        source_product_id="12345",
        source_url="https://example.com/ornek-gecmis",
        captured_at=AT,
    )


def sample_product(
    scenario=SCENARIOS[0], *, now=AT + timedelta(minutes=30), product=PRODUCTS[0]
):
    history = (
        sample_history(1),
        sample_history(2),
        sample_history(
            3,
            best_price=None,
            best_listing_id=None,
            best_checked_at=None,
            offer_pages=0,
            sold_out_pages=2,
        ),
        sample_history(4),
        sample_history(5),
        sample_history(
            6,
            answered_pages=1,
            offer_pages=1,
            partial=True,
            unchecked_pages=1,
            comparable_with_previous=False,
        ),
        sample_history(7, comparable_with_previous=False),
    )
    current = history[-1]
    best = sample_offer()
    previous = sample_offer(
        6, current_price=history[-2].best_price, checked_at=history[-2].best_checked_at
    )
    other = sample_offer(
        listing_id="b",
        platform="hepsiburada",
        platform_name="Hepsiburada",
        current_price=2990000,
        original_price=None,
        seller_name="İkinci Örnek Satıcı",
    )
    checks, state = (best, other), "offer"
    market = tuple(
        sample_market(
            date(2026, 9, 29) + timedelta(days=i),
            None if i in (3, 4) else 3100000 - i * 15000,
        )
        for i in range(10)
    )
    if scenario == "Kısmi kapsam":
        other = other.model_copy(
            update=dict(
                outcome="error",
                current_price=None,
                error_code="network",
                stock_status=None,
            )
        )
        current = current.model_copy(
            update=dict(answered_pages=1, offer_pages=1, error_pages=1, partial=True)
        )
        history = history[:-1] + (current,)
        checks = best, other
    elif scenario in (
        "Bütün sayfalar stoksuz",
        "Fiyat doğrulanamadı",
        "Fiyatların hepsi eksik",
    ):
        sold_out = scenario == "Bütün sayfalar stoksuz"
        state = "sold_out" if sold_out else "unverified"
        checks = tuple(
            offer.model_copy(
                update=dict(
                    outcome="sold_out" if sold_out else "error",
                    current_price=None,
                    original_price=None,
                    seller_name=None,
                    seller_rating=None,
                    seller_rating_scale=None,
                    stock_status="Tükendi" if sold_out else None,
                    error_code=None if sold_out else "parse",
                )
            )
            for offer in checks
        )
        current = current.model_copy(
            update=dict(
                answered_pages=2 if sold_out else 0,
                offer_pages=0,
                sold_out_pages=2 if sold_out else 0,
                error_pages=0 if sold_out else 2,
                best_price=None,
                best_listing_id=None,
                best_checked_at=None,
                partial=not sold_out,
            )
        )
        history = history[:-1] + (current,)
        best = None
    elif scenario == "Yalnız Cimri geçmişi":
        state, current, best, previous, history, checks = (
            "no_history",
            None,
            None,
            None,
            (),
            (),
        )
    elif scenario == "Cimri geçmişi yok":
        market = ()
    if scenario == "Fiyatların hepsi eksik":
        history = tuple(
            point.model_copy(
                update=dict(
                    best_price=None,
                    best_checked_at=None,
                    best_listing_id=None,
                    answered_pages=2,
                    offer_pages=0,
                    sold_out_pages=2,
                    error_pages=0,
                    partial=False,
                    unchecked_pages=0,
                )
            )
            for point in history
        )
        market = tuple(
            point.model_copy(update=dict(price_kurus=None)) for point in market
        )
    scope_reasons = (
        ("no_history",)
        if current is None
        else ("incomplete_scope",) if current.partial else ()
    )
    scope = history[-1:] if history and not current.partial else ()
    period = dict(
        period_started_at=current.run_started_at if scope else None,
        period_ended_at=current.run_started_at if current else None,
        observations=sum(point.best_price is not None for point in scope),
    )
    if scope_reasons:
        period = dict(period_started_at=None, period_ended_at=None, observations=0)
    statistics = StatisticsResponse(
        source_run_id=current.run_id if current else None,
        scope_started_at=period["period_started_at"],
        scope_ended_at=period["period_ended_at"],
        scope_runs=len(scope),
        planned_listing_ids=current.planned_listing_ids if current else (),
        low_30d=IndicatorResponse(
            value=None, reasons=scope_reasons or ("insufficient_period",), **period
        ),
        high_in_scope=IndicatorResponse(
            value=(
                None
                if scope_reasons
                else max(
                    (p.best_price for p in scope if p.best_price is not None),
                    default=None,
                )
            ),
            reasons=scope_reasons
            or (("no_prices",) if not period["observations"] else ()),
            **period,
        ),
        volatility_30d=VolatilityResponse(
            value=None,
            reasons=scope_reasons or ("insufficient_transitions", "insufficient_days"),
            transitions=0,
            days=0,
            **period,
        ),
    )
    age = max(0.0, (now - best.checked_at).total_seconds()) if best else None
    if scenario == "Eski teklif" and best:
        best = best.model_copy(update=dict(checked_at=now - timedelta(hours=18)))
        checks = best, other
        current = current.model_copy(update=dict(best_checked_at=best.checked_at))
        history = history[:-1] + (current,)
        age = 18 * 3600.0
    if best is not None:
        previous = best
    return ProductResponse(
        product=product,
        state=state,
        current=(
            current.model_copy(update={"product_id": product.product_id})
            if current
            else None
        ),
        checks=tuple(
            p.model_copy(update={"product_id": product.product_id}) for p in checks
        ),
        best_offer=(
            best.model_copy(update={"product_id": product.product_id}) if best else None
        ),
        last_successful_offer=(
            previous.model_copy(update={"product_id": product.product_id})
            if previous
            else None
        ),
        history=tuple(
            p.model_copy(update={"product_id": product.product_id}) for p in history
        ),
        cimri_history=market,
        statistics=statistics,
        generated_at=now,
        price_age_seconds=age,
        is_stale=age >= 18 * 3600 if age is not None else None,
    )


def sample_status() -> StatusResponse:
    return StatusResponse(
        running=None,
        completed=RunResponse(
            run_id=99,
            trigger="scheduled",
            status="completed",
            started_at=AT,
            finished_at=AT + timedelta(minutes=30),
            planned_count=2,
        ),
    )


def preview_client(scenario: str) -> ApiClient:
    def respond(request):
        if scenario == "API bağlantı hatası":
            raise httpx.ConnectError("Sahte bağlantı hatası", request=request)
        if scenario == "Bozuk API cevabı":
            return httpx.Response(200, content=b"{}")
        if request.url.path == "/api/v1/products":
            return httpx.Response(
                200,
                json=(
                    []
                    if scenario == "Etkin telefon yok"
                    else [p.model_dump(mode="json") for p in PRODUCTS]
                ),
            )
        if request.url.path == "/api/v1/status":
            return httpx.Response(200, json=sample_status().model_dump(mode="json"))
        product = next(
            p for p in PRODUCTS if p.product_key == request.url.path.rsplit("/", 1)[-1]
        )
        snapshot = sample_product(
            scenario, now=datetime.now(timezone.utc), product=product
        )
        days = int(request.url.params["history_days"])
        cimri_days = int(request.url.params["cimri_days"])
        history = (
            tuple(
                p
                for p in snapshot.history
                if p.run_started_at
                >= snapshot.history[-1].run_started_at - timedelta(days=days)
            )
            if snapshot.history
            else ()
        )
        market = (
            tuple(
                p
                for p in snapshot.cimri_history
                if p.day
                >= snapshot.cimri_history[-1].day - timedelta(days=cimri_days - 1)
            )
            if snapshot.cimri_history
            else ()
        )
        snapshot = snapshot.model_copy(
            update={"history": history, "cimri_history": market}
        )
        return httpx.Response(200, json=snapshot.model_dump(mode="json"))

    return ApiClient(transport=httpx.MockTransport(respond))
