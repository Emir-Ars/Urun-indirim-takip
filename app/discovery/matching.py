"""Arama adaylarını gerçek telefon varyantlarından ayırır."""

import re

from app.scraper.parsing import normalize

EXCLUDED = re.compile(
    r"\b(?:kilif|kapak|koruyucu|sarj|adapt[oö]r|kablo|ekran koruyucu|"
    r"kulaklik|yenilenmis|refurbished|teshir|ikinci[ _-]*el)\b"
)
MODEL_SUFFIX = re.compile(r"\b(?:pro|plus|max|ultra|fe|lite|mini)\b")
CAPACITY = re.compile(r"(?<!\d)(\d+)\s*(gb|tb)\b")


def storage_gb(value: str) -> int | None:
    match = CAPACITY.fullmatch(normalize(str(value)).strip())
    if not match:
        return None
    capacity = int(match.group(1)) * (1024 if match.group(2) == "tb" else 1)
    return capacity if capacity > 0 else None


def title_storage(name: str, model: str) -> int | None:
    """Birden çok GB sayısı varsa RAM/depolama tahmini yapma."""
    title = normalize(name)
    matches = [storage_gb(match.group()) for match in CAPACITY.finditer(title)]
    matches = [value for value in matches if value is not None]
    if len(matches) == 1:
        return matches[0]
    return None


def matches_model(name: str, brand: str, model: str) -> bool:
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


def phone_category(value: str) -> bool:
    category = normalize(value)
    if any(word in category for word in ("aksesuar", "kilif", "sarj", "kapak")):
        return False
    return any(
        word in category for word in ("cep telefon", "mobile phone", "smartphone")
    )


def attribute(attributes: list, *names: str) -> str | None:
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
