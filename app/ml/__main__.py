"""ML veri hazırlığı komutları; veritabanına yazmaz."""

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

from app.console import utf8_output
from app.contracts import utc_now
from app.ml.dataset import (
    FILE_NAME,
    MlSnapshot,
    SnapshotError,
    build_snapshot,
    read_snapshot,
    write_snapshot,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser(
        "snapshot", help="Veritabanını okuma hesabıyla okuyup veri görüntüsü yaz"
    )
    snapshot.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    labels = commands.add_parser(
        "labels", help="Görüntüden günlük seri ve etiket raporu yaz"
    )
    labels.add_argument(
        "--snapshot", type=Path, required=True, metavar="GORUNTU_KLASORU"
    )
    labels.add_argument("--output-dir", type=Path, required=True, metavar="YENI_KLASOR")
    features = commands.add_parser(
        "features", help="Görüntüden geçmişe dayalı model girdileri yaz"
    )
    features.add_argument(
        "--snapshot", type=Path, required=True, metavar="GORUNTU_KLASORU"
    )
    features.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    split = commands.add_parser(
        "split", help="Etiket ve girdilerden tarih bölmesi ve kat raporu yaz"
    )
    split.add_argument(
        "--labels-dir", type=Path, required=True, metavar="ETIKET_KLASORU"
    )
    split.add_argument(
        "--features-dir", type=Path, required=True, metavar="GIRDI_KLASORU"
    )
    split.add_argument("--output-dir", type=Path, required=True, metavar="YENI_KLASOR")
    experiment = commands.add_parser(
        "experiment",
        help="Referans modelleri ve LightGBM'i doğrulama aylarında puanla",
    )
    experiment.add_argument(
        "--labels-dir", type=Path, required=True, metavar="ETIKET_KLASORU"
    )
    experiment.add_argument(
        "--features-dir", type=Path, required=True, metavar="GIRDI_KLASORU"
    )
    experiment.add_argument(
        "--split-dir", type=Path, required=True, metavar="BOLME_KLASORU"
    )
    experiment.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    freeze = commands.add_parser(
        "freeze",
        help="Deney sonucundan seçilen modeli saklı teste dokunmadan dondur",
    )
    freeze.add_argument(
        "--labels-dir", type=Path, required=True, metavar="ETIKET_KLASORU"
    )
    freeze.add_argument(
        "--features-dir", type=Path, required=True, metavar="GIRDI_KLASORU"
    )
    freeze.add_argument(
        "--split-dir", type=Path, required=True, metavar="BOLME_KLASORU"
    )
    freeze.add_argument(
        "--experiment-dir", type=Path, required=True, metavar="DENEY_KLASORU"
    )
    freeze.add_argument("--output-dir", type=Path, required=True, metavar="YENI_KLASOR")
    final_test = commands.add_parser(
        "final-test",
        help="Dondurulan modelle saklı testi yalnız bir kez aç ve puanla",
    )
    final_test.add_argument(
        "--labels-dir", type=Path, required=True, metavar="ETIKET_KLASORU"
    )
    final_test.add_argument(
        "--features-dir", type=Path, required=True, metavar="GIRDI_KLASORU"
    )
    final_test.add_argument(
        "--split-dir", type=Path, required=True, metavar="BOLME_KLASORU"
    )
    final_test.add_argument(
        "--model-dir", type=Path, required=True, metavar="MODEL_KLASORU"
    )
    final_test.add_argument(
        "--expected-model-sha256", required=True, metavar="ON_KAYITLI_SHA256"
    )
    final_test.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    shadow_predict = commands.add_parser(
        "shadow-predict",
        help="Dondurulan modelle kendi serimiz için değişmeyen tahmin kaydı yaz",
    )
    shadow_predict.add_argument(
        "--snapshot", type=Path, required=True, metavar="GORUNTU_KLASORU"
    )
    shadow_predict.add_argument(
        "--output-dir", type=Path, required=True, metavar="YENI_KLASOR"
    )
    shadow_predict.add_argument("--config", type=Path, metavar="AYAR_DOSYASI")
    shadow_predict.add_argument("--records-dir", type=Path, metavar="KAYIT_KLASORU")
    shadow_daily = commands.add_parser(
        "shadow-daily", help="Yeni veri görüntüsü alıp resmi gölge tahminlerini kaydet"
    )
    shadow_daily.add_argument("--scheduled", action="store_true")
    shadow_daily.add_argument("--config", type=Path, metavar="AYAR_DOSYASI")
    args = parser.parse_args(argv)
    utf8_output()
    if args.command == "labels":
        return run_labels(args.snapshot, args.output_dir)
    if args.command == "features":
        return run_features(args.snapshot, args.output_dir)
    if args.command == "split":
        return run_split(args.labels_dir, args.features_dir, args.output_dir)
    if args.command == "experiment":
        return run_experiment(
            args.labels_dir, args.features_dir, args.split_dir, args.output_dir
        )
    if args.command == "freeze":
        return run_freeze(
            args.labels_dir,
            args.features_dir,
            args.split_dir,
            args.experiment_dir,
            args.output_dir,
        )
    if args.command == "final-test":
        return run_reserved_test(
            args.labels_dir,
            args.features_dir,
            args.split_dir,
            args.model_dir,
            args.expected_model_sha256,
            args.output_dir,
        )
    if args.command == "shadow-predict":
        return run_shadow_predict(
            args.snapshot, args.output_dir, args.config, args.records_dir
        )
    if args.command == "shadow-daily":
        from app.ml.daily import run_daily

        return run_daily(args.config, args.scheduled, run_snapshot, run_shadow_predict)
    return run_snapshot(args.output_dir)


def run_snapshot(directory: Path) -> int:
    # Etiket komutu SQL veya bağlantı sürücüsünü bile yüklemesin.
    import psycopg
    from app.database.connection import API_DATABASE_URL_ENV, connect, database_url
    from app.database.ml_data import MlDataBusy, MlDataError, read_ml_data

    # Veritabanı okunmadan önce: yanlış klasör adı boşuna okuma yaptırmasın.
    if directory.exists():
        print(
            "Görüntü alınmadı: klasör zaten var; yeni bir klasör seç.", file=sys.stderr
        )
        return 1
    try:
        with connect(database_url(API_DATABASE_URL_ENV)) as conn:
            data = read_ml_data(conn)
        snapshot = build_snapshot(data.tables, utc_now(), data.schema_version)
        digest = write_snapshot(snapshot, directory)
        # Diske yazılan dosya, sonraki adımların okuyacağı yolla denetlenir.
        read_snapshot(directory)
    except MlDataBusy as exc:
        print(f"Görüntü alınmadı: {exc}", file=sys.stderr)
        return 3
    except FileExistsError:
        print(
            "Görüntü alınmadı: klasör zaten var; yeni bir klasör seç.", file=sys.stderr
        )
        return 1
    except (
        MlDataError,
        SnapshotError,
        RuntimeError,
        ValueError,
        OSError,
        psycopg.Error,
    ) as exc:
        print(f"Görüntü alınmadı: {exc}", file=sys.stderr)
        return 1
    print(f"Görüntü: {directory / FILE_NAME}")
    print(f"SHA-256: {digest}")
    _print_summary(snapshot)
    print("Dosya yeniden okunup doğrulandı. Veritabanına yazılmadı.")
    return 0


def run_labels(source: Path, directory: Path) -> int:
    from app.ml.labels import analyze_labels
    from app.ml.reporting import verify_outputs, write_outputs

    if directory.exists():
        print(
            "Etiketler hazırlanmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        snapshot, digest = read_snapshot(source)
        result = analyze_labels(snapshot)
        write_outputs(directory, digest, result)
        verify_outputs(directory, digest)
    except KeyboardInterrupt:
        print("Etiket hazırlığı kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except (SnapshotError, ValueError, OSError, TypeError) as exc:
        print(f"Etiketler hazırlanmadı: {exc}", file=sys.stderr)
        return 1
    print(f"Etiket raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {digest}")
    for source, title in (("own", "Kendi ölçümlerimiz"), ("cimri", "Cimri")):
        count = result[0]["sources"][source]["primary"]
        print(
            f"{title}: kullanılabilir {count['usable']} "
            f"· olumlu {count['positive']} · olumsuz {count['negative']} "
            f"· belirsiz {count['unknown']}"
        )
    print("Dosyalar doğrulandı. Model eğitilmedi; veritabanına bağlanılmadı.")
    return 0


def run_features(source: Path, directory: Path) -> int:
    from app.ml.features import analyze_features
    from app.ml.reporting import verify_feature_outputs, write_feature_outputs

    if directory.exists():
        print(
            "Girdiler hazırlanmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        snapshot, digest = read_snapshot(source)
        result = analyze_features(snapshot)
        write_feature_outputs(directory, digest, result)
        verify_feature_outputs(directory, digest)
    except KeyboardInterrupt:
        print("Girdi hazırlığı kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except (SnapshotError, ValueError, OSError, TypeError) as exc:
        print(f"Girdiler hazırlanmadı: {exc}", file=sys.stderr)
        return 1
    print(f"Girdi raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {digest}")
    for name, title in (("own", "Kendi ölçümlerimiz"), ("cimri", "Cimri")):
        count = result[0]["sources"][name]["rows"]
        print(f"{title}: girdi satırı {count}")
    print(f"Tanınmayan model ailesi: {len(result[0]['unknown_models'])}")
    print("Dosyalar ve girdi şeması doğrulandı. Etiket okunmadı; DB/ağ kullanılmadı.")
    return 0


def run_split(labels: Path, features: Path, directory: Path) -> int:
    from app.ml.splitting import build_split, load_split_inputs
    from app.ml.reporting import verify_split_outputs, write_split_outputs

    if directory.exists():
        print(
            "Bölme hazırlanmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        inputs = load_split_inputs(labels, features)
        plan = build_split(inputs.samples)
        write_split_outputs(directory, inputs, plan)
        verify_split_outputs(directory, inputs.snapshot_sha256, inputs.input_manifests)
    except KeyboardInterrupt:
        print("Bölme hazırlığı kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Bölme hazırlanmadı: {exc}", file=sys.stderr)
        return 1
    print(f"Bölme raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {inputs.snapshot_sha256}")
    print(
        f"Durum: {'sınırlı' if plan.report['status'] == 'limited' else 'yeterli'} "
        f"· kat sayısı {len(plan.folds)}"
    )
    print(
        f"Başlangıç ataması: {len(plan.assignments)} "
        f"· saklı test satırı {plan.report['partitions']['test_reserved']['rows']}"
    )
    if plan.report["limitations"]:
        print(
            "Sınırlamalar: "
            + "; ".join(
                plan.report["limitation_labels"][reason]
                for reason in plan.report["limitations"]
            )
        )
    print(
        "Dosyalar doğrulandı. Saklı test açılmadı; model eğitilmedi, "
        "gerçek tahmin puanı hesaplanmadı."
    )
    return 0


def run_experiment(labels: Path, features: Path, split: Path, directory: Path) -> int:
    if directory.exists():
        print(
            "Deney yapılmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        # numpy, scikit-learn ve LightGBM yalnız bu komutta yüklenir.
        from app.ml import experiment
        from app.ml.models import PREDICTION_NAMES
        from app.ml.reporting import verify_experiment_outputs, write_experiment_outputs

        inputs = experiment.load_experiment_inputs(labels, features, split)
        result = experiment.run_experiment(inputs.split, inputs.plan)
        write_experiment_outputs(directory, inputs, result)
        verify_experiment_outputs(directory, inputs)
    except KeyboardInterrupt:
        print("Deney kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except ImportError as exc:
        print(
            f"Deney yapılmadı: ML kütüphaneleri eksik ('.[ml]' kurulu mu?): {exc}",
            file=sys.stderr,
        )
        return 1
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Deney yapılmadı: {exc}", file=sys.stderr)
        return 1
    report = result.report
    combined, selection = report["combined"], report["selection"]
    print(f"Deney raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {inputs.snapshot_sha256}")
    print(
        f"Değerlendirilen kat: {selection['values']['ready_folds']} "
        f"/ {len(report['folds'])} · doğrulama satırı {combined['rows']}"
    )
    if combined["rows"]:
        print(f"Olumlu oranı (taban AP): %{100 * combined['positive_rate']:.2f}")
        for name in PREDICTION_NAMES:
            score = combined["scores"][name]
            average = score["average_precision"]
            print(
                f"  {name}: AP {'—' if average is None else f'{average:.4f}'} "
                f"· Brier {score['brier']:.4f} · log loss {score['log_loss']:.4f}"
            )
    titles = dict(
        met="karşılandı", not_met="karşılanmadı", not_evaluable="değerlendirilemedi"
    )
    print(f"LightGBM seçim ölçütü: {titles[selection['status']]} (yalnız öneri)")
    print(
        "Dosyalar doğrulandı. Saklı test açılmadı; kendi serimiz puanlanmadı; "
        "DB/ağ kullanılmadı."
    )
    return 0


def run_freeze(
    labels: Path, features: Path, split: Path, experiment: Path, directory: Path
) -> int:
    if directory.exists():
        print(
            "Model dondurulmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        # numpy, scikit-learn ve LightGBM yalnız bu komutta yüklenir.
        from app.ml import final
        from app.ml.experiment import load_experiment_inputs
        from app.ml.reporting import (
            MODEL_TITLES,
            SELECTION_TITLES,
            write_model_outputs,
        )

        inputs = load_experiment_inputs(labels, features, split)
        result = final.freeze_model(inputs, experiment)
        write_model_outputs(directory, inputs, result)
        digest = hashlib.sha256((directory / "manifest.json").read_bytes()).hexdigest()
        # Yazılan model, sonraki adımların açacağı yolla yeniden yüklenip denetlenir.
        final.load_frozen_model(directory, inputs, digest)
    except KeyboardInterrupt:
        print("Model dondurma kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except ImportError as exc:
        print(
            "Model dondurulmadı: ML kütüphaneleri eksik "
            f"('.[ml]' kurulu mu?): {exc}",
            file=sys.stderr,
        )
        return 1
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Model dondurulmadı: {exc}", file=sys.stderr)
        return 1
    slices = result.document["slices"]
    status = result.document["selection"]["status"]
    print(f"Model raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {inputs.snapshot_sha256}")
    print(
        f"Dondurulan model: {MODEL_TITLES[result.choice]} "
        f"(deney seçim ölçütü: {SELECTION_TITLES[status].lower()})"
    )
    for role, title in (("train", "Eğitim"), ("calibration", "Kalibrasyon")):
        item = slices[role]
        print(
            f"{title}: {item['rows']} satır · olumlu {item['positive']} "
            f"· {item['first_anchor']} – {item['last_anchor']}"
        )
    preserved = result.document["model"]["platt"]["order_preserved"]
    print(f"Platt sıralamayı koruyor: {'evet' if preserved else 'hayır'}")
    print(f"Model manifest SHA-256 (ön kayıt için): {digest}")
    print(
        "Dosyalar ve yeniden yükleme denetimi doğrulandı. Saklı test açılmadı; "
        "kendi serimiz puanlanmadı; DB/ağ kullanılmadı."
    )
    return 0


def run_reserved_test(
    labels: Path,
    features: Path,
    split: Path,
    model: Path,
    expected_sha256: str,
    directory: Path,
) -> int:
    if directory.exists():
        print(
            "Saklı test açılmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        # numpy, scikit-learn ve LightGBM yalnız bu komutta yüklenir.
        from app.ml import final
        from app.ml.experiment import load_experiment_inputs
        from app.ml.reporting import (
            MODEL_TITLES,
            SELECTION_TITLES,
            verify_final_test_outputs,
            write_final_test_outputs,
        )

        inputs = load_experiment_inputs(labels, features, split)
        # Model beklenen SHA-256'yı taşımıyorsa saklı test satırlarına hiç gelinmez.
        loaded = final.load_frozen_model(model, inputs, expected_sha256)
        result = final.run_final_test(inputs, loaded)
        write_final_test_outputs(directory, inputs, result)
        verify_final_test_outputs(directory, inputs, loaded.manifest_sha256)
    except KeyboardInterrupt:
        print("Saklı test kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except ImportError as exc:
        print(
            "Saklı test açılmadı: ML kütüphaneleri eksik "
            f"('.[ml]' kurulu mu?): {exc}",
            file=sys.stderr,
        )
        return 1
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Saklı test açılmadı: {exc}", file=sys.stderr)
        return 1
    report = result.report
    test, reading = report["reserved_test"], report["reading"]
    interval = report["bootstrap"]
    print(f"Saklı test raporu: {directory / 'report.md'}")
    print(f"Model manifest SHA-256: {report['model_manifest_sha256']}")
    print(f"Model: {MODEL_TITLES[report['choice']]}")
    print(
        f"Saklı test: {test['rows']} satır · olumlu {test['positives']} "
        f"· %{100 * test['positive_rate']:.2f} · {test['first_anchor']} "
        f"– {test['last_anchor']}"
    )
    for name in ("r0", report["choice"]):
        score = report["scores"][name]
        average = score["average_precision"]
        skill = score["brier_skill"]
        print(
            f"  {name}: AP {'—' if average is None else f'{average:.4f}'} "
            f"· Brier {score['brier']:.4f} · log loss {score['log_loss']:.4f} "
            f"· Brier skill {'—' if skill is None else f'{skill:.4f}'}"
        )
    difference = interval["point_difference"]
    if difference is None:
        print(
            f"AP farkı (model − R0): hesaplanamadı ({', '.join(interval['reasons'])})"
        )
    elif interval["lower"] is None:
        print(f"AP farkı (model − R0): {difference:.4f} · aralık hesaplanamadı")
    else:
        print(
            f"AP farkı (model − R0): {difference:.4f} "
            f"· %95 aralık [{interval['lower']:.4f}, {interval['upper']:.4f}]"
        )
    titles = {key: value.lower() for key, value in SELECTION_TITLES.items()}
    print(f"Okuma koşulları: {titles[reading['status']]} (yalnız bilgi)")
    print(
        "Dosyalar doğrulandı. Saklı test bu komutla açıldı; model değişmedi. "
        "Kendi serimiz puanlanmadı; DB/ağ kullanılmadı."
    )
    return 0


def run_shadow_predict(
    source: Path,
    directory: Path,
    config_path: Path | None,
    records_override: Path | None,
) -> int:
    from filelock import Timeout

    if directory.exists():
        print(
            "Tahmin yazılmadı: klasör zaten var; yeni bir klasör seç.",
            file=sys.stderr,
        )
        return 1
    try:
        # numpy, scikit-learn ve LightGBM yalnız bu komutta yüklenir.
        from app.ml import shadow

        config = shadow.load_config(config_path)
        records_dir = records_override or shadow.resolve_path(config.records_dir)
        snapshot, digest = read_snapshot(source)
        with shadow.record_lock(records_dir):
            if directory.exists():
                raise FileExistsError("Tahmin klasörü zaten var")
            model = shadow.load_model(config)
            recorded = shadow.recorded_keys(records_dir, config.model_manifest_sha256)
            result = shadow.build_shadow_predictions(
                snapshot, digest, model, config.start_day, recorded
            )
            if not result.rows:
                print(
                    f"Yeni tahmin yok ({result.skipped_recorded} gün zaten kayıtlı); "
                    "klasör oluşturulmadı."
                )
                return 0
            shadow.write_shadow_outputs(directory, result, model, config.start_day)
            manifest, _ = shadow.read_shadow_outputs(directory)
    except Timeout:
        print(
            "Tahmin yazılmadı: başka bir gölge tahmin kaydı sürüyor.", file=sys.stderr
        )
        return 3
    except KeyboardInterrupt:
        print("Tahmin kaydı kullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except ImportError as exc:
        print(
            "Tahmin yazılmadı: ML kütüphaneleri eksik " f"('.[ml]' kurulu mu?): {exc}",
            file=sys.stderr,
        )
        return 1
    except (SnapshotError, ValueError, OSError, TypeError, KeyError) as exc:
        print(f"Tahmin yazılmadı: {exc}", file=sys.stderr)
        return 1
    summary = manifest["summary"]
    print(f"Tahmin raporu: {directory / 'report.md'}")
    print(f"Görüntü SHA-256: {digest} · son kapanmış gün: {result.last_closed_day}")
    print(f"Model manifest SHA-256: {manifest['model_manifest_sha256']}")
    print(
        f"Yeni kayıt: {summary['rows']} · olasılık üretilen: {summary['predicted']} "
        f"· gösterilebilir: {summary['showable']} "
        f"· daha önce kayıtlı: {summary['skipped_recorded']}"
    )
    if shadow.is_official(directory, records_dir):
        print("Resmi kayıt klasörüne yazıldı.")
    else:
        print(
            f"Deneme çıktısı: resmi kayıt düzenine ({records_dir}/tahmin_*) "
            "uymuyor; kayıt sayılmaz."
        )
    print(
        "Dosyalar doğrulandı. Ekranda tahmin yok; tahmin aşamasında "
        "veritabanı ve ağ kullanılmadı."
    )
    return 0


def _print_summary(snapshot: MlSnapshot) -> None:
    captured = snapshot.captured_at.isoformat().replace("+00:00", "Z")
    print(f"Şema sürümü: {snapshot.schema_version}; okuma anı (UTC): {captured}")
    print(
        f"Ürün: {len(snapshot.products)} "
        f"(etkin {sum(row.active for row in snapshot.products)}); "
        f"sayfa: {len(snapshot.listings)} "
        f"(etkin {sum(row.active for row in snapshot.listings)})"
    )
    statuses = Counter(run.status for run in snapshot.collection_runs)
    print(
        f"Tur: {len(snapshot.collection_runs)} "
        f"(tamamlanan {statuses['completed']}, "
        f"yarıda kalan {statuses['interrupted']}); "
        f"sayfa sonucu: {len(snapshot.listing_checks)}"
    )
    market = snapshot.market_history
    print(
        f"Cimri: {len(market)} satır, "
        f"{len({row.product_id for row in market})} ürün "
        f"(eksik fiyat {sum(row.price_kurus is None for row in market)})"
    )


if __name__ == "__main__":
    sys.exit(main())
