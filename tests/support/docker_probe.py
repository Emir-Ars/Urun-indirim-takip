"""Yapay Docker kopyasının gerçek HTTP, yetki, çevrimdışı ve ML kabulü."""

import argparse
import json
import os
import pickle
import shutil
import socket
import stat
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import psycopg

from app.delivery import bundle, display, prepare
from app.ml import shadow_display, shadow_records
from app.ui.api_client import ApiClient, ApiClientError


def runtime():
    from streamlit.testing.v1 import AppTest

    assert "API_DATABASE_URL" not in os.environ
    assert "DATABASE_URL" not in os.environ
    assert not Path("/run/secrets").exists()
    with ApiClient() as client:
        client.get_health()
        product = client.list_products()[0]
        data = client.get_product(product.product_key)
        prediction = client.get_prediction(product.product_key)
    assert data.best_offer.current_price == 5299900
    assert len(data.history) == len(data.cimri_history) == 2
    assert prediction.state == "closed" and prediction.forecast is None
    app = AppTest.from_file("/app/app/ui/main.py", default_timeout=60).run()
    assert not app.exception and not app.error
    assert len(app.get("vega_lite_chart")) == 2
    assert any("Teslim kopyası" in item.value for item in app.info)
    assert any("Test verisi" in item.value for item in app.warning)
    app.selectbox(key="_history_days").set_value(7).run()
    assert not app.exception and not app.error
    return dict(http=True, charts=True, metadata=True, closed=True)


def offline():
    result = runtime()
    try:
        connection = socket.create_connection(("1.1.1.1", 443), timeout=2)
    except OSError:
        pass
    else:
        connection.close()
        raise AssertionError("Kabul ağı dış dünyaya kapalı olmalı.")
    return dict(**result, offline=True)


def reader():
    from tools.docker_entrypoint import prepare_api_passfile

    url = os.environ["API_DATABASE_URL"]
    path = prepare_api_passfile(url, "/run/secrets/api_password")
    try:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        with psycopg.connect(url, passfile=str(path), autocommit=True) as conn:
            assert conn.info.dbname.endswith("_test")
            assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 1
            conn.execute("SET default_transaction_read_only=off")
            try:
                conn.execute("DELETE FROM products WHERE false")
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError("API rolü yazma yetkisi taşıyor.")
    finally:
        path.unlink()
    return dict(select=True, write_denied=True, passfile_0600=True)


def unavailable():
    try:
        with ApiClient() as client:
            client.get_product("apple_iphone_15_128gb")
    except ApiClientError:
        pass
    else:
        raise AssertionError("Kesintide başarılı fiyat beklenmez.")
    return dict(unavailable=True)


def gate():
    from app.contracts import Catalog
    from app.delivery.__main__ import main as delivery_main

    manifest, _ = bundle.verify_bundle("/bundle")
    assert manifest.database.name.endswith("_test")
    original = bundle.ROOT
    root = Path("/tmp/gate_copy")
    for name in ("app", "config", bundle.SHADOW):
        shutil.copytree(original / name, root / name)
    for name in (
        "requirements-linux.lock",
        "scripts/api_okuma_rolu.sql",
        "tools/docker_entrypoint.py",
    ):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original / name, target)
    with patch.object(bundle, "ROOT", root), patch.object(shadow_records, "ROOT", root):
        config = shadow_records.load_config(root / "config/shadow.json")
        product = Catalog.model_validate_json(
            (root / "config/catalog.json").read_bytes()
        ).products[0]
        approval = root / bundle.SHADOW / shadow_display.APPROVAL_FILE
        before = {
            name: bundle.sha(root / name)
            for name in manifest.files
            if name != "database.dump"
        }
        args = [
            "shadow-display",
            "--bundle",
            "/bundle",
            "--evaluation",
            "degerlendirme_final",
        ]
        for now, expected in (
            (datetime(2026, 11, 10, 12, tzinfo=timezone.utc), 1),
            (datetime(2027, 1, 5, 12, tzinfo=timezone.utc), 0),
        ):
            with (
                patch.object(display, "utc_now", lambda: now),
                patch.object(shadow_display, "utc_now", lambda: now),
                patch.object(pickle, "load", side_effect=AssertionError("pickle")),
                patch.object(pickle, "loads", side_effect=AssertionError("pickle")),
            ):
                assert delivery_main(args) == expected
                if expected == 1:
                    assert not approval.exists()
                    continue
                assert shadow_display.prediction_for(product, config, now)["state"] == (
                    "available"
                )
                tomorrow = shadow_display.prediction_for(
                    product, config, now + timedelta(days=1)
                )
                assert tomorrow["state"] == "unavailable"
                assert tomorrow["forecast"] is None
                assert (
                    delivery_main(
                        ["shadow-display", "--bundle", "/bundle", "--disable"]
                    )
                    == 0
                )
                assert (
                    shadow_display.prediction_for(product, config, now)["forecast"]
                    is None
                )
                prepare.prepare_target("/bundle", "check")
        assert all(bundle.sha(root / name) == sha for name, sha in before.items())
    assert not (original / bundle.SHADOW / shadow_display.APPROVAL_FILE).exists()
    return dict(
        early_rejected=True, final_gate=True, next_day_hidden=True, disabled=True
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("runtime", "offline", "reader", "unavailable", "gate")
    )
    args = parser.parse_args()
    print(json.dumps(globals()[args.mode](), ensure_ascii=False))


if __name__ == "__main__":
    main()
