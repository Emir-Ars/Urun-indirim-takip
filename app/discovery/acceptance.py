"""Keşif kabulü: yalnız aynı ürün koduna bağlı, kaydedilebilir kimlik kanıtı."""

import hashlib
import json
import re
from collections import defaultdict
from urllib.parse import urlsplit

from app.contracts import (
    DiscoveryCandidate,
    DiscoveryDecision,
    DiscoveryEvidence,
    DiscoveryFact,
    utc_now,
)
from app.discovery.matching import phone_category
from app.scraper.parsing import (
    EXCLUDED,
    assigned_json,
    embedded_json,
    excluded_term,
    hepsiburada_sku,
    matches_model,
    nested_dicts,
    network_type,
    normalize,
    storage_gb,
    title_storage,
    trendyol_product_id,
)

READERS = {"trendyol": trendyol_product_id, "hepsiburada": hepsiburada_sku}
HOSTS = {"trendyol": "www.trendyol.com", "hepsiburada": "www.hepsiburada.com"}
# Bu iki dildeki aynı renk 6 Ekim kayıtlı iPhone örneğinde birlikte bulunur.
COLOR_ALIASES = {"blue": "mavi"}
GENERIC_COLORS = {"cok renkli", "multicolor", "multi color"}
# Trendyol'da bağlantının rengi renk seçicisindeki addır. Satıcının "Renk"
# özelliği genel ad yazar ("Black" için "Siyah"), yapısal veri bazen kapasite
# ("256 GB"); seçici adı varken bunlar renk karşılaştırmasına girmez. Gerçek
# örnekler: tests/fixtures/discovery/acceptance_examples.json.
TRENDYOL_COLOR_SELECTOR = (
    "variants.products.id.DsmColor",
    "product.slicingAttributes.",
)
# Satışa kapalı 14 Ekim sayfalarında renk yalnız tam ürün başlığında kaldı.
TITLE_COLORS = ("Titan Gri", "Siyah", "Beyaz", "Mor", "Yeşil", "Mavi", "Pembe")
RAM = re.compile(r"(\d+)\s*gb\s*ram\b|\bram\s*(\d+)\s*gb\b")


def color_key(value):
    key = normalize(value).strip()
    return COLOR_ALIASES.get(key, key)


def _heading_color(name):
    text = normalize(name)
    for color in TITLE_COLORS:
        pattern = (
            r"(?<!\w)"
            + re.escape(normalize(color))
            + r"(?:\s+(?:akilli\s+)?cep telefonu)?"
            + r"(?:\s*\([^)]*garant[^)]*\))?\s*$"
        )
        match = re.search(pattern, text)
        if match:
            prefix = text[: match.start()].rstrip(" -")
            if prefix.endswith(")") or re.search(r"\b(?:gb|tb|ram)$", prefix):
                return color
    return None


def _fact(facts, field, value, owner, source):
    if value is not None and str(value).strip():
        facts.append(
            DiscoveryFact(
                field=field,
                value=str(value).strip(),
                owner_id=str(owner),
                source=source,
            )
        )


def _jsonld(soup, expected):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            root = json.loads(script.get_text())
        except (ValueError, TypeError):
            continue
        for node in nested_dicts(root):
            kind = node.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if not {"Product", "ProductGroup"}.intersection(kinds):
                continue
            ids = [
                str(node[k]).upper() for k in ("sku", "productGroupID") if node.get(k)
            ]
            if ids and all(value == expected.upper() for value in ids):
                yield node


def _structured(soup, platform, expected, facts):
    reader = READERS[platform]
    for node in _jsonld(soup, expected):
        for key, field in (("name", "name"), ("color", "color")):
            _fact(facts, field, node.get(key), expected, f"jsonld.{key}")
        brand = node.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        _fact(facts, "brand", brand, expected, "jsonld.brand")
        offers = node.get("offers") or []
        offers = offers if isinstance(offers, list) else [offers]
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            # Bir grubun başka ürüne giden teklifinden ürün durumu alınmaz.
            url = offer.get("url")
            if url and (
                reader(url) != expected.upper()
                or urlsplit(url).hostname != HOSTS[platform]
            ):
                continue
            _fact(
                facts,
                "condition",
                offer.get("itemCondition"),
                expected,
                "jsonld.offers.itemCondition",
            )


def _evidence(soup, html, platform, url, expected, facts):
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):
        actual = READERS[platform](canonical["href"])
        if actual and actual != expected.upper():
            _fact(facts, "source_id", actual, actual, "page.canonical")
    _structured(soup, platform, expected, facts)
    return DiscoveryEvidence(
        platform=platform,
        platform_product_id=expected,
        url=url,
        captured_at=utc_now(),
        html_sha256=hashlib.sha256(html.encode("utf-8")).hexdigest(),
        facts=facts,
    )


def trendyol_evidence(soup, html, url, expected, variant_color=None):
    facts = []
    state = assigned_json(soup, "__envoy__SHARED_PROPS") or {}
    product = state.get("product") or {}
    actual = str(product.get("id", ""))
    if actual:
        _fact(facts, "source_id", actual, actual, "product.id")
    if actual == expected:
        for field, value, source in (
            ("name", product.get("name"), "product.name"),
            ("brand", (product.get("brand") or {}).get("name"), "product.brand"),
            (
                "category",
                (product.get("category") or {}).get("name"),
                "product.category",
            ),
            ("color", variant_color, "variants.products.id.DsmColor"),
        ):
            _fact(facts, field, value, expected, source)
        _fact(
            facts,
            "category",
            (product.get("businessUnitData") or {}).get("name"),
            expected,
            "product.businessUnitData",
        )
        for key, value in (product.get("slicingAttributes") or {}).items():
            field = {"dsmcolor": "color", "internal memory": "storage"}.get(
                normalize(key)
            )
            if field:
                _fact(facts, field, value, expected, f"product.slicingAttributes.{key}")
        fields = {
            "dahili hafiza": "storage",
            "internal memory": "storage",
            "renk": "color",
            "webcolor": "color",
            "mobil baglanti hizi": "network",
            "ram kapasitesi": "ram",
            "ram (system memory)": "ram",
            "garanti tipi": "warranty",
            "warranty type": "warranty",
        }
        for item in product.get("attributes") or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("key") or {}).get("name") or item.get("type") or ""
            field = fields.get(normalize(key)) or fields.get(
                normalize(item.get("type") or "")
            )
            if field:
                _fact(
                    facts,
                    field,
                    (item.get("value") or {}).get("name"),
                    expected,
                    f"product.attributes.{key}",
                )
    return _evidence(soup, html, "trendyol", url, expected, facts)


def _owned_nodes(value, expected):
    if isinstance(value, list):
        for item in value:
            yield from _owned_nodes(item, expected)
    elif isinstance(value, dict):
        if value.get("sku") and str(value["sku"]).upper() != expected:
            return
        yield value
        for key, item in value.items():
            if key not in {"allVariantCombinations", "recommendations", "offers"}:
                yield from _owned_nodes(item, expected)


def hepsiburada_evidence(soup, html, url, expected):
    facts = []
    roots = list(embedded_json(soup))
    details = []
    for root in roots:
        if not isinstance(root, dict):
            continue
        state = root.get("productState") or {}
        own = state.get("product") if isinstance(state, dict) else None
        for node in (root, root.get("product"), own):
            if (
                not isinstance(node, dict)
                or not node.get("definitionName")
                or not node.get("sku")
            ):
                continue
            actual = str(node["sku"]).upper()
            if actual != expected:
                _fact(facts, "source_id", actual, actual, "product.sku")
            elif node not in details:
                details.append(node)
    for detail in details:
        _fact(facts, "source_id", detail["sku"], expected, "product.sku")
        _fact(facts, "brand", detail.get("brand"), expected, "product.brand")
        _fact(
            facts,
            "category",
            detail.get("definitionName"),
            expected,
            "product.definitionName",
        )
        properties = [detail.get("expends", []), detail.get("properties", [])]
        for node in _owned_nodes(properties, expected):
            field = {
                "mobil baglanti hizi": "network",
                "dahili hafiza": "storage",
                "ram kapasitesi": "ram",
                "renk": "color",
            }.get(normalize(str(node.get("name", ""))))
            if field:
                _fact(
                    facts,
                    field,
                    node.get("property"),
                    expected,
                    f"product.properties.{node['name']}",
                )
    if details:
        heading = soup.find("h1")
        if heading:
            name = heading.get_text(" ", strip=True)
            _fact(facts, "name", name, expected, "page.h1")
            _fact(
                facts, "color", _heading_color(name), expected, "page.h1.explicit_color"
            )
    for root in roots:
        for node in nested_dicts(root):
            variants = node.get("allVariantCombinations")
            if not isinstance(variants, list):
                continue
            for variant in variants:
                if (
                    not isinstance(variant, dict)
                    or str(variant.get("sku", "")).upper() != expected
                ):
                    continue
                for key, field in (("Kapasite", "storage"), ("Renk", "color")):
                    _fact(
                        facts, field, variant.get(key), expected, f"variants.sku.{key}"
                    )
    return _evidence(soup, html, "hepsiburada", url, expected, facts)


def decide(evidence, target):
    """Ağsız tekrar hesap; raporun kendi kabul iddiasına güvenmez."""
    fields = defaultdict(list)
    bad, missing = [], []
    platform, expected = evidence.platform, evidence.platform_product_id.upper()
    reader = READERS.get(platform)
    if (
        reader is None
        or reader(evidence.url) != expected
        or urlsplit(evidence.url).hostname != HOSTS.get(platform)
    ):
        bad.append("source_url_mismatch")
    selector_colors = []
    for fact in evidence.facts:
        if fact.owner_id.upper() != expected:
            bad.append("source_id_mismatch")
        else:
            fields[fact.field].append(fact.value)
            if fact.field == "color" and fact.source.startswith(
                TRENDYOL_COLOR_SELECTOR
            ):
                selector_colors.append(fact.value)
    if not fields["source_id"]:
        missing.append("source_identity_missing")
    elif any(value.upper() != expected for value in fields["source_id"]):
        bad.append("source_id_mismatch")
    names = fields["name"]
    if not names:
        missing.append("name_missing")
    elif any(EXCLUDED.search(normalize(name)) for name in names) or excluded_term(
        names, target.exclude_terms
    ):
        bad.append("out_of_scope")
    elif any(not matches_model(name, target.model) for name in names):
        bad.append("model_mismatch")
    for field, predicate in (
        ("brand", lambda v: normalize(v) == normalize(target.brand)),
        ("category", phone_category),
    ):
        if not fields[field]:
            missing.append(f"{field}_missing")
        elif not all(predicate(value) for value in fields[field]):
            bad.append(f"{field}_mismatch")
    capacities = {storage_gb(v) for v in fields["storage"]} | {
        title_storage(n) for n in names
    }
    capacities.discard(None)
    if not capacities:
        missing.append("storage_missing")
    elif len(capacities) > 1:
        bad.append("storage_mismatch")
    colors = [v for v in fields["color"] if color_key(v) not in GENERIC_COLORS]
    if platform == "trendyol":
        named = [v for v in selector_colors if color_key(v) not in GENERIC_COLORS]
        colors = named or [v for v in colors if storage_gb(v) is None]
    if not colors:
        missing.append("color_missing")
    elif len({color_key(v) for v in colors}) > 1:
        bad.append("color_mismatch")
    expected_network = target.network or (
        "5G" if excluded_term([target.model], ["5G"]) else None
    )
    networks = {network_type(v) for v in fields["network"]}
    networks.discard(None)
    title_networks = {
        network_type(v)
        for n in names
        for v in re.findall(r"\b[45](?:[.,]5)?\s*g\b", normalize(n))
    }
    networks.update(title_networks - {None})
    if expected_network:
        if not networks:
            missing.append("network_missing")
        elif networks != {expected_network}:
            bad.append("network_mismatch")
    elif len(networks) > 1:
        bad.append("network_mismatch")
    ram = {storage_gb(v) for v in fields["ram"]}
    ram.update(int(a or b) for n in names for a, b in RAM.findall(normalize(n)))
    ram.discard(None)
    if len(ram) > 1:
        bad.append("ram_mismatch")
    conditions = set(fields["condition"])
    allowed = {"https://schema.org/NewCondition", "http://schema.org/NewCondition"}
    if not conditions:
        missing.append("new_condition_missing")
    elif not conditions.issubset(allowed):
        bad.append("condition_mismatch")
    status = "mismatch" if bad else "insufficient" if missing else "verified"
    candidate = None
    if status == "verified":
        candidate = DiscoveryCandidate(
            target_key=target.key,
            platform=platform,
            platform_product_id=expected,
            url=evidence.url,
            brand=target.brand,
            model=target.model,
            storage_gb=next(iter(capacities)),
            color=colors[0],
            ram_gb=next(iter(ram)) if ram else None,
            warranty_text=fields["warranty"][0] if fields["warranty"] else None,
            warranty_source="product.attributes" if fields["warranty"] else None,
        )
    return DiscoveryDecision(
        target_key=target.key,
        evidence=evidence,
        status=status,
        reasons=sorted(set(bad + missing)),
        candidate=candidate,
    )
