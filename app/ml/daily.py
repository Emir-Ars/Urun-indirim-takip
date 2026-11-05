"""Günlük gölge akışı: tur dışında salt okunur görüntü, ardından tahmin kaydı."""

import os
import sys
from time import monotonic, sleep

from app.console import run_logged
from app.contracts import utc_now
from app.scrape_lock import ScrapeBusy, scrape_lock
from app.settings import Settings

WAIT_SECONDS = 5 * 60
MAX_WAIT_SECONDS = 90 * 60


def snapshot_when_idle(directory, snapshot_work):
    """Tarama kilidi ve DB'deki running kaydı bitene kadar sınırlı bekler."""
    deadline = monotonic() + MAX_WAIT_SECONDS
    while True:
        try:
            # Tur görüntü okunurken başlayamasın; model hesabı bu kilidi tutmaz.
            with scrape_lock():
                code = snapshot_work(directory)
            if code != 3:
                return code
        except ScrapeBusy:
            print("Tarama kilidi dolu; görüntü için tur/keşif bitişi bekleniyor.")
        remaining = deadline - monotonic()
        if remaining <= 0:
            print(
                "Görüntü alınmadı: 90 dakikalık bekleme sınırı doldu.", file=sys.stderr
            )
            return 3
        delay = min(WAIT_SECONDS, remaining)
        print(f"Görüntü için {delay:g} saniye sonra yeniden denenecek.")
        sleep(delay)


def run_daily(config_path, scheduled, snapshot_work, predict_work):
    """Elle ve zamanlanmış çalışma aynı komutları, kilitleri ve logu kullanır."""

    def work(log_path):
        try:
            from app.ml.shadow import load_config, resolve_path
            from app.ml.series import ISTANBUL

            print(f"Log: {log_path}")
            if not os.getenv("API_DATABASE_URL", "").strip():
                raise RuntimeError(
                    "API_DATABASE_URL tanımlı değil; okuma hesabı gerekli."
                )
            config = load_config(config_path)
            records_dir = resolve_path(config.records_dir)
            stamp = utc_now().astimezone(ISTANBUL).strftime("%Y%m%d_%H%M%S_%f")
            source = records_dir / "goruntuler" / f"veri_{stamp}"
            target = records_dir / f"tahmin_{stamp}"
            print("1/2 — Salt okunur veri görüntüsü alınıyor.")
            code = snapshot_when_idle(source, snapshot_work)
            if code:
                return code
            print("2/2 — Görüntüden resmi tahmin kaydı hazırlanıyor.")
            return predict_work(source, target, config_path, None)
        except KeyboardInterrupt:
            print(
                "Günlük gölge çalışması kullanıcı tarafından durduruldu.",
                file=sys.stderr,
            )
            return 130
        except (
            ImportError,
            RuntimeError,
            ValueError,
            OSError,
            TypeError,
            KeyError,
        ) as exc:
            print(f"Günlük gölge çalışması tamamlanamadı: {exc}", file=sys.stderr)
            return 1

    mode = "zamanlanmış" if scheduled else "elle"
    return run_logged(
        Settings().log_dir, "golge", f"Günlük gölge tahmini ({mode})", work
    )
