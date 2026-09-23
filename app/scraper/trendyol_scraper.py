"""Trendyol öne çıkan satıcı adaptörü; diğer satıcılar dolaşılmaz."""

import re

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper
from app.scraper.http import FetchError
from app.scraper.parsing import assigned_json, money, verify_identity


class Scraper(BaseScraper):
    def get_product_data(self, listing):
        return self.parse(self.pages.get(listing.url), listing)

    def parse(self, html, listing):
        soup = BeautifulSoup(html, "html.parser")
        state = assigned_json(soup, "__envoy__SHARED_PROPS")
        if state is None:
            raise FetchError("parse", "Trendyol ürün durum verisi bulunamadı")
        product = state["product"]
        verify_identity(product["name"], listing.model, listing.storage_gb)
        match = re.search(r"-p-(\d+)", listing.url)
        if not match or str(product["id"]) != match.group(1):
            raise FetchError("identity", "Trendyol ürün kimliği değişmiş")
        merchant_listing = product.get("merchantListing") or {}
        winner = merchant_listing.get("winnerVariant") or {}
        merchant = merchant_listing.get("merchant") or {}
        in_stock = winner.get("inStock", product.get("inStock"))
        status = None
        if in_stock is False:
            status = "Tükendi"
        elif in_stock is True:
            status = (
                "Kritik Stok" if winner.get("isRunningOut") is True else "Stokta Var"
            )
        price = winner.get("price") or {}
        current, original = None, None
        if price:
            if price.get("currency") != "TRY":
                raise FetchError("currency", "Teklif TRY cinsinden değil")
            current = money(price["sellingPrice"]["value"])
            old = (price.get("originalPrice") or {}).get("value")
            if old is not None:
                old = money(old)
                original = old if old > current else None
        score = (merchant.get("sellerScore") or {}).get("value")
        return self.observation(
            listing,
            current_price=current,
            original_price=original,
            seller_name=merchant.get("name"),
            seller_rating=float(score) if score is not None else None,
            seller_rating_scale=10.0 if score is not None else None,
            stock_status=status,
        )
