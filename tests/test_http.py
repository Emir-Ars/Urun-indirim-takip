"""HTTP katmanı (PageClient), platform adaptörü yükleyici ve HTTP mimari kuralı.

Testler internete çıkmaz: istemci yerine sahte oturum verilir; bekleme için
gerçek `time.sleep` yerine çağrıları kaydeden bir liste kullanılır.
"""

import ast
import sys
import types
from pathlib import Path

import pytest
from curl_cffi.curl import CURL_WRITEFUNC_ERROR
from curl_cffi.requests.exceptions import RequestException

import app.scraper.http as http
import app.scraper.factory as factory
from app.contracts import DiscoveryConfig, DiscoveryTarget
from app.discovery.base import error_code
from app.discovery.trendyol import Discovery as TrendyolDiscovery
from app.scraper.base import BaseScraper
from app.scraper.factory import create_scraper
from app.scraper.hepsiburada_scraper import Scraper as HepsiburadaScraper
from app.scraper.http import FetchError, PageClient
from app.scraper.trendyol_scraper import Scraper as TrendyolScraper
from app.settings import Runtime

APP = Path(__file__).parents[1] / "app"
TRENDYOL = "https://www.trendyol.com/"


@pytest.fixture(autouse=True)
def slept(monkeypatch):
    """Hiçbir test gerçekten beklemez; `time.sleep` çağrıları listeye yazılır.

    Alan adı başına son istek zamanı da testler arasında paylaşılmasın.
    """
    calls = []
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    monkeypatch.setattr(http.time, "sleep", calls.append)
    return calls


def target(model="iPhone 16"):
    return DiscoveryTarget(key="apple_iphone_16", brand="Apple", model=model)


# Her isteğe 418 döndüren sahte oturum (test_discovery.py'den taşındı).
class Response:
    status_code = 418
    headers = {}
    content = b""


class Session:
    def request(self, *args, **kwargs):
        return Response()

    def close(self):
        pass


class Reply:
    """Sahte yanıt. Başlık anahtarı küçük harftir: http.py "location" okur."""

    def __init__(self, status=200, content=b"{}", location=None):
        self.status_code = status
        self.content = content
        self.headers = {} if location is None else {"location": location}

    def iter_chunks(self):
        for offset in range(0, len(self.content), 16384):
            yield self.content[offset : offset + 16384]


class ChunkedReply:
    def __init__(self, chunks, status=200, location=None):
        self.chunks = chunks
        self.status_code = status
        self.headers = {} if location is None else {"location": location}
        self.delivered = 0

    @property
    def content(self):
        raise AssertionError("Yanıtın tamamı belleğe alınmamalı")

    def iter_chunks(self):
        for chunk in self.chunks:
            self.delivered += 1
            yield chunk


class Recorder:
    """Verilen yanıtları sırayla döndürür (istisnayı fırlatır), çağrıları kaydeder."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        callback = kwargs.get("content_callback")
        if callback is not None:
            for chunk in reply.iter_chunks():
                if isinstance(chunk, Exception):
                    raise chunk
                if callback(chunk) == CURL_WRITEFUNC_ERROR:
                    raise RequestException("Yanıt aktarımı durduruldu", response=reply)
        return reply

    def close(self):
        self.closed = True


def page_client(session, request_budget=None, **runtime):
    settings = {"request_interval_seconds": 0, **runtime}
    return PageClient(
        ["www.trendyol.com"],
        Runtime(**settings),
        client=session,
        request_budget=request_budget,
    )


def call(pages, method, url=TRENDYOL):
    if method == "post_json":
        return pages.post_json(url, {"q": "iphone"})
    return getattr(pages, method)(url)


# --- test_discovery.py'den taşınan testler ---------------------------------


def test_request_interval_is_shared_between_clients(monkeypatch):
    # Canlı kontrol her bağlantı için yeni istemci açıyor; aynı siteye iki istek
    # arasında bekleme yine uygulanmalı, başka siteye geçerken beklenmemeli.
    slept = []
    monkeypatch.setattr(http, "_LAST_REQUEST", {})
    monkeypatch.setattr(http.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(http.time, "sleep", slept.append)

    class Ok:
        status_code = 200
        headers = {}
        content = b"ok"

    class Quiet(Session):
        def request(self, *args, **kwargs):
            if kwargs.get("content_callback"):
                kwargs["content_callback"](b"ok")
            return Ok()

    runtime = Runtime(request_interval_seconds=3)
    for host in ("www.trendyol.com", "www.trendyol.com", "www.hepsiburada.com"):
        PageClient([host], runtime, client=Quiet()).get(f"https://{host}/")
    assert slept == [3.0]


def test_cookie_conflict_is_treated_as_missing():
    # curl_cffi, aynı adlı çerez iki alt alan adında farklıysa hata verir.
    from curl_cffi.requests.cookies import CookieConflict

    class Jar:
        def get(self, name):
            raise CookieConflict("iki alan adında aynı çerez")

    class WithCookies(Session):
        cookies = Jar()

    client = PageClient(
        ["www.hepsiburada.com"], Runtime(request_interval_seconds=0), WithCookies()
    )
    assert client.cookie("hbus_anonymousId") is None


def test_http_418_is_blocked():
    client = PageClient(
        ["www.trendyol.com"], Runtime(request_interval_seconds=0), client=Session()
    )
    with pytest.raises(FetchError) as error:
        client.get("https://www.trendyol.com/sr?q=iphone")
    assert error.value.code == "blocked"
    # Raporda engelin türü ve yeri görünür: 429 hız sınırı, 403 erişim reddi.
    assert error_code(error.value) == (
        "blocked: Kaynak HTTP 418 döndürdü (www.trendyol.com/sr)"
    )
    assert error_code(KeyError("key")) == "KeyError"


def test_discovery_budget_is_enforced_by_http_layer():
    # Keşifte ayrı sayaç yok; bütçe PageClient'a keşif ayarından verilir.
    discovery = TrendyolDiscovery(
        target(),
        DiscoveryConfig(targets=[], max_requests=1),
        Runtime(request_interval_seconds=0, request_attempts=1),
    )
    discovery.pages.client = Session()
    with pytest.raises(FetchError) as first:
        discovery.get("https://www.trendyol.com/")
    assert first.value.code == "blocked"
    with pytest.raises(FetchError) as second:
        discovery.get("https://www.trendyol.com/")
    assert second.value.code == "limit"
    assert discovery.pages.request_count == 1
    discovery.close()


def test_http_budget_counts_actual_attempts(slept):
    # Bütçe gönderilen her HTTP isteğini sayar: 5xx sonrası tekrar ve her
    # yönlendirme ayrı istektir (app/discovery/base.py'deki vaat).
    retried = Recorder(Reply(503), Reply(200))
    pages = page_client(retried, request_attempts=2)
    pages.get(TRENDYOL)
    assert pages.request_count == 2
    assert slept == [1]

    redirected = Recorder(Reply(302, location="/yeni"), Reply(200))
    pages = page_client(redirected)
    pages.get(TRENDYOL)
    assert pages.request_count == 2

    # Bütçe tekrarın ortasında dolarsa ikinci istek gitmez; hata "limit" olur.
    limited = Recorder(Reply(503), Reply(200))
    pages = page_client(limited, request_budget=1, request_attempts=2)
    with pytest.raises(FetchError) as error:
        pages.get(TRENDYOL)
    assert error.value.code == "limit"
    assert pages.request_count == 1
    assert len(limited.calls) == 1


# --- Hata kodları ------------------------------------------------------------


@pytest.mark.parametrize(
    "method, reply, code",
    [
        ("get", Reply(404), "http_error"),
        ("get", Reply(content=b"\xff"), "parse"),
        ("get_json", Reply(content=b"\xff"), "parse"),
        ("get_json", Reply(content=b"<html>"), "parse"),
        ("get_json", Reply(content=b"[]"), "parse"),
        ("post_json", Reply(content=b"<html>"), "parse"),
        ("post_json", Reply(content=b"[]"), "parse"),
    ],
)
def test_response_error_codes(method, reply, code):
    session = Recorder(reply)
    with pytest.raises(FetchError) as error:
        call(page_client(session, request_attempts=3), method)
    assert error.value.code == code
    assert len(session.calls) == 1  # kalıcı hata tekrar denenmez


@pytest.mark.parametrize("method", ["get", "get_json", "post_json"])
def test_response_over_8_mb_is_too_large(method):
    session = Recorder(Reply(content=b"x" * (http.MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(FetchError) as error:
        call(page_client(session), method)
    assert error.value.code == "too_large"


def test_response_at_8_mb_is_accepted():
    body = b"x" * http.MAX_RESPONSE_BYTES
    assert page_client(Recorder(Reply(content=body))).get(TRENDYOL) == body.decode()


@pytest.mark.parametrize(
    "method, chunks, expected",
    [
        ("get", [b"Mer", b"ha", b"ba"], "Merhaba"),
        ("get_json", [b'{"ok":', b"true}"], {"ok": True}),
        ("post_json", [b'{"ok":', b"true}"], {"ok": True}),
    ],
)
def test_chunked_response_does_not_read_full_content(method, chunks, expected):
    reply = ChunkedReply(chunks)
    assert call(page_client(Recorder(reply)), method) == expected
    assert reply.delivered == len(chunks)


@pytest.mark.parametrize("method", ["get", "get_json", "post_json"])
def test_download_stops_at_first_chunk_over_limit(monkeypatch, slept, method):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"1234", b"5678", b"x", b"alinmamali"])
    session = Recorder(reply)
    pages = page_client(session, request_attempts=3)
    with pytest.raises(FetchError) as error:
        call(pages, method)
    assert error.value.code == "too_large"
    assert reply.delivered == 3
    assert pages.request_count == len(session.calls) == 1
    assert slept == []


def test_chunked_response_at_exact_limit_is_accepted(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"1234", b"5678"])
    assert page_client(Recorder(reply)).get(TRENDYOL) == "12345678"


def test_single_oversized_chunk_stops_download(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"123456789", b"alinmamali"])
    with pytest.raises(FetchError) as error:
        page_client(Recorder(reply)).get(TRENDYOL)
    assert error.value.code == "too_large"
    assert reply.delivered == 1


def test_oversized_response_does_not_poison_next_request(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    session = Recorder(ChunkedReply([b"12345678", b"x"]), Reply(content=b"ok"))
    pages = page_client(session)
    with pytest.raises(FetchError) as error:
        pages.get(TRENDYOL)
    assert error.value.code == "too_large"
    assert pages.get(TRENDYOL) == "ok"
    assert pages.request_count == 2


@pytest.mark.parametrize(
    "status, code",
    [
        (401, "blocked"),
        (403, "blocked"),
        (418, "blocked"),
        (429, "blocked"),
        (404, "http_error"),
    ],
)
def test_oversized_http_error_keeps_status_code(monkeypatch, slept, status, code):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"12345678", b"x", b"alinmamali"], status=status)
    session = Recorder(reply)
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == code
    assert reply.delivered == 2
    assert len(session.calls) == 1
    assert slept == []


def test_oversized_server_error_is_retried_with_empty_buffer(monkeypatch, slept):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"12345678", b"x", b"alinmamali"], status=503)
    pages = page_client(Recorder(reply, Reply(content=b"ok")), request_attempts=2)
    assert pages.get(TRENDYOL) == "ok"
    assert reply.delivered == 2
    assert pages.request_count == 2
    assert slept == [1]


def test_oversized_server_error_still_obeys_request_budget(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"12345678", b"x"], status=503)
    pages = page_client(Recorder(reply), request_budget=1, request_attempts=2)
    with pytest.raises(FetchError) as error:
        pages.get(TRENDYOL)
    assert error.value.code == "limit"
    assert reply.delivered == 2
    assert pages.request_count == 1


def test_oversized_redirect_keeps_location_and_uses_empty_buffer(monkeypatch):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply(
        [b"12345678", b"x", b"alinmamali"], status=302, location="/yeni"
    )
    session = Recorder(reply, Reply(content=b"ok"))
    pages = page_client(session)
    assert pages.get(TRENDYOL) == "ok"
    assert reply.delivered == 2
    assert pages.request_count == 2
    assert session.calls[1][1] == TRENDYOL + "yeni"


@pytest.mark.parametrize(
    "location, code", [(None, "redirect"), ("https://evil.example/", "invalid_host")]
)
def test_oversized_redirect_still_checks_destination(monkeypatch, location, code):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    reply = ChunkedReply([b"12345678", b"x"], status=302, location=location)
    session = Recorder(reply)
    with pytest.raises(FetchError) as error:
        page_client(session).get(TRENDYOL)
    assert error.value.code == code
    assert reply.delivered == 2
    assert len(session.calls) == 1


def test_partial_body_is_discarded_before_network_retry(slept):
    reply = ChunkedReply([b"yarim", RequestException("bağlantı koptu")])
    session = Recorder(reply, Reply(content=b"ok"))
    pages = page_client(session, request_attempts=2)
    assert pages.get(TRENDYOL) == "ok"
    assert pages.request_count == 2
    assert slept == [1]


def test_request_exception_response_is_not_used_without_size_abort(slept):
    session = Recorder(
        RequestException("zaman aşımı", response=Reply()), Reply(content=b"ok")
    )
    assert page_client(session, request_attempts=2).get(TRENDYOL) == "ok"
    assert len(session.calls) == 2
    assert slept == [1]


def test_size_abort_without_response_is_not_retried(monkeypatch, slept):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)

    class WithoutResponse(Recorder):
        def request(self, *args, **kwargs):
            try:
                return super().request(*args, **kwargs)
            except RequestException as exc:
                exc.response = None
                raise

    reply = ChunkedReply([b"123456789", b"alinmamali"])
    session = WithoutResponse(reply)
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == "too_large"
    assert reply.delivered == len(session.calls) == 1
    assert slept == []


def test_utf8_character_split_between_chunks_is_decoded_after_download():
    reply = ChunkedReply([b"Fiyat: \xc4", b"\xb1"])
    assert page_client(Recorder(reply)).get(TRENDYOL) == "Fiyat: ı"


@pytest.mark.parametrize("method", ["get", "get_json", "post_json"])
def test_empty_chunked_response_keeps_parse_behavior(method):
    pages = page_client(Recorder(ChunkedReply([])))
    if method == "get":
        assert call(pages, method) == ""
    else:
        with pytest.raises(FetchError) as error:
            call(pages, method)
        assert error.value.code == "parse"


def test_oversized_server_errors_end_as_network(monkeypatch, slept):
    monkeypatch.setattr(http, "MAX_RESPONSE_BYTES", 8)
    replies = [
        ChunkedReply([b"12345678", b"x"], status=status) for status in (500, 503)
    ]
    pages = page_client(Recorder(*replies), request_attempts=2)
    with pytest.raises(FetchError) as error:
        pages.get(TRENDYOL)
    assert error.value.code == "network"
    assert [reply.delivered for reply in replies] == [2, 2]
    assert pages.request_count == 2
    assert slept == [1]


@pytest.mark.parametrize(
    "url, code",
    [
        ("http://www.trendyol.com/", "invalid_url"),
        ("https://kullanici:sifre@www.trendyol.com/", "invalid_url"),
        ("https://www.trendyol.com:8443/", "invalid_url"),
        ("https://www.trendyol.com/#yorumlar", "invalid_url"),
        ("https://www.google.com/", "invalid_host"),
        ("https://trendyol.com/", "invalid_host"),
    ],
)
def test_url_outside_platform_is_rejected_before_request(url, code):
    session = Recorder()
    with pytest.raises(FetchError) as error:
        page_client(session).get(url)
    assert error.value.code == code
    assert session.calls == []


@pytest.mark.parametrize(
    "start, location",
    [
        # Adresin kendisi izinli alan adı dışında.
        ("https://www.google.com/arama?gizli=1", None),
        # Yönlendirme hedefi izinli alan adı dışında (tur 14'teki durumun biçimi).
        (TRENDYOL, "https://evil.example/arama?gizli=1"),
    ],
)
def test_invalid_host_message_names_the_target_host_and_path(start, location):
    # Tur 14'te (5 Ekim) bir Hepsiburada sayfası invalid_host verdi ama mesaj hedef
    # alan adını söylemediği için nedeni anlaşılamadı. Sorgu metni mesaja girmez.
    session = Recorder(Reply(302, location=location)) if location else Recorder()
    with pytest.raises(FetchError) as error:
        page_client(session).get(start)
    assert error.value.code == "invalid_host"
    message = str(error.value)
    assert "(www.google.com/arama)" in message or "(evil.example/arama)" in message
    assert "gizli" not in message


@pytest.mark.parametrize("status", [401, 403, 418, 429])
def test_blocked_statuses_are_not_retried(slept, status):
    session = Recorder(Reply(status))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == "blocked"
    assert len(session.calls) == 1
    assert slept == []


def test_request_passes_timeout_and_disables_automatic_redirects():
    session = Recorder(Reply(200, b'{"ok": true}'))
    pages = page_client(session, request_timeout_seconds=20.0)
    assert pages.post_json(TRENDYOL, {"a": 1}, headers={"X-Test": "1"}) == {"ok": True}
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", TRENDYOL)
    callback = kwargs.pop("content_callback", None)
    assert callable(callback)
    assert kwargs == {
        "timeout": 20.0,
        "allow_redirects": False,
        "json": {"a": 1},
        "headers": {"X-Test": "1"},
    }


# --- Yönlendirme ---------------------------------------------------------------


@pytest.mark.parametrize("status", sorted(http.REDIRECT_STATUSES))
def test_redirect_is_followed_within_platform(status):
    session = Recorder(Reply(status, location="/yeni?x=1"), Reply(200, b"ok"))
    assert page_client(session).get("https://www.trendyol.com/eski") == "ok"
    assert [url for _, url, _ in session.calls] == [
        "https://www.trendyol.com/eski",
        "https://www.trendyol.com/yeni?x=1",
    ]


@pytest.mark.parametrize(
    "location, code",
    [
        ("https://evil.example/x", "invalid_host"),
        ("//evil.example/x", "invalid_host"),
        ("http://www.trendyol.com/x", "invalid_url"),
    ],
)
def test_redirect_outside_platform_is_rejected(location, code):
    session = Recorder(Reply(302, location=location))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == code
    assert len(session.calls) == 1  # izinsiz hedefe istek gitmez


def test_redirect_without_location_is_an_error():
    session = Recorder(Reply(302))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == "redirect"
    assert len(session.calls) == 1


def test_three_redirects_are_followed_fourth_is_an_error():
    hops = [Reply(302, location=f"/adim-{i}") for i in range(http.MAX_REDIRECTS)]
    session = Recorder(*hops, Reply(200, b"ok"))
    assert page_client(session).get(TRENDYOL) == "ok"
    assert len(session.calls) == http.MAX_REDIRECTS + 1

    loop = Recorder(*[Reply(302, location="/dongu")] * (http.MAX_REDIRECTS + 1))
    with pytest.raises(FetchError) as error:
        page_client(loop, request_attempts=3).get(TRENDYOL)
    assert error.value.code == "redirect"
    assert len(loop.calls) == http.MAX_REDIRECTS + 1  # tekrar denenmez


# --- Tekrar deneme -------------------------------------------------------------


def test_server_error_is_retried_then_reported_as_network(slept):
    session = Recorder(Reply(500), Reply(502))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=2).get(TRENDYOL)
    assert error.value.code == "network"
    assert len(session.calls) == 2
    assert slept == [1]


def test_server_error_then_success_returns_page(slept):
    session = Recorder(Reply(503), Reply(200, b"ok"))
    assert page_client(session, request_attempts=2).get(TRENDYOL) == "ok"
    assert slept == [1]


def test_network_error_is_retried(slept):
    session = Recorder(RequestException("bağlantı koptu"), Reply(200, b"ok"))
    assert page_client(session, request_attempts=2).get(TRENDYOL) == "ok"
    assert len(session.calls) == 2
    assert slept == [1]


def test_retry_waits_one_then_two_seconds(slept):
    # request_attempts en çok 3 (Runtime); son denemeden sonra beklenmez.
    session = Recorder(Reply(503), Reply(503), Reply(503))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=3).get(TRENDYOL)
    assert error.value.code == "network"
    assert len(session.calls) == 3
    assert slept == [1, 2]


def test_single_attempt_does_not_retry(slept):
    session = Recorder(RequestException("zaman aşımı"))
    with pytest.raises(FetchError) as error:
        page_client(session, request_attempts=1).get(TRENDYOL)
    assert error.value.code == "network"
    assert slept == []


# --- İstemcinin kapatılması ---------------------------------------------------


def test_close_only_closes_owned_session(monkeypatch):
    created = []

    def fake_session(**options):
        created.append(options)
        return Recorder()

    monkeypatch.setattr(http.curl_requests, "Session", fake_session)
    owned = PageClient(["www.trendyol.com"], Runtime())
    owned.close()
    assert owned.client.closed
    # Mimari karar: Chrome taklidi, yönlendirmeleri PageClient kendisi izler.
    assert created[0]["impersonate"] == "chrome120"
    assert created[0]["allow_redirects"] is False

    given = Recorder()
    PageClient(["www.trendyol.com"], Runtime(), client=given).close()
    assert not given.closed


# --- Platform adaptörü yükleyici (factory) -----------------------------------


@pytest.fixture
def no_curl_session(monkeypatch):
    # Gerçek scraper kurulurken curl_cffi oturumu açılmasın.
    monkeypatch.setattr(http.curl_requests, "Session", lambda **options: Recorder())


@pytest.mark.parametrize(
    "key, expected",
    [("trendyol", TrendyolScraper), ("hepsiburada", HepsiburadaScraper)],
)
def test_factory_loads_platform_scraper(no_curl_session, key, expected):
    scraper = create_scraper(key, [f"www.{key}.com"], Runtime())
    assert type(scraper) is expected
    assert scraper.pages.hosts == {f"www.{key}.com"}
    scraper.close()


@pytest.mark.parametrize(
    "key", ["Trendyol", "../trendyol", "", "trendyol.x", "1trendyol", "olmayan"]
)
def test_factory_rejects_invalid_or_missing_platform(key):
    with pytest.raises(FetchError) as error:
        create_scraper(key, ["www.trendyol.com"], Runtime())
    assert error.value.code == "plugin"
    if key == "olmayan":
        assert isinstance(error.value.__cause__, ModuleNotFoundError)


def test_factory_checks_key_before_import(monkeypatch, no_curl_session):
    # Desen dışı anahtar, o adla yüklenmiş geçerli bir modül olsa bile kullanılmaz.
    valid = types.SimpleNamespace(Scraper=TrendyolScraper)
    monkeypatch.setitem(sys.modules, "app.scraper.Trendyol_scraper", valid)
    monkeypatch.setitem(sys.modules, "app.scraper.alt.trendyol_scraper", valid)
    imports = []

    def load(name):
        imports.append(name)
        return valid

    monkeypatch.setattr(factory.importlib, "import_module", load)
    for key in ("Trendyol", "alt.trendyol", "../x", "", "1trendyol"):
        with pytest.raises(FetchError) as error:
            create_scraper(key, ["www.trendyol.com"], Runtime())
        assert error.value.code == "plugin"
        assert error.value.__cause__ is None
    assert imports == []


class NotAScraper:
    pass


class BrokenScraper(BaseScraper):
    def __init__(self, hosts, runtime, client=None):
        raise RuntimeError("kurulamadı")

    def get_product_data(self, listing):
        raise NotImplementedError


@pytest.mark.parametrize(
    "module, cause_type",
    [
        (types.SimpleNamespace(), AttributeError),  # Scraper sınıfı yok
        (types.SimpleNamespace(Scraper="Scraper"), TypeError),  # sınıf değil
        (types.SimpleNamespace(Scraper=NotAScraper), TypeError),  # BaseScraper değil
        (types.SimpleNamespace(Scraper=BaseScraper), TypeError),  # soyut
        (types.SimpleNamespace(Scraper=BrokenScraper), RuntimeError),
    ],
)
def test_factory_rejects_module_without_valid_scraper(monkeypatch, module, cause_type):
    monkeypatch.setitem(sys.modules, "app.scraper.sahte_scraper", module)
    with pytest.raises(FetchError) as error:
        create_scraper("sahte", ["www.trendyol.com"], Runtime())
    assert error.value.code == "plugin"
    assert isinstance(error.value.__cause__, cause_type)
    assert "sahte adaptörü yüklenemedi" in str(error.value)


def test_factory_builds_instance_with_original_constructor_arguments(monkeypatch):
    calls = []

    class ValidScraper(BaseScraper):
        def __init__(self, hosts, runtime):
            calls.append((hosts, runtime))

        def get_product_data(self, listing):
            raise AssertionError("Yükleme sırasında sayfa okunmamalı")

    monkeypatch.setitem(
        sys.modules,
        "app.scraper.sahte_scraper",
        types.SimpleNamespace(Scraper=ValidScraper),
    )
    hosts = ["www.trendyol.com"]
    runtime = Runtime()
    scraper = create_scraper("sahte", hosts, runtime)
    assert type(scraper) is ValidScraper
    assert len(calls) == 1
    assert calls[0][0] is hosts and calls[0][1] is runtime


@pytest.mark.parametrize("stage", ["import", "constructor"])
@pytest.mark.parametrize("error_type", [ImportError, RuntimeError, KeyboardInterrupt])
def test_factory_preserves_error_cause_and_does_not_wrap_ctrl_c(
    monkeypatch, stage, error_type
):
    failure = error_type("Yerel adaptör hata taklidi")
    imports = []

    class FailingScraper(BaseScraper):
        def __init__(self, hosts, runtime):
            raise failure

        def get_product_data(self, listing):
            raise AssertionError("Kurulamayan scraper sayfa okumamalı")

    def load(name):
        imports.append(name)
        if stage == "import":
            raise failure
        return types.SimpleNamespace(Scraper=FailingScraper)

    monkeypatch.setattr(factory.importlib, "import_module", load)
    expected = KeyboardInterrupt if error_type is KeyboardInterrupt else FetchError
    with pytest.raises(expected) as error:
        create_scraper("sahte", ["www.trendyol.com"], Runtime())
    assert imports == ["app.scraper.sahte_scraper"]
    if error_type is KeyboardInterrupt:
        assert error.value is failure
    else:
        assert error.value.code == "plugin"
        assert error.value.__cause__ is failure
        assert "sahte adaptörü yüklenemedi" in str(error.value)


# --- Mimari kural: HTTP yalnız app/scraper/http.py ve curl_cffi ile ------------

FORBIDDEN_HTTP = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "playwright",
    "selenium",
)


def app_imports():
    """app/ altındaki her .py dosyasının içe aktardığı modüller (dosya, modül).

    `from urllib import request` gibi alt modül aktarmaları da "urllib.request"
    olarak görünür; göreli aktarmalar proje içidir, atlanır.
    """
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(APP.parent).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    yield relative, alias.name
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                yield relative, node.module
                for alias in node.names:
                    yield relative, f"{node.module}.{alias.name}"


def is_within(module, package):
    return module == package or module.startswith(package + ".")


def test_app_does_not_import_other_http_libraries():
    # Yerel .venv'de eski taslaklardan kalan requests/httpx/playwright kurulu;
    # yanlışlıkla eklenen bir import testleri yine de geçirmesin.
    offenders = [
        f"{path}: {module}"
        for path, module in app_imports()
        if any(is_within(module, forbidden) for forbidden in FORBIDDEN_HTTP)
        and not (path == "app/ui/api_client.py" and is_within(module, "httpx"))
    ]
    assert offenders == []


def test_curl_cffi_is_imported_only_by_http_module():
    users = {path for path, module in app_imports() if is_within(module, "curl_cffi")}
    assert users == {"app/scraper/http.py"}


@pytest.mark.parametrize(
    "relative,source,allowed",
    [
        ("ui/api_client.py", "import httpx", True),
        ("ui/api_client.py", "from httpx import Client", True),
        ("ui/api_client.py", "import httpx._client", True),
        ("ui/other.py", "import httpx", False),
        ("api/main.py", "from httpx import Client", False),
        ("scraper/http.py", "import httpx", False),
        ("ui/sub/api_client.py", "import httpx", False),
        ("ui/api_client.py", "import requests", False),
        ("ui/api_client.py", "from urllib import request", False),
    ],
)
def test_local_api_http_exception_is_limited_to_one_module(
    tmp_path, monkeypatch, relative, source, allowed
):
    root = tmp_path / "app"
    path = root / relative
    path.parent.mkdir(parents=True)
    path.write_text(source, encoding="utf-8")
    monkeypatch.setitem(globals(), "APP", root)
    if allowed:
        test_app_does_not_import_other_http_libraries()
    else:
        with pytest.raises(AssertionError):
            test_app_does_not_import_other_http_libraries()
