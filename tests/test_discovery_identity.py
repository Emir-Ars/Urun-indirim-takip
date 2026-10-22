"""Keşif hedefi ve keşifle scraper'ın ortak kimlik kuralları."""

import pytest

from app.contracts import DiscoveryConfig, DiscoveryTarget
from app.discovery.matching import phone_category
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.http import FetchError
from app.scraper.parsing import (
    excluded_term,
    identify,
    matches_model,
    network_type,
    storage_gb,
    title_storage,
    verify_identity,
    verify_model_network,
)
from app.settings import Runtime
from tests.support.discovery import fixture


def test_discovery_target_requires_model_instead_of_manual_urls():
    with pytest.raises(ValueError):
        DiscoveryTarget(
            key="apple_iphone_15",
            brand="Apple",
            model="iPhone 15",
            seed_urls={"trendyol": ["https://www.trendyol.com/example-p-1"]},
        )


def test_exact_model_and_storage():
    assert matches_model("iPhone 16 128 GB Siyah", "iPhone 16")
    for wrong in (
        "iPhone 16e 128 GB",
        "iPhone 16 Pro 128 GB",
        "iPhone 16+ 128 GB",
        "iPhone 16 uyumlu kılıf",
        "iPhone 16 yenilenmiş 128 GB",
    ):
        assert not matches_model(wrong, "iPhone 16")
    assert storage_gb("1 TB") == 1024
    # "RAM" etiketli değer hafıza sayılmaz; canlı örnek: Galaxy S25 128 GB.
    assert title_storage("iPhone 16 8 GB RAM 256 GB") == 256
    assert title_storage("Samsung Galaxy S25 128 GB 12 GB Ram (Türkiye)") == 128
    assert title_storage("Redmi Note 14 Pro 12GB+512GB Siyah") is None  # etiketsiz
    assert matches_model("Samsung Galaxy S24 8 GB RAM 256 GB", "Galaxy S24")
    assert not matches_model("Samsung Galaxy S24 Ultra 256 GB", "Galaxy S24")


def test_variant_words_separate_models():
    # Katalog hedeflerindeki kardeş modeller birbirine karışmamalı.
    for title, model in (
        ("Samsung Galaxy S25 Edge 256 GB", "Galaxy S25"),
        ("Apple iPhone 17 Air 256 GB", "iPhone 17"),
        ("Samsung Galaxy S24 FE 128 GB", "Galaxy S24"),
        ("Samsung Galaxy S24+ 256 GB", "Galaxy S24"),
        ("Samsung Galaxy S24 Ultra 256 GB", "Galaxy S24"),
        ("Xiaomi Redmi Note 14 Pro+ 5G 512 GB", "Redmi Note 14 Pro 5G"),
        ("Xiaomi Redmi Note 14 Pro 5G 256 GB", "Redmi Note 14 Pro 4G"),
        ("Xiaomi 14T 512 GB", "14T Pro"),
        ("Xiaomi 14T Pro 512 GB", "14T"),
    ):
        assert not matches_model(title, model), (title, model)
    for title, model in (
        ("Samsung Galaxy S25 Edge 256 GB", "Galaxy S25 Edge"),
        ("Apple iPhone Air 256 GB", "iPhone Air"),
        ("Samsung Galaxy S24FE 128 GB", "Galaxy S24 FE"),
        ("Xiaomi Redmi Note 14 Pro 5G 256 GB", "Redmi Note 14 Pro 5G"),
        ("Xiaomi Redmi Note 13 Pro 4G 256 GB", "Redmi Note 13 Pro 4G"),
        ("Xiaomi 14T Pro 12 GB 512 GB", "14T Pro"),
        ("Xiaomi POCO X6 Pro 5G 256 GB", "POCO X6 Pro"),
    ):
        assert matches_model(title, model), (title, model)


def test_underscore_separated_titles():
    # Canlı Trendyol adı: "_" regex'te harf sayıldığı için "Ultra" görülmüyor ve
    # sayfa hem S25 hem S25 Ultra hedefine giriyordu (catalog_conflict).
    title = "Galaxy S25 Ultra_12GB_256GB Gri"
    assert not matches_model(title, "Galaxy S25")
    assert matches_model(title, "Galaxy S25 Ultra")
    assert identify([title], "Galaxy S25 Ultra", 256) == 256
    assert not matches_model("Galaxy S25 Kılıf_Şeffaf", "Galaxy S25")


def test_identity_rules_shared_by_discovery_and_scraper():
    # Canlı Hepsiburada adları: kapasite başlıkta yok, yapısal veride var.
    assert identify(["Apple  iPhone 15 128"], "iPhone 15", 128) == 128
    assert (
        identify(["Apple iphone 15 Siyah", "Apple iphone 15 Siyah 128GB"], "iPhone 15")
        == 128
    )
    assert identify(["iPhone 15 Pro Max 1 TB Siyah"], "iPhone 15 Pro Max") == 1024
    assert identify(["Samsung Galaxy S24 8 GB RAM 256 GB"], "Galaxy S24", 256) == 256
    for names, model, capacity in (
        (["Apple iPhone 15 256 GB"], "iPhone 15", 128),  # kaynaklar çelişiyor
        (["Apple iPhone 15 Mavi"], "iPhone 15", None),  # kapasite yok
        (["Apple iPhone 13 mini 128 GB"], "iPhone 13", None),
        (["Samsung Galaxy S24+ 256 GB"], "Galaxy S24", None),
        (["Samsung Galaxy S24 FE 128 GB"], "Galaxy S24", None),
        (["Apple iPhone 15 128 GB Yenilenmiş"], "iPhone 15", 128),
    ):
        with pytest.raises(FetchError) as error:
            identify(names, model, capacity)
        assert error.value.code == "identity"
        assert names[0] in str(error.value)
    with pytest.raises(FetchError):
        verify_identity(["Apple iPhone 15 128 GB"], "iPhone 15", 256)


@pytest.mark.parametrize("word", ["Kılıfı", "Adaptörü", "Kapağı"])
def test_inflected_accessories_do_not_match_phone_model(word):
    assert not matches_model(f"Apple iPhone 16 128 GB {word}", "iPhone 16")


@pytest.mark.parametrize("word", ["Kılıfı", "Adaptörü", "Kapağı"])
@pytest.mark.parametrize("capacity_source", ["title", "structured"])
def test_identify_rejects_inflected_accessories_with_valid_capacity(
    word, capacity_source
):
    storage = "128 GB " if capacity_source == "title" else ""
    capacity = 128 if capacity_source == "structured" else None
    with pytest.raises(FetchError) as error:
        identify([f"Apple iPhone 16 {storage}{word}"], "iPhone 16", capacity)
    assert error.value.code == "identity"


@pytest.mark.parametrize("word", ["Kılıfı", "Adaptörü", "Kapağı"])
@pytest.mark.parametrize("capacity_source", ["title", "structured"])
def test_verify_identity_rejects_inflected_accessories_with_valid_capacity(
    word, capacity_source
):
    storage = "128 GB " if capacity_source == "title" else ""
    capacity = 128 if capacity_source == "structured" else None
    with pytest.raises(FetchError) as error:
        verify_identity(
            [f"Apple iPhone 16 {storage}{word}"], "iPhone 16", 128, capacity
        )
    assert error.value.code == "identity"


@pytest.mark.parametrize("word", ["Kılıfı", "Adaptörü", "Kapağı"])
def test_inflected_accessory_in_another_name_rejects_phone_identity(word):
    names = ["Apple iPhone 16 128 GB", f"Telefon {word}"]
    with pytest.raises(FetchError) as discovery_error:
        identify(names, "iPhone 16")
    with pytest.raises(FetchError) as scraper_error:
        verify_identity(names, "iPhone 16", 128)
    assert discovery_error.value.code == scraper_error.value.code == "identity"


@pytest.mark.parametrize(
    "sample",
    fixture("phone_identity_examples.json"),
    ids=lambda sample: f"{sample['platform']}_{sample['platform_product_id']}",
)
def test_recorded_phone_identity_examples_remain_accepted(sample):
    names = sample["names"]
    model = sample["model"]
    capacity = sample["structured_capacity"]
    expected = sample["storage_gb"]
    assert any(matches_model(name, model) for name in names)
    assert identify(names, model, capacity) == expected
    verify_identity(names, model, expected, capacity)


def test_target_exclude_terms_split_same_named_phones():
    # Canlı veri: Redmi Note 14 (4G) ile Note 14 5G farklı telefonlardır.
    note_4g = ["Redmi Note 14 8+256 Mavi(Xiaomi Türkiye Garantili)"]
    note_5g = ["Redmi Note 14 5G 8GB+256GB Siyah"]
    assert identify(note_4g, "Redmi Note 14", 256, exclude=["5G"]) == 256
    with pytest.raises(FetchError) as error:
        identify(note_5g, "Redmi Note 14", 256, exclude=["5G"])
    assert "5G" in str(error.value)
    assert identify(note_5g, "Redmi Note 14 5G", 256) == 256
    with pytest.raises(FetchError):
        identify(["Redmi Note 14 Pro 5G 8GB+256GB"], "Redmi Note 14 5G", 256)
    # "5 GB" bir kapasite ifadesidir; "5G" sanılmaz.
    assert excluded_term(["Telefon 4 GB + 5 GB RAM 128 GB"], ["5G"]) is None
    # Canlı Hepsiburada başlığı: 4G telefon "4.5G Mobil Bağlantı" diye yazılır.
    assert (
        excluded_term(["Redmi Note 14 Pro 256 GB 4.5G Mobil Bağlantı"], ["5G"]) is None
    )
    assert excluded_term(["Redmi Note 14 Pro 5G 512 GB"], ["5G"]) == "5G"

    target = DiscoveryTarget(
        key="xiaomi_redmi_note_14",
        brand="Xiaomi",
        model="Redmi Note 14",
        exclude_terms=["5G"],
    )
    discovery = TrendyolDiscovery(
        target, DiscoveryConfig(targets=[]), Runtime(request_interval_seconds=0)
    )
    card = {
        "name": note_5g[0],
        "brand": "Xiaomi",
        "category": {"name": "Android Cep Telefonu"},
    }
    assert discovery._card_reason(card) == "excluded_term"
    assert discovery._card_reason({**card, "name": note_4g[0]}) is None
    discovery.close()
    with pytest.raises(ValueError):
        DiscoveryTarget(key="x", brand="Xiaomi", model="Redmi", exclude_terms=[""])


def test_network_type_values():
    assert network_type("4G") == "4G"
    assert network_type("4.5G") == "4G"  # Hepsiburada 4G telefonları böyle yazar
    assert network_type("5G") == "5G"
    for value in ("5G+", "5G NR", "4G/5G"):  # 5G desteği söyleyen her değer
        assert network_type(value) == "5G", value
    assert network_type(None) is None and network_type("3G") is None


def test_foreign_version_pages_are_out_of_scope():
    # Canlı örnek: trendyol_991304922, iPhone 16 128 GB karşılaştırmasına giriyordu.
    for title in (
        "iPhone 16 128GB Teal 5G with FaceTime International Version",
        "Xiaomi 14T Pro 512 GB Global Version",
        "Redmi Note 14 Pro 256 GB Yurt Dışı Sürüm",
    ):
        with pytest.raises(FetchError, match="yurt dışı"):
            identify([title], "iPhone 16")  # kapsam kontrolü modelden önce yapılır
    assert identify(["Apple iPhone 16 128 GB Deniz Mavisi"], "iPhone 16") == 128


@pytest.mark.parametrize(
    "category",
    [
        "Cep Telefonu",
        "iPhone IOS Cep Telefonları",
        "Android Cep Telefonu",
        "Smartphone",
        "Mobile Phone",
    ],
)
def test_phone_category_accepts_new_phone_categories(category):
    assert phone_category(category)


@pytest.mark.parametrize(
    "category",
    [
        # Her biri "cep telefon" içerir; hariç tutma listesinin her terimi sınanır.
        "Cep Telefonu Aksesuarları",
        "Cep Telefonu Kılıfı",
        "Cep Telefonu Şarj Aleti",
        "Cep Telefonu Arka Kapak",
        "Yenilenmiş Cep Telefonu",
        "İkinci El Cep Telefonu",
        "Refurbished Mobile Phone",
        # Telefon kategorisi değil.
        "Tablet",
        "",
    ],
)
def test_phone_category_rejects_accessory_used_and_other_categories(category):
    assert not phone_category(category)


@pytest.mark.parametrize("word", ["Kılıfı", "Adaptörü", "Kapağı"])
def test_phone_category_rejects_inflected_accessory_categories(word):
    assert not phone_category(f"Cep Telefonu {word}")


@pytest.mark.parametrize(
    "model", ["Redmi Note 13 Pro", "iPhone 15", "Phone 5GB RAM", "Phone 15G"]
)
def test_network_guard_does_not_infer_network_without_explicit_5g_model(model):
    verify_model_network(model, "4G")
    verify_model_network(model, "5G")


@pytest.mark.parametrize("separator", [" ", "-", "_", "  ", "\t", "\n"])
def test_yenilio_grade_scope_handles_title_separators(separator):
    name = "iPhone 15 Pro 128 GB " + separator.join(
        ["YENİLİO", "OUTLET", "C", "KALİTE"]
    )
    with pytest.raises(FetchError) as error:
        identify([name], "iPhone 15 Pro", 128)
    assert error.value.code == "identity"


@pytest.mark.parametrize(
    "label",
    [
        "Yenilio",
        "Outlet",
        "A Kalite",
        "B Kalite",
        "Yenilio sıfır",
        "YenilioX A Kalite",
        "Yenilio A Kaliteli",
        "Yenilio A KaliteX",
    ],
)
def test_generic_outlet_quality_or_seller_name_preserves_identity(label):
    name = f"iPhone 15 Pro 128 GB {label}"
    assert identify([name], "iPhone 15 Pro", 128) == 128
    verify_identity([name], "iPhone 15 Pro", 128, 128)
