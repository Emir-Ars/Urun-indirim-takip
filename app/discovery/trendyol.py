"""Trendyol aramasından ürün gruplarını ve doğrulanmış seçenekleri bulur."""

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.contracts import DiscoveryCandidate, DiscoveryResult
from app.discovery.base import BaseDiscovery
from app.discovery.matching import (
    attribute,
    matches_model,
    phone_category,
    storage_gb,
    title_storage,
)
from app.scraper.http import FetchError
from app.scraper.parsing import assigned_json, normalize

HOME = "https://www.trendyol.com/"
SEARCH = "https://apigw.trendyol.com/discovery-sfint-search-service/api/search/products"
VARIANTS = (
    "https://apigw.trendyol.com/discovery-storefront-trproductgw-service/"
    "api/slicing-attributes/product-group/{group}/slicing-attributes"
)
PRODUCT_ID = re.compile(r"-p-(\d+)(?:[/?]|$)")


class Discovery(BaseDiscovery):
    platform = "trendyol"
    hosts = ["www.trendyol.com", "apigw.trendyol.com"]

    def _search(self):
        query = f"{self.target.brand} {self.target.model}"
        search_params = {"q": query, "qt": query, "st": query, "os": "1"}
        referer = HOME + "sr?" + urlencode(search_params)
        self.get(HOME)
        self.get(referer)
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
                    if group.get("filterKey") != "LeafCategory":
                        continue
                    for item in group.get("values", []):
                        if phone_category(item.get("text", "")):
                            category = str(item["id"])
                            break
                    if category:
                        break
            except FetchError as exc:
                self.issue("filter_unavailable", exc.code)
        if not brand or not category:
            self.issue(
                "filter_unavailable", "Marka/telefon kategori filtresi bulunamadı"
            )
        else:
            params.update(wb=brand, lc=category)
            referer = (
                HOME + "sr?" + urlencode(search_params | {"wb": brand, "lc": category})
            )
            self.get(referer)
            headers["Referer"] = referer
            first = self.get_json(SEARCH + "?" + urlencode(params), headers=headers)
        return first, headers

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
            for item in products:
                if not isinstance(item, dict) or not matches_model(
                    item.get("name", ""), self.target.brand, self.target.model
                ):
                    continue
                if normalize(item.get("brand", "")) != normalize(self.target.brand):
                    continue
                if not phone_category((item.get("category") or {}).get("name", "")):
                    continue
                group = item.get("groupId")
                if group and item.get("id"):
                    groups.setdefault(str(group), str(item["id"]))
                relative_url = item.get("url", "").split("?", 1)[0]
                if item.get("id") and PRODUCT_ID.search(relative_url):
                    cards[str(item["id"])] = urljoin(HOME, relative_url)
            next_url = (page.get("_links") or {}).get("next")
            if not products or not next_url:
                total = page.get("total")
                if isinstance(total, int) and len(seen_ids) != total:
                    self.issue("count_mismatch", f"{len(seen_ids)} / {total}")
                    return groups, cards, False
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
            seen_urls.add(next_url)
            page = self.get_json(next_url, headers=headers)
        self.issue("search_limit", "Arama sayfası sınırı doldu")
        return groups, cards, False

    def _candidate(self, url, expected_id):
        self.product_pages += 1
        html = self.get(url)
        state = assigned_json(
            BeautifulSoup(html, "html.parser"), "__envoy__SHARED_PROPS"
        )
        product = (state or {}).get("product")
        if not isinstance(product, dict) or str(product.get("id")) != expected_id:
            raise FetchError("identity", "Trendyol ürün kimliği uyuşmuyor")
        brand = (product.get("brand") or {}).get("name", "")
        name = product.get("name", "")
        category = (product.get("businessUnitData") or {}).get("name", "")
        if not category:
            category = (product.get("category") or {}).get("name", "")
        if (
            normalize(brand) != normalize(self.target.brand)
            or not matches_model(name, brand, self.target.model)
            or not phone_category(category)
        ):
            raise FetchError("identity", "Trendyol telefon/model doğrulanamadı")
        attrs = product.get("attributes") or []
        capacity = storage_gb(
            attribute(attrs, "Dahili Hafıza", "Internal Memory") or ""
        )
        if capacity is None:
            capacity = storage_gb(
                (product.get("slicingAttributes") or {}).get("Internal Memory", "")
            )
        if capacity is None:
            capacity = title_storage(name, self.target.model)
        if capacity is None:
            raise FetchError("identity", "Depolama kapasitesi doğrulanamadı")
        color = attribute(attrs, "Renk", "WebColor") or ""
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
        try:
            groups, cards, complete = self._search_candidates()
            choices.update(cards)
            for group, seed in groups.items():
                if self.product_pages >= self.config.max_product_pages:
                    self.issue("product_limit", "Ürün sayfası sınırı doldu")
                    complete = False
                    break
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
                    if not any(
                        item.get("id")
                        for axis in response.get("result", [])
                        for value in axis.get("values", [])
                        for item in value.get("products", [])
                        if isinstance(item, dict)
                    ):
                        self.issue("missing_variants", group)
                        complete = False
                except FetchError as exc:
                    self.issue("variant_fetch", f"{group}: {exc.code}")
                    complete = False
        except FetchError as exc:
            self.issue("search_fetch", exc.code)
            complete = False
        for product_id, url in choices.items():
            if product_id in found:
                continue
            if self.product_pages >= self.config.max_product_pages:
                self.issue("product_limit", "Ürün sayfası sınırı doldu")
                break
            try:
                found[product_id] = self._candidate(url, product_id)
            except (FetchError, ValueError, KeyError, TypeError) as exc:
                self.issue("candidate_rejected", f"{product_id}: {exc}")
        return DiscoveryResult(
            platform=self.platform,
            target_key=self.target.key,
            candidates=list(found.values()),
            issues=self.issues,
            complete=complete and not self.issues,
            search_pages=self.search_pages,
            product_pages=self.product_pages,
        )
