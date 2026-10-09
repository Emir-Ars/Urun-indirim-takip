"""Yalnız bu bilgisayardaki API'yi okur ve ortak sözleşmeyle doğrular."""

import re
from typing import Annotated

import httpx
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from app.api.schemas import (
    ErrorResponse,
    HealthResponse,
    ProductResponse,
    StatusResponse,
)
from app.contracts import Key, Product

_KEY = TypeAdapter(Key)
_DAYS = TypeAdapter(Annotated[int, Field(ge=1, le=366)])
_HEALTH = TypeAdapter(HealthResponse)
_STATUS = TypeAdapter(StatusResponse)
_PRODUCTS = TypeAdapter(tuple[Product, ...])
_PRODUCT = TypeAdapter(ProductResponse)
_ERRORS = {
    (404, "product_not_found"): "Telefon bulunamadı.",
    (404, "not_found"): "İstenen API adresi bulunamadı.",
    (405, "method_not_allowed"): "Bu API adresinde yalnız GET kullanılabilir.",
    (422, "invalid_request"): "İstek parametreleri geçersiz.",
    (500, "internal_error"): "API cevabı hazırlanamadı.",
    (503, "pool_unavailable"): "Veritabanı bağlantısı şu anda alınamıyor.",
    (503, "database_unavailable"): "Veritabanı şu anda okunamıyor.",
    (503, "read_access_denied"): "API okuma hesabının izinleri uygun değil.",
    (503, "schema_not_ready"): "Veritabanı şeması API için hazır değil.",
}


class ApiClientError(Exception):
    def __init__(self, code: str, message: str, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _complete(value) -> bool:
    if isinstance(value, BaseModel):
        fields = type(value).model_fields
        return value.model_fields_set == fields.keys() and all(
            _complete(getattr(value, field)) for field in fields
        )
    if isinstance(value, tuple):
        return all(_complete(item) for item in value)
    return True


def _validate_target(request: httpx.Request) -> None:
    url = request.url
    product_path = re.fullmatch(r"/api/v1/products/([a-z][a-z0-9_]*)", url.path)
    allowed_query = {"history_days", "cimri_days"} if product_path else set()
    query = url.params.multi_items()
    if (
        request.method != "GET"
        or (url.scheme, url.host, url.port) != ("http", "127.0.0.1", 8000)
        or url.username
        or url.password
        or url.fragment
        or (
            url.path not in ("/health", "/api/v1/status", "/api/v1/products")
            and not product_path
        )
        or len(query) != len({key for key, value in query})
        or any(
            key not in allowed_query
            or len(value) > 3
            or not re.fullmatch(r"[0-9]+", value)
            or not 1 <= int(value) <= 366
            for key, value in query
        )
    ):
        raise ApiClientError(
            "invalid_target", "İstek izin verilen yerel API'ye ait değil."
        )


class ApiClient:
    def __init__(self, *, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url="http://127.0.0.1:8000",
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(15, connect=3, write=3, pool=3),
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self) -> None:
        self._client.close()

    def get_health(self) -> HealthResponse:
        return self._get("/health", _HEALTH)

    def get_status(self) -> StatusResponse:
        return self._get("/api/v1/status", _STATUS)

    def list_products(self) -> tuple[Product, ...]:
        return self._get("/api/v1/products", _PRODUCTS)

    def get_product(
        self, product_key: str, history_days: int = 30, cimri_days: int = 366
    ) -> ProductResponse:
        try:
            _KEY.validate_python(product_key, strict=True)
            _DAYS.validate_python(history_days, strict=True)
            _DAYS.validate_python(cimri_days, strict=True)
        except ValidationError:
            raise ApiClientError(
                "invalid_request", "İstek parametreleri geçersiz."
            ) from None
        return self._get(
            f"/api/v1/products/{product_key}",
            _PRODUCT,
            {"history_days": history_days, "cimri_days": cimri_days},
        )

    def _get[T](self, path: str, adapter: TypeAdapter[T], params=None) -> T:
        if self._client.is_closed:
            raise ApiClientError("client_closed", "API istemcisi kapatılmış.")
        request = self._client.build_request("GET", path, params=params)
        _validate_target(request)
        try:
            response = self._client.send(request, follow_redirects=False)
        except httpx.TimeoutException:
            raise ApiClientError(
                "timeout", "Yerel API yanıtı zaman aşımına uğradı."
            ) from None
        except httpx.RequestError:
            raise ApiClientError(
                "connection_error", "Yerel API'ye erişilemiyor."
            ) from None
        try:
            if 300 <= response.status_code < 400:
                raise ApiClientError(
                    "redirect_rejected",
                    "Yerel API yönlendirmesi kabul edilmedi.",
                    response.status_code,
                )
            if response.status_code >= 400:
                self._raise_http_error(response)
            if response.status_code != 200:
                raise ApiClientError(
                    "invalid_response",
                    "Yerel API cevabı geçersiz.",
                    response.status_code,
                )
            try:
                result = adapter.validate_json(response.content, strict=True)
            except ValidationError:
                raise ApiClientError(
                    "invalid_response",
                    "Yerel API cevabı geçersiz.",
                    response.status_code,
                ) from None
            # API varsayılanları JSON'da da bulunur; eksik alanı veri diye doldurma.
            if not _complete(result):
                raise ApiClientError(
                    "invalid_response",
                    "Yerel API cevabı geçersiz.",
                    response.status_code,
                )
            return result
        finally:
            response.close()

    @staticmethod
    def _raise_http_error(response: httpx.Response) -> None:
        try:
            error = ErrorResponse.model_validate_json(response.content, strict=True)
        except ValidationError:
            error = None
        code = error.detail.code if error is not None else "http_error"
        message = _ERRORS.get((response.status_code, code))
        if message is None:
            code, message = "http_error", "Yerel API isteği tamamlanamadı."
        raise ApiClientError(code, message, response.status_code)
