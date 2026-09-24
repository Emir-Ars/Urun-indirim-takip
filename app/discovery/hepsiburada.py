"""Hepsiburada arama ve ürün sayfası varyant adaptörü."""

import re
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup

from app.contracts import DiscoveryCandidate, DiscoveryResult
from app.discovery.base import RECOVERABLE, BaseDiscovery, error_code
from app.discovery.matching import phone_category
from app.scraper.hepsiburada_scraper import product_names, variant_capacity
from app.scraper.http import FetchError
from app.scraper.parsing import (
    embedded_json,
    excluded_term,
    identify,
    matches_model,
    nested_dicts,
    normalize,
)

HOME = "https://www.hepsiburada.com/"
SEARCH_API = "https://blackgate.hepsiburada.com/moriaapi/api/product"
SKU_PATTERN = re.compile(r"-p-(HBCV[A-Z0-9]+)(?:[/?]|$)", re.IGNORECASE)
# Grup (-pm-) sayfası aday değildir; yalnız gerçek varyant SKU'larına çözülür.
GROUP_PATTERN = re.compile(r"-pm-(HBC[A-Z0-9]+)(?:[/?]|$)", re.IGNORECASE)


def _card_id(href: str) -> str | None:
    """Kart bağlantısındaki ürün SKU'su veya grup kimliği."""
    match = SKU_PATTERN.search(href) or GROUP_PATTERN.search(href)
    return match.group(1).upper() if match else None


def _variants(soup) -> list:
    """Sayfanın varyant listesi (allVariantCombinations)."""
    variants = []
    for root in embedded_json(soup):
        for node in nested_dicts(root):
            if (
                isinstance(node.get("allVariantCombinations"), list)
                and node["allVariantCombinations"]
            ):
                variants = node["allVariantCombinations"]
    return variants


class Discovery(BaseDiscovery):
    platform = "hepsiburada"
    hosts = ["www.hepsiburada.com", "blackgate.hepsiburada.com"]

    @staticmethod
    def _cards(soup):
        cards = {}
        for anchor in soup.select("a[href][title]"):
            relative = anchor["href"].split("?", 1)[0]
            card_id = _card_id(relative)
            if card_id:
                cards[card_id] = urljoin(HOME, relative)
        return cards

    @staticmethod
    def _card_titles(soup):
        """Tanılama için kart kimliği → görünen başlık."""
        titles = {}
        for anchor in soup.select("a[href][title]"):
            card_id = _card_id(anchor["href"].split("?", 1)[0])
            if card_id:
                titles.setdefault(card_id, anchor["title"])
        return titles

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
        self.note(
            "html_cards",
            model_filters=model_links,
            total=total,
            cards=self._card_titles(soup),
        )
        if total is not None and len(cards) < total:
            self.issue("html_partial", f"HTML: {len(cards)} / {total}")
        try:
            self._api(query, cards)
        except RECOVERABLE as exc:
            # API engellense veya bozuk dönse de HTML'den bulunan kartlar korunur.
            self.issue("search_api", error_code(exc))
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
                    name = variant.get("name", "")
                    if not matches_model(name, self.target.model) or excluded_term(
                        [name], self.target.exclude_terms
                    ):
                        continue
                    sku = str(variant.get("sku", "")).upper()
                    url = variant.get("url", "")
                    if sku in seen_ids:
                        continue
                    seen_ids.add(sku)
                    fresh += 1
                    relative = url.split("?", 1)[0]
                    if SKU_PATTERN.search(relative):
                        cards[sku] = urljoin(HOME, relative)
                    elif GROUP_PATTERN.search(relative):
                        cards[_card_id(relative)] = urljoin(HOME, relative)
                    elif url:
                        self.issue("group_url_pending", sku)
            self.note(
                "api_page", page=page_no, products=len(data["products"]), fresh=fresh
            )
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
        names = product_names(soup, expected_sku)
        details = [
            node
            for root in embedded_json(soup)
            for node in nested_dicts(root)
            if str(node.get("sku", "")).upper() == expected_sku
            and node.get("definitionName")
        ]
        variants = _variants(soup)
        self.note(
            "product_page",
            sku=expected_sku,
            names=names,
            definitions=[item.get("definitionName") for item in details],
            variants=len(variants),
        )
        detail = next(
            (item for item in details if phone_category(item["definitionName"])),
            None,
        )
        if detail is None or normalize(str(detail.get("brand", ""))) != normalize(
            self.target.brand
        ):
            raise FetchError(
                "identity",
                f"Hepsiburada telefon/marka doğrulanamadı: {' | '.join(names)[:160]}",
            )
        selected = next(
            (
                item
                for item in variants
                if isinstance(item, dict)
                and str(item.get("sku") or "").upper() == expected_sku
            ),
            None,
        )
        if selected is None:
            raise FetchError("identity", "Hepsiburada SKU seçeneklerde bulunamadı")
        capacity = identify(
            names,
            self.target.model,
            variant_capacity(soup, expected_sku),
            exclude=self.target.exclude_terms,
        )
        canonical = soup.select_one('link[rel="canonical"][href]')
        if canonical is not None:
            canonical_url = canonical["href"]
            if (
                # Yalnız https://www.hepsiburada.com adresi kabul edilir; başka alan
                # adı katalog doğrulamasını ve bütün çalışmayı bozardı.
                canonical_url.startswith(HOME)
                and SKU_PATTERN.search(canonical_url)
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
            color=str(selected.get("Renk") or ""),
        )
        return candidate, variants

    def _group(self, url):
        """-pm- grup sayfasındaki varyantları döndürür; kendisi aday olmaz."""
        self.product_pages += 1
        variants = _variants(BeautifulSoup(self.get(url), "html.parser"))
        self.note(
            "group_page",
            url=url,
            variants=[item.get("sku") for item in variants if isinstance(item, dict)],
        )
        if not variants:
            raise FetchError("identity", "Hepsiburada grup sayfası varyant içermiyor")
        return variants

    @staticmethod
    def _enqueue(variants, queue, seen) -> list[str]:
        """Varyant SKU'larını ürün sayfası bağlantısıyla kuyruğa ekler."""
        queued = []
        for item in variants:
            if not isinstance(item, dict):
                continue
            other_sku = str(item.get("sku", "")).upper()
            slug = item.get("urlName") or ""
            if (
                other_sku.startswith("HBCV")
                and re.fullmatch(r"[a-z0-9-]+", slug)
                and other_sku not in seen
                and other_sku not in queue
            ):
                queued.append(other_sku)
                queue[other_sku] = urljoin(HOME, f"{slug}-p-{other_sku}")
        return queued

    def discover(self):
        found = {}
        queue = {}
        try:
            queue.update(self._search())
        except RECOVERABLE as exc:
            self.issue("search_fetch", error_code(exc))
        seen = set()
        while queue:
            if self.product_pages >= self.config.max_product_pages:
                self.issue("product_limit", "Ürün sayfası sınırı doldu")
                break
            key, url = queue.popitem()
            seen.add(key)
            try:
                if GROUP_PATTERN.search(url):
                    variants = self._group(url)
                else:
                    candidate, variants = self._product(url, key)
                    found[key] = candidate
                queued = self._enqueue(variants, queue, seen)
                self.note("variant_queue", sku=key, added=queued)
            except RECOVERABLE as exc:
                # Tek sayfanın beklenmeyen yapısı bütün taramayı durdurmaz; raporlanır.
                self.issue("candidate_rejected", f"{key}: {exc}")
        return DiscoveryResult(
            platform=self.platform,
            target_key=self.target.key,
            candidates=list(found.values()),
            issues=self.issues,
            complete=not self.issues,
            search_pages=self.search_pages,
            product_pages=self.product_pages,
        )
