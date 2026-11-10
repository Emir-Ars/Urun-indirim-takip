"""Docker kabulü için yalnız ayrı _test kaynağında üretilen yapay paket."""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.contracts import Catalog
from app.database.catalog_sync import sync_catalog
from app.database.migrate import migrate
from app.delivery import bundle, database
from app.ml.reporting import json_bytes
from tests.support.delivery import add_final_evaluation, write_bundle, write_source

DATABASE = "teslim_kabul_test"


def seed(output):
    source = write_source(output / "build")
    add_final_evaluation(source)
    with database.target_connection(DATABASE, "/run/secrets/admin_password") as conn:
        assert conn.info.dbname == DATABASE
        assert (
            conn.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n "
                "ON n.oid=c.relnamespace WHERE n.nspname='public'"
            ).fetchone()[0]
            == 0
        )
        # Kaynak bağlantısının güvenli arama yolu yeni tabloyu pg_catalog'a yöneltmez.
        conn.execute("SET search_path=public")
        migrate(conn)
        conn.execute("SET search_path=pg_catalog,public")
        sync_catalog(
            conn,
            Catalog.model_validate_json((source / "config/catalog.json").read_bytes()),
        )
        start = datetime(2026, 11, 9, 19, tzinfo=timezone.utc)
        for offset, price in enumerate((5664900, 5299900)):
            at = start + timedelta(days=offset)
            run = conn.execute(
                "INSERT INTO collection_runs"
                "(trigger,status,started_at,catalog_sha256,planned_count) "
                "VALUES('manual','running',%s,%s,1) RETURNING run_id",
                (at, "0" * 64),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO listing_checks(run_id,listing_id,product_id,"
                "checked_at,outcome,current_price,seller_name,stock_status) "
                "VALUES(%s,'hepsiburada_a',1,%s,'offer',%s,'Yapay satıcı',"
                "'Stokta Var')",
                (run, at + timedelta(minutes=1), price),
            )
            conn.execute(
                "UPDATE collection_runs SET status='completed',finished_at=%s "
                "WHERE run_id=%s",
                (at + timedelta(minutes=5), run),
            )
            conn.execute(
                "INSERT INTO market_history(product_id,source,source_product_id,"
                "source_url,day,price_kurus,captured_at,page_sha256,api_sha256,"
                "report_sha256) VALUES(1,'cimri','123456',"
                "'https://www.cimri.com/cep-telefonlari/test,a123456',"
                "%s,%s,%s,%s,%s,%s)",
                (at.date(), price, at, "1" * 64, "2" * 64, "3" * 64),
            )
        proof = database.fingerprint(conn)
        assert proof.name.endswith("_test")
        (output / "source_proof.json").write_bytes(
            json_bytes(json.loads(proof.model_dump_json()))
        )


def seal(output):
    source = output / "build/source"
    proof = bundle.DatabaseProof.model_validate_json(
        (output / "source_proof.json").read_bytes()
    )
    assert proof.name == DATABASE
    manifest, digest = write_bundle(source, output / "package", proof)
    with database.target_connection(DATABASE, "/run/secrets/admin_password") as conn:
        assert database.fingerprint(conn) == manifest.database
    print(json.dumps(dict(bundle_sha256=digest, synthetic=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed", "seal"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "seed":
        seed(args.output)
    else:
        seal(args.output)


if __name__ == "__main__":
    main()
