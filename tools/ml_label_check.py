"""Kaydedilmiş etiketlerin sıkı varyantını eski hesaplayıcıyla ağsız karşılaştırır."""

import argparse
import json
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.console import utf8_output  # noqa: E402
from app.ml.dataset import SnapshotError, read_snapshot  # noqa: E402
from app.ml.reporting import json_bytes, verify_outputs  # noqa: E402
from app.ml.series import ISTANBUL, half_day  # noqa: E402


def legacy_windows(snapshot):
    from tools import ml_data_check as legacy

    # Görüntüde URL yok; eski aracın yalnız envanterde kullandığı alan bilinmiyor.
    # Kimlik veya adres uydurulmaz. Fiyat maskesi eski hesaplayıcıya da uygulanır.
    market = [
        SimpleNamespace(
            **{
                **row.model_dump(),
                "price_kurus": None if half_day(row) else row.price_kurus,
            },
            source_url=None,
        )
        for row in snapshot.market_history
    ]
    adapted = SimpleNamespace(
        collection_runs=snapshot.collection_runs,
        listing_checks=snapshot.listing_checks,
        market_history=market,
    )
    groups = legacy.grouped_checks(adapted)
    slots = defaultdict(list)
    for run in snapshot.collection_runs:
        if run.trigger == "scheduled":
            slots[legacy.scheduled_slot(run.started_at)].append(run)
    closed = snapshot.captured_at.astimezone(ISTANBUL).date() - timedelta(days=1)
    expected = []
    for product in snapshot.products:
        for source in ("own", "cimri"):
            days, _ = (
                legacy.own_series(adapted, product, groups, slots, closed)
                if source == "own"
                else legacy.market_series(adapted, product, closed)
            )
            rows = legacy.windows_for(product.product_id, source, days)
            for row in rows:
                row.pop("partition")
            expected.extend(rows)
    return sorted(
        expected, key=lambda row: (row["product_id"], row["source"], row["anchor_day"])
    )


def check_labels(source, directory):
    snapshot, digest = read_snapshot(source)
    verify_outputs(directory, digest)
    actual = [
        json.loads(line)
        for line in (directory / "strict_windows.jsonl").read_bytes().splitlines()
    ]
    expected = legacy_windows(snapshot)
    # Tarih nesneleri ve JSON dizgileri aynı kanonik biçime çevrilir.
    if json_bytes(actual) != json_bytes(expected):
        raise ValueError("Sıkı pencere kayıtları eski hesaplayıcıyla uyuşmuyor")
    return len(actual)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--labels-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    utf8_output()
    try:
        count = check_labels(args.snapshot, args.labels_dir)
    except KeyboardInterrupt:
        print("Çapraz kontrol kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except (SnapshotError, ValueError, OSError, TypeError) as exc:
        print(f"Çapraz kontrol tamamlanamadı: {exc}", file=sys.stderr)
        return 1
    print(f"Sıkı çapraz kontrol doğrulandı: {count} pencere kaydı aynı.")
    print("Cimri yarım gün maskesi iki hesaplayıcıya da uygulandı. DB/ağ kullanılmadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
