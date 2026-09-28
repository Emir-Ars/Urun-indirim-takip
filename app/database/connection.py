"""PostgreSQL bağlantısı. Adres ortam değişkeninden okunur, şifre pgpass.conf'tadır."""

import os

import psycopg

DATABASE_URL_ENV = "DATABASE_URL"


def database_url(env: str = DATABASE_URL_ENV) -> str:
    url = os.getenv(env, "").strip()
    if not url:
        raise RuntimeError(
            f"{env} tanımlı değil (ör. "
            "postgresql://fiyat_takip@localhost:5432/fiyat_takip)"
        )
    return url


def connect(url: str) -> psycopg.Connection:
    """Oturum saati UTC olan bağlantı.

    Her komut kendi başına kalıcı olur (autocommit); birlikte kalıcı olması
    gereken komutlar çağıran tarafta `with conn.transaction():` içinde çalışır.
    Süre sınırları: sunucuya bağlanma 10 sn; bir tablo kilidini bekleme 30 sn
    (ör. pgAdmin'de yarım bırakılmış bir işlem zamanlanmış turu sonsuza kadar
    bekletmesin, hata versin).
    """
    return psycopg.connect(
        url,
        autocommit=True,
        application_name="fiyat_takip",
        connect_timeout=10,
        options="-c TimeZone=UTC -c lock_timeout=30s",
    )
