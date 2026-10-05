"""Pydantic sözleşmelerinin kuralları ve fiyat ayrıştırma (parsing.money).

Hata mesajı değil, hatanın türü ve konumu denetlenir: mesaj metni değişebilir,
hangi alanın hangi kuralla reddedildiği değişmemeli. Model düzeyindeki kurallar
(model_validator) konumsuz tek bir "value_error" verir; her vaka geçerli bir
temelden tek bir değişiklikle kurulduğu için hangi kuralın çalıştığı bellidir.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.contracts import Catalog, PriceObservation, Product
from app.scraper.parsing import money

URL = "https://www.trendyol.com/apple/iphone-15-128-gb-p-1"
NOW = datetime(2026, 9, 29, 7, 0, tzinfo=timezone.utc)
MODEL_RULE = [("value_error", ())]


def errors(excinfo):
    return [(error["type"], error["loc"]) for error in excinfo.value.errors()]


# --- PriceObservation ----------------------------------------------------------


def observation(**fields):
    values = {
        "listing_id": "trendyol_1",
        "product_id": 1,
        "platform": "trendyol",
        "product_name": "Apple iPhone 15 128 GB",
        "product_url": URL,
        "current_price": 5_724_900,
        "seller_name": "Satıcı A",
        "stock_status": "Stokta Var",
        "timestamp": NOW,
        **fields,
    }
    return PriceObservation(**values)


@pytest.mark.parametrize("stock", ["Stokta Var", "Kritik Stok"])
def test_purchasable_observation_is_valid(stock):
    item = observation(
        stock_status=stock,
        original_price=6_000_000,
        seller_rating=9.4,
        seller_rating_scale=10.0,
    )
    assert item.current_price == 5_724_900
    assert item.currency == "TRY"


def test_sold_out_without_price_or_seller_is_valid():
    # Trendyol/Hepsiburada stoksuz sayfası böyle bir gözlem üretir.
    item = observation(stock_status="Tükendi", current_price=None, seller_name=None)
    assert item.current_price is None
    assert item.seller_name is None


@pytest.mark.parametrize("stock", ["Stokta Var", "Kritik Stok"])
@pytest.mark.parametrize(
    "missing",
    [{"current_price": None}, {"seller_name": None}, {"seller_name": ""}],
)
def test_purchasable_offer_needs_price_and_seller(stock, missing):
    with pytest.raises(ValidationError) as excinfo:
        observation(stock_status=stock, **missing)
    assert errors(excinfo) == MODEL_RULE


@pytest.mark.parametrize(
    "original",
    [5_724_900, 5_000_000],
    ids=["guncel-fiyata-esit", "guncel-fiyattan-kucuk"],
)
def test_struck_price_must_exceed_current_price(original):
    with pytest.raises(ValidationError) as excinfo:
        observation(original_price=original)
    assert errors(excinfo) == MODEL_RULE
    # Bir kuruş büyük olması yeter.
    assert observation(original_price=5_724_901).original_price == 5_724_901


def test_struck_price_needs_a_current_price():
    # Fiyatı olmayan (Tükendi) gözlemde üstü çizili fiyat da olamaz.
    with pytest.raises(ValidationError) as excinfo:
        observation(
            stock_status="Tükendi",
            current_price=None,
            seller_name=None,
            original_price=6_000_000,
        )
    assert errors(excinfo) == MODEL_RULE


def test_seller_rating_cannot_exceed_scale():
    with pytest.raises(ValidationError) as excinfo:
        observation(seller_rating=5.5, seller_rating_scale=5.0)
    assert errors(excinfo) == MODEL_RULE
    # Ölçeğe eşit puan ve ölçeği bilinmeyen puan geçerlidir.
    assert observation(seller_rating=5.0, seller_rating_scale=5.0).seller_rating == 5
    assert observation(seller_rating=4.8).seller_rating_scale is None


@pytest.mark.parametrize(
    "fields, expected",
    [
        # Hatalı veri içeri giremez: fiyat alanına "Tükendi" yazılamaz.
        ({"current_price": "Tükendi"}, ("int_type", ("current_price",))),
        ({"current_price": "5724900"}, ("int_type", ("current_price",))),
        ({"current_price": 0}, ("greater_than", ("current_price",))),
        ({"original_price": -1}, ("greater_than", ("original_price",))),
        ({"seller_rating": -0.5}, ("greater_than_equal", ("seller_rating",))),
        ({"seller_rating_scale": 0.0}, ("greater_than", ("seller_rating_scale",))),
        ({"stock_status": "Stokta"}, ("literal_error", ("stock_status",))),
        ({"currency": "USD"}, ("literal_error", ("currency",))),
        ({"timestamp": datetime(2026, 9, 29)}, ("timezone_aware", ("timestamp",))),
        (
            {"product_url": "http://www.trendyol.com/x"},
            ("value_error", ("product_url",)),
        ),
        ({"platform": "Trendyol"}, ("string_pattern_mismatch", ("platform",))),
        ({"seller": "Satıcı A"}, ("extra_forbidden", ("seller",))),
    ],
)
def test_observation_field_rules(fields, expected):
    with pytest.raises(ValidationError) as excinfo:
        observation(**fields)
    assert errors(excinfo) == [expected]


# --- Product ---------------------------------------------------------------------


def product(**fields):
    values = {
        "product_id": 1,
        "product_key": "apple_iphone_15_128gb",
        "brand": "Apple",
        "model": "iPhone 15",
        "storage_gb": 128,
        **fields,
    }
    return Product(**values)


def test_product_id_fits_32_bit_integer():
    assert product(product_id=2**31 - 1).product_id == 2**31 - 1
    with pytest.raises(ValidationError) as excinfo:
        product(product_id=2**31)
    assert errors(excinfo) == [("less_than", ("product_id",))]
    with pytest.raises(ValidationError) as excinfo:
        product(product_id=0)
    assert errors(excinfo) == [("greater_than", ("product_id",))]


# --- Catalog ---------------------------------------------------------------------


def catalog_data():
    return {
        "platforms": [
            {"key": "trendyol", "name": "Trendyol", "hosts": ["www.trendyol.com"]},
            {
                "key": "hepsiburada",
                "name": "Hepsiburada",
                "hosts": ["www.hepsiburada.com"],
            },
        ],
        "products": [
            {
                "product_id": 1,
                "product_key": "apple_iphone_15_128gb",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 128,
            },
            {
                "product_id": 2,
                "product_key": "apple_iphone_15_256gb",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 256,
            },
        ],
        "listings": [
            {
                "listing_id": "trendyol_1",
                "product_id": 1,
                "platform": "trendyol",
                "url": "https://www.trendyol.com/apple/iphone-15-p-1",
                "color": "Siyah",
            },
            {
                "listing_id": "hepsiburada_hbcv1",
                "product_id": 2,
                "platform": "hepsiburada",
                "url": "https://www.hepsiburada.com/iphone-15-p-HBCV1",
            },
        ],
    }


def load(data):
    # Uygulama kataloğu JSON'dan okur (catalog_sync, discovery.service).
    return Catalog.model_validate_json(json.dumps(data))


def test_valid_catalog_loads():
    catalog = load(catalog_data())
    assert [p.product_id for p in catalog.products] == [1, 2]
    assert len(catalog.listings) == 2


def duplicate_platform(data):
    data["platforms"].append(dict(data["platforms"][0], name="Başka"))


def duplicate_product_id(data):
    data["products"][1]["product_id"] = 1


def duplicate_product_key(data):
    data["products"][1]["product_key"] = "apple_iphone_15_128gb"


def duplicate_variant(data):
    # Marka/model büyük-küçük harf farkıyla aynı ürün sayılır.
    data["products"][1].update(brand="APPLE", model="iphone 15", storage_gb=128)


def duplicate_listing_id(data):
    data["listings"][1]["listing_id"] = "trendyol_1"


def duplicate_listing_url(data):
    data["listings"].append(
        dict(data["listings"][0], listing_id="trendyol_2", product_id=2)
    )


def unknown_product(data):
    data["listings"][0]["product_id"] = 99


def unknown_platform(data):
    data["listings"][0]["platform"] = "akakce"


def foreign_host(data):
    # Trendyol bağlantısı Hepsiburada alan adında olamaz.
    data["listings"][0]["url"] = "https://www.hepsiburada.com/iphone-15-p-HBCV2"


@pytest.mark.parametrize(
    "change",
    [
        duplicate_platform,
        duplicate_product_id,
        duplicate_product_key,
        duplicate_variant,
        duplicate_listing_id,
        duplicate_listing_url,
        unknown_product,
        unknown_platform,
        foreign_host,
    ],
)
def test_catalog_reference_rules(change):
    data = catalog_data()
    change(data)
    with pytest.raises(ValidationError) as excinfo:
        load(data)
    assert errors(excinfo) == MODEL_RULE


@pytest.mark.parametrize(
    "host",
    [
        "WWW.trendyol.com",
        "www.trendyol.com/",
        "www.trendyol.com:443",
        "localhost",
        "127.0.0.1",
        "kullanici@www.trendyol.com",
    ],
)
def test_platform_hosts_must_be_plain_domain_names(host):
    data = catalog_data()
    data["platforms"][0]["hosts"] = [host]
    with pytest.raises(ValidationError) as excinfo:
        load(data)
    assert errors(excinfo) == [("value_error", ("platforms", 0, "hosts"))]


@pytest.mark.parametrize(
    "url",
    [
        "http://www.trendyol.com/x-p-1",
        "https://kullanici:sifre@www.trendyol.com/x-p-1",
        "https://www.trendyol.com:8443/x-p-1",
        "https://www.trendyol.com/x-p-1#yorumlar",
    ],
)
def test_listing_url_must_be_public_https(url):
    data = catalog_data()
    data["listings"][0]["url"] = url
    with pytest.raises(ValidationError) as excinfo:
        load(data)
    assert errors(excinfo) == [("value_error", ("listings", 0, "url"))]


# --- parsing.money ---------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("57249.01", 5_724_901),
        (57249, 5_724_900),
        (57249.01, 5_724_901),
        (Decimal("57249.01"), 5_724_901),
        ("0.01", 1),
        ("12.5", 1_250),
        (" 1 TL ", 100),
        ("₺1234", 123_400),
        ("1234\xa0TL", 123_400),
        ("TRY 10", 1_000),
        # Decimal bilimsel gösterimi kabul eder; kaynaklar böyle göndermez,
        # bugünkü davranış bilerek sabitlenir (money docstring'i).
        ("1e3", 100_000),
    ],
)
def test_money_converts_to_kurus(value, expected):
    assert money(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        0,
        -1,
        "0",
        "-5.00",
        "12.345",  # ikiden fazla ondalık
        "0.001",
        "57.249",  # Türkçe binlik ayırıcı yanlış tutar olarak okunmaz
        "57.249,01",
        "₺1.234,50",
        "NaN",
        "Infinity",
        float("inf"),
        "",
        "fiyat yok",
    ],
)
def test_money_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        money(value)
