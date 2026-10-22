"""Cimri alımı ve aktarımı testlerinin kayıtlı örnekleri ve sahte istemcisi."""

import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

from app.contracts import Catalog
from app.market_history.capture import Mapping, MappingEntry
from app.market_history.cimri import CIMRI_HOSTS

ROOT = Path(__file__).parents[2]
RECORDED = json.loads(
    (ROOT / "tests/fixtures/cimri_recorded_samples.json").read_text(encoding="utf-8")
)
CATALOG = Catalog.model_validate_json(
    (ROOT / "config/catalog.json").read_text(encoding="utf-8-sig")
)
PRODUCTS = {product.product_key: product for product in CATALOG.products}
SAMPLES = RECORDED["samples"]
FRONTEND_SAMPLES = RECORDED["frontend_history"]["samples"]
MAPPING = Mapping(
    version=1,
    source="cimri",
    entries=[
        MappingEntry(
            product_key=sample["product_key"],
            url=sample["url"],
            cimri_product_id=sample["cimri_product_id"],
        )
        for sample in SAMPLES
    ],
)


def source_pair(sample=SAMPLES[0]):
    """Kaydedilmiş başlık/fiyatla sentetik zarf; tam API yanıtı olduğu iddia edilmez."""
    product = PRODUCTS[sample["product_key"]]
    metadata = {
        "id": sample["cimri_product_id"],
        "title": sample["headings"][0],
        "brand": {"name": product.brand},
        "category": {"slug": "cep-telefonlari"},
    }
    if product.brand == "Xiaomi":
        metadata = deepcopy(RECORDED["xiaomi_product"])
    last = date.fromisoformat(sample["last_day"])
    page = {
        "product": metadata,
        "priceHistoryTablePrices": [
            {
                "date": (last - timedelta(days=index)).strftime("%d/%m/%Y"),
                "minPrice": price,
            }
            for index, price in enumerate(sample["latest_three_prices_tl"])
        ],
    }
    response = {
        "data": {
            "priceHistoryV2": {
                "productId": sample["cimri_product_id"],
                "lastDay": sample["last_day"],
                "prices": list(sample["latest_three_prices_tl"]),
            }
        }
    }
    return page, response


def page_html(page, heading=None):
    data = {"props": {"pageProps": {"data": page}}}
    name = heading if heading is not None else page["product"].get("title", "")
    return (
        f"<h1>{name}</h1><script id='__OCTOPUS_DATA__'>"
        f"{json.dumps(data, ensure_ascii=False)}</script>"
    )


def small_catalog(keys=None):
    keys = keys or [sample["product_key"] for sample in SAMPLES]
    return Catalog(platforms=[], products=[PRODUCTS[key] for key in keys], listings=[])


def fake_clients(*pairs):
    pending = list(pairs)
    created = []

    class Client:
        def __init__(self, hosts, runtime, request_budget):
            assert hosts == CIMRI_HOSTS
            assert request_budget == 4
            self.pair = pending.pop(0)
            self.request_count = 0
            self.calls = []
            self.closed = False
            created.append(self)

        def get(self, url):
            self.request_count += 1
            self.calls.append(("GET", url))
            if isinstance(self.pair[0], BaseException):
                raise self.pair[0]
            return self.pair[0]

        def post_json(self, url, payload, *, headers):
            self.request_count += 1
            self.calls.append(("POST", url, payload, headers))
            if isinstance(self.pair[1], BaseException):
                raise self.pair[1]
            return self.pair[1]

        def close(self):
            self.closed = True

    return Client, created


def good_pair(sample=SAMPLES[0]):
    page, response = source_pair(sample)
    return page_html(page), response
