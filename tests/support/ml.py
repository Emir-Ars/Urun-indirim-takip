"""ML veri görüntüsü testlerinin küçük, tutarlı tablo örneği (veritabanısız)."""

import json
import random
from datetime import date, datetime, timedelta, timezone

FEATURE_DEFAULTS = dict(
    log_return_1d=0.0,
    log_return_7d=0.0,
    log_return_14d=0.0,
    log_return_30d=0.0,
    ratio_min_7d=1.0,
    ratio_min_30d=1.0,
    ratio_mean_30d=1.0,
    volatility_30d=0.01,
    change_count_30d=2,
    days_since_drop_30d=10,
    drop_observed_30d=True,
    history_days=100,
    missing_ratio_30d=0.0,
    weekday="2",
    brand="Apple",
    family="Apple iPhone 15",
    segment="standard",
    capacity="128",
)
CAPTURED_AT = datetime(2026, 10, 28, 9, 30, tzinfo=timezone.utc)
START = datetime(2026, 10, 27, 19, tzinfo=timezone.utc)


def snapshot_tables():
    """Veritabanının döndürdüğü biçimde satırlar: tamamlanan ve yarıda kalan tur,
    üç sonuç türü, kontrol edilmemiş sayfa ve fiyatı boş Cimri günü."""
    return {
        "products": [
            {
                "product_id": 1,
                "product_key": "apple_iphone_15_128gb",
                "brand": "Apple",
                "model": "iPhone 15",
                "storage_gb": 128,
                "active": True,
            },
            {
                "product_id": 2,
                "product_key": "samsung_galaxy_s24_256gb",
                "brand": "Samsung",
                "model": "Galaxy S24",
                "storage_gb": 256,
                "active": False,
            },
        ],
        "platforms": [
            {"key": "hepsiburada", "active": True},
            {"key": "trendyol", "active": True},
        ],
        "listings": [
            {
                "listing_id": "hepsiburada_a",
                "product_id": 1,
                "platform": "hepsiburada",
                "active": True,
            },
            {
                "listing_id": "trendyol_b",
                "product_id": 1,
                "platform": "trendyol",
                "active": False,
            },
            {
                "listing_id": "trendyol_c",
                "product_id": 2,
                "platform": "trendyol",
                "active": True,
            },
        ],
        "collection_runs": [
            {
                "run_id": 1,
                "trigger": "scheduled",
                "status": "completed",
                "started_at": START,
                "finished_at": START + timedelta(minutes=31),
                "planned_count": 3,
            },
            {
                "run_id": 2,
                "trigger": "manual",
                "status": "interrupted",
                "started_at": START + timedelta(hours=12),
                "finished_at": START + timedelta(hours=12, minutes=5),
                "planned_count": 2,
            },
        ],
        "listing_checks": [
            check(1, "hepsiburada_a", 1, "offer", 4_299_900, minutes=1),
            check(1, "trendyol_b", 1, "sold_out", minutes=2),
            check(1, "trendyol_c", 2, "error", minutes=3),
            check(2, "hepsiburada_a", 1, "offer", 4_199_900, minutes=12 * 60 + 1),
            check(2, "trendyol_c", 2),
        ],
        "market_history": [
            market(1, date(2026, 10, 7), 4_350_000),
            market(1, date(2026, 10, 8), None),
        ],
    }


def check(run_id, listing_id, product_id, outcome=None, price=None, minutes=None):
    return {
        "run_id": run_id,
        "listing_id": listing_id,
        "product_id": product_id,
        "checked_at": None if minutes is None else START + timedelta(minutes=minutes),
        "outcome": outcome,
        "current_price": price,
    }


def market(product_id, day, price):
    return {
        "product_id": product_id,
        "source": "cimri",
        "source_product_id": "123456",
        "day": day,
        "price_kurus": price,
        "captured_at": datetime(2026, 10, 8, 13, 51, 42, 423000, tzinfo=timezone.utc),
    }


def label_tables(count=37, prices=None):
    """Tam iki turlu tek ürün; son günün ertesi sabahında alınmış görüntü."""
    prices = prices if prices is not None else [10000] * count
    tables = snapshot_tables()
    tables["products"] = tables["products"][:1]
    tables["listings"] = tables["listings"][:1]
    tables["collection_runs"] = []
    tables["listing_checks"] = []
    tables["market_history"] = []
    first = date(2026, 1, 1)
    for offset, price in enumerate(prices):
        day = first + timedelta(days=offset)
        for hour in (10, 22):
            run_id = 2 * offset + (1 if hour == 10 else 2)
            at = datetime.combine(day, datetime.min.time(), timezone.utc).replace(
                hour=hour - 3
            )
            tables["collection_runs"].append(
                dict(
                    run_id=run_id,
                    trigger="scheduled",
                    status="completed",
                    started_at=at,
                    finished_at=at + timedelta(minutes=30),
                    planned_count=1,
                )
            )
            tables["listing_checks"].append(
                dict(
                    run_id=run_id,
                    listing_id="hepsiburada_a",
                    product_id=1,
                    checked_at=at + timedelta(minutes=1),
                    outcome="offer" if price is not None else "sold_out",
                    current_price=price,
                )
            )
        tables["market_history"].append(
            dict(
                product_id=1,
                source="cimri",
                source_product_id="123456",
                day=day,
                price_kurus=price,
                captured_at=datetime.combine(
                    first + timedelta(days=count), datetime.min.time(), timezone.utc
                ),
            )
        )
    return tables


def label_snapshot(tables=None, count=37, prices=None):
    from app.ml.dataset import build_snapshot

    tables = tables if tables is not None else label_tables(count, prices)
    last = max(
        [row["day"] for row in tables["market_history"]]
        + [row["started_at"].date() for row in tables["collection_runs"]]
    )
    return build_snapshot(
        tables,
        datetime.combine(last + timedelta(days=1), datetime.min.time(), timezone.utc),
        5,
    )


def feature_values(**overrides):
    """Geçerli bir model girdi satırı; yalnız verilen alanlar değişir."""
    from app.ml.features import FeatureValues

    return FeatureValues(**{**FEATURE_DEFAULTS, **overrides})


def walk_prices(count, seed=7):
    """Tohumlu, günlük %3 oynaklıkta yapay fiyat yürüyüşü (kuruş)."""
    rng = random.Random(seed)
    price, prices = 10000, []
    for _ in range(count):
        price = max(5000, int(price * (1 + rng.gauss(0, 0.03))))
        prices.append(price)
    return prices


def write_ml_evidence(root, count=365):
    """Görüntü, etiket, girdi ve bölme klasörlerini yazar; yolları döndürür."""
    from app.ml.__main__ import main
    from app.ml.dataset import write_snapshot
    from app.ml.features import analyze_features
    from app.ml.labels import analyze_labels
    from app.ml.reporting import write_feature_outputs, write_outputs

    snapshot = label_snapshot(prices=walk_prices(count))
    digest = write_snapshot(snapshot, root / "source")
    write_outputs(root / "labels", digest, analyze_labels(snapshot))
    write_feature_outputs(root / "features", digest, analyze_features(snapshot))
    paths = dict(
        source=root / "source",
        labels=root / "labels",
        features=root / "features",
        split=root / "split",
        digest=digest,
    )
    code = main(
        [
            "split",
            "--labels-dir",
            str(paths["labels"]),
            "--features-dir",
            str(paths["features"]),
            "--output-dir",
            str(paths["split"]),
        ]
    )
    assert code == 0
    return paths


def write_experiment_evidence(root, count=365):
    """`write_ml_evidence` kanıtlarına deney klasörünü ekler; yolları döndürür."""
    from app.ml.__main__ import main

    paths = write_ml_evidence(root, count)
    paths["experiment"] = root / "experiment"
    code = main(
        [
            "experiment",
            "--labels-dir",
            str(paths["labels"]),
            "--features-dir",
            str(paths["features"]),
            "--split-dir",
            str(paths["split"]),
            "--output-dir",
            str(paths["experiment"]),
        ]
    )
    assert code == 0
    return paths


def write_shadow_config(path, evidence, records, sha=None, **extra):
    """Yapay model kanıtlarıyla, gerçek kayıt dizininden bağımsız gölge ayarı."""
    path.write_text(
        json.dumps(
            dict(
                start_day="2026-01-20",
                model_manifest_sha256=sha or evidence["model_sha256"],
                evidence={
                    name: str(evidence[name])
                    for name in ("labels", "features", "split", "model")
                },
                records_dir=str(records),
                **extra,
            )
        ),
        encoding="utf-8",
    )
    return path


def write_model_evidence(root, count=365):
    """`write_experiment_evidence` kanıtlarına dondurulmuş model klasörünü ekler.

    `model_sha256`, model manifestinin parmak izidir (gerçek akıştaki ön kayıt).
    """
    import hashlib

    from app.ml.__main__ import main

    paths = write_experiment_evidence(root, count)
    paths["model"] = root / "model"
    code = main(
        [
            "freeze",
            "--labels-dir",
            str(paths["labels"]),
            "--features-dir",
            str(paths["features"]),
            "--split-dir",
            str(paths["split"]),
            "--experiment-dir",
            str(paths["experiment"]),
            "--output-dir",
            str(paths["model"]),
        ]
    )
    assert code == 0
    paths["model_sha256"] = hashlib.sha256(
        (paths["model"] / "manifest.json").read_bytes()
    ).hexdigest()
    return paths


def write_evaluation_evidence(root):
    """Yalnız yapay veriden dondurulmuş model ve ilk resmi kayıt üretir."""
    from app.ml.__main__ import main

    evidence = write_model_evidence(root)
    evidence["records"] = root / "records"
    evidence["record"] = evidence["records"] / "tahmin_01"
    evidence["config"] = write_shadow_config(
        root / "shadow.json", evidence, evidence["records"]
    )
    assert (
        main(
            [
                "shadow-predict",
                "--snapshot",
                str(evidence["source"]),
                "--config",
                str(evidence["config"]),
                "--output-dir",
                str(evidence["record"]),
            ]
        )
        == 0
    )
    return evidence


def remove_label_run(tables, run_id):
    tables["collection_runs"] = [
        row for row in tables["collection_runs"] if row["run_id"] != run_id
    ]
    tables["listing_checks"] = [
        row for row in tables["listing_checks"] if row["run_id"] != run_id
    ]


def add_label_page(
    tables,
    start_offset=0,
    end_offset=36,
    price=10000,
    product_id=1,
    listing_id="new_page",
):
    tables["listings"].append(
        dict(
            listing_id=listing_id,
            product_id=product_id,
            platform="hepsiburada",
            active=True,
        )
    )
    for run in tables["collection_runs"]:
        offset = (run["run_id"] - 1) // 2
        if start_offset <= offset <= end_offset:
            run["planned_count"] += 1
            tables["listing_checks"].append(
                dict(
                    run_id=run["run_id"],
                    listing_id=listing_id,
                    product_id=product_id,
                    checked_at=run["started_at"] + timedelta(minutes=2),
                    outcome="offer",
                    current_price=price,
                )
            )
