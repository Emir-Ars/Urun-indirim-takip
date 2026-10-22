"""PageClient'a verilen sahte oturum ve yanıtlar; gerçek istek yapılmaz."""

from curl_cffi.curl import CURL_WRITEFUNC_ERROR
from curl_cffi.requests.exceptions import RequestException

from app.scraper.http import PageClient
from app.settings import Runtime


class Reply:
    """Sahte yanıt. Başlık anahtarı küçük harftir: http.py "location" okur."""

    def __init__(self, status=200, content=b"{}", location=None):
        self.status_code = status
        self.content = content
        self.headers = {} if location is None else {"location": location}

    def iter_chunks(self):
        for offset in range(0, len(self.content), 16384):
            yield self.content[offset : offset + 16384]


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
