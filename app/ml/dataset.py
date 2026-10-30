"""ML veri görüntüsünün sözleşmesi ve dosyası.

Görüntü, veritabanının tek tutarlı okumasıdır; etiket ve deney adımları aynı
dosyadan çalışır, böylece aynı veri aynı sonucu verir. Dosya içeriğin SHA-256
parmak iziyle yazılır; okurken parmak izi ve kayıtlar arası bağlar yeniden
denetlenir.
"""

import hashlib
import json
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    Field,
    ValidationError,
    model_validator,
)

from app.contracts import Contract, Key, Product

FORMAT_VERSION = 1
FILE_NAME = "snapshot.json"


def _utc(value: datetime) -> datetime:
    # Aynı an farklı saat diliminde farklı yazılır; aynı veri aynı baytları versin.
    if value.utcoffset() != timedelta(0):
        raise ValueError("Zaman UTC olmalı")
    return value


UtcDatetime = Annotated[AwareDatetime, AfterValidator(_utc)]
PositiveInt = Annotated[int, Field(gt=0)]


class SnapshotError(Exception):
    """Görüntü dosyası okunamadı, değiştirilmiş veya içeriği tutarsız."""


class PlatformRow(Contract):
    key: Key
    active: bool


class ListingRow(Contract):
    listing_id: str = Field(min_length=1)
    product_id: PositiveInt
    platform: Key
    active: bool


class RunRow(Contract):
    run_id: PositiveInt
    trigger: Literal["scheduled", "manual"]
    # Süren tur varken görüntü alınmaz; her turun bitişi vardır.
    status: Literal["completed", "interrupted"]
    started_at: UtcDatetime
    finished_at: UtcDatetime
    planned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def _finished_after_start(self):
        if self.finished_at < self.started_at:
            raise ValueError(f"Tur {self.run_id}: bitiş başlangıçtan önce")
        return self


class CheckRow(Contract):
    run_id: PositiveInt
    listing_id: str = Field(min_length=1)
    product_id: PositiveInt
    checked_at: UtcDatetime | None
    outcome: Literal["offer", "sold_out", "error"] | None
    current_price: PositiveInt | None

    @model_validator(mode="after")
    def _consistent_outcome(self):
        if (self.outcome is None) != (self.checked_at is None) or (
            self.outcome == "offer"
        ) != (self.current_price is not None):
            raise ValueError(
                f"Tur {self.run_id} sayfa {self.listing_id}: sonuç alanları uyuşmuyor"
            )
        return self


class MarketRow(Contract):
    product_id: PositiveInt
    source: Literal["cimri"]
    source_product_id: str = Field(pattern=r"^[1-9][0-9]*$")
    day: date
    price_kurus: PositiveInt | None
    captured_at: UtcDatetime


_TABLES = {
    "products": (Product, lambda row: row.product_id),
    "platforms": (PlatformRow, lambda row: row.key),
    "listings": (ListingRow, lambda row: row.listing_id),
    "collection_runs": (RunRow, lambda row: row.run_id),
    "listing_checks": (CheckRow, lambda row: (row.run_id, row.listing_id)),
    "market_history": (MarketRow, lambda row: (row.product_id, row.source, row.day)),
}


class MlSnapshot(Contract):
    format_version: Literal[1]
    captured_at: UtcDatetime
    schema_version: PositiveInt
    products: tuple[Product, ...]
    platforms: tuple[PlatformRow, ...]
    listings: tuple[ListingRow, ...]
    collection_runs: tuple[RunRow, ...]
    listing_checks: tuple[CheckRow, ...]
    market_history: tuple[MarketRow, ...]

    @model_validator(mode="after")
    def _consistent_links(self):
        # Sıralı ve tekil kayıt: aynı veri tek bir dosya biçimine sahip olur.
        for name, (_, key) in _TABLES.items():
            keys = [key(row) for row in getattr(self, name)]
            if any(left >= right for left, right in zip(keys, keys[1:])):
                raise ValueError(
                    f"{name}: kayıtlar anahtara göre sıralı ve tekil olmalı"
                )
        product_keys = Counter(row.product_key for row in self.products)
        repeated = sorted(key for key, count in product_keys.items() if count > 1)
        if repeated:
            raise ValueError(f"Tekrarlı ürün anahtarı: {', '.join(repeated)}")
        products = {row.product_id for row in self.products}
        platforms = {row.key for row in self.platforms}
        owners = {row.listing_id: row.product_id for row in self.listings}
        runs = {row.run_id: row for row in self.collection_runs}
        for row in self.listings:
            if row.product_id not in products or row.platform not in platforms:
                raise ValueError(
                    f"Sayfa {row.listing_id}: ürün veya platform kaydı yok"
                )
        for row in self.listing_checks:
            run = runs.get(row.run_id)
            label = f"Tur {row.run_id} sayfa {row.listing_id}"
            if run is None or owners.get(row.listing_id) != row.product_id:
                raise ValueError(f"{label}: tur veya sayfa bağı uyuşmuyor")
            if row.checked_at is not None and not (
                run.started_at <= row.checked_at <= run.finished_at
            ):
                raise ValueError(f"{label}: kontrol zamanı tur aralığı dışında")
        planned = Counter(row.run_id for row in self.listing_checks)
        for run in self.collection_runs:
            if planned[run.run_id] != run.planned_count:
                raise ValueError(
                    f"Tur {run.run_id}: planlanan {run.planned_count}, "
                    f"sonuç satırı {planned[run.run_id]}"
                )
        for row in self.market_history:
            if row.product_id not in products:
                raise ValueError(
                    f"Cimri ürün {row.product_id} ({row.day}): ürün kaydı yok"
                )
        return self


def build_snapshot(
    tables: dict[str, list[dict]], captured_at: datetime, schema_version: int
) -> MlSnapshot:
    """Veritabanı satırlarından görüntü; satırlar anahtar sırasına dizilir."""
    if set(tables) != set(_TABLES):
        raise ValueError(
            f"Görüntü tabloları eksik veya fazla: {sorted(tables)}; "
            f"beklenen {sorted(_TABLES)}"
        )
    rows = {}
    for name, (model, key) in _TABLES.items():
        rows[name] = tuple(
            sorted((model.model_validate(row) for row in tables[name]), key=key)
        )
    return MlSnapshot(
        format_version=FORMAT_VERSION,
        captured_at=captured_at,
        schema_version=schema_version,
        **rows,
    )


def _canonical(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def write_snapshot(snapshot: MlSnapshot, directory: Path) -> str:
    """Görüntüyü yeni klasöre yazar ve parmak izini döndürür.

    Var olan klasöre yazılmaz (FileExistsError): eski bir görüntü sessizce
    değişmesin.
    """
    payload = snapshot.model_dump(mode="json")
    digest = hashlib.sha256(_canonical(payload)).hexdigest()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / FILE_NAME).write_bytes(
        _canonical({"sha256": digest, "payload": payload})
    )
    return digest


def read_snapshot(directory: Path) -> tuple[MlSnapshot, str]:
    """Görüntüyü ve parmak izini okur; değişmiş veya tutarsız dosyayı reddeder."""
    try:
        envelope = json.loads((directory / FILE_NAME).read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotError(f"Görüntü dosyası JSON değil: {exc}") from None
    if not isinstance(envelope, dict) or set(envelope) != {"sha256", "payload"}:
        raise SnapshotError("Görüntü dosyasının zarfı geçersiz (sha256 ve payload)")
    payload = _canonical(envelope["payload"])
    digest = hashlib.sha256(payload).hexdigest()
    if envelope["sha256"] != digest:
        raise SnapshotError(
            "Görüntünün parmak izi tutmuyor; dosya değiştirilmiş veya bozuk"
        )
    try:
        snapshot = MlSnapshot.model_validate_json(payload)
    except ValidationError as exc:
        error = exc.errors()[0]
        place = ".".join(str(part) for part in error["loc"])
        detail = f"{place}: {error['msg']}" if place else error["msg"]
        raise SnapshotError(f"Görüntü içeriği geçersiz: {detail}") from None
    return snapshot, digest
