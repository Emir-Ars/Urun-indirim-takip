"""Veritabanı testlerinin ortak hazırlığı.

Testler yalnızca TEST_DATABASE_URL'deki, adı `_test` ile biten veritabanını
kullanır; gerçek veri bulunan veritabanına dokunulmaz. Her testten önce
`public` şeması silinip boş olarak yeniden kurulur.
"""

import os

import pytest

from app.database.connection import connect


@pytest.fixture
def db():
    url = os.getenv("TEST_DATABASE_URL", "").strip()
    if not url:
        if os.getenv("CI"):
            pytest.fail("CI'da TEST_DATABASE_URL tanımlı olmalı")
        pytest.skip("TEST_DATABASE_URL tanımlı değil; veritabanı testi atlandı")
    conn = connect(url)
    try:
        name = conn.execute("SELECT current_database()").fetchone()[0]
        if not name.endswith("_test"):
            pytest.exit(
                f"Güvenlik: '{name}' bir test veritabanı değil (adı _test ile bitmeli)",
                returncode=1,
            )
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        yield conn
    finally:
        conn.close()
