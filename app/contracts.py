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


class Catalog(Contract):
    platforms: list[Platform]
    products: list[Product]
    listings: list[Listing]

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
        return self


class ProductListing(Listing):
    """Scraper'a verilen bağlantı: katalog kaydı + doğrulanacak model/kapasite."""

    product_name: str
    model: str
    storage_gb: int


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
    stock_status: Stock
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


class DiscoveryTarget(Contract):
    key: Key
    brand: str = Field(min_length=1)
    model: str = Field(min_length=1)
    active: bool = True
    # Aynı adı taşıyan farklı telefonları ayırır; ör. "Redmi Note 14" için ["5G"].
    exclude_terms: list[Annotated[str, Field(min_length=1)]] = Field(
        default_factory=list
    )


class DiscoveryConfig(Contract):
    targets: list[DiscoveryTarget]
    max_search_pages: int = Field(default=20, ge=1, le=100)
    max_product_pages: int = Field(default=100, ge=1, le=500)
    max_requests: int = Field(default=200, ge=1, le=1000)

    @model_validator(mode="after")
    def unique_targets(self):
        if len({target.key for target in self.targets}) != len(self.targets):
            raise ValueError("Keşif hedefleri benzersiz olmalı")
        return self


class DiscoveryCandidate(Contract):
    target_key: Key
    platform: Key
    platform_product_id: str = Field(min_length=1)
    url: URL
    brand: str = Field(min_length=1)
    model: str = Field(min_length=1)
    storage_gb: int = Field(gt=0)
    color: str = ""
    ram_gb: int | None = Field(default=None, gt=0)
    warranty_text: str | None = None
    warranty_source: str | None = None


class DiscoveryIssue(Contract):
    platform: Key
    target_key: Key
    reason: str
    detail: str = ""


class DiscoveryResult(Contract):
    platform: Key
    target_key: Key
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    issues: list[DiscoveryIssue] = Field(default_factory=list)
    complete: bool = False
    search_pages: int = 0
    product_pages: int = 0


class DiscoveryReport(Contract):
    complete: bool
    dry_run: bool
    results: list[DiscoveryResult]
    added_products: list[str] = Field(default_factory=list)
    added_listings: list[str] = Field(default_factory=list)
    existing_listings: list[str] = Field(default_factory=list)
    retained_unobserved_listings: list[str] = Field(default_factory=list)
    pending: list[DiscoveryIssue] = Field(default_factory=list)
    rejected: list[DiscoveryIssue] = Field(default_factory=list)
    coverage_changes: dict[str, int] = Field(default_factory=dict)
    observed_colors: dict[str, dict[str, dict[str, list[str]]]] = Field(
        default_factory=dict
    )
