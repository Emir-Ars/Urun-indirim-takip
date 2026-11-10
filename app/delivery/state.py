"""Hazırlanmış teslim kopyasının değişmeyen yerel durum sözleşmesi."""

from datetime import timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from app.contracts import Contract

READY_FILE = ".delivery_ready.json"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class DeliveryState(Contract):
    format_version: Literal[1]
    status: Literal["complete"]
    bundle_sha256: Digest
    code_sha256: Digest
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    database: str = Field(pattern=r"^(fiyat_takip|[a-z][a-z0-9_]*_test)$")
    captured_at: AwareDatetime
    prepared_at: AwareDatetime
    # Hazırlık anında gösterim kapalıdır; güncel onay ayrı dosyada tutulur.
    display_enabled: Literal[False]

    @field_validator("captured_at", "prepared_at")
    @classmethod
    def utc_time(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError("Teslim zamanı UTC olmalı.")
        return value

    @model_validator(mode="after")
    def chronological(self):
        if self.prepared_at < self.captured_at:
            raise ValueError("Kopya paketten önce hazırlanmış olamaz.")
        return self


def load_state(path):
    return DeliveryState.model_validate_json(Path(path).read_bytes())
