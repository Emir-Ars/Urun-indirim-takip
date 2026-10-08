"""Alım dosyalarını değiştirmeden, kaydedilmiş kaynaklardan yeniden doğrular."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path, PureWindowsPath
from typing import Literal

from pydantic import Field, ValidationError

from app.contracts import Catalog, Contract, Product
from app.market_history.capture import MappingEntry
from app.market_history.cimri import history_in_kurus, verified_page
from app.scraper.http import FetchError

IDENTITY_FIELDS = ("product_id", "product_key", "brand", "model", "storage_gb")


class HistoryImportError(ValueError):
    """Girdi veya kimlik güvenle aktarılamıyor; komut durmalıdır."""


class _Record(Contract):
    product: Product
    mapping: MappingEntry | None
    status: Literal["captured", "error", "unmapped", "not_attempted", "interrupted"]
    request_count: int = Field(ge=0, le=4)
    page_started_at_utc: str | None = None
    captured_at_utc: str | None = None
    page: dict | None = None
    api: dict | None = None
    identity: dict | None = None
    history: dict | None = None
    error: dict | None = None
    reason: str | None = None


class _Report(Contract):
    version: Literal[1]
    source: Literal["cimri"]
    started_at_utc: str
    finished_at_utc: str
    result: Literal["completed", "partial", "interrupted", "failed"]
    catalog_product_count: int = Field(ge=1)
    unmapped_catalog_product_keys: list[str]
    products: list[_Record] = Field(min_length=1)
    error: dict | None = None


@dataclass(frozen=True)
class HistoryPoint:
    day: date
    price_kurus: int | None


@dataclass(frozen=True)
class CapturedProduct:
    product: Product
    mapping: MappingEntry
    captured_at: datetime
    points: tuple[HistoryPoint, ...]
    page_sha256: str
    api_sha256: str
    report_sha256: str
    summary: dict
    uncompared_days: tuple[date, ...]


@dataclass(frozen=True)
class ImportBatch:
    products: tuple[Product, ...]
    verified: tuple[CapturedProduct, ...]
    skipped: tuple[tuple[str, str], ...]
    report_sha256: str


def product_identity(product: Product) -> tuple:
    return tuple(getattr(product, field) for field in IDENTITY_FIELDS)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON alanı tekrarlanıyor: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Geçersiz JSON sayısı: {value}")


def _json(body: bytes):
    return json.loads(
        body.decode("utf-8-sig"),
        object_pairs_hook=_unique_object,
        parse_constant=_invalid_constant,
    )


def _utc(value) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Alım zamanı eksik")
    instant = datetime.fromisoformat(value)
    if instant.utcoffset() != timedelta():
        raise ValueError("Alım zamanı UTC olmalı")
    return instant


def _response(directory: Path, reference: dict | None) -> tuple[bytes, str]:
    if not isinstance(reference, dict) or set(reference) != {"file", "sha256"}:
        raise ValueError("Kaynak dosyası bilgisi eksik veya geçersiz")
    name, digest = reference["file"], reference["sha256"]
    if not isinstance(name, str) or not name:
        raise ValueError("Kaynak dosyası yolu geçersiz")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Kaynak dosyası parmak izi geçersiz")
    relative = Path(name)
    path = (directory / relative).resolve()
    if (
        relative.is_absolute()
        or PureWindowsPath(name).anchor
        or not path.is_relative_to(directory)
    ):
        raise ValueError("Kaynak dosyası alım klasörü dışında")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Kaynak dosyası parmak izi uyuşmuyor")
    return body, digest


def _same_json(left, right) -> bool:
    # Python'da True == 1; rapordaki fiyat veya sayaç türü değişimi gizlenmemeli.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(
        right, sort_keys=True, allow_nan=False
    )


def _verify_record(directory, record, report, digest) -> CapturedProduct:
    start = _utc(record.page_started_at_utc)
    end = _utc(record.captured_at_utc)
    if not _utc(report.started_at_utc) <= start <= end <= _utc(report.finished_at_utc):
        raise ValueError("Ürün alım zamanları rapor aralığında ve sıralı olmalı")
    page, page_hash = _response(directory, record.page)
    api, api_hash = _response(directory, record.api)
    identity, table = verified_page(
        page.decode("utf-8"), record.product, record.mapping.cimri_product_id
    )
    history = history_in_kurus(
        _json(api),
        record.mapping.cimri_product_id,
        table,
        first_offer_price=identity["first_offer_price"],
        page_started_at_utc=record.page_started_at_utc,
        captured_at_utc=record.captured_at_utc,
    )
    if not _same_json(identity, record.identity) or not _same_json(
        history, record.history
    ):
        raise ValueError("Yeniden doğrulanan kimlik/geçmiş alım raporuyla uyuşmuyor")
    points = tuple(
        HistoryPoint(date.fromisoformat(point["day"]), point["price_kurus"])
        for point in history["points"]
    )
    if any(p.price_kurus is not None and p.price_kurus >= 2**63 for p in points):
        raise ValueError("Fiyat veritabanının bigint sınırını aşıyor")
    table_days = {datetime.strptime(row["date"], "%d/%m/%Y").date() for row in table}
    return CapturedProduct(
        record.product,
        record.mapping,
        end,
        points,
        page_hash,
        api_hash,
        digest,
        history["summary"],
        tuple(point.day for point in points if point.day not in table_days),
    )


def read_capture(directory: Path, catalog: Catalog) -> ImportBatch:
    directory = directory.resolve()
    report_path = (directory / "report.json").resolve()
    if not report_path.is_relative_to(directory):
        raise HistoryImportError("Alım raporu alım klasörü dışında")
    body = report_path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    try:
        raw = _json(body)
        if not isinstance(raw, dict) or type(raw.get("version")) is not int:
            raise ValueError("Rapor sürümü geçersiz")
        report = _Report.model_validate(raw)
        if _utc(report.started_at_utc) > _utc(report.finished_at_utc):
            raise ValueError("Rapor zamanları sıralı değil")
        if len(report.products) > report.catalog_product_count:
            raise ValueError("Raporun ürün sayısı katalog sayısını aşıyor")
        if report.result == "completed" and any(
            record.status != "captured" for record in report.products
        ):
            raise ValueError("Tamamlandı raporunda başarısız ürün var")
    except (ValueError, TypeError) as exc:
        raise HistoryImportError(
            "Alım raporu geçersiz veya sonlandırılmamış; güncel alım raporu gerekli"
        ) from exc

    current = {product.product_key: product for product in catalog.products}
    seen_ids, seen_keys, seen_sources, seen_urls = set(), set(), set(), set()
    for record in report.products:
        product, mapping = record.product, record.mapping
        for value, seen in (
            (product.product_id, seen_ids),
            (product.product_key, seen_keys),
        ):
            if value in seen:
                raise HistoryImportError("Raporda tekrarlanan ürün kimliği var")
            seen.add(value)
        if product.product_key not in current or product_identity(
            current[product.product_key]
        ) != product_identity(product):
            raise HistoryImportError(
                f"{product.product_key}: rapor ile katalog ürün kimliği uyuşmuyor"
            )
        if mapping is None:
            if record.status != "unmapped":
                raise HistoryImportError("Raporda ürün eşleştirmesi eksik")
            continue
        if mapping.product_key != product.product_key or record.status == "unmapped":
            raise HistoryImportError("Raporda ürün eşleştirmesi tutarsız")
        for value, seen in (
            (mapping.cimri_product_id, seen_sources),
            (mapping.url, seen_urls),
        ):
            if value in seen:
                raise HistoryImportError("Raporda tekrarlanan Cimri eşleştirmesi var")
            seen.add(value)

    verified, skipped = [], []
    for record in report.products:
        key = record.product.product_key
        if record.status != "captured":
            reason = (
                (record.error or {}).get("detail") or record.reason or record.status
            )
            skipped.append((key, f"Alımda kaydedilmedi: {reason}"))
            continue
        try:
            verified.append(_verify_record(directory, record, report, digest))
        except (OSError, ValueError, FetchError, ValidationError) as exc:
            skipped.append((key, f"Kaynak doğrulanamadı: {exc}"))
    return ImportBatch(
        tuple(record.product for record in report.products),
        tuple(verified),
        tuple(skipped),
        digest,
    )
