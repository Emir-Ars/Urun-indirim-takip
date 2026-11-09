"""Teslim paketinin kapalı dosya kümesi, kanıt zinciri ve bütünlük sözleşmesi."""

import hashlib
import json
import re
import stat
from datetime import timedelta
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field

from app.contracts import Contract
from app.database.migrate import load as load_migrations
from app.ml import shadow_records as records
from app.ml.dataset import UtcDatetime, read_snapshot
from app.ml.reporting import json_bytes

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILES = (
    "catalog.json",
    "discovery.json",
    "runtime.json",
    "market_history.json",
    "shadow.json",
)
SHADOW = "data/ml/golge"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class DeliveryError(Exception):
    """Ham bağlantı/parola ayrıntısı taşımayan teslim hatası."""


class TableProof(Contract):
    rows: int = Field(ge=0)
    sha256: Digest


class DatabaseProof(Contract):
    name: str = Field(pattern=r"^(fiyat_takip|[a-z][a-z0-9_]*_test)$")
    server_version: int = Field(ge=170000, lt=180000)
    migrations: dict[str, Digest]
    schema_sha256: Digest
    tables: dict[str, TableProof]
    sequence_value: int
    sequence_called: bool


class BundleManifest(Contract):
    format_version: Literal[1]
    kind: Literal["delivery_bundle"]
    status: Literal["complete"]
    created_at: UtcDatetime
    code_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    source_dirty: bool
    code_sha256: Digest
    model_manifest_sha256: Digest
    database: DatabaseProof
    files: dict[str, Digest]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def reference_path():
    image = Path("/opt/delivery/shadow.json")
    return image if image.is_file() else ROOT / "config/shadow.json"


def code_sha256(reference=None):
    paths = [
        p
        for p in (ROOT / "app").rglob("*")
        if p.is_file() and p.suffix in (".py", ".sql")
    ]
    paths += [
        ROOT / "tools/docker_entrypoint.py",
        ROOT / "scripts/api_okuma_rolu.sql",
        ROOT / "requirements-linux.lock",
    ]
    values = {}
    for path in paths:
        content = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        values[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
            content.encode()
        ).hexdigest()
    content = (
        Path(reference or reference_path())
        .read_text(encoding="utf-8-sig")
        .replace("\r\n", "\n")
    )
    values["config/shadow.json"] = hashlib.sha256(content.encode()).hexdigest()
    return hashlib.sha256(json_bytes(values)).hexdigest()


def safe_path(root, name):
    part = PurePosixPath(name)
    if (
        not name
        or str(part) != name
        or part.is_absolute()
        or ".." in part.parts
        or "\\" in name
        or ":" in name
        or "\0" in name
    ):
        raise DeliveryError("Paket dosya yolu geçersiz.")
    result = Path(root).joinpath(*part.parts)
    current = result
    while current != Path(root).parent:
        if current.exists() or current.is_symlink():
            info = current.lstat()
            if (
                stat.S_ISLNK(info.st_mode)
                or getattr(info, "st_file_attributes", 0) & 0x400
            ):
                raise DeliveryError(
                    "Paket sembolik bağlantı veya yeniden yönlendirme içeremez."
                )
        if current == Path(root):
            break
        current = current.parent
    return result


def inventory(root):
    import os

    root = Path(root)
    result = set()
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            safe_path(root, relative)
            if name in files:
                if not stat.S_ISREG(path.stat().st_mode):
                    raise DeliveryError("Paket yalnız normal dosyalar içermeli.")
                result.add(relative)
    return result


def relocated_config(root, config):
    evidence = config.evidence.model_copy(
        update={
            key: str(Path(root) / SHADOW / "kanitlar" / key)
            for key in ("labels", "features", "split", "model")
        }
    )
    return config.model_copy(
        update={"records_dir": str(Path(root) / SHADOW), "evidence": evidence}
    )


def validate_assets(root, reference=None):
    from app.contracts import Catalog, DiscoveryConfig
    from app.settings import Runtime
    from app.market_history.capture import read_mapping
    from app.ml import shadow_evaluation
    from app.ml.series import ISTANBUL

    root = Path(root)
    config = records.load_config(root / "config/shadow.json")
    expected = records.load_config(reference or reference_path())
    if (
        config != expected
        or config.records_dir != SHADOW
        or any(
            getattr(config.evidence, key) != f"{SHADOW}/kanitlar/{key}"
            for key in ("labels", "features", "split", "model")
        )
    ):
        raise DeliveryError("Gölge ön kaydı imajın modeliyle uyuşmuyor.")
    catalog = Catalog.model_validate_json((root / "config/catalog.json").read_bytes())
    DiscoveryConfig.model_validate_json((root / "config/discovery.json").read_bytes())
    Runtime.model_validate_json((root / "config/runtime.json").read_bytes())
    read_mapping(root / "config/market_history.json", catalog)
    model = shadow_evaluation.load_evaluation_model(relocated_config(root, config))
    wanted = {f"config/{name}" for name in CONFIG_FILES} | {"database.dump"}
    for kind in ("labels", "features", "split", "model"):
        prefix = f"{SHADOW}/kanitlar/{kind}"
        manifest = json.loads((root / prefix / "manifest.json").read_bytes())
        wanted.add(f"{prefix}/manifest.json")
        wanted.update(f"{prefix}/{name}" for name in manifest["files"])
    record_root = root / SHADOW
    records.recorded_keys(record_root, config.model_manifest_sha256)
    required_sources = {}
    for folder in sorted(record_root.iterdir()):
        if not folder.is_dir() or folder.name in ("kanitlar", "goruntuler"):
            continue
        if not re.fullmatch(r"(?:tahmin|degerlendirme)_[a-zA-Z0-9_]+", folder.name):
            raise DeliveryError("Paket beklenmeyen gölge klasörü içeriyor.")
        if folder.name.startswith("tahmin_"):
            manifest, rows = records.read_shadow_outputs(folder)
            if (
                manifest["choice"] != model.choice
                or manifest["start_day"] != config.start_day.isoformat()
            ):
                raise DeliveryError(
                    "Resmi kayıt model veya başlangıç bilgisi uyuşmuyor."
                )
            captured = records.parse_utc(manifest["snapshot_captured_at"])
            closed = captured.astimezone(ISTANBUL).date() - timedelta(days=1)
            if manifest["last_closed_day"] != closed.isoformat() or any(
                row["anchor_day"] > closed.isoformat() for row in rows
            ):
                raise DeliveryError("Resmi kaydın gün bilgisi uyuşmuyor.")
            source_digest = manifest["snapshot_sha256"]
        else:
            report, _ = shadow_evaluation.read_outputs(folder)
            manifest = json.loads((folder / "manifest.json").read_bytes())
            inputs = report["input"]
            if (
                inputs["model_manifest_sha256"] != config.model_manifest_sha256
                or inputs["choice"] != model.choice
                or inputs["start_day"] != config.start_day.isoformat()
                or inputs["reference_rate"] != model.reference_rate
            ):
                raise DeliveryError("Değerlendirme başka modele ait.")
            captured = records.parse_utc(report["input"]["snapshot_captured_at"])
            closed = captured.astimezone(ISTANBUL).date() - timedelta(days=1)
            if inputs["last_closed_day"] != closed.isoformat():
                raise DeliveryError("Değerlendirmenin kapanmış günü uyuşmuyor.")
            for origin in inputs["records"]:
                if not re.fullmatch(r"tahmin_[a-zA-Z0-9_]+", origin["folder"]):
                    raise DeliveryError("Değerlendirmenin resmi kayıt yolu geçersiz.")
                original = record_root / origin["folder"]
                original_manifest, _ = records.read_shadow_outputs(original)
                if (
                    sha(original / "manifest.json") != origin["manifest_sha256"]
                    or original_manifest["snapshot_sha256"] != origin["snapshot_sha256"]
                    or original_manifest["choice"] != origin["choice"]
                    or records.parse_utc(original_manifest["snapshot_captured_at"])
                    != records.parse_utc(origin["captured_at"])
                ):
                    raise DeliveryError("Değerlendirmenin resmi kayıt bağı uyuşmuyor.")
            source_digest = report["input"]["snapshot_sha256"]
        if (
            source_digest in required_sources
            and required_sources[source_digest] != captured
        ):
            raise DeliveryError("Aynı görüntü için farklı zaman kayıtlı.")
        required_sources[source_digest] = captured
        prefix = f"{SHADOW}/{folder.name}"
        wanted.add(f"{prefix}/manifest.json")
        wanted.update(f"{prefix}/{name}" for name in manifest["files"])
    for digest in required_sources:
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise DeliveryError("Kaynak görüntü kimliği geçersiz.")
        snapshot, actual = read_snapshot(record_root / "goruntuler" / digest)
        if actual != digest or snapshot.captured_at != required_sources[digest]:
            raise DeliveryError("Kaynak görüntü SHA'sı uyuşmuyor.")
        wanted.add(f"{SHADOW}/goruntuler/{digest}/snapshot.json")
    return wanted, config


def verify_bundle(root, reference=None):
    from app.delivery.database import SCHEMA_SHA256, TABLES

    root = Path(root)
    safe_path(root, "manifest.json")
    raw = (root / "manifest.json").read_bytes()
    manifest = BundleManifest.model_validate_json(raw)
    if manifest.code_sha256 != code_sha256(reference):
        raise DeliveryError("Paket ve çalışan kod/bağımlılık sürümü uyuşmuyor.")
    expected_migrations = {m.file_name: m.checksum for m in load_migrations()}
    if (
        manifest.database.migrations != expected_migrations
        or set(manifest.database.tables) != set(TABLES)
        or manifest.database.schema_sha256 != SCHEMA_SHA256
    ):
        raise DeliveryError("Paketin migration sözleşmesi uyumsuz.")
    if inventory(root) != set(manifest.files) | {"manifest.json"}:
        raise DeliveryError("Paket dosya listesi eksik veya fazla.")
    for name, digest in manifest.files.items():
        if sha(safe_path(root, name)) != digest:
            raise DeliveryError("Paket dosyasının SHA-256 değeri uyuşmuyor.")
    with (root / "database.dump").open("rb") as stream:
        header = stream.read(5)
    if header != b"PGDMP":
        raise DeliveryError("Veritabanı arşivi PostgreSQL özel biçiminde değil.")
    wanted, config = validate_assets(root, reference)
    if (
        wanted != set(manifest.files)
        or manifest.model_manifest_sha256 != config.model_manifest_sha256
    ):
        raise DeliveryError("Paket izinli kanıt ve yapılandırma kümesine uymuyor.")
    if (root / "manifest.json").read_bytes() != raw:
        raise DeliveryError("Doğrulama sırasında paket değişti.")
    return manifest, hashlib.sha256(raw).hexdigest()
