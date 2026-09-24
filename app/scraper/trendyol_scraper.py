"""Trendyol satıcı tekliflerini doğrular ve en ucuz geçerli teklifi döndürür."""

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper
from app.scraper.http import FetchError
from app.scraper.parsing import (
    DISALLOWED_CONDITIONS,
    assigned_json,
    attribute,
    money,
    normalize,
    storage_gb,
    verify_identity,
)


def product_capacity(product: dict) -> int | None:
    """Ürün JSON'undaki yapısal depolama kapasitesi; keşif de aynı kaynağı okur."""
    value = attribute(
        product.get("attributes") or [], "Dahili Hafıza", "Internal Memory"
    )
    if value is None:
        value = (product.get("slicingAttributes") or {}).get("Internal Memory")
    return storage_gb(value or "")


def _product_id(url: str) -> str | None:
    match = re.search(r"-p-(\d+)", url)
    return match.group(1) if match else None


def _price(price: dict) -> tuple[int | None, int | None, str | None]:
    if not price:
        return None, None, "missing_price"
    if price.get("currency") != "TRY":
        return None, None, "invalid_currency"
    selling = (price.get("sellingPrice") or {}).get("value")
    discounted = (price.get("discountedPrice") or {}).get("value")
    # Güncel fiyat sayfanın gösterdiği koşulsuz indirimli fiyattır (ör. "Net 400 TL
    # İndirim"); adet/sepet koşullu indirimler bu alana girmez.
    offered = [money(value) for value in (selling, discounted) if value is not None]
    if not offered:
        return None, None, "missing_price"
    current = min(offered)
    # Sayfada üstü çizili görünen fiyat: originalPrice ile satış fiyatının büyüğü.
    old = (price.get("originalPrice") or {}).get("value")
    listed = [money(value) for value in (old, selling) if value is not None]
    original = max(listed) if listed else None
    if original is not None and original <= current:
        original = None
    return current, original, None


def _condition_text(merchant: dict, offer_url: str) -> str:
    values = [str(merchant.get("name", "")), offer_url]
    for promotion in merchant.get("promotions") or []:
        if isinstance(promotion, dict):
            values.extend(str(promotion.get(key, "")) for key in ("name", "shortName"))
    return normalize(" ".join(values))


def _offer(
    merchant: dict,
    variant: dict,
    listing,
    *,
    fallback_stock=None,
) -> dict:
    relative_url = merchant.get("url") or listing.url
    offer_url = urljoin("https://www.trendyol.com", relative_url)
    current, original, reason = _price(
        variant.get("price") or merchant.get("price") or {}
    )
    in_stock = variant.get("inStock", fallback_stock)
    sellable = variant.get("sellable", in_stock)
    if in_stock is False or sellable is False:
        status = "Tükendi"
        reason = reason or "out_of_stock"
    elif in_stock is True or sellable is True:
        status = "Kritik Stok" if variant.get("isRunningOut") is True else "Stokta Var"
    else:
        status = None
        reason = reason or "unknown_stock"
    seller_name = merchant.get("name")
    if not seller_name:
        reason = reason or "missing_seller"
    if any(
        pattern.search(_condition_text(merchant, offer_url))
        for pattern in DISALLOWED_CONDITIONS
    ):
        reason = "disallowed_condition"
    if _product_id(offer_url) != _product_id(listing.url):
        reason = "different_product_page"
    score = (merchant.get("sellerScore") or {}).get("value")
    return {
        "listing_id": str(variant.get("listingId", "")) or None,
        "seller_name": str(seller_name) if seller_name else None,
        "seller_rating": float(score) if score is not None else None,
        "seller_rating_scale": 10.0 if score is not None else None,
        "current_price": current,
        "original_price": original,
        "stock_status": status,
        "offer_url": offer_url,
        "eligible": reason is None,
        "rejection_reason": reason,
        "selected": False,
    }


class Scraper(BaseScraper):
    def __init__(self, hosts, runtime, client=None):
        super().__init__(hosts, runtime, client)
        self._last_offers = []

    def get_product_data(self, listing):
        return self.parse(self.pages.get(listing.url), listing)

    def parse(self, html, listing):
        soup = BeautifulSoup(html, "html.parser")
        state = assigned_json(soup, "__envoy__SHARED_PROPS")
        if state is None:
            raise FetchError("parse", "Trendyol ürün durum verisi bulunamadı")
        product = state["product"]
        verify_identity(
            [product["name"]],
            listing.model,
            listing.storage_gb,
            capacity=product_capacity(product),
        )
        if _product_id(listing.url) != str(product["id"]):
            raise FetchError("identity", "Trendyol ürün kimliği değişmiş")

        merchant_listing = product.get("merchantListing") or {}
        merchant = merchant_listing.get("merchant") or {}
        winner_variant = merchant_listing.get("winnerVariant") or {}
        offers = [
            _offer(
                merchant,
                winner_variant,
                listing,
                fallback_stock=product.get("inStock"),
            )
        ]
        for other in merchant_listing.get("otherMerchants") or []:
            if not isinstance(other, dict):
                continue
            for variant in other.get("variants") or [{}]:
                if isinstance(variant, dict):
                    offers.append(_offer(other, variant, listing))

        candidates = [offer for offer in offers if offer["eligible"]]
        if not candidates:
            self._last_offers = offers
            on_page = [
                offer
                for offer in offers
                if _product_id(offer["offer_url"]) == _product_id(listing.url)
                and offer["rejection_reason"] != "disallowed_condition"
            ]
            if on_page and all(offer["stock_status"] == "Tükendi" for offer in on_page):
                return self.observation(
                    listing,
                    current_price=None,
                    original_price=None,
                    seller_name=None,
                    seller_rating=None,
                    seller_rating_scale=None,
                    stock_status="Tükendi",
                )
            raise FetchError(
                "no_eligible_offer", "Trendyol'da uygun satılabilir teklif yok"
            )
        selected = min(
            candidates,
            key=lambda item: (
                item["current_price"],
                item["seller_name"],
                item["listing_id"] or "",
            ),
        )
        selected["selected"] = True
        self._last_offers = offers
        return self.observation(
            listing,
            current_price=selected["current_price"],
            original_price=selected["original_price"],
            seller_name=selected["seller_name"],
            seller_rating=selected["seller_rating"],
            seller_rating_scale=selected["seller_rating_scale"],
            stock_status=selected["stock_status"],
        )
