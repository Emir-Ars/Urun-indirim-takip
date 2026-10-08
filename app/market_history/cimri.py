"""Kaydedilmiş Cimri ürün ve grafik yanıtlarını ağsız doğrular."""

import json
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app.scraper.http import FetchError
from app.scraper.parsing import money, normalize, verify_identity

CIMRI_API_URL = "https://www.cimri.com/api/cimri"
CIMRI_HOSTS = ["www.cimri.com", "cimri.com"]
MAX_HISTORY_DAYS = 366


def _cimri_product_id(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise FetchError("parse", "Cimri ürün kimliği bulunamadı")
    product_id = str(value)
    if not product_id.isascii() or not product_id.isdecimal():
        raise FetchError("parse", "Cimri ürün kimliği geçersiz")
    return product_id


def _cimri_price(value) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FetchError("parse", "Cimri geçmişinde geçersiz fiyat")
    try:
        price = Decimal(str(value))
    except InvalidOperation as exc:
        raise FetchError("parse", "Cimri geçmişinde geçersiz fiyat") from exc
    if not price.is_finite() or price <= 0:
        raise FetchError("parse", "Cimri geçmişinde geçersiz fiyat")
    return price


def _price_in_kurus(value) -> int:
    _cimri_price(value)
    try:
        return money(value)
    except ValueError as exc:
        raise FetchError("parse", "Cimri fiyatı kuruş olarak doğrulanamadı") from exc


def _first_offer_price(product: dict):
    offers = product.get("offers", [])
    if not isinstance(offers, list):
        raise FetchError("parse", "Cimri teklif listesi geçersiz")
    if not offers:
        return None
    try:
        price = offers[0]["price"]
    except (KeyError, TypeError) as exc:
        raise FetchError("parse", "Cimri ilk teklif fiyatı eksik") from exc
    _price_in_kurus(price)
    return price


def _capture_day(page_started_at_utc: str, captured_at_utc: str) -> str:
    try:
        start = datetime.fromisoformat(page_started_at_utc)
        end = datetime.fromisoformat(captured_at_utc)
    except (TypeError, ValueError) as exc:
        raise FetchError("parse", "Cimri alım zamanı geçersiz") from exc
    if (
        start.utcoffset() != timedelta()
        or end.utcoffset() != timedelta()
        or start > end
    ):
        raise FetchError("parse", "Cimri alım zamanı UTC ve sıralı olmalı")
    zone = ZoneInfo("Europe/Istanbul")
    day = end.astimezone(zone).date()
    if start.astimezone(zone).date() != day:
        raise FetchError("parse", "Cimri alımı gün sınırını aştı")
    return day.isoformat()


def _cimri_day(value: str, date_format: str) -> date:
    if not isinstance(value, str):
        raise FetchError("parse", "Cimri geçmişinde geçersiz tarih")
    try:
        day = datetime.strptime(value, date_format).date()
    except ValueError as exc:
        raise FetchError("parse", "Cimri geçmişinde geçersiz tarih") from exc
    if day.strftime(date_format) != value:
        raise FetchError("parse", "Cimri geçmişinde geçersiz tarih")
    return day


def _page_data(soup: BeautifulSoup) -> dict:
    script = soup.find("script", id="__OCTOPUS_DATA__")
    try:
        data = json.loads(script.string)["props"]["pageProps"]["data"]
        _cimri_product_id(data["product"]["id"])
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise FetchError("parse", "Cimri ürün verisi okunamadı") from exc
    if not isinstance(data.get("priceHistoryTablePrices", []), list):
        raise FetchError("parse", "Cimri tablo verisi geçersiz")
    return data


def cimri_page_data(html: str) -> tuple[str, list]:
    data = _page_data(BeautifulSoup(html, "html.parser"))
    return _cimri_product_id(data["product"]["id"]), data.get(
        "priceHistoryTablePrices", []
    )


def verified_page(html: str, product, expected_id: str) -> tuple[dict, list]:
    soup = BeautifulSoup(html, "html.parser")
    data = _page_data(soup)
    page_product = data["product"]
    source_id = _cimri_product_id(page_product["id"])
    if source_id != expected_id:
        raise FetchError("identity", "Cimri sayfası eşleştirmedeki ürüne ait değil")
    try:
        title = page_product["title"]
        brand = page_product["brand"]["name"]
        category = page_product["category"]["slug"]
    except (KeyError, TypeError) as exc:
        raise FetchError("identity", "Cimri marka, başlık veya kategori eksik") from exc
    if not isinstance(title, str) or not isinstance(brand, str):
        raise FetchError("identity", "Cimri başlık veya marka doğrulanamadı")
    if normalize(brand).strip() != normalize(product.brand).strip():
        raise FetchError("identity", "Cimri markası katalogla eşleşmiyor")
    if category != "cep-telefonlari":
        raise FetchError("identity", "Cimri ürünü yeni telefon kategorisinde değil")
    headings = [item.get_text(" ", strip=True) for item in soup.find_all("h1")]
    for name in [title, *headings]:
        verify_identity([name], product.model, product.storage_gb)
    return {
        "product_id": source_id,
        "title": title,
        "brand": brand,
        "category": category,
        "headings": headings,
        "first_offer_price": _first_offer_price(page_product),
    }, data.get("priceHistoryTablePrices", [])


def cimri_history(
    response: dict, product_id: str, table_rows: list, *, zero_as_missing: bool = False
) -> dict:
    try:
        history = response["data"]["priceHistoryV2"]
        response_id = _cimri_product_id(history["productId"])
        last_day = _cimri_day(history["lastDay"], "%Y-%m-%d")
        prices = history["prices"]
    except (KeyError, TypeError) as exc:
        raise FetchError("parse", "Cimri grafik yanıtı eksik") from exc
    if response_id != product_id:
        raise FetchError("identity", "Cimri grafik yanıtı farklı ürüne ait")
    if not isinstance(prices, list) or not 1 <= len(prices) <= MAX_HISTORY_DAYS:
        raise FetchError("parse", "Cimri grafik fiyat dizisi geçersiz")

    points = []
    for offset, raw_price in enumerate(prices):
        try:
            day = last_day - timedelta(days=offset)
        except OverflowError as exc:
            raise FetchError("parse", "Cimri tarih dizisi geçersiz") from exc
        if (
            zero_as_missing
            and isinstance(raw_price, (int, float))
            and not isinstance(raw_price, bool)
            and raw_price == 0
        ):
            raw_price = None
        if raw_price is not None:
            _cimri_price(raw_price)
        points.append({"day": day.isoformat(), "price_tl": raw_price})
    points.reverse()
    compared = _compare_table(points, table_rows)

    return {
        "summary": {
            "product_id": product_id,
            "oldest_day": points[0]["day"],
            "newest_day": points[-1]["day"],
            "point_count": len(points),
            "missing_price_count": sum(p["price_tl"] is None for p in points),
            "table_compared_rows": compared,
            "table_comparison": "matched" if compared else "unavailable",
            "interpretation": "Tekrarlanan fiyatlar ayrı günlük gözlemleri kanıtlamaz.",
        },
        "points": points,
    }


def _compare_table(points: list, table_rows: list) -> int:
    by_day = {point["day"]: point["price_tl"] for point in points}
    compared = 0
    for row in table_rows:
        if not isinstance(row, dict):
            raise FetchError("parse", "Cimri tablo verisi geçersiz")
        try:
            day = _cimri_day(row["date"], "%d/%m/%Y").isoformat()
            table_price = _cimri_price(row["minPrice"])
        except KeyError as exc:
            raise FetchError("parse", "Cimri tablo verisi eksik") from exc
        if day not in by_day:
            continue
        compared += 1
        graph_price = by_day[day]
        if graph_price is None or _cimri_price(graph_price) != table_price:
            raise FetchError("parse", f"Cimri tablo ve grafik fiyatı uyuşmuyor: {day}")
    return compared


def history_in_kurus(
    response: dict,
    product_id: str,
    table_rows: list,
    *,
    first_offer_price=None,
    page_started_at_utc: str | None = None,
    captured_at_utc: str | None = None,
) -> dict:
    history = cimri_history(response, product_id, [], zero_as_missing=True)
    points = [
        {
            "day": point["day"],
            "price_kurus": (
                None
                if point["price_tl"] is None
                else _price_in_kurus(point["price_tl"])
            ),
        }
        for point in history["points"]
    ]
    latest = points[-1]
    api_price = latest["price_kurus"]
    offer_price = None
    if first_offer_price is not None:
        offer_price = _price_in_kurus(first_offer_price)
        if latest["day"] != _capture_day(page_started_at_utc, captured_at_utc):
            raise FetchError("parse", "Cimri API son günü ile alım günü uyuşmuyor")
        if api_price is None:
            raise FetchError(
                "parse", "Cimri bugünkü API fiyatı eksik; dönüşüm doğrulanamadı"
            )
        # Cimri grafiği yalnız bugünkü noktayı HTML'nin ilk teklifiyle değiştirir.
        history["points"][-1]["price_tl"] = first_offer_price
        latest["price_kurus"] = offer_price
    compared = _compare_table(history["points"], table_rows)
    table_days = set()
    for row in table_rows:
        _price_in_kurus(row["minPrice"])
        table_days.add(_cimri_day(row["date"], "%d/%m/%Y").isoformat())
    history["summary"].update(
        table_compared_rows=compared,
        table_comparison="matched" if compared else "unavailable",
        latest_price={
            "day": latest["day"],
            "rule": "page_first_offer" if offer_price is not None else "api",
            "api_price_kurus": api_price,
            "first_offer_price_kurus": offer_price,
            "effective_price_kurus": latest["price_kurus"],
            "changed": api_price != latest["price_kurus"],
            "table_comparison": (
                "matched" if latest["day"] in table_days else "unavailable"
            ),
        },
    )
    return {"summary": history["summary"], "points": points}
