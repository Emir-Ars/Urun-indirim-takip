"""Ortak kilitler altında aynı salt okunur işlemden veri ve kanıt paketi."""

import json
import shutil
import subprocess
from pathlib import Path

from filelock import FileLock
from psycopg import sql

from app.contracts import Catalog, utc_now
from app.delivery import bundle, database
from app.ml import shadow_records as records
from app.ml.dataset import read_snapshot
from app.ml.reporting import json_bytes
from app.ml.shadow_evaluation import load_evaluation_model, read_outputs
from app.scrape_lock import scrape_lock
from app.settings import Settings


def copy_assets(source, target, reference=None, settings=None):
    source, target = Path(source), Path(target)
    paths = {name: source / "config" / name for name in bundle.CONFIG_FILES}
    if settings is not None:
        paths.update(
            {
                "catalog.json": settings.catalog_path,
                "discovery.json": settings.discovery_path,
                "runtime.json": settings.runtime_path,
            }
        )
    config = records.load_config(paths["shadow.json"])
    if config != records.load_config(reference or bundle.reference_path()):
        raise bundle.DeliveryError("Kaynak gölge ayarı ön kayıtla uyuşmuyor.")
    load_evaluation_model(bundle.relocated_config(source, config))
    sources = {f"config/{name}": path for name, path in paths.items()}
    for kind in ("labels", "features", "split", "model"):
        prefix = f"{bundle.SHADOW}/kanitlar/{kind}"
        folder = source / prefix
        manifest = json.loads((folder / "manifest.json").read_bytes())
        for name in (*manifest["files"], "manifest.json"):
            sources[f"{prefix}/{name}"] = bundle.safe_path(source, f"{prefix}/{name}")
    digests = set()
    record_root = source / bundle.SHADOW
    records.recorded_keys(record_root, config.model_manifest_sha256)
    for folder in sorted(record_root.iterdir()):
        if not folder.is_dir() or not folder.name.startswith(
            ("tahmin_", "degerlendirme_")
        ):
            continue
        if not (folder / "manifest.json").is_file():
            continue
        if folder.name.startswith("tahmin_"):
            manifest, _ = records.read_shadow_outputs(folder)
            digests.add(manifest["snapshot_sha256"])
        else:
            report, _ = read_outputs(folder)
            manifest = json.loads((folder / "manifest.json").read_bytes())
            digests.add(report["input"]["snapshot_sha256"])
        for name in (*manifest["files"], "manifest.json"):
            relative = f"{bundle.SHADOW}/{folder.name}/{name}"
            sources[relative] = bundle.safe_path(source, relative)
    for path in sorted((record_root / "goruntuler").glob("*/snapshot.json")):
        envelope = json.loads(path.read_bytes())
        digest = envelope.get("sha256") if isinstance(envelope, dict) else None
        if digest not in digests:
            continue
        _, actual = read_snapshot(path.parent)
        if actual != digest:
            raise bundle.DeliveryError("Kaynak görüntü bozuk.")
        sources[f"{bundle.SHADOW}/goruntuler/{digest}/snapshot.json"] = path
    hashes = {}
    for name, path in sources.items():
        bundle.safe_path(path.parent, path.name)
        digest = bundle.sha(path)
        destination = bundle.safe_path(target, name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        if bundle.sha(destination) != digest or bundle.sha(path) != digest:
            raise bundle.DeliveryError("Kopyalama sırasında kaynak değişti.")
        hashes[name] = digest
    return hashes


def validate_catalog(conn, path):
    catalog = Catalog.model_validate_json(Path(path).read_bytes())
    for table, key in (
        ("platforms", "key"),
        ("products", "product_id"),
        ("listings", "listing_id"),
    ):
        for item in getattr(catalog, table):
            values = item.model_dump(exclude={"hosts"})
            columns = list(values)
            row = conn.execute(
                sql.SQL("SELECT {} FROM public.{} WHERE {}=%s").format(
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.Identifier(table),
                    sql.Identifier(key),
                ),
                (values[key],),
            ).fetchone()
            if row != tuple(values.values()):
                raise bundle.DeliveryError(
                    "Katalog ve DB eşleşmiyor; tamamlanmış toplama turu gerekli."
                )


def export_bundle(destination, executable, url, *, source=None, reference=None):
    source = Path(source or bundle.ROOT)
    destination = Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(source / bundle.SHADOW):
        raise bundle.DeliveryError(
            "Çıktı yeni ve gölge kayıtlarının dışında bir klasör olmalı."
        )
    settings = Settings()
    lock_path = (
        settings.lock_path if source == bundle.ROOT else source / "data/scrape.lock"
    )
    with (
        scrape_lock(lock_path),
        FileLock(str(source / bundle.SHADOW / "tahmin.lock"), timeout=0),
    ):
        with database.source_connection(url) as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            proof = database.fingerprint(conn)
            snapshot = conn.execute("SELECT pg_export_snapshot()").fetchone()[0]
            destination.mkdir(parents=True, exist_ok=False)
            copy_assets(
                source,
                destination,
                reference,
                settings if source == bundle.ROOT else None,
            )
            validate_catalog(conn, destination / "config/catalog.json")
            database.dump_database(
                conn, executable, destination / "database.dump", snapshot
            )
            wanted, config = bundle.validate_assets(destination, reference)
            if bundle.inventory(destination) != wanted:
                raise bundle.DeliveryError("Paket kaynak dosya kapsamı tutarsız.")
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=bundle.ROOT, text=True
            ).strip()
            dirty = bool(
                subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=bundle.ROOT, text=True
                ).strip()
            )
            manifest = bundle.BundleManifest(
                format_version=1,
                kind="delivery_bundle",
                status="complete",
                created_at=utc_now(),
                code_commit=commit,
                source_dirty=dirty,
                code_sha256=bundle.code_sha256(reference),
                model_manifest_sha256=config.model_manifest_sha256,
                database=proof,
                files={
                    name: bundle.sha(bundle.safe_path(destination, name))
                    for name in sorted(wanted)
                },
            )
            with (destination / "manifest.json").open("xb") as stream:
                stream.write(json_bytes(manifest.model_dump(mode="json")) + b"\n")
    return bundle.verify_bundle(destination, reference)
