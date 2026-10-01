"""Komut satırı araçlarının ortak çıktı yardımcıları.

Görev Zamanlayıcı'nın pythonw.exe ile penceresiz başlattığı komutlar (fiyat turu ve
zamanlanmış keşif) çıktısını bir log dosyasına da yazar; ekran akışları yoktur
(sys.stdout ve sys.stderr None). İkisi aynı yardımcıları kullanır.
"""

import contextlib
import sys
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
