"""Bütün testlerin ortak hazırlığı ve emniyet kemerleri.

Ağ: otomatik testler internete çıkmaz. Her testte curl_cffi'nin gerçek isteği
kesilir; sahte istemci vermeyi ya da bir yöntemi yamalamayı unutan test siteye
gitmek yerine hemen başarısız olur.

Veritabanı: testler yalnızca TEST_DATABASE_URL'deki, adı `_test` ile biten
veritabanını kullanır; gerçek veri bulunan veritabanına dokunulmaz. Her testin
başında DATABASE_URL silinir; komut satırını deneyen test onu kendisi
TEST_DATABASE_URL'e çevirir. `db` fixture'ı her testten önce `public` şemasını
silip boş olarak yeniden kurar.
"""

import os

import pytest
from curl_cffi import requests as curl_requests

from app.database.connection import connect

# Advisory kilit numaraları veritabanında ortaktır: migrate.py (_LOCK_ID
# 2026_0928) ve runs.py (_RUN_LOCK_ID 2026_0929) ile aynı olmamalı; testler
# kendi bağlantılarında o kilitleri alırken bu kilit tutuluyor.
TEST_DATABASE_LOCK = 2026_0930


def _no_internet(self, method=None, url=None, *args, **kwargs):
    # pytest.fail BaseException'dan türer: üretim kodundaki `except Exception`
    # blokları (ör. turda beklenmeyen sayfa hatası) onu yutup testi geçiremez.
    pytest.fail(
        f"Otomatik test internete çıkmaya çalıştı: {method} {url} "
        "(sahte istemci veya yama kullanın)"
    )


@pytest.fixture(autouse=True)
def _block_internet(monkeypatch):
    """Gerçek curl_cffi isteğini keser; sahte istemci kullanan testler etkilenmez.

    Session.get/post ve modül düzeyindeki curl_cffi.requests.get/request de
    sonunda Session.request'i çağırdığı için onlar da kesilir.
    """
    monkeypatch.setattr(curl_requests.Session, "request", _no_internet)
    monkeypatch.setattr(curl_requests.AsyncSession, "request", _no_internet)


@pytest.fixture(autouse=True)
def _no_production_database_url(monkeypatch):
    """Kalıcı DATABASE_URL (gerçek veritabanı) hiçbir teste sızmasın.

    Komut satırını deneyen test onu kendi içinde TEST_DATABASE_URL'e çevirir
    (monkeypatch.setenv bu fixture'dan sonra çalışır); çevirmeyi unutan test
    "DATABASE_URL tanımlı değil" hatasıyla düşer.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)


def ensure_test_database(conn) -> str:
    """Bağlantı adı `_test` ile biten veritabanında değilse pytest'i durdurur.

    `db` fixture'ı şemayı sildiği için bu denetim gerçek veriyi koruyan son
    engeldir; adı döndürür.
    """
    name = conn.execute("SELECT current_database()").fetchone()[0]
    if not name.endswith("_test"):
        pytest.exit(
            f"Güvenlik: '{name}' bir test veritabanı değil (adı _test ile bitmeli)",
            returncode=1,
        )
    return name


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        if os.getenv("CI"):
            pytest.fail("CI'da TEST_DATABASE_URL tanımlı olmalı")
        pytest.skip("TEST_DATABASE_URL tanımlı değil; veritabanı testi atlandı")
    conn = connect(url)
    try:
        ensure_test_database(conn)
        # Aynı anda iki pytest çalışırsa biri diğerinin şemasını silmesin: kilit
        # test bitene (bağlantı kapanana) kadar tutulur, ikincisi bekler (en çok
        # 30 sn, bağlantının lock_timeout ayarı; sonra hata verir).
        conn.execute("SELECT pg_advisory_lock(%s)", (TEST_DATABASE_LOCK,))
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        yield conn
    finally:
        conn.close()
