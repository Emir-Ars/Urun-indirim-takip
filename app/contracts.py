"""Modüller arası sözleşmeler. Bütün parasal alanlar TRY kuruş cinsindedir."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def public_url(value: str) -> str:
    url = urlsplit(value)
    if (
        url.scheme != "https"
        or not url.hostname
        or url.username
        or url.password
        or url.port not in (None, 443)
        or url.fragment
    ):
        raise ValueError("URL, kimlik bilgisi içermeyen bir HTTPS bağlantısı olmalı")
    return value


Money = Annotated[int, Field(gt=0)]
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
URL = Annotated[str, AfterValidator(public_url)]
Stock = Literal["Stokta Var", "Kritik Stok", "Tükendi"]


class Contract(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Platform(Contract):
    key: Key
    name: str = Field(min_length=1)
    hosts: list[str] = Field(min_length=1)
    active: bool = True

    @field_validator("hosts")
    @classmethod
    def valid_hosts(cls, hosts):
        for host in hosts:
            if (
                host != host.lower()
                or "." not in host
                or any(c in host for c in "/:@ ")
                or host.replace(".", "").isdigit()
            ):
                raise ValueError("hosts yalnızca açık alan adları içermeli")
        return hosts


class Product(Contract):
    product_id: int = Field(gt=0, lt=2**31)
    product_key: str = Field(min_length=1)
    brand: str = Field(min_length=1)
    model: str = Field(min_length=1)
    storage_gb: int = Field(gt=0)
    active: bool = True

    @property
    def name(self) -> str:
        return f"{self.brand} {self.model} {self.storage_gb} GB"


class Listing(Contract):
    listing_id: str = Field(min_length=1)
    product_id: int = Field(gt=0)
    platform: Key
    url: URL
    color: str = ""
    active: bool = True


class HistorySource(Contract):
    source: Literal["akakce", "cimri"]
    product_id: int = Field(gt=0)
    url: URL
    active: bool = True


class Catalog(Contract):
    platforms: list[Platform]
    products: list[Product]
    listings: list[Listing]
    history_sources: list[HistorySource] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        groups = (
            [p.key for p in self.platforms],
            [p.product_id for p in self.products],
            [p.product_key for p in self.products],
            [
                (p.brand.casefold(), p.model.casefold(), p.storage_gb)
                for p in self.products
            ],
            [v.listing_id for v in self.listings],
            [(v.platform, v.url) for v in self.listings],
            [(v.source, v.product_id, v.url) for v in self.history_sources],
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("Katalogda tekrarlanan kimlik veya varyant var")
        platforms = {p.key: p for p in self.platforms}
        products = {p.product_id for p in self.products}
        for listing in self.listings:
            if listing.product_id not in products or listing.platform not in platforms:
                raise ValueError("Bağlantının ürün veya platform referansı bulunamadı")
            if urlsplit(listing.url).hostname not in platforms[listing.platform].hosts:
                raise ValueError("Bağlantı, platformun izin verilen alan adında değil")
        for source in self.history_sources:
            if source.product_id not in products:
                raise ValueError("Geçmiş kaynağının ürün referansı bulunamadı")
            if urlsplit(source.url).hostname not in {
                f"www.{source.source}.com",
                f"{source.source}.com",
            }:
                raise ValueError("Geçmiş kaynağının alan adı yanlış")
        return self


class ProductListing(Listing):
    product_name: str
    brand: str
    model: str
    storage_gb: int
    platform_name: str
    hosts: list[str]
    coverage_version: str


class PriceObservation(Contract):
    listing_id: str
    product_id: int
    platform: Key
    product_name: str
    product_url: URL
    current_price: Money | None
    original_price: Money | None = None
    seller_name: str | None = None
    seller_rating: float | None = Field(default=None, ge=0)
    seller_rating_scale: float | None = Field(default=None, gt=0)
    stock_status: Stock | None
    timestamp: AwareDatetime
    currency: Literal["TRY"] = "TRY"

    @model_validator(mode="after")
    def purchasable_offer(self):
        if self.stock_status in ("Stokta Var", "Kritik Stok"):
            if self.current_price is None or not self.seller_name:
                raise ValueError("Satılabilir teklif fiyat ve satıcı içermeli")
        if self.seller_rating is not None and self.seller_rating_scale is not None:
            if self.seller_rating > self.seller_rating_scale:
                raise ValueError("Satıcı puanı ölçeği aşıyor")
        return self


class PricePoint(Contract):
    product_id: int
    timestamp: AwareDatetime
    price: Money
    coverage_version: str
    run_id: str


class FeatureVector(Contract):
    product_id: int
    haftanin_gunu: int
    ay: int
    normalize_fiyat_orani: float
    son_indirimden_gecen_gun_sayisi: float | None


class PredictionResult(Contract):
    probability: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    model_version: str | None = None
    as_of: AwareDatetime | None = None


class PlatformOffer(Contract):
    platform_name: str
    observation: PriceObservation


class ProductSummary(Contract):
    product_id: int
    product_name: str
    coverage_version: str
    as_of: AwareDatetime | None = None
    attempted_at: AwareDatetime | None = None
    complete: bool = False
    stale: bool = False
    expected_listings: int = 0
    observed_listings: int = 0
    offers: list[PlatformOffer] = Field(default_factory=list)
    best_offer: PlatformOffer | None = None
    lowest_30_days: bool = False
    historical_peak: Money | None = None
    volatility: float | None = None
    critical_stock: bool = False
    prediction: PredictionResult
    forecast_horizon_days: int = 7
    discount_threshold: float = 0.05
    money_unit: Literal["kurus"] = "kurus"


class MarketRecord(Contract):
    source: Literal["akakce", "cimri"]
    product_id: int
    source_url: URL
    timestamp: AwareDatetime
    price: Money
    scope: Literal["market_minimum"] = "market_minimum"
    eligible_for_target: Literal[False] = False
