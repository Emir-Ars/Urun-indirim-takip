"""Alan adı sınırı, tekrar ve Chrome taklidi içeren HTTP taşıması."""

import json
import time
from urllib.parse import urljoin, urlsplit

from curl_cffi import requests as curl_requests
from curl_cffi.requests.cookies import CookieConflict
from curl_cffi.requests.exceptions import RequestException

from app.contracts import public_url
from app.settings import Runtime

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
# Yönlendirmeler elle izlenir. Her yönlendirme ayrı istek sayılır: bütçeden
# düşer, 3 sn aralık uygulanır ve hedef alan adı yeniden denetlenir (izinsiz
# alana yönlendirme = invalid_host). Bundan fazlası "redirect" hatasıdır.
MAX_REDIRECTS = 3
# Son istek zamanı alan adı başına ve süreç genelinde tutulur: her bağlantı için
# yeni istemci açılsa da aynı siteye istekler arasındaki bekleme korunur.
_LAST_REQUEST: dict[str, float] = {}


class FetchError(Exception):
    """Sayfa okunamadı; `code` hatanın türü, mesaj ayrıntısıdır.

    Kod, toplama turunda `listing_checks.error_code` sütununa, keşifte rapora
    aynen yazılır. Hiçbiri fiyat veya Tükendi yerine geçmez. Üretilen kodlar:

    HTTP katmanı (bu dosya):
      invalid_url        adres düz bir HTTPS adresi değil (kullanıcı adı, port
                         veya # parçası içeriyor ya da şeması https değil)
      invalid_host       adres veya yönlendirme hedefi platformun alan adı dışında
      limit              istek bütçesi doldu (bütçeyi yalnız keşif verir)
      redirect           yönlendirme hedefi eksik veya 3'ten fazla yönlendirme
      blocked            kaynak 401/403/418/429 döndürdü; tekrar denenmez
      http_error         diğer 4xx (ör. 404); kalıcı sayılır, tekrar denenmez
      network            bağlantı hatası, zaman aşımı veya 5xx; tekrarlardan
                         sonra da sürdü
      too_large          yanıt 8 MB sınırını aştı
      parse              yanıt UTF-8 metin veya JSON nesnesi değil
    Platform adaptörleri, keşif ve ortak kimlik kuralı:
      parse              sayfa/API verisi beklenen yapıda değil ya da teklif
                         Pydantic doğrulamasından geçmedi (scraper/base.py)
      identity           sayfa hedef ürün değil: model, kapasite, dışlanan ifade,
                         ağ türü ya da yenilenmiş/aksesuar/yurt dışı sürüm
                         (parsing.identify; keşif ve scraper ortak)
      no_eligible_offer  uygun satılabilir teklif yok, ama Tükendi için açık
                         stok sinyali de yok (Tükendi uydurulmaz)
      api_error          Hepsiburada satıcı veya fiyat API'si başarısız ya da
                         satılabilir teklif için boş yanıt verdi
      plugin             platform adaptörü yüklenemedi (scraper/factory.py)

    Toplama turu (app/collection/service.py) FetchError dışındaki hatalara aynı
    sütunda kendi kodlarını verir: validation (gözlem doğrulanamadı veya başka
    sayfaya ait), unexpected (beklenmeyen istisna), storage (veritabanı değeri
    reddetti).
    """

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class PageClient:
    """Tek platformun alan adlarına giden istemci.

    `request_budget` verilirse (keşif) yeniden denemeler ve yönlendirmeler
    dahil gerçek HTTP denemeleri `request_count` ile sayılır ve sınırlanır.
    Dışarıdan `client` verilmezse curl_cffi oturumu Chrome taklidiyle açılır
    ve `close()` onu kapatır; verilen istemciyi çağıran taraf kapatır.
    """

    def __init__(
        self,
        hosts: list[str],
        runtime: Runtime,
        client=None,
        request_budget: int | None = None,
    ):
        self.hosts = set(hosts)
        self.runtime = runtime
        self._owned = client is None
        self.client = client or curl_requests.Session(
            impersonate="chrome120",
            allow_redirects=False,
            headers={
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        self.request_budget = request_budget
        self.request_count = 0

    def _allowed(self, url: str) -> None:
        try:
            public_url(url)
        except ValueError as exc:
            raise FetchError("invalid_url", str(exc)) from exc
        parts = urlsplit(url)
        if parts.hostname not in self.hosts:
            # Hedef, blocked hatasındaki gibi yazılır (sorgu metni hariç): yönlendirme
            # nereye gitmişti sorusu tur kaydından yanıtlanabilsin.
            raise FetchError(
                "invalid_host",
                f"İstek platformun alan adı dışında ({parts.hostname}{parts.path})",
            )

    def _wait_for_interval(self, host: str) -> None:
        delay = self.runtime.request_interval_seconds - (
            time.monotonic() - _LAST_REQUEST.get(host, float("-inf"))
        )
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST[host] = time.monotonic()

    @staticmethod
    def _body(response) -> bytes:
        body = response.content
        if len(body) > MAX_RESPONSE_BYTES:
            raise FetchError("too_large", "Yanıt 8 MB sınırını aştı")
        return body

    def _request(self, method: str, url: str, **kwargs) -> bytes:
        """İsteği gönderir ve başarılı yanıtın gövdesini (8 MB denetimli) döndürür.

        Adres, ilk turda `target == url` olduğundan döngüdeki ilk `_allowed`
        çağrısıyla istek gitmeden denetlenir. Döngü en az bir kez döner
        (Runtime.request_attempts >= 1) ve son deneme her zaman ya döner ya da
        FetchError verir; döngüden sonrasına ulaşılmaz.
        """
        for attempt in range(self.runtime.request_attempts):
            target = url
            try:
                for _ in range(MAX_REDIRECTS + 1):
                    self._allowed(target)
                    if (
                        self.request_budget is not None
                        and self.request_count >= self.request_budget
                    ):
                        raise FetchError("limit", "HTTP istek sınırı doldu")
                    self._wait_for_interval(urlsplit(target).hostname)
                    self.request_count += 1
                    response = self.client.request(
                        method,
                        target,
                        timeout=self.runtime.request_timeout_seconds,
                        allow_redirects=False,
                        **kwargs,
                    )
                    if response.status_code in REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("redirect", "Yönlendirme hedefi eksik")
                        target = urljoin(target, location)
                        continue
                    if response.status_code in (401, 403, 418, 429):
                        parts = urlsplit(target)
                        raise FetchError(
                            "blocked",
                            f"Kaynak HTTP {response.status_code} döndürdü "
                            f"({parts.hostname}{parts.path})",
                        )
                    # 5xx geçici sayılır: ağ hatası gibi aşağıda tekrar denenir;
                    # son denemede de sürerse kod "network" olur. Diğer 4xx
                    # kalıcıdır, tekrar denenmez.
                    if response.status_code >= 500:
                        raise RequestException(
                            f"Kaynak HTTP {response.status_code} döndürdü",
                            response=response,
                        )
                    if response.status_code >= 400:
                        raise FetchError(
                            "http_error",
                            f"Kaynak HTTP {response.status_code} döndürdü",
                        )
                    return self._body(response)
                raise FetchError("redirect", "Çok fazla yönlendirme")
            # FetchError (blocked, limit, redirect, too_large…) burada
            # yakalanmaz; tekrar denenmeden olduğu gibi yükselir.
            except RequestException as exc:
                if attempt + 1 == self.runtime.request_attempts:
                    raise FetchError("network", str(exc)) from exc
                # Üstel bekleme: 1 sn, sonra 2 sn. request_attempts en çok 3
                # olduğundan (app/settings.py) daha uzun bekleme oluşmaz.
                time.sleep(2**attempt)

    def get(self, url: str, *, headers: dict | None = None) -> str:
        body = self._request("GET", url, headers=headers)
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FetchError("parse", "Kaynak UTF-8 metin döndürmedi") from exc

    @staticmethod
    def _json_object(body: bytes) -> dict:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError) as exc:
            raise FetchError("parse", "Kaynak geçerli JSON döndürmedi") from exc
        if not isinstance(data, dict):
            raise FetchError("parse", "Kaynak JSON nesnesi döndürmedi")
        return data

    def get_json(self, url: str, *, headers: dict | None = None) -> dict:
        return self._json_object(self._request("GET", url, headers=headers))

    def post_json(
        self, url: str, payload: dict, *, headers: dict | None = None
    ) -> dict:
        return self._json_object(
            self._request("POST", url, json=payload, headers=headers)
        )

    def cookie(self, name: str) -> str | None:
        try:
            return self.client.cookies.get(name)
        except (KeyError, TypeError, ValueError, CookieConflict):
            # Aynı adlı çerez iki alt alan adında farklı değerle varsa hata verir;
            # çağıran taraf çerez yokmuş gibi devam eder.
            return None

    def close(self):
        if self._owned:
            self.client.close()
