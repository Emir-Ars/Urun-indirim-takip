"""Komut satırı araçlarının ortak çıktı yardımcıları.

Görev Zamanlayıcı'nın pythonw.exe ile penceresiz başlattığı komutlar (fiyat turu ve
zamanlanmış keşif) çıktısını bir log dosyasına da yazar; ekran akışları yoktur
(sys.stdout ve sys.stderr None). İkisi aynı yardımcıları kullanır.
"""

import contextlib
import sys
import traceback
from datetime import datetime
from pathlib import Path


def utf8_output() -> None:
    # Çıktı dosyaya yönlendirildiğinde de Türkçe karakterler bozulmasın; hata
    # çıktısı (stderr) da dahil. pythonw.exe altında akışlar hiç yoktur (None).
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def open_log(log_dir: Path, prefix: str):
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{prefix}_{datetime.now():%Y-%m-%d_%H-%M-%S}.log"
    # Satır satır yazılır: iş ortasında bilgisayar kapanırsa o ana kadarki
    # satırlar dosyada kalır.
    return path.open("a", encoding="utf-8", buffering=1)


class _Tee:
    """Yazılanı log dosyasına ve (varsa) asıl akışa gönderir."""

    def __init__(self, log, stream):
        self.log = log
        self.stream = stream

    def write(self, text):
        self.log.write(text)
        if self.stream is not None:
            self.stream.write(text)
        return len(text)

    def flush(self):
        self.log.flush()
        if self.stream is not None:
            self.stream.flush()


@contextlib.contextmanager
def tee_output(log):
    """stdout ve stderr'e (ilerleme, hata, traceback) yazılanı log'a da yazar."""
    saved = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Tee(log, saved[0]), _Tee(log, saved[1])
    try:
        yield
    finally:
        sys.stdout, sys.stderr = saved


def run_logged(log_dir: Path, prefix: str, title: str, work) -> int:
    """Zamanlanmış komutu log dosyasıyla çalıştırır ve çıkış kodunu döndürür.

    Ekransız çalışmanın tek yazılı kaydı log olduğu için log açılamazsa iş hiç
    başlamaz (1). `work` açılan log dosyasının yolunu alır ve çıkış kodu döndürür.
    """
    try:
        log = open_log(log_dir, prefix)
    except OSError as exc:
        print(f"Log dosyası açılamadı: {exc}", file=sys.stderr)
        return 1
    with log, tee_output(log):
        print(f"{title} · {datetime.now():%Y-%m-%d %H:%M:%S} (yerel saat)")
        try:
            code = work(Path(log.name))
        except Exception:
            # Program hatası: ayrıntısı ekransız çalışmada da kaybolmasın.
            traceback.print_exc()
            code = 1
        print(f"Çıkış kodu: {code}")
        return code
