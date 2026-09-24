"""Kaynak metnini ortak fiyat, ürün kimliği ve JSON biçimine dönüştürür."""

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from bs4 import BeautifulSoup

from app.scraper.http import FetchError

# Keşif ve scraper aynı kimlik kurallarını kullanır; kurallar yalnız burada tutulur.
EXCLUDED = re.compile(
    r"\b(?:kilif|kapak|koruyucu|sarj|adaptor|kablo|"
    r"kulaklik|yenilenmis|refurbished|teshir|ikinci[ _-]*el)\b"
)
MODEL_SUFFIX = re.compile(r"\b(?:pro|plus|max|ultra|fe|lite|mini)\b")
# Satıcı/teklif düzeyinde kapsam dışı koşullar (her iki scraper kullanır).
DISALLOWED_CONDITIONS = (
    re.compile(r"\byenilenmis\b"),
    re.compile(r"\bikinci[\s_-]*el\b"),
    re.compile(r"\bteshir\b"),
)
CAPACITY = re.compile(r"(?<!\d)(\d+)\s*(gb|tb)\b")


def money(value) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError("Fiyat sayısal olmalı")
    text = str(value).strip().replace("\xa0", "").replace(" ", "")
    text = text.replace("₺", "").replace("TL", "").replace("TRY", "")
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


def storage_gb(value) -> int | None:
    """'128 GB' veya '1 TB' gibi tek bir kapasite değerini GB'ye çevirir."""
    match = CAPACITY.fullmatch(normalize(str(value)).strip())
    if not match:
        return None
    capacity = int(match.group(1)) * (1024 if match.group(2) == "tb" else 1)
    return capacity if capacity > 0 else None


def title_storage(name: str) -> int | None:
    """Başlıkta tek kapasite varsa döndürür; birden çoksa RAM tahmini yapmaz."""
    matches = [
        storage_gb(match.group()) for match in CAPACITY.finditer(normalize(name))
    ]
    matches = [value for value in matches if value is not None]
    return matches[0] if len(matches) == 1 else None


def matches_model(name: str, model: str) -> bool:
    """Başlık tam modeli içeriyor mu; Pro/Plus/mini/16e/S24+ gibi farklar reddedilir."""
    title = normalize(name)
    desired = normalize(model)
    if EXCLUDED.search(title):
        return False
    tokens = re.findall(r"[a-z]+|\d+", desired)
    if not tokens:
        return False
    pattern = r"(?<![a-z0-9])" + r"[\s_-]*".join(map(re.escape, tokens))
    match = re.search(pattern, title)
    if not match or (
        match.end() < len(title)
        and (title[match.end()].isalnum() or title[match.end()] == "+")
    ):
        return False
    extras = set(MODEL_SUFFIX.findall(title)) - set(MODEL_SUFFIX.findall(desired))
    return not extras


def excluded_term(names, terms) -> str | None:
    """Adlardan birinde bütün sözcük olarak geçen ilk dışlanan ifade.

    "5G" ifadesi "Note 14 5G" başlığında bulunur, "5 GB RAM" içinde bulunmaz.
    """
    for term in terms:
        tokens = re.findall(r"[a-z]+|\d+", normalize(term))
        if not tokens:
            continue
        pattern = (
            r"(?<![a-z0-9])" + r"[\s_-]*".join(map(re.escape, tokens)) + r"(?![a-z0-9])"
        )
        if any(re.search(pattern, normalize(name)) for name in names):
            return term
    return None


def page_capacity(names: list[str], structured: int | None = None) -> int | None:
    """Yapısal kapasite ve başlıklardaki tekil kapasiteler çelişmiyorsa kapasite.

    Hiç kaynak yoksa veya kaynaklar farklı kapasite söylüyorsa None döner.
    """
    found = {title_storage(name) for name in names}
    found.add(structured)
    found.discard(None)
    return found.pop() if len(found) == 1 else None


def identify(
    names: list[str], model: str, capacity: int | None = None, exclude=()
) -> int:
    """Sayfa tam modele aitse kapasitesini döndürür; değilse FetchError verir.

    `names` sayfadaki ürün adlarının listesidir; `capacity` sayfanın
    yapısal verisinden okunan kapasitedir; `exclude` hedefin dışladığı ifadelerdir.
    Keşif bu kapasiteyle aday oluşturur, scraper aynı fonksiyonla katalogdaki
    kapasiteyi doğrular.
    """
    names = [name for name in names if name]
    seen = " | ".join(names)[:160] or "ürün adı bulunamadı"
    if any(EXCLUDED.search(normalize(name)) for name in names):
        raise FetchError(
            "identity",
            f"Yenilenmiş, ikinci el, teşhir veya aksesuar ürün kapsam dışında: {seen}",
        )
    if not any(matches_model(name, model) for name in names):
        raise FetchError("identity", f"Sayfadaki model hedefle eşleşmiyor: {seen}")
    term = excluded_term(names, exclude)
    if term:
        raise FetchError("identity", f"Hedefin dışladığı ifade ({term}): {seen}")
    found = page_capacity(names, capacity)
    if found is None:
        raise FetchError("identity", f"Sayfadaki kapasite doğrulanamadı: {seen}")
    return found


def verify_identity(
    names: list[str], model: str, expected_gb: int, capacity=None
) -> None:
    """Sayfanın katalogdaki model ve kapasiteye ait olduğunu doğrular."""
    found = identify(names, model, capacity)
    if found != expected_gb:
        raise FetchError(
            "identity", f"Sayfadaki kapasite katalogla eşleşmiyor: {found} GB"
        )


def attribute(attributes: list, *names: str) -> str | None:
    """Ürün özellik listesinden adı verilen özelliğin değerini okur."""
    expected = {normalize(name) for name in names}
    for item in attributes:
        if not isinstance(item, dict):
            continue
        key = item.get("key") or {}
        if (
            normalize(str(key.get("name", ""))) in expected
            or normalize(str(item.get("type", ""))) in expected
        ):
            value = item.get("value") or {}
            if isinstance(value, dict) and value.get("name"):
                return str(value["name"])
    return None


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
