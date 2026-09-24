"""Keşfe özgü kategori kuralı; model ve kapasite kuralları scraper ile ortaktır.

Model/kapasite kimliği `app.scraper.parsing` içindedir ki keşfin kabul ettiği
sayfayı scraper aynı kuralla doğrulasın.
"""

from app.scraper.parsing import normalize

NOT_NEW_PHONE = (
    "aksesuar",
    "kilif",
    "sarj",
    "kapak",
    "yenilenmis",
    "ikinci el",
    "refurbished",
)


def phone_category(value: str) -> bool:
    """Yeni telefon kategorisi mi; aksesuar ve yenilenmiş kategoriler hariç."""
    category = normalize(value)
    if any(word in category for word in NOT_NEW_PHONE):
        return False
    return any(
        word in category for word in ("cep telefon", "mobile phone", "smartphone")
    )
