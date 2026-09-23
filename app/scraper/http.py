"""Alan adı sınırı, tekrar ve Chrome taklidi içeren HTTP taşıması."""

import json
import time
from urllib.parse import urljoin, urlsplit

from curl_cffi import requests as curl_requests
from curl_cffi.requests.exceptions import RequestException

from app.contracts import public_url
from app.settings import Runtime

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
REDIRECT_STATUSES = {301, 302, 303, 307, 308}


class FetchError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class PageClient:
    def __init__(self, hosts: list[str], runtime: Runtime, client=None):
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
        self._last_request = 0.0

    def _allowed(self, url: str) -> None:
        try:
            public_url(url)
        except ValueError as exc:
            raise FetchError("invalid_url", str(exc)) from exc
        if urlsplit(url).hostname not in self.hosts:
            raise FetchError("invalid_host", "İstek platformun alan adı dışında")

    def _wait_for_interval(self) -> None:
        delay = self.runtime.request_interval_seconds - (
            time.monotonic() - self._last_request
        )
        if delay > 0:
            time.sleep(delay)
        self._last_request = time.monotonic()

    @staticmethod
    def _body(response) -> bytes:
        body = response.content
        if len(body) > MAX_RESPONSE_BYTES:
            raise FetchError("too_large", "Yanıt 8 MB sınırını aştı")
        return body

    def _request(self, method: str, url: str, **kwargs):
        self._allowed(url)
        for attempt in range(self.runtime.request_attempts):
            target = url
            try:
                for _ in range(4):
                    self._allowed(target)
                    self._wait_for_interval()
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
                    if response.status_code in (401, 403, 429):
                        raise FetchError(
                            "blocked",
                            f"Kaynak HTTP {response.status_code} döndürdü",
                        )
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
                    self._body(response)
                    return response
                raise FetchError("redirect", "Çok fazla yönlendirme")
            except FetchError:
                raise
            except RequestException as exc:
                if attempt + 1 == self.runtime.request_attempts:
                    raise FetchError("network", str(exc)) from exc
                time.sleep(min(2**attempt, 8))
        raise FetchError("network", "İstek tamamlanamadı")

    def get(self, url: str, *, headers: dict | None = None) -> str:
        response = self._request("GET", url, headers=headers)
        try:
            return self._body(response).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FetchError("parse", "Kaynak UTF-8 metin döndürmedi") from exc

    def get_json(self, url: str, *, headers: dict | None = None) -> dict:
        response = self._request("GET", url, headers=headers)
        try:
            data = json.loads(self._body(response).decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError) as exc:
            raise FetchError("parse", "Kaynak geçerli JSON döndürmedi") from exc
        if not isinstance(data, dict):
            raise FetchError("parse", "Kaynak JSON nesnesi döndürmedi")
        return data

    def post_json(
        self, url: str, payload: dict, *, headers: dict | None = None
    ) -> dict:
        response = self._request("POST", url, json=payload, headers=headers)
        try:
            data = json.loads(self._body(response).decode("utf-8"))
        except (UnicodeDecodeError, TypeError, ValueError) as exc:
            raise FetchError("parse", "Kaynak geçerli JSON döndürmedi") from exc
        if not isinstance(data, dict):
            raise FetchError("parse", "Kaynak JSON nesnesi döndürmedi")
        return data

    def cookie(self, name: str) -> str | None:
        try:
            return self.client.cookies.get(name)
        except (KeyError, TypeError, ValueError):
            return None

    def close(self):
        if self._owned:
            self.client.close()
