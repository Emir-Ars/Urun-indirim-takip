"""Hepsiburada arama ve ürün sayfası varyant adaptörü."""

import re
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.contracts import DiscoveryCandidate, DiscoveryResult
from app.discovery.base import BaseDiscovery
from app.discovery.matching import (
    matches_model,
    phone_category,
    storage_gb,
    title_storage,
)
from app.scraper.http import FetchError
from app.scraper.parsing import embedded_json, nested_dicts, normalize, product_jsonld

HOME = "https://www.hepsiburada.com/"
SEARCH_API = "https://blackgate.hepsiburada.com/moriaapi/api/product"
SKU_PATTERN = re.compile(r"-p-(HBCV[A-Z0-9]+)(?:[/?]|$)", re.IGNORECASE)


class Discovery(BaseDiscovery):
    platform = "hepsiburada"
    hosts = ["www.hepsiburada.com", "blackgate.hepsiburada.com"]

    @staticmethod
    def _cards(soup):
        cards = {}
        for anchor in soup.select("a[href][title]"):
            relative = anchor["href"].split("?", 1)[0]
            match = SKU_PATTERN.search(relative)
            if match:
                cards[match.group(1).upper()] = urljoin(HOME, relative)
        return cards

    def _search(self):
        query = f"{self.target.brand} {self.target.model}"
        search_url = HOME + "ara?" + urlencode({"q": query})
        soup = BeautifulSoup(self.get(search_url), "html.parser")
        self.search_pages += 1
        model_links = [
            urljoin(HOME, anchor["href"])
            for anchor in soup.select("a[href]")
            if normalize(anchor.get_text(" ", strip=True))
            == normalize(self.target.model)
            and "-xc-" in anchor["href"]
            and urlsplit(urljoin(HOME, anchor["href"])).hostname
            == "www.hepsiburada.com"
        ]
        if model_links:
            soup = BeautifulSoup(self.get(model_links[0]), "html.parser")
            self.search_pages += 1
        else:
            self.issue("model_filter_missing", "Model filtresi bulunamadı")
        cards = self._cards(soup)
        total = None
        for root in embedded_json(soup):
            for node in nested_dicts(root):
                value = node.get("totalProductCount")
                if isinstance(value, int) and value > 0:
                    total = value
                    break
            if total is not None:
                break
        if total is not None and len(cards) < total:
            self.issue("html_partial", f"HTML: {len(cards)} / {total}")
        try:
            self._api(query, cards)
        except FetchError as exc:
            self.issue("search_api", exc.code)
        return cards

    def _api(self, query, cards):
        seen_ids = set()
        for page_no in range(1, self.config.max_search_pages + 1):
            params = {"page": page_no, "pageType": "Search", "q": query, "size": 36}
            data = self.get_json(
                SEARCH_API + "?" + urlencode(params),
                headers={"Accept": "application/json", "Referer": HOME + "ara"},
            )
            if (
                not isinstance(data.get("products"), list)
                or data.get("currentPage") != page_no
            ):
                raise FetchError("parse", "Hepsiburada arama sayfası geçersiz")
            self.search_pages += 1
            fresh = 0
            for product in data["products"]:
                if not isinstance(product, dict):
                    continue
                if normalize(product.get("brand", "")) != normalize(self.target.brand):
                    continue
                category = (product.get("mainCategory") or {}).get("name", "")
                if not phone_category(category):
                    continue
                for variant in product.get("variantList") or []:
                    if not matches_model(
                        variant.get("name", ""), self.target.brand, self.target.model
                    ):
                        continue
                    sku = str(variant.get("sku", "")).upper()
                    url = variant.get("url", "")
                    if sku in seen_ids:
                        continue
                    seen_ids.add(sku)
                    fresh += 1
                    if SKU_PATTERN.search(url):
                        cards[sku] = urljoin(HOME, url.split("?", 1)[0])
                    elif url:
                        self.issue("group_url_pending", sku)
            if data["products"] and not fresh and page_no > 1:
                self.issue("repeated_page", str(page_no))
                return
            last_page = data.get("lastPage")
            if isinstance(last_page, int) and page_no >= last_page:
                return
            if not data["products"]:
                return
        self.issue("search_limit", "Arama sayfası sınırı doldu")

    def _product(self, url, expected_sku):
        self.product_pages += 1
        soup = BeautifulSoup(self.get(url), "html.parser")
        product_nodes = product_jsonld(soup)
        names = [str(p.get("name")) for p in product_nodes if p.get("name")]
        if not names and soup.find("h1"):
            names = [soup.find("h1").get_text(" ", strip=True)]
        details = []
        variants = []
        for root in embedded_json(soup):
            for node in nested_dicts(root):
                if str(node.get("sku", "")).upper() == expected_sku and node.get(
                    "definitionName"
                ):
                    details.append(node)
                if (
                    isinstance(node.get("allVariantCombinations"), list)
                    and node["allVariantCombinations"]
                ):
                    variants = node["allVariantCombinations"]
        detail = next(
            (item for item in details if phone_category(item["definitionName"])),
            None,
        )
        if detail is None or normalize(str(detail.get("brand", ""))) != normalize(
            self.target.brand
        ):
            raise FetchError("identity", "Hepsiburada telefon/marka doğrulanamadı")
        if not any(
            matches_model(name, self.target.brand, self.target.model) for name in names
        ):
            raise FetchError("identity", "Hepsiburada model adı uyuşmuyor")
        selected = next(
            (item for item in variants if item.get("sku", "").upper() == expected_sku),
            None,
        )
        if selected is None:
            raise FetchError("identity", "Hepsiburada SKU seçeneklerde bulunamadı")
        capacity = storage_gb(selected.get("Kapasite", ""))
        if capacity is None:
            capacity = title_storage(names[0], self.target.model)
        if capacity is None:
            raise FetchError("identity", "Depolama kapasitesi doğrulanamadı")
        canonical = soup.select_one('link[rel="canonical"][href]')
        if canonical is not None:
            canonical_url = canonical["href"]
            if (
                SKU_PATTERN.search(canonical_url)
                and expected_sku in canonical_url.upper()
            ):
                url = canonical_url
        candidate = DiscoveryCandidate(
            target_key=self.target.key,
            platform=self.platform,
            platform_product_id=expected_sku,
            url=url,
            brand=self.target.brand,
            model=self.target.model,
            storage_gb=capacity,
            color=str(selected.get("Renk", "")),
        )
        return candidate, variants

    def discover(self):
        found = {}
        queue = {}
        try:
            queue.update(self._search())
        except FetchError as exc:
            self.issue("search_fetch", exc.code)
        seen = set()
        while queue:
            if self.product_pages >= self.config.max_product_pages:
                self.issue("product_limit", "Ürün sayfası sınırı doldu")
                break
            sku, url = queue.popitem()
            if sku in seen:
                continue
            seen.add(sku)
            try:
                candidate, variants = self._product(url, sku)
                found[sku] = candidate
                for item in variants:
                    other_sku = str(item.get("sku", "")).upper()
                    slug = item.get("urlName", "")
                    if (
                        other_sku.startswith("HBCV")
                        and re.fullmatch(r"[a-z0-9-]+", slug)
                        and other_sku not in seen
                    ):
                        queue.setdefault(
                            other_sku, urljoin(HOME, f"{slug}-p-{other_sku}")
                        )
            except (FetchError, ValueError, TypeError, KeyError) as exc:
                self.issue("candidate_rejected", f"{sku}: {exc}")
        return DiscoveryResult(
            platform=self.platform,
            target_key=self.target.key,
            candidates=list(found.values()),
            issues=self.issues,
            complete=not self.issues,
            search_pages=self.search_pages,
            product_pages=self.product_pages,
        )
