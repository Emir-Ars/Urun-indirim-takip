"""Katalog eşleştirmelerini okuyup Cimri yanıtlarını yalnız yerelde saklar."""

import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from app.contracts import Catalog, Contract, Key, URL, utc_now
from app.market_history.cimri import (
    CIMRI_API_URL,
    CIMRI_HOSTS,
    history_in_kurus,
    verified_page,
)
from app.scraper.http import FetchError, PageClient
from app.settings import Runtime


class MappingEntry(Contract):
    product_key: Key
    url: URL
    cimri_product_id: str = Field(pattern=r"^[1-9][0-9]*$")

    @field_validator("url")
    @classmethod
    def cimri_url(cls, value):
        parts = urlsplit(value)
        if parts.hostname not in CIMRI_HOSTS or not parts.path.startswith(
            "/cep-telefonlari/"
        ):
            raise ValueError("Eşleştirme adresi Cimri telefon sayfası olmalı")
        return value


class Mapping(Contract):
    version: Literal[1]
    source: Literal["cimri"]
    entries: list[MappingEntry]

    @model_validator(mode="after")
    def unique_entries(self):
        for field in ("product_key", "url", "cimri_product_id"):
            values = [getattr(entry, field) for entry in self.entries]
            if len(values) != len(set(values)):
                raise ValueError(f"Eşleştirmede tekrarlanan {field} var")
        return self


def read_mapping(path: Path, catalog: Catalog) -> Mapping:
    mapping = Mapping.model_validate_json(path.read_text(encoding="utf-8-sig"))
    keys = {product.product_key for product in catalog.products if product.active}
    if any(entry.product_key not in keys for entry in mapping.entries):
        raise ValueError("Eşleştirmede etkin katalog dışında ürün var")
    return mapping


def _save_response(directory: Path, name: str, content: str) -> dict:
    body = content.encode("utf-8")
    path = directory / "responses" / name
    with path.open("xb") as output:
        output.write(body)
    return {
        "file": path.relative_to(directory).as_posix(),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def _save_report(directory: Path, report: dict) -> None:
    body = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    temporary = directory / "report.json.tmp"
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(directory / "report.json")


def capture(
    catalog: Catalog,
    mapping: Mapping,
    output_dir: Path,
    runtime: Runtime,
    product_keys: list[str] | None = None,
    *,
    client_class=None,
) -> dict:
    products = {p.product_key: p for p in catalog.products if p.active}
    entries = {entry.product_key: entry for entry in mapping.entries}
    if set(entries) - set(products):
        raise ValueError("Eşleştirmede etkin katalog dışında ürün var")
    selected = product_keys if product_keys is not None else list(products)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Ürün seçimi boş veya tekrarlı")
    if set(selected) - set(products):
        raise ValueError("Seçilen ürün etkin katalogda bulunamadı")
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "responses").mkdir()
    report = {
        "version": 1,
        "source": "cimri",
        "started_at_utc": utc_now().isoformat(),
        "finished_at_utc": None,
        "result": "running",
        "catalog_product_count": len(products),
        "unmapped_catalog_product_keys": sorted(set(products) - set(entries)),
        "products": [
            {
                "product": products[key].model_dump(mode="json"),
                "mapping": entries[key].model_dump() if key in entries else None,
                "status": "not_attempted" if key in entries else "unmapped",
                "request_count": 0,
            }
            for key in selected
        ],
    }
    _save_report(output_dir, report)
    client_class = client_class or PageClient
    stopped = None
    try:
        for record in report["products"]:
            if record["status"] == "unmapped":
                continue
            if stopped:
                record["reason"] = stopped
                continue
            key = record["product"]["product_key"]
            entry = entries[key]
            client = client_class(CIMRI_HOSTS, runtime, request_budget=4)
            try:
                record["page_started_at_utc"] = utc_now().isoformat()
                html = client.get(entry.url)
                record["page"] = _save_response(output_dir, f"{key}.html", html)
                identity, table = verified_page(
                    html, products[key], entry.cimri_product_id
                )
                record["identity"] = identity
                response = client.post_json(
                    CIMRI_API_URL,
                    {
                        "queryName": "priceHistoryV2Query",
                        "variables": {"productId": identity["product_id"]},
                        "platform": "CIMRI_DESKTOP_V2",
                    },
                    headers={"Referer": entry.url},
                )
                record["captured_at_utc"] = utc_now().isoformat()
                record["api"] = _save_response(
                    output_dir,
                    f"{key}.json",
                    json.dumps(response, ensure_ascii=False, indent=2),
                )
                record["history"] = history_in_kurus(
                    response,
                    identity["product_id"],
                    table,
                    first_offer_price=identity["first_offer_price"],
                    page_started_at_utc=record["page_started_at_utc"],
                    captured_at_utc=record["captured_at_utc"],
                )
                record["status"] = "captured"
            except FetchError as exc:
                record["status"] = "error"
                record["error"] = {"code": exc.code, "detail": str(exc)}
                if exc.code == "blocked":
                    stopped = "blocked"
            except KeyboardInterrupt:
                record["status"] = "interrupted"
                raise
            finally:
                record["request_count"] = client.request_count
                client.close()
            _save_report(output_dir, report)
    except KeyboardInterrupt:
        report["result"] = "interrupted"
        for record in report["products"]:
            if record["status"] == "not_attempted":
                record["reason"] = "interrupted"
        raise
    except Exception as exc:
        report["result"] = "failed"
        report["error"] = {"type": type(exc).__name__, "detail": str(exc)}
        if record["status"] == "not_attempted":
            record["status"] = "error"
            record["error"] = {
                "code": "storage" if isinstance(exc, OSError) else "unexpected",
                "detail": str(exc),
            }
        raise
    else:
        report["result"] = (
            "completed"
            if all(record["status"] == "captured" for record in report["products"])
            else "partial"
        )
    finally:
        report["finished_at_utc"] = utc_now().isoformat()
        _save_report(output_dir, report)
    return report
