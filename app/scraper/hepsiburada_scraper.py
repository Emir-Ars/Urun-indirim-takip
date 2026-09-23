"""Hepsiburada ürün bağlamı ve otherMerchants API adaptörü."""

import json
import re
from uuid import uuid4

from bs4 import BeautifulSoup

from app.scraper.base import BaseScraper
from app.scraper.http import FetchError
from app.scraper.parsing import (
    embedded_json,
    money,
    nested_dicts,
    normalize,
    product_jsonld,
    verify_identity,
)

API_URL = "https://www.hepsiburada.com/api/v1/otherMerchants"
LISTINGS_URL = "https://www.hepsiburada.com/api/v1/product/listings/{sku}"
PRODUCT_FIELDS = (
    "productTags",
    "sku",
    "productId",
    "brand",
    "rootCategoryList",
    "rootBuyingCategoryList",
    "definitionName",
    "definitionId",
    "taxVatRate",
    "campaignIds",
    "otherMerchants",
)
DISALLOWED_CONDITIONS = (
    re.compile(r"\byenilenmis\b"),
    re.compile(r"\bikinci[\s_-]*el\b"),
    re.compile(r"\bteshir\b"),
)


def _sku_from_url(url: str) -> str:
    match = re.search(r"-p-(HBCV[A-Z0-9]+)(?:[/?]|$)", url, re.IGNORECASE)
    if not match:
        raise FetchError("identity", "Hepsiburada SKU kodu URL'de bulunamadı")
    return match.group(1).upper()


def _product_context(soup: BeautifulSoup, sku: str) -> dict:
    matches = []
    seen = set()
    for root in embedded_json(soup):
        for candidate in nested_dicts(root):
            if str(candidate.get("sku", "")).upper() != sku:
                continue
            context = _payload_context(candidate)
            if context is None:
                continue
            marker = json.dumps(context, sort_keys=True, ensure_ascii=False)
            if marker not in seen:
                seen.add(marker)
                matches.append(context)
    if len(matches) != 1:
        raise FetchError("parse", "Tek bir tam Hepsiburada ürün bağlamı bulunamadı")
    return matches[0]


def _payload_context(candidate: dict) -> dict | None:
    if all(field in candidate for field in PRODUCT_FIELDS):
        if isinstance(candidate["otherMerchants"], list):
            return {field: candidate[field] for field in PRODUCT_FIELDS}
        return None

    redux_fields = {
        "sku",
        "productId",
        "brand",
        "definitionName",
        "definitionId",
        "taxVatRate",
        "campaignIds",
        "mainProductTagList",
        "rootCategoryList",
        "listings",
        "merchantId",
        "merchantName",
        "listingId",
        "prices",
    }
    if not redux_fields.issubset(candidate):
        return None
    categories = [
        _category_id(item)
        for item in candidate["rootCategoryList"]
        if _category_id(item) not in (None, 0)
    ]
    if not categories:
        return None
    merchants = [
        _merchant_payload(candidate, _tag_ids(candidate["mainProductTagList"]))
    ]
    for listing in candidate["listings"]:
        if isinstance(listing, dict) and listing.get("isSalable") is not False:
            merchants.append(
                _merchant_payload(listing, _tag_ids(listing.get("tagList")))
            )
    return {
        "productTags": _tag_ids(candidate["mainProductTagList"]),
        "sku": candidate["sku"],
        "productId": candidate["productId"],
        "brand": candidate["brand"],
        "rootCategoryList": categories,
        "rootBuyingCategoryList": [categories[-1]],
        "definitionName": candidate["definitionName"],
        "definitionId": str(candidate["definitionId"]),
        "taxVatRate": candidate["taxVatRate"],
        "campaignIds": candidate["campaignIds"],
        "otherMerchants": merchants,
    }


def _tag_ids(items) -> list[str]:
    if not isinstance(items, list):
        return []
    return [
        str(item["tagId"])
        for item in items
        if isinstance(item, dict) and item.get("tagId")
    ]


def _merchant_tags(merchant: dict) -> list[str]:
    tags = _tag_ids(merchant.get("tagList"))
    payment_tags = merchant.get("paymentTag")
    if isinstance(payment_tags, str):
        tags.extend(tag.strip() for tag in payment_tags.split(",") if tag.strip())
    return list(dict.fromkeys(tags))


def _category_id(item) -> int | None:
    if not isinstance(item, dict):
        return None
    try:
        return int(item["categoryId"])
    except (KeyError, TypeError, ValueError):
        return None


def _amount(value):
    if isinstance(value, dict):
        return value.get("value")
    return value


def _merchant_payload(merchant: dict, tags: list[str] | None = None) -> dict:
    price = _amount(merchant.get("price"))
    prices = merchant.get("prices") or []
    if price is None and prices and isinstance(prices[0], dict):
        price = prices[0].get("value")
    if price is None:
        price = _amount(merchant.get("originalPrice"))
    if price is None:
        raise FetchError("parse", "Hepsiburada satıcı fiyatı eksik")
    return {
        "productTags": tags if tags is not None else _merchant_tags(merchant),
        "campaignIds": merchant.get("campaignIds") or [],
        "finalPriceOnSale": price,
        "minimumPriceForNLastDays": _amount(merchant.get("minimumPrice")) or price,
        "merchantId": merchant["merchantId"],
        "merchantName": merchant["merchantName"],
        "listingId": merchant["listingId"],
    }


def _verify_product(soup: BeautifulSoup, listing, sku: str) -> None:
    names = []
    for product in product_jsonld(soup):
        product_sku = str(product.get("sku", "")).upper()
        if not product_sku or product_sku == sku:
            if product.get("name"):
                names.append(product["name"])
    if not names:
        heading = soup.find("h1")
        if heading is not None:
            names.append(heading.get_text(" ", strip=True))
    for name in names:
        try:
            verify_identity(name, listing.model, listing.storage_gb)
            return
        except FetchError:
            continue
    raise FetchError("identity", "Hepsiburada ürün adı katalogla eşleşmiyor")


def _offer_text(offer: dict, source: dict) -> str:
    values = [str(offer.get("merchantName", ""))]
    for campaign in offer.get("campaigns") or []:
        if isinstance(campaign, dict):
            values.append(str(campaign.get("text", "")))
    for tag in source.get("productTags") or []:
        values.append(str(tag))
    return normalize(" ".join(values))


def _is_allowed(offer: dict, source: dict) -> bool:
    text = _offer_text(offer, source)
    return not any(pattern.search(text) for pattern in DISALLOWED_CONDITIONS)


def _response_listings(response: dict) -> list[dict]:
    if response.get("statusCode") != 200:
        raise FetchError(
            "api_error", "Hepsiburada satıcı listesi API'si başarısız oldu"
        )
    try:
        listings = response["data"]["listings"]
    except (KeyError, TypeError) as exc:
        raise FetchError("parse", "Hepsiburada tam satıcı listesi eksik") from exc
    if not isinstance(listings, list):
        raise FetchError("parse", "Hepsiburada tam satıcı listesi geçersiz")
    return [item for item in listings if isinstance(item, dict)]


def _seller_rating(listing: dict) -> float | None:
    summary = listing.get("ratingSummary") or {}
    if not isinstance(summary, dict) or not summary.get("ratingQuantity"):
        return None
    rating = summary.get("lifetimeRating")
    try:
        return float(rating) if rating is not None else None
    except (TypeError, ValueError):
        return None


def _response_products(response: dict, sku: str) -> dict:
    if response.get("statusCode") != 200:
        raise FetchError("api_error", "Hepsiburada satıcı API'si başarısız oldu")
    try:
        products = response["data"]["result"]["products"]
    except (KeyError, TypeError) as exc:
        raise FetchError("parse", "Hepsiburada satıcı yanıtı eksik") from exc
    if not isinstance(products, dict) or str(products.get("sku", "")).upper() != sku:
        raise FetchError("identity", "Hepsiburada API SKU kodu eşleşmiyor")
    if not isinstance(products.get("otherMerchants"), list):
        raise FetchError("parse", "Hepsiburada API satıcı listesi eksik")
    return products


class Scraper(BaseScraper):
    def __init__(self, hosts, runtime, client=None):
        super().__init__(hosts, runtime, client)
        self._anonymous_user_id = None
        self._last_offers = []

    def _user_id(self) -> str:
        if self._anonymous_user_id is None:
            self._anonymous_user_id = self.pages.cookie("hbus_anonymousId") or str(
                uuid4()
            )
        return self._anonymous_user_id

    def get_product_data(self, listing):
        sku = _sku_from_url(listing.url)
        soup = BeautifulSoup(self.pages.get(listing.url), "html.parser")
        _verify_product(soup, listing, sku)
        product = _product_context(soup, sku)

        listings_response = self.pages.get_json(
            LISTINGS_URL.format(sku=sku),
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": listing.url,
            },
        )
        full_listings = _response_listings(listings_response)
        diagnostics = []
        diagnostic_by_id = {}
        for item in full_listings:
            listing_id = item.get("listingId")
            try:
                current = money(_amount(item.get("price")))
            except (TypeError, ValueError):
                current = None
            try:
                raw_original = _amount(item.get("originalPrice"))
                original = money(raw_original) if raw_original is not None else None
            except (TypeError, ValueError):
                original = None
            if original is not None and current is not None and original <= current:
                original = None
            salable = item.get("isSalable")
            diagnostic = {
                "listing_id": str(listing_id) if listing_id else None,
                "seller_name": item.get("merchantName"),
                "seller_rating": _seller_rating(item),
                "seller_rating_scale": (
                    10.0 if _seller_rating(item) is not None else None
                ),
                "current_price": current,
                "original_price": original,
                "stock_status": "Stokta Var" if salable is True else "Tükendi",
                "offer_url": listing.url,
                "eligible": salable is True and current is not None,
                "rejection_reason": None,
                "selected": False,
            }
            if salable is not True:
                diagnostic["rejection_reason"] = "out_of_stock"
            elif current is None:
                diagnostic["rejection_reason"] = "missing_price"
            diagnostics.append(diagnostic)
            if listing_id:
                diagnostic_by_id[listing_id] = diagnostic
        if not full_listings or not any(
            item.get("isSalable") is True for item in full_listings
        ):
            self._last_offers = diagnostics
            return self.observation(
                listing,
                current_price=None,
                original_price=None,
                seller_name=None,
                seller_rating=None,
                seller_rating_scale=None,
                stock_status="Tükendi",
            )

        listing_sources = {}
        merchant_payloads = []
        for item in full_listings:
            if item.get("isSalable") is not True:
                continue
            diagnostic = diagnostic_by_id.get(item.get("listingId"))
            try:
                source = _merchant_payload(item)
            except (FetchError, KeyError, TypeError):
                if diagnostic is not None:
                    diagnostic["eligible"] = False
                    diagnostic["rejection_reason"] = "invalid_offer"
                continue
            if not _is_allowed({"merchantName": item.get("merchantName", "")}, source):
                if diagnostic is not None:
                    diagnostic["eligible"] = False
                    diagnostic["rejection_reason"] = "disallowed_condition"
                continue
            listing_id = source["listingId"]
            listing_sources[listing_id] = item
            merchant_payloads.append(source)

        if not merchant_payloads:
            self._last_offers = diagnostics
            raise FetchError(
                "no_eligible_offer", "Hepsiburada'da uygun satılabilir teklif yok"
            )
        product["otherMerchants"] = merchant_payloads
        response = self.pages.post_json(
            API_URL,
            {"userId": self._user_id(), "product": product},
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Content-Type": "application/json;charset=UTF-8",
                "Origin": "https://www.hepsiburada.com",
                "Referer": listing.url,
            },
        )
        products = _response_products(response, sku)
        offers = products["otherMerchants"]
        if not offers:
            self._last_offers = diagnostics
            return self.observation(
                listing,
                current_price=None,
                original_price=None,
                seller_name=None,
                seller_rating=None,
                seller_rating_scale=None,
                stock_status="Tükendi",
            )

        payload_sources = {
            item.get("listingId"): item
            for item in product["otherMerchants"]
            if isinstance(item, dict) and item.get("listingId")
        }
        candidates = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            listing_id = offer.get("listingId")
            source = payload_sources.get(listing_id)
            full_listing = listing_sources.get(listing_id)
            if source is None or full_listing is None:
                continue
            if not _is_allowed(offer, source):
                diagnostic = diagnostic_by_id.get(listing_id)
                if diagnostic is not None:
                    diagnostic["eligible"] = False
                    diagnostic["rejection_reason"] = "disallowed_condition"
                continue
            price_data = offer.get("priceData") or {}
            raw_price = price_data.get("discountedPrice")
            if raw_price is None:
                raw_price = price_data.get("price")
            if raw_price is None or not offer.get("merchantName"):
                continue
            current = money(raw_price)
            regular = price_data.get("price")
            original = money(regular) if regular is not None else None
            if original is not None and original <= current:
                original = None
            diagnostic = diagnostic_by_id.get(listing_id)
            if diagnostic is not None:
                diagnostic.update(
                    current_price=current,
                    original_price=original,
                    seller_name=str(offer["merchantName"]),
                    seller_rating=_seller_rating(full_listing),
                    seller_rating_scale=(
                        10.0 if _seller_rating(full_listing) is not None else None
                    ),
                    eligible=True,
                    rejection_reason=None,
                )
            candidates.append(
                {
                    "current": current,
                    "seller": str(offer["merchantName"]),
                    "listing_id": str(listing_id),
                    "original": original,
                    "rating": _seller_rating(full_listing),
                }
            )
        if not candidates:
            self._last_offers = diagnostics
            raise FetchError(
                "no_eligible_offer", "Hepsiburada'da uygun satılabilir teklif yok"
            )
        winner = min(
            candidates,
            key=lambda item: (item["current"], item["seller"], item["listing_id"]),
        )
        winner_diagnostic = diagnostic_by_id.get(winner["listing_id"])
        if winner_diagnostic is not None:
            winner_diagnostic["selected"] = True
        self._last_offers = diagnostics
        return self.observation(
            listing,
            current_price=winner["current"],
            original_price=winner["original"],
            seller_name=winner["seller"],
            seller_rating=winner["rating"],
            seller_rating_scale=10.0 if winner["rating"] is not None else None,
            stock_status="Stokta Var",
        )
