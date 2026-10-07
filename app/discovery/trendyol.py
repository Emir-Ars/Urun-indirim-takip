"""Trendyol aramasından ürün gruplarını ve doğrulanmış seçenekleri bulur."""

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.contracts import DiscoveryCandidate, DiscoveryResult
from app.discovery.base import RECOVERABLE, BaseDiscovery, error_code
from app.discovery.matching import phone_category
from app.scraper.http import FetchError
from app.scraper.parsing import (
    EXCLUDED,
    assigned_json,
    attribute,
    excluded_term,
    identify,
    matches_model,
    normalize,
    storage_gb,
    trendyol_product_id,
)
from app.scraper.trendyol_scraper import product_capacity

HOME = "https://www.trendyol.com/"
SEARCH = "https://apigw.trendyol.com/discovery-sfint-search-service/api/search/products"
VARIANTS = (
    "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/"
    "api/slicing-attributes/product-group/{group}/slicing-attributes"
)


def _axes(response: dict) -> list[dict]:
    """Varyant yanıtını tanılama için eksen → değer → ürün kimliği biçiminde özetler."""
    return [
        {
            "type": axis.get("type"),
            "values": [
                {
                    "name": value.get("name"),
                    "ids": [
                        str(item.get("id"))
                        for item in value.get("products", [])
                        if isinstance(item, dict)
                    ],
                }
                for value in axis.get("values", [])
            ],
        }
        for axis in response.get("result", [])
    ]


class Discovery(BaseDiscovery):
    platform = "trendyol"
    hosts = ["www.trendyol.com", "apigw.trendyol.com"]

    def _search(self):
        query = f"{self.target.brand} {self.target.model}"
        # Parametreler sitenin kendi arama isteğindeki değerlerdir; hangilerinin
        # zorunlu olduğu ölçülmedi. Anlamlı ayar değildir, olduğu gibi gönderilir.
        search_params = {"q": query, "qt": query, "st": query, "os": "1"}
        referer = HOME + "sr?" + urlencode(search_params)
        # HTML arama sayfası (/sr) açılmaz: içeriği kullanılmıyor ve canlıda
        # HTTP 403 ile engelleniyordu. API'ye yalnız Referer olarak gönderilir.
        self.get(HOME)
        params = {
            **search_params,
            "pathModel": "sr",
            "pi": "1",
            "initialSearchText": query,
            "tyPlusStripViewEnabled": "true",
            "channelId": "1",
        }
        headers = {"Accept": "application/json", "Referer": referer}
        first = self.get_json(SEARCH + "?" + urlencode(params), headers=headers)
        if not isinstance(first.get("products"), list):
            raise FetchError("parse", "Trendyol arama ürünleri eksik")
        brand = next(
            (
                str(item["key"])
                for item in (first.get("canonicalFilters") or {}).get("brands", [])
                if normalize(item.get("name", "")) == normalize(self.target.brand)
            ),
            None,
        )
        category = None
        aggregation_url = (first.get("_links") or {}).get("aggregation")
        if aggregation_url:
            try:
                aggregations = self.get_json(aggregation_url, headers=headers)
                for group in aggregations.get("aggregation", []):
                    values = group.get("values", [])
                    if group.get("filterKey") == "WebBrand" and brand is None:
                        # Bazı aramalarda canonicalFilters boş gelir; marka buradadır.
                        brand = next(
                            (
                                str(item["id"])
                                for item in values
                                if normalize(str(item.get("text", "")))
                                == normalize(self.target.brand)
                            ),
                            None,
                        )
                    if group.get("filterKey") != "LeafCategory" or category:
                        continue
                    phones = [
                        item for item in values if phone_category(item.get("text", ""))
                    ]
                    self.note(
                        "leaf_categories",
                        total=len(values),
                        phone=[
                            {key: item.get(key) for key in ("id", "text", "count")}
                            for item in phones
                        ],
                    )
                    if not phones:
                        continue
                    category = str(phones[0]["id"])
                    if len(phones) > 1:
                        # Arama tek kategoriyle filtrelenir; diğerleri taranmamıştır.
                        self.issue(
                            "category_partial",
                            "Yalnız ilk telefon kategorisi tarandı: "
                            + ", ".join(str(item.get("text")) for item in phones),
                        )
            except RECOVERABLE as exc:
                self.issue("filter_unavailable", error_code(exc))
        if not category:
            # Kategori filtresi olmadan arama aksesuarlarla dolar; kısmi raporlanır.
            # Filtre isteği zaten hata verdiyse o uyarı (hata kodu ve mesajıyla)
            # nedeni söylüyor; aynı uyarı ikinci kez yazılmaz.
            if not any(item.reason == "filter_unavailable" for item in self.issues):
                self.issue("filter_unavailable", "Telefon kategori filtresi bulunamadı")
        else:
            # Marka yoksa yalnız kategori uygulanır; marka kartta ayrıca denetlenir.
            filters = ({"wb": brand} if brand else {}) | {"lc": category}
            params.update(filters)
            referer = HOME + "sr?" + urlencode(search_params | filters)
            headers["Referer"] = referer
            first = self.get_json(SEARCH + "?" + urlencode(params), headers=headers)
        self.note(
            "search_filter", brand=brand, category=category, total=first.get("total")
        )
        return first, headers

    def _card_reason(self, item) -> str | None:
        """Arama kartının neden aday sayılmadığını döndürür; uygunsa None."""
        name = item.get("name", "")
        if EXCLUDED.search(normalize(name)):
            return "excluded_word"
        if not matches_model(name, self.target.model):
            return "other_model"
        if excluded_term([name], self.target.exclude_terms):
            return "excluded_term"
        if normalize(item.get("brand", "")) != normalize(self.target.brand):
            return "brand"
        if not phone_category((item.get("category") or {}).get("name", "")):
            return "category"
        return None

    def _search_candidates(self):
        page, headers = self._search()
        groups = {}
        cards = {}
        seen_urls = set()
        seen_ids = set()
        for number in range(self.config.max_search_pages):
            products = page.get("products")
            if not isinstance(products, list):
                raise FetchError(
                    "parse", "Trendyol arama sayfası ürün listesi içermiyor"
                )
            self.search_pages += 1
            new_ids = {
                item["id"]
                for item in products
                if isinstance(item, dict) and item.get("id")
            } - seen_ids
            if products and not new_ids:
                self.issue("repeated_page", f"Sayfa {page.get('pageIndex')}")
                return groups, cards, False
            seen_ids.update(new_ids)
            if number == 0 and products and isinstance(products[0], dict):
                self.note("search_card_fields", keys=sorted(products[0]))
            for item in products:
                if not isinstance(item, dict):
                    continue
                reason = self._card_reason(item)
                self.note(
                    "search_card",
                    page=self.search_pages,
                    id=item.get("id"),
                    name=item.get("name"),
                    brand=item.get("brand"),
                    category=(item.get("category") or {}).get("name"),
                    group=item.get("groupId"),
                    decision=reason or "accepted",
                )
                if reason:
                    continue
                group = item.get("groupId")
                if group and item.get("id"):
                    groups.setdefault(str(group), str(item["id"]))
                relative_url = item.get("url", "").split("?", 1)[0]
                if item.get("id") and trendyol_product_id(relative_url) is not None:
                    cards[str(item["id"])] = urljoin(HOME, relative_url)
            next_url = (page.get("_links") or {}).get("next")
            if not products or not next_url:
                total = page.get("total")
                if isinstance(total, int) and len(seen_ids) != total:
                    self.issue("count_mismatch", f"{len(seen_ids)} / {total}")
                    return groups, cards, False
                # Sayfalama sorunsuz bitti; yine de _search'te yazılan
                # category_partial / filter_unavailable uyarısı aramayı kısmi sayar.
                return groups, cards, not self.issues
            parts = urlsplit(next_url)
            query = dict(parse_qsl(parts.query))
            if page.get("offsetParameters"):
                query["offsetParameters"] = page["offsetParameters"]
            next_url = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urlencode(query), "")
            )
            if parts.hostname != "apigw.trendyol.com" or next_url in seen_urls:
                self.issue(
                    "repeated_page", "Sonraki arama bağlantısı geçersiz/tekrarlı"
                )
                return groups, cards, False
            if number + 1 >= self.config.max_search_pages:
                # Sınır doldu ama sonraki sayfa var: işlenmeyecek sayfa istenmez.
                break
            seen_urls.add(next_url)
            page = self.get_json(next_url, headers=headers)
        self.issue("search_limit", "Arama sayfası sınırı doldu")
        return groups, cards, False

    def _candidate(self, url, expected_id, variant_color=None):
        self.product_pages += 1
        if trendyol_product_id(url) != expected_id:
            raise FetchError("identity", "Trendyol adres kimliği kaynakla uyuşmuyor")
        html = self.get(url)
        state = assigned_json(
            BeautifulSoup(html, "html.parser"), "__envoy__SHARED_PROPS"
        )
        product = (state or {}).get("product")
        # HTTP izinli alan adlarında yönlendirmeyi izleyebilir; açılan sayfanın
        # kendi kimliği de kaynakla eşleşmelidir.
        if not isinstance(product, dict) or str(product.get("id")) != expected_id:
            raise FetchError("identity", "Trendyol ürün kimliği uyuşmuyor")
        brand = (product.get("brand") or {}).get("name", "")
        name = product.get("name", "")
        category = (product.get("businessUnitData") or {}).get("name", "")
        if not category:
            category = (product.get("category") or {}).get("name", "")
        self.note(
            "product_page",
            id=expected_id,
            name=name,
            brand=brand,
            category=category,
            in_stock=product.get("inStock"),
        )
        if normalize(brand) != normalize(self.target.brand) or not phone_category(
            category
        ):
            raise FetchError(
                "identity", f"Trendyol telefon/marka doğrulanamadı: {name[:160]}"
            )
        capacity = identify(
            [name],
            self.target.model,
            product_capacity(product),
            exclude=self.target.exclude_terms,
        )
        attrs = product.get("attributes") or []
        if self.target.network:
            self.verify_network(attribute(attrs, "Mobil Bağlantı Hızı"), [name])
        # Renk, sayfanın renk seçicisindeki addır (varyant listesi, ör. "Abis").
        # Satıcının "Renk" özelliği ("Çok Renkli" gibi) yalnız bu ad yoksa kullanılır.
        color = variant_color or attribute(attrs, "Renk", "WebColor") or ""
        ram = storage_gb(
            attribute(attrs, "RAM Kapasitesi", "Ram (System Memory)") or ""
        )
        warranty = attribute(attrs, "Garanti Tipi", "Warranty Type")
        return DiscoveryCandidate(
            target_key=self.target.key,
            platform=self.platform,
            platform_product_id=expected_id,
            url=url,
            brand=self.target.brand,
            model=self.target.model,
            storage_gb=capacity,
            color=color,
            ram_gb=ram,
            warranty_text=warranty,
            warranty_source="product.attributes" if warranty else None,
        )

    def discover(self):
        found = {}
        complete = False
        choices = {}
        colors = {}
        cards = {}
        try:
            groups, cards, complete = self._search_candidates()
            choices.update(cards)
            for group, seed in groups.items():
                endpoint = (
                    VARIANTS.format(group=group)
                    + "?"
                    + urlencode({"contentId": seed, "channelId": 1})
                )
                try:
                    response = self.get_json(endpoint)
                    if (
                        response.get("isSuccess") is not True
                        or response.get("statusCode") != 200
                    ):
                        raise FetchError("parse", "Trendyol seçenek yanıtı başarısız")
                    self.note("variants", group=group, seed=seed, axes=_axes(response))
                    for axis in response.get("result", []):
                        for value in axis.get("values", []):
                            for item in value.get("products", []):
                                if (
                                    isinstance(item, dict)
                                    and item.get("id")
                                    and item.get("pageUrl")
                                ):
                                    choices[str(item["id"])] = urljoin(
                                        HOME, item["pageUrl"]
                                    )
                                    if axis.get("type") == "DsmColor" and value.get(
                                        "name"
                                    ):
                                        colors[str(item["id"])] = str(value["name"])
                    if not any(
                        item.get("id")
                        for axis in response.get("result", [])
                        for value in axis.get("values", [])
                        for item in value.get("products", [])
                        if isinstance(item, dict)
                    ):
                        self.issue("missing_variants", group)
                        complete = False
                except RECOVERABLE as exc:
                    self.issue("variant_fetch", f"{group}: {error_code(exc)}")
                    complete = False
        except RECOVERABLE as exc:
            self.issue("search_fetch", error_code(exc))
            complete = False
        self.note(
            "choices",
            from_search=sorted(cards),
            from_variants=sorted(set(choices) - set(cards)),
        )
        for product_id, url in choices.items():
            if self.product_pages >= self.config.max_product_pages:
                self.issue("product_limit", "Ürün sayfası sınırı doldu")
                break
            try:
                found[product_id] = self._candidate(
                    url, product_id, colors.get(product_id)
                )
            except RECOVERABLE as exc:
                self.issue("candidate_rejected", f"{product_id}: {exc}")
        return DiscoveryResult(
            platform=self.platform,
            target_key=self.target.key,
            candidates=list(found.values()),
            issues=self.issues,
            # complete yalnız arama aşamasını kapsar; varyant, ürün sınırı ve
            # candidate_rejected gibi sonradan eklenen uyarılar da taramayı kısmi
            # sayar.
            complete=complete and not self.issues,
            search_pages=self.search_pages,
            product_pages=self.product_pages,
        )
