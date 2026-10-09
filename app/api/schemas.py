"""API ve yerel istemcinin bağımsız, ortak cevap sözleşmeleri."""

from datetime import date, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field, FiniteFloat

from app.contracts import Contract, Product, Reason, Stock, URL

UTCDateTime = Annotated[
    AwareDatetime, AfterValidator(lambda value: value.astimezone(timezone.utc))
]
Count = Annotated[int, Field(ge=0)]
Price = Annotated[int, Field(gt=0)]


class APIModel(Contract):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(APIModel):
    code: str
    message: str


class ErrorResponse(APIModel):
    detail: ErrorDetail


class HealthResponse(APIModel):
    ready: Literal[True] = True


class RunResponse(APIModel):
    run_id: int
    trigger: Literal["manual", "scheduled"]
    status: Literal["running", "completed", "interrupted"]
    started_at: UTCDateTime
    finished_at: UTCDateTime | None
    planned_count: Count


class StatusResponse(APIModel):
    running: RunResponse | None
    completed: RunResponse | None


class ListingResponse(APIModel):
    run_id: int
    listing_id: str
    product_id: int
    platform: str
    platform_name: str
    platform_active: bool
    url: URL
    color: str
    listing_active: bool
    checked_at: UTCDateTime | None
    outcome: Literal["offer", "sold_out", "error"] | None
    current_price: Price | None
    original_price: Price | None
    seller_name: str | None
    seller_rating: FiniteFloat | None
    seller_rating_scale: FiniteFloat | None
    stock_status: Stock | None
    error_code: str | None


class HistoryResponse(APIModel):
    run_id: int
    product_id: int
    run_started_at: UTCDateTime
    run_finished_at: UTCDateTime
    planned_pages: Count
    answered_pages: Count
    offer_pages: Count
    sold_out_pages: Count
    error_pages: Count
    best_price: Price | None
    best_listing_id: str | None
    best_checked_at: UTCDateTime | None
    last_checked_at: UTCDateTime | None
    previous_run_id: int | None
    previous_best_price: Price | None
    hours_since_previous: FiniteFloat | None
    comparable_with_previous: bool
    planned_listing_ids: tuple[str, ...]
    partial: bool
    unchecked_pages: Count


class MarketResponse(APIModel):
    day: date
    price_kurus: Price | None
    source: Literal["cimri"]
    source_product_id: str
    source_url: URL
    captured_at: UTCDateTime


class IndicatorResponse[T](APIModel):
    value: T | None
    reasons: tuple[Reason, ...]
    period_started_at: UTCDateTime | None
    period_ended_at: UTCDateTime | None
    observations: Count


class VolatilityResponse(IndicatorResponse[FiniteFloat]):
    transitions: Count
    days: Count


class StatisticsResponse(APIModel):
    source_run_id: int | None
    scope_started_at: UTCDateTime | None
    scope_ended_at: UTCDateTime | None
    scope_runs: Count
    planned_listing_ids: tuple[str, ...]
    low_30d: IndicatorResponse[Price]
    high_in_scope: IndicatorResponse[Price]
    volatility_30d: VolatilityResponse


class ProductResponse(APIModel):
    product: Product
    state: Literal["offer", "sold_out", "unverified", "no_history"]
    current: HistoryResponse | None
    checks: tuple[ListingResponse, ...]
    best_offer: ListingResponse | None
    last_successful_offer: ListingResponse | None
    history: tuple[HistoryResponse, ...]
    cimri_history: tuple[MarketResponse, ...]
    statistics: StatisticsResponse
    generated_at: UTCDateTime
    currency: Literal["TRY"] = "TRY"
    price_age_seconds: Annotated[FiniteFloat, Field(ge=0)] | None
    is_stale: bool | None
