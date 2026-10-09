"""Bütün testlerin ortak hazırlığı ve emniyet kemerleri.

Ağ: otomatik testler internete çıkmaz. Her testte curl_cffi ve HTTPX'in gerçek
isteği kesilir; süreç içindeki ASGI ve sahte HTTPX transport'ları çalışabilir.

Veritabanı: testler yalnızca TEST_DATABASE_URL'deki, adı `_test` ile biten
veritabanını kullanır; gerçek veri bulunan veritabanına dokunulmaz. Her testin
başında DATABASE_URL ve API_DATABASE_URL silinir; komut satırını deneyen test
gereken adresi kendisi
TEST_DATABASE_URL'e çevirir. `db` fixture'ı her testten önce `public` şemasını
silip boş olarak yeniden kurar.
"""

import os
from pathlib import Path

import httpx
import pytest
from curl_cffi import requests as curl_requests

from app.database.connection import connect
from app.database.migrate import migrate

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
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", _no_httpx_request)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", _no_async_httpx_request
    )


def _no_httpx_request(self, request):
    _no_internet(self, request.method, request.url)


async def _no_async_httpx_request(self, request):
    _no_internet(self, request.method, request.url)


@pytest.fixture(autouse=True)
def _no_production_database_url(monkeypatch):
    """Kalıcı DATABASE_URL (gerçek veritabanı) hiçbir teste sızmasın.

    Komut satırını deneyen test onu kendi içinde TEST_DATABASE_URL'e çevirir
    (monkeypatch.setenv bu fixture'dan sonra çalışır); çevirmeyi unutan test
    "DATABASE_URL tanımlı değil" hatasıyla düşer.
    """
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("API_DATABASE_URL", raising=False)


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


@pytest.fixture
def api_db(request):
    url = os.getenv("TEST_API_DATABASE_URL", "").strip()
    if not url:
        if os.getenv("CI"):
            pytest.fail("CI'da TEST_API_DATABASE_URL tanımlı olmalı")
        pytest.skip("TEST_API_DATABASE_URL tanımlı değil; API rolü testi atlandı")
    conn = connect(url)
    try:
        name = ensure_test_database(conn)
        user = conn.execute("SELECT current_user").fetchone()[0]
        if user != "fiyat_takip_api_test":
            pytest.fail("API testi yalnız fiyat_takip_api_test hesabını kullanabilir")
        owner = request.getfixturevalue("db")
        if name != owner.execute("SELECT current_database()").fetchone()[0]:
            pytest.fail("İki test bağlantısı aynı _test veritabanını kullanmalı")
        migrate(owner)
        setup = Path(__file__).resolve().parents[1] / "scripts/api_okuma_rolu.sql"
        owner.execute(setup.read_text(encoding="utf-8"))
        yield conn
    finally:
        conn.close()
