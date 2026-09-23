"""Kaynak metnini ortak fiyat, ürün kimliği ve JSON biçimine dönüştürür."""

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.scraper.http import FetchError


def money(value, *, localized=False) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError("Fiyat sayısal olmalı")
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    text = text.replace("₺", "").replace("TL", "").replace("TRY", "")
    if localized:
        text = text.replace(".", "").replace(",", ".")
    try:
        amount = Decimal(text) * 100
    except InvalidOperation as exc:
        raise ValueError("Fiyat ayrıştırılamadı") from exc
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise ValueError("Fiyat pozitif ve en fazla iki ondalıklı olmalı")
    return int(amount)


def normalize(text: str) -> str:
    text = text.casefold().replace("ı", "i")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def verify_identity(name: str, model: str, storage_gb: int) -> None:
    name, model = normalize(name), normalize(model)
    tokens = re.findall(r"[a-z]+|\d+", model)
    pattern = r"(?<!\w)" + r"[\s-]*".join(map(re.escape, tokens)) + r"(?!\w)"
    if not re.search(pattern, name):
        raise FetchError("identity", "Sayfadaki model katalogla eşleşmiyor")
    capacities = {int(v) for v in re.findall(r"(?<!\d)(\d+)\s*gb\b", name)}
    if storage_gb not in capacities:
        raise FetchError("identity", "Sayfadaki kapasite katalogla eşleşmiyor")
    # Aynı ailedeki Pro/Plus/Ultra modellerinin temel modele karışmasını önler.
    for suffix in ("pro", "plus", "max", "ultra", "fe", "lite"):
        if re.search(rf"\b{suffix}\b", name) and not re.search(rf"\b{suffix}\b", model):
            raise FetchError("identity", "Sayfadaki alt model katalogla eşleşmiyor")
    if any(word in name for word in ("yenilenmis", "ikinci el", "refurbished")):
        raise FetchError("identity", "Yenilenmiş/ikinci el ürün kapsam dışında")


def assigned_json(soup: BeautifulSoup, variable: str) -> dict | None:
    pattern = re.compile(r"window\[\s*['\"]" + re.escape(variable) + r"['\"]\s*\]\s*=")
    for script in soup.find_all("script"):
        match = pattern.search(script.get_text())
        if match:
            try:
                return json.JSONDecoder().raw_decode(
                    script.get_text()[match.end() :].lstrip()
                )[0]
            except (ValueError, TypeError) as exc:
                raise FetchError("parse", "Sayfa durum JSON'u geçersiz") from exc
    return None


def embedded_json(soup: BeautifulSoup):
    """JSON scriptlerini ve window atamalarını sayfa çalıştırmadan okur."""
    assignment = re.compile(
        r"(?:window\.[\w$]+|window\[\s*['\"][^'\"]+['\"]\s*\])\s*=\s*"
    )
    for script in soup.find_all("script"):
        text = script.get_text().strip()
        if not text:
            continue
        if (
            text[:1] in {"{", "["}
            or script.get("id") == "__NEXT_DATA__"
            or script.get("type") in {"application/json", "application/ld+json"}
        ):
            try:
                yield json.loads(text)
            except (ValueError, TypeError):
                pass
        for match in assignment.finditer(text):
            try:
                yield json.JSONDecoder().raw_decode(text[match.end() :].lstrip())[0]
            except (ValueError, TypeError):
                continue


def nested_dicts(value):
    """Gömülü JSON içindeki tüm nesneleri derinlik öncelikli dolaşır."""
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_dicts(child)


def product_jsonld(soup: BeautifulSoup) -> list[dict]:
    def nodes(value):
        if isinstance(value, list):
            for item in value:
                yield from nodes(item)
        elif isinstance(value, dict):
            kind = value.get("@type", [])
            if kind == "Product" or (isinstance(kind, list) and "Product" in kind):
                yield value
            yield from nodes(value.get("@graph", []))

    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            products.extend(nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    return products
